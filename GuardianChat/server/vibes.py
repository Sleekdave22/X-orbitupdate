"""Expiring account Vibes. Every media read rechecks audience, block and expiry."""
import base64,hashlib,io,json,time,uuid
from PIL import Image
HOURS=(12,24,48)
EMOJI=('❤️','🔥','😂','👏','😮','🎉')

def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS vibe_settings(uid TEXT PRIMARY KEY,public_hours INTEGER NOT NULL DEFAULT 24,private_hours INTEGER NOT NULL DEFAULT 24);
 CREATE TABLE IF NOT EXISTS vibe_items(id TEXT PRIMARY KEY,uid TEXT NOT NULL,visibility TEXT NOT NULL,mime TEXT NOT NULL,media BLOB,caption TEXT NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL,client_id TEXT NOT NULL,digest TEXT NOT NULL,UNIQUE(uid,client_id));
 CREATE TABLE IF NOT EXISTS vibe_audience(item TEXT NOT NULL,uid TEXT NOT NULL,PRIMARY KEY(item,uid));
 CREATE TABLE IF NOT EXISTS vibe_views(item TEXT NOT NULL,uid TEXT NOT NULL,first_seen INTEGER NOT NULL,last_seen INTEGER NOT NULL,opens INTEGER NOT NULL DEFAULT 1,PRIMARY KEY(item,uid));
 CREATE TABLE IF NOT EXISTS vibe_reactions(item TEXT NOT NULL,uid TEXT NOT NULL,emoji TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(item,uid));
 CREATE INDEX IF NOT EXISTS vibe_active ON vibe_items(expires,uid,visibility);
 ''')

def preferences(d,uid):
 r=d.execute('SELECT * FROM vibe_settings WHERE uid=?',(uid,)).fetchone()
 return dict(r) if r else {'public_hours':24,'private_hours':24}

def allowed(d,uid,item,now=None):
 import social
 if item is None or item['expires']<=(int(time.time()) if now is None else now) or item['media'] is None:return False
 if item['uid']==uid:return True
 if social.blocked(d,uid,item['uid']):return False
 return item['visibility']=='public' or bool(d.execute('SELECT 1 FROM vibe_audience a JOIN contacts c ON c.owner=? AND c.peer=a.uid WHERE a.item=? AND a.uid=?',(item['uid'],item['id'],uid)).fetchone())

def item(d,uid,ident):
 r=d.execute('SELECT * FROM vibe_items WHERE id=?',(ident,)).fetchone()
 if not allowed(d,uid,r):raise PermissionError('This Vibe expired or is unavailable to your account')
 return r

def get(server,uid,action,q):
 with server.db() as d:
  if action=='feed':
   visibility=q.get('visibility',['public'])[0]
   if visibility not in ('public','private'):raise ValueError('Choose Public or Private Vibe')
   groups={}
   for r in d.execute('SELECT i.id,i.uid,i.visibility,i.mime,i.caption,i.created,i.expires,1 AS media,u.name,u.nickname FROM vibe_items i JOIN users u ON u.id=i.uid WHERE i.visibility=? AND i.expires>? AND i.media IS NOT NULL ORDER BY i.created,i.id',(visibility,int(time.time()))):
    if not allowed(d,uid,r):continue
    group=groups.setdefault(r['uid'],{'uid':r['uid'],'name':r['name'],'nickname':r['nickname'],'items':[]})
    v=d.execute('SELECT 1 FROM vibe_views WHERE item=? AND uid=?',(r['id'],uid)).fetchone()
    group['items'].append({'id':r['id'],'created':r['created'],'expires':r['expires'],'caption':r['caption'] if visibility=='public' or r['uid']==uid else '', 'mime':r['mime'],'viewed':bool(v),'views':d.execute('SELECT COUNT(*) FROM vibe_views WHERE item=?',(r['id'],)).fetchone()[0] if r['uid']==uid else None})
   return {'groups':list(groups.values()),'preferences':preferences(d,uid),'emoji':EMOJI}
  if action=='status':
   r=item(d,uid,q.get('id',[''])[0]);return {'active':True,'expires':r['expires']}
  if action=='viewers':
   r=item(d,uid,q.get('id',[''])[0])
   if r['uid']!=uid:raise PermissionError('Only the author can inspect viewers')
   return {'viewers':[dict(v) for v in d.execute('SELECT v.uid,u.name,u.nickname,v.first_seen,v.last_seen,v.opens,r.emoji FROM vibe_views v JOIN users u ON u.id=v.uid LEFT JOIN vibe_reactions r ON r.item=v.item AND r.uid=v.uid WHERE v.item=? ORDER BY v.last_seen DESC',(r['id'],))]}
  raise ValueError('Unknown Vibe action')

def media(server,uid,ident,protected=False):
 with server.db() as d:
  r=item(d,uid,ident)
  if r['visibility']=='private' and not protected:raise PermissionError('Open Private Vibe in the GuardianLab-protected Android viewer')
  return {'data':base64.b64encode(r['media']).decode(),'mime':r['mime'],'expires':r['expires'],'server_now':int(time.time()),'caption':r['caption'],'uid':r['uid'],'visibility':r['visibility']}

def validate(b):
 try:raw=base64.b64decode(b.get('media',''),validate=True)
 except Exception as e:raise ValueError('Invalid Vibe media') from e
 mime=str(b.get('mime',''))
 if not raw or len(raw)>20*1024*1024:raise ValueError('Use media up to 20 MB')
 if mime in ('image/jpeg','image/png'):
  if len(raw)>5*1024*1024:raise ValueError('Use a photo up to 5 MB')
  try:
   with Image.open(io.BytesIO(raw)) as im:
    if im.width*im.height>24000000 or im.format not in ('JPEG','PNG'):raise ValueError()
    actual='image/jpeg' if im.format=='JPEG' else 'image/png';im.verify()
  except Exception as e:raise ValueError('Use a complete JPEG or PNG photo') from e
  return raw,actual
 if mime.startswith('video/'):
  import result_reviews
  return raw,result_reviews.video_probe(raw)['mime']
 raise ValueError('Vibes support JPEG, PNG, MP4 and WebM')

def post(server,uid,action,b):
 now=int(time.time())
 if action=='publish':raw,mime=validate(b)
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  if action=='preferences':
   public=b.get('public_hours');private=b.get('private_hours')
   if type(public)!=int or public not in HOURS or type(private)!=int or private not in HOURS:raise ValueError('Choose 12, 24 or 48 hours independently')
   d.execute('INSERT INTO vibe_settings VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET public_hours=excluded.public_hours,private_hours=excluded.private_hours',(uid,public,private));return {'ok':True}
  if action=='publish':
   visibility=b.get('visibility');client=str(b.get('client_id',''));caption=str(b.get('caption','')).strip()
   if visibility not in ('public','private') or not 8<=len(client)<=100 or len(caption)>500:raise ValueError('Invalid Vibe publication')
   digest=hashlib.sha256(raw).hexdigest();old=d.execute('SELECT * FROM vibe_items WHERE uid=? AND client_id=?',(uid,client)).fetchone()
   if old:
    if old['digest']!=digest or old['visibility']!=visibility or old['caption']!=caption:raise ValueError('A retry cannot replace an existing Vibe')
    return {'id':old['id'],'expires':old['expires'],'already_published':True}
   if d.execute('SELECT COUNT(*) FROM vibe_items WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0]>=30:raise ValueError('Limit: 30 Vibe uploads per hour')
   audience=b.get('audience',[])
   if not isinstance(audience,list) or len(audience)>200 or any(not isinstance(x,str) for x in audience):raise ValueError('Choose valid private recipients')
   # Private audiences are explicit and frozen; publishing never creates contacts.
   if visibility=='private':
    if not audience:raise ValueError('Choose at least one existing contact for this Private Vibe')
    import social
    for target in set(audience):
     if not d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone() or social.blocked(d,uid,target):raise PermissionError('Private Vibe recipients must be your available contacts')
   ident=uuid.uuid4().hex;expires=now+preferences(d,uid)[visibility+'_hours']*3600
   d.execute('INSERT INTO vibe_items VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,uid,visibility,mime,raw,caption,now,expires,client,digest))
   for target in set(audience) if visibility=='private' else ():
    d.execute('INSERT INTO vibe_audience VALUES(?,?)',(ident,target))
    __import__('account_notifications').add(d,target,'vibe','private','A contact shared a Private Vibe with you.',{'item':ident,'visibility':'private'})
   return {'id':ident,'expires':expires}
  r=item(d,uid,str(b.get('id','')))
  if action=='view':
   if r['uid']!=uid:d.execute('INSERT INTO vibe_views VALUES(?,?,?,?,1) ON CONFLICT(item,uid) DO UPDATE SET last_seen=excluded.last_seen,opens=opens+1',(r['id'],uid,now,now))
   return {'ok':True}
  if action=='react':
   emoji=b.get('emoji')
   if emoji not in EMOJI or r['uid']==uid:raise ValueError('Choose an available reaction to another account')
   prior=d.execute('SELECT emoji FROM vibe_reactions WHERE item=? AND uid=?',(r['id'],uid)).fetchone()
   d.execute('INSERT INTO vibe_reactions VALUES(?,?,?,?) ON CONFLICT(item,uid) DO UPDATE SET emoji=excluded.emoji,created=excluded.created',(r['id'],uid,emoji,now))
   if not prior or prior['emoji']!=emoji:__import__('account_notifications').add(d,r['uid'],'vibe',r['visibility'],'Someone reacted '+emoji+' to your Vibe.',{'item':r['id'],'visibility':r['visibility']})
   return {'ok':True}
  if action=='remove':
   if r['uid']!=uid:raise PermissionError('Only the author can remove this Vibe')
   d.execute('UPDATE vibe_items SET expires=?,media=NULL WHERE id=?',(now,r['id']));return {'ok':True}
  raise ValueError('Unknown Vibe action')

def purge(server):
 with server.db() as d:
  d.execute('UPDATE vibe_items SET media=NULL WHERE expires<=? AND media IS NOT NULL',(int(time.time()),))
  # Metadata is kept briefly for deduplication, then discarded with view history.
  old=[r[0] for r in d.execute('SELECT id FROM vibe_items WHERE expires<?',(int(time.time())-7*86400,))]
  for ident in old:
   for table in ('vibe_views','vibe_audience','vibe_reactions'):d.execute('DELETE FROM '+table+' WHERE item=?',(ident,))
   d.execute('DELETE FROM vibe_items WHERE id=?',(ident,))
