"""Listing connections, offers and Market-only activity; no payments."""
import hashlib,json,time,uuid
import account_notifications as activity
from market_pilot import accessible,amount,text,view,row

def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS market_saves(uid TEXT NOT NULL,listing TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(uid,listing));
 CREATE TABLE IF NOT EXISTS market_offers(id TEXT PRIMARY KEY,listing TEXT NOT NULL,buyer TEXT NOT NULL,seller TEXT NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,state TEXT NOT NULL,turn TEXT NOT NULL,revision INTEGER NOT NULL,created INTEGER NOT NULL,expires INTEGER NOT NULL);
 CREATE INDEX IF NOT EXISTS market_offer_participants ON market_offers(buyer,seller,created);
 CREATE TABLE IF NOT EXISTS market_offer_history(id INTEGER PRIMARY KEY,offer TEXT NOT NULL,actor TEXT NOT NULL,event TEXT NOT NULL,amount_minor INTEGER NOT NULL,created INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS market_reservations(listing TEXT PRIMARY KEY,offer TEXT UNIQUE NOT NULL,buyer TEXT NOT NULL,expires INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS market_operations(uid TEXT NOT NULL,key TEXT NOT NULL,fingerprint TEXT NOT NULL,result TEXT NOT NULL,PRIMARY KEY(uid,key));
 CREATE TABLE IF NOT EXISTS market_inquiries(buyer TEXT NOT NULL,seller TEXT NOT NULL,listing TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(buyer,listing));
 ''')

def emit(d,uid,section,message,target):activity.add(d,uid,'market',section,message,target)
def permitted(d,a,b):
 import social
 if social.blocked(d,a,b):raise ValueError('Account interaction unavailable')

def release(d,reservation):
 d.execute('DELETE FROM market_reservations WHERE listing=?',(reservation['listing'],))
 d.execute("UPDATE market_listing_meta SET state='ACTIVE',revision=revision+1 WHERE id=? AND state='RESERVED'",(reservation['listing'],))
 d.execute("UPDATE market_ads SET status='active' WHERE id=? AND status='reserved'",(reservation['listing'],))

def expire(d):
 now=int(time.time())
 for r in d.execute('SELECT * FROM market_reservations WHERE expires<?',(now,)).fetchall():
  # Demo orders extend/own their reservation; an unstarted negotiation expires.
  release(d,r);d.execute("UPDATE market_offers SET state='EXPIRED',revision=revision+1 WHERE id=? AND state='ACCEPTED'",(r['offer'],))
 d.execute("UPDATE market_offers SET state='EXPIRED',revision=revision+1 WHERE expires<? AND state IN ('PENDING','COUNTERED')",(now,))

def offer_view(d,uid,ident):
 r=d.execute('SELECT * FROM market_offers WHERE id=? AND (buyer=? OR seller=?)',(ident,uid,uid)).fetchone()
 if not r:raise ValueError('Offer unavailable')
 out=dict(r);out['history']=[dict(x) for x in d.execute('SELECT actor,event,amount_minor,created FROM market_offer_history WHERE offer=? ORDER BY id',(ident,))]
 out['listing_title']=row(d,r['listing'])['title'];order=d.execute('SELECT id FROM market_demo_orders WHERE offer=?',(ident,)).fetchone();out['demo_order']=order['id'] if order else None;return out

def context(d,uid,peer):
 permitted(d,uid,peer)
 can=bool(d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,peer)).fetchone())
 if not can:return {'can_chat':False,'items':[]}
 refs=[]
 for r in d.execute('SELECT listing FROM market_inquiries WHERE (buyer=? AND seller=?) OR (buyer=? AND seller=?) ORDER BY created DESC LIMIT 5',(uid,peer,peer,uid)):
  try:
   v=view(d,row(d,r['listing']),uid);refs.append({k:v[k] for k in ('id','title','price','amount_minor','currency','state','images')})
  except ValueError:pass
 return {'can_chat':True,'items':refs}

def get(server,uid,path,q):
 arg=lambda key,default='':q.get(key,[default])[0]
 with server.db() as d:
  if path=='/market/saved':
   items=[]
   for r in d.execute('SELECT listing FROM market_saves WHERE uid=? ORDER BY created DESC',(uid,)):
    try:items.append(accessible(d,uid,r['listing']))
    except ValueError:items.append({'id':r['listing'],'title':'Listing unavailable','nickname':'','uid':'','unavailable':True})
   return {'listings':items}
  if path=='/market/chat_context':return context(d,uid,arg('peer'))
  if path in ('/market/offers','/market/offer'):
   d.execute('BEGIN IMMEDIATE');expire(d)
   if path.endswith('/offer'):return {'offer':offer_view(d,uid,arg('id'))}
   return {'offers':[offer_view(d,uid,r['id']) for r in d.execute('SELECT id FROM market_offers WHERE buyer=? OR seller=? ORDER BY created DESC LIMIT 100',(uid,uid))]}
  if path=='/market/activity':
   before=max(0,int(arg('before','0')));rows=d.execute("SELECT * FROM account_activity WHERE uid=? AND category='market' AND (?=0 OR id<?) ORDER BY id DESC LIMIT 51",(uid,before,before)).fetchall()
   count=d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND category='market' AND seen=0",(uid,)).fetchone()[0]
   return {'notifications':[dict(r)|{'target':json.loads(r['target'])} for r in rows[:50]],'more':len(rows)>50,'unread':count}
 raise ValueError('Unknown Market connection route')

def post(server,uid,action,b):
 now=int(time.time())
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE');expire(d)
  if action=='save_item':
   ident=text(b.get('id',''),40,True)
   if b.get('saved') is True:accessible(d,uid,ident);d.execute('INSERT OR IGNORE INTO market_saves VALUES(?,?,?)',(uid,ident,now))
   elif b.get('saved') is False:d.execute('DELETE FROM market_saves WHERE uid=? AND listing=?',(uid,ident))
   else:raise ValueError('Choose saved or unsaved')
   return {'ok':True}
  if action=='activity_seen':
   through=b.get('through_id');ids=b.get('ids',[])
   if through is not None:
    if type(through)!=int or through<1:raise ValueError('Invalid notification snapshot')
    d.execute("UPDATE account_activity SET seen=1 WHERE uid=? AND category='market' AND id<=?",(uid,through))
   else:
    if not isinstance(ids,list) or len(ids)>100 or any(type(i)!=int for i in ids):raise ValueError('Invalid notification selection')
    for i in ids:d.execute("UPDATE account_activity SET seen=1 WHERE uid=? AND category='market' AND id=?",(uid,i))
   return {'ok':True}
  if action=='inquiry':
   v=accessible(d,uid,b.get('id'));target=v['uid'];permitted(d,uid,target)
   if target==uid:raise ValueError('This is your own listing')
   if v['state']!='ACTIVE':raise ValueError('This listing is not accepting new inquiries')
   prior=d.execute('SELECT * FROM market_inquiries WHERE buyer=? AND listing=?',(uid,v['id'])).fetchone()
   if not prior:
    if d.execute('SELECT count(*) FROM market_inquiries WHERE buyer=? AND created>?',(uid,now-3600)).fetchone()[0]>=20:raise ValueError('Please slow down before opening more inquiries')
    d.execute('INSERT INTO market_inquiries VALUES(?,?,?,?)',(uid,target,v['id'],now));emit(d,target,'inquiries','Buyer inquiry: '+v['title'],{'chat':uid,'listing':v['id'],'event':'inquiry'})
   can=bool(d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,target)).fetchone())
   if not can:
    import social
    old=d.execute('SELECT state FROM social_message_requests WHERE sender=? AND target=?',(uid,target)).fetchone()
    if not old:d.execute("INSERT INTO social_message_requests VALUES(?,?,'pending',?)",(uid,target,now));social.notice(d,target,uid,'message_request')
    state=old['state'] if old else 'pending'
   else:state='accepted'
   return {'ok':True,'peer':target,'name':v['owner_name'],'state':state}
  if action not in ('offer_create','offer_action'):raise ValueError('Unknown Market connection action')
  key=text(b.get('client_id',''),80,True);fingerprint=hashlib.sha256(json.dumps({'action':action,'body':b},sort_keys=True).encode()).hexdigest()
  old=d.execute('SELECT * FROM market_operations WHERE uid=? AND key=?',(uid,key)).fetchone()
  if old:
   if old['fingerprint']!=fingerprint:raise ValueError('Retry key used for a different operation')
   return json.loads(old['result'])
  if action=='offer_create':
   v=accessible(d,uid,b.get('listing'));target=v['uid'];permitted(d,uid,target)
   if target==uid or v['state']!='ACTIVE' or v['amount_minor'] is None or v['availability']=='unavailable':raise ValueError('This listing cannot accept offers')
   if d.execute("SELECT 1 FROM market_offers WHERE buyer=? AND listing=? AND state IN ('PENDING','COUNTERED','ACCEPTED')",(uid,v['id'])).fetchone():raise ValueError('You already have an open offer for this item')
   if d.execute('SELECT count(*) FROM market_offers WHERE buyer=? AND created>?',(uid,now-3600)).fetchone()[0]>=20:raise ValueError('Please slow down before sending more offers')
   minor=amount(b.get('price'),v['currency'])
   if minor<=0:raise ValueError('Offer must be greater than zero')
   ident=uuid.uuid4().hex;d.execute("INSERT INTO market_offers VALUES(?,?,?,?,?,?,'PENDING',?,1,?,?)",(ident,v['id'],uid,target,minor,v['currency'],target,now,now+48*3600));event='new_offer'
  else:
   o=offer_view(d,uid,b.get('id'));permitted(d,o['buyer'],o['seller']);__import__('market_pilot').seller(d,o['seller']);ident=o['id'];v=view(d,row(d,o['listing']),uid);target=o['seller'] if uid==o['buyer'] else o['buyer'];minor=o['amount_minor'];operation=b.get('action')
   if b.get('revision')!=o['revision']:raise ValueError('Offer changed. Reopen it before responding.')
   if o['state'] not in ('PENDING','COUNTERED') or v['state']!='ACTIVE':raise ValueError('Offer no longer open for negotiation')
   if operation=='cancel':
    if uid!=o['buyer']:raise ValueError('Only the buyer can cancel an offer')
    state='CANCELLED'
   else:
    if o['turn']!=uid:raise ValueError('Waiting for the other person to respond')
    if operation=='accept':
     d.execute('INSERT INTO market_reservations VALUES(?,?,?,?)',(v['id'],ident,o['buyer'],now+24*3600));d.execute("UPDATE market_ads SET status='reserved' WHERE id=?",(v['id'],));d.execute("UPDATE market_listing_meta SET state='RESERVED',revision=revision+1,updated=? WHERE id=?",(now,v['id']));state='ACCEPTED'
    elif operation=='reject':state='REJECTED'
    elif operation=='counter':
     minor=amount(b.get('price'),o['currency'])
     if minor<=0:raise ValueError('Offer must be greater than zero')
     state='COUNTERED'
    else:raise ValueError('Choose accept, reject, counter or cancel')
   d.execute('UPDATE market_offers SET state=?,amount_minor=?,turn=?,revision=revision+1 WHERE id=?',(state,minor,target,ident));event=state.lower()
  d.execute('INSERT INTO market_offer_history(offer,actor,event,amount_minor,created) VALUES(?,?,?,?,?)',(ident,uid,event,minor,now));emit(d,target,'offers','Offer '+event.replace('_',' ')+': '+v['title'],{'offer':ident,'listing':v['id'],'event':event})
  result={'ok':True,'id':ident};d.execute('INSERT INTO market_operations VALUES(?,?,?,?)',(uid,key,fingerprint,json.dumps(result)));return result
