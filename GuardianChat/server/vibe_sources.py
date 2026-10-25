"""References into existing Market/Play records; never copies source media or trophies."""
import hashlib, io, json, textwrap, time, uuid
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

KINDS=('market','profile','trophy','sponsored','milestone')
def schema(d):
 d.executescript('''
 CREATE TABLE IF NOT EXISTS vibe_links(item TEXT PRIMARY KEY,kind TEXT NOT NULL,source TEXT NOT NULL,game TEXT NOT NULL DEFAULT '');
 CREATE TABLE IF NOT EXISTS vibe_link_keys(uid TEXT,client TEXT,fingerprint TEXT,item TEXT,PRIMARY KEY(uid,client));
 CREATE TABLE IF NOT EXISTS vibe_prompt_dismissals(uid TEXT,kind TEXT,source TEXT,PRIMARY KEY(uid,kind,source));
 CREATE TABLE IF NOT EXISTS vibe_milestone_policy(id INTEGER PRIMARY KEY CHECK(id=1),thresholds TEXT NOT NULL);
 INSERT OR IGNORE INTO vibe_milestone_policy VALUES(1,'[1,10,50,100]');
 CREATE TABLE IF NOT EXISTS vibe_rank_milestones(id TEXT PRIMARY KEY,uid TEXT,game TEXT,threshold INTEGER,history INTEGER,created INTEGER,UNIQUE(uid,game,threshold));
 ''')

def resolve(d,viewer,owner,kind,source,game='',publishing=False,visibility='private'):
 import social, game_identities, rankings
 social.ensure(d,viewer,owner)
 u=d.execute('SELECT name,nickname FROM users WHERE id=?',(owner,)).fetchone()
 if not u:raise ValueError('Account unavailable')
 result={'kind':kind,'source':source,'game':game,'owner':owner,'name':u['name'],'handle':'@'+(u['nickname'] or owner),'available':True,'status':'Available'}
 if kind=='market':
  import market_pilot
  a=market_pilot.accessible(d,viewer,source)
  if a['uid']!=owner:raise PermissionError('Share your own listing')
  restricted=d.execute('SELECT restricted FROM market_seller_meta WHERE uid=?',(owner,)).fetchone()
  if a['state'] not in ('ACTIVE','RESERVED','SOLD') or a['expires']<=int(time.time()) or restricted and restricted[0]:raise ValueError('Listing unavailable')
  if publishing and a['state']!='ACTIVE':raise ValueError('Publish an active listing before sharing it')
  price=(a['currency']+' '+format(a['amount_minor']/(1 if a['currency']=='JPY' else 100),',.2f')) if a['amount_minor'] is not None else a['price']
  result.update(title=a['title'],detail=a['description'][:240]+('…' if len(a['description'])>240 else ''),price=price,status=a['state'],version=str(a['revision']),image=a['images'][0] if a['images'] else None,url='/market.html?listing='+source,can_message=a['state']=='ACTIVE')
  return result
 if kind not in KINDS:raise ValueError('Unknown Vibe source')
 m=game_identities.meta(d,owner,game)
 identity=d.execute('SELECT game_id FROM gb_game_ids WHERE uid=? AND game=?',(owner,game)).fetchone()
 if not identity or not m or m['state']!='active' or not m['visible']:raise PermissionError('Enable this gaming profile’s visibility before sharing')
 if viewer!=owner and not game_identities.visible(d,viewer,owner,game):raise PermissionError('This gaming profile is private')
 if publishing and visibility=='public' and social.settings(d,owner)['private']:raise PermissionError('A private gaming profile can only be shared with authorized private recipients')
 result.update(title='Player profile',detail='',gaming_id=identity[0],identity_verification=m['verification'],url='/gaming.html?vibe_player='+owner+'&game='+game,status='Player profile')
 if kind=='profile':
  if source!=owner:raise PermissionError('Share your own profile')
  s=rankings.stats(d,owner,game);result['detail']='Rating '+str(s['rating'])+' · '+('Provisional' if s['provisional'] else s['grade']);result['version']=str(s['rating'])+str(s['played'])
 elif kind=='trophy':
  l=d.execute('SELECT * FROM leagues WHERE id=?',(source,)).fetchone()
  final=d.execute("SELECT * FROM fixtures WHERE league=? AND stage='final' AND state='confirmed' ORDER BY round DESC LIMIT 1",(source,)).fetchone()
  if not l or l['game']!=game or l['state']!='finished' or l['champion']!=owner or not final or final['score_a']==final['score_b'] or (final['a'] if final['score_a']>final['score_b'] else final['b'])!=owner:raise ValueError('No verified championship victory is available')
  if d.execute("SELECT 1 FROM fixtures WHERE league=? AND state IN ('disputed','review','pending')",(source,)).fetchone():raise ValueError('Competition review is still open')
  result.update(title='X-ORBIT CHAMPION',detail=l['name']+' · '+l['format'].title()+' Winner',status='Verified trophy',version=str((final['id'],final['score_a'],final['score_b'])),achievement_url='/gaming.html?league='+source)
 elif kind=='sponsored':
  import sponsored_leagues
  l=sponsored_leagues.get_league(d,source)
  standing=next((s for s in sponsored_leagues.table(d,source) if s['uid']==owner),None)
  if l['game']!=game or l['state'] not in ('COMPLETED','ARCHIVED') or not l['final_snapshot'] or not standing or standing['position']!=1 or standing['played']<1:raise ValueError('No finalized league victory is available')
  results=d.execute('SELECT r.*,m.state,m.score_a AS actual_a,m.score_b AS actual_b FROM sl_results r JOIN gb_matches m ON m.id=r.match WHERE r.league=?',(source,)).fetchall()
  if not results or any(r['state']!='verified' or r['score_a']!=r['actual_a'] or r['score_b']!=r['actual_b'] for r in results) or d.execute("SELECT 1 FROM sl_appeals a JOIN sl_results r ON r.match=a.match WHERE r.league=? AND a.state='pending'",(source,)).fetchone():raise ValueError('League results are under review')
  result.update(title='X-ORBIT CHAMPION',detail=l['name']+' · League Winner',status='Verified trophy',version=hashlib.sha256(json.dumps([dict(r) for r in results],sort_keys=True).encode()).hexdigest(),achievement_url='/gaming.html?vibe_sponsored='+source)
 else:
  r=d.execute('SELECT v.*,h.kind,h.source,h.rating_after FROM vibe_rank_milestones v JOIN gb_rank_history h ON h.id=v.history WHERE v.id=? AND v.uid=? AND v.game=?',(source,owner,game)).fetchone()
  a=d.execute('SELECT a.*,m.state,m.score_a AS actual_a,m.score_b AS actual_b FROM gb_rank_awards a JOIN gb_matches m ON m.id=a.id WHERE a.kind=? AND a.id=?',(r['kind'],r['source'])).fetchone() if r else None
  if not a or a['state']!='verified' or a['score_a']!=a['actual_a'] or a['score_b']!=a['actual_b']:raise ValueError('Milestone result is unavailable or corrected')
  result.update(title='Number 1' if r['threshold']==1 else 'Top '+str(r['threshold']),detail='Verified global ranking milestone',status='Ranking achievement',version=str(r['history']))
 return result

def linked(d,viewer,item):
 link=d.execute('SELECT * FROM vibe_links WHERE item=?',(item['id'],)).fetchone()
 if not link:return None
 try:return resolve(d,viewer,item['uid'],link['kind'],link['source'],link['game'])
 except (ValueError,PermissionError):return {'kind':link['kind'],'available':False,'status':'Source unavailable or under review','title':'This shared content is no longer available','detail':''}

def card(d,source):
 """Rendered on read; the database only holds the original source reference."""
 im=Image.new('RGB',(720,960),'#091020');draw=ImageDraw.Draw(im)
 font_path=Path(__file__).parent/'vibe-body.ttf'
 if not font_path.exists():font_path=Path(__file__).parent/'roboto-0.ttf'
 def font(size):
  try:return ImageFont.truetype(str(font_path),size)
  except OSError:return ImageFont.load_default(size=size)
 y=40
 if source.get('image') and source['available']:
  r=d.execute('SELECT data FROM market_images WHERE id=?',(source['image'],)).fetchone()
  if r:
   with Image.open(io.BytesIO(r[0])) as picture:im.paste(ImageOps.contain(picture.convert('RGB'),(656,420)),(32,32))
   y=480
 for text,size,color in [(source.get('handle',''),26,'#22d3ee'),(source['title'],36,'#f4f5fa'),(source.get('price',''),30,'#34d399'),(source.get('name',''),28,'#f4f5fa'),((__import__('gaming').GAMES.get(source.get('game'),'')+' ID: '+source['gaming_id']) if source.get('gaming_id') else '',25,'#adb4c5'),(source.get('detail',''),24,'#f4f5fa'),(source.get('status',''),22,'#adb4c5')]:
  for line in textwrap.wrap(str(text),width=32 if size>=30 else 44):
   draw.text((32,y),line,font=font(size),fill=color);y+=size+10
   if y>910:break
 out=io.BytesIO();im.save(out,'PNG');return out.getvalue()

def publish(d,uid,b):
 import vibes,social
 kind=b.get('kind');source=b.get('source');game=b.get('game','');visibility=b.get('visibility');client=b.get('client_id');audience=b.get('audience',[])
 if kind not in KINDS or not isinstance(source,str) or not source or not isinstance(game,str) or visibility not in ('public','private') or not isinstance(client,str) or not 8<=len(client)<=100:raise ValueError('Choose a source and Public or Private Vibe')
 recipients=vibes.recipients(d,uid,visibility,audience)
 payload=json.dumps([kind,source,game,visibility,recipients],separators=(',',':'));digest=hashlib.sha256(payload.encode()).hexdigest()
 prior=d.execute('SELECT * FROM vibe_link_keys WHERE uid=? AND client=?',(uid,client)).fetchone()
 if prior:
  if prior['fingerprint']!=digest:raise ValueError('A retry cannot change the shared source or audience')
  v=d.execute('SELECT expires FROM vibe_items WHERE id=?',(prior['item'],)).fetchone()
  return {'id':prior['item'],'expires':v[0] if v else 0,'already_published':True}
 resolve(d,uid,uid,kind,source,game,True,visibility)
 for target in recipients:resolve(d,target,uid,kind,source,game)
 now=int(time.time())
 existing=d.execute('SELECT i.id,i.expires FROM vibe_items i JOIN vibe_links l ON l.item=i.id WHERE i.uid=? AND i.visibility=? AND i.digest=? AND i.expires>? AND i.media IS NOT NULL',(uid,visibility,digest,now)).fetchone()
 if existing:ident=existing['id'];expires=existing['expires']
 else:
  if d.execute('SELECT COUNT(*) FROM vibe_items WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0]>=30:raise ValueError('Limit: 30 Vibe uploads per hour')
  ident=uuid.uuid4().hex;expires=now+86400
  d.execute('INSERT INTO vibe_items VALUES(?,?,?,?,?,?,?,?,?,?)',(ident,uid,visibility,'image/png',b'','',now,expires,'link-'+client,digest))
  d.execute('INSERT INTO vibe_links VALUES(?,?,?,?)',(ident,kind,source,game))
  for target in recipients:
   d.execute('INSERT INTO vibe_audience VALUES(?,?)',(ident,target));__import__('account_notifications').add(d,target,'vibe','private','A contact shared a Private Vibe with you.',{'item':ident,'visibility':'private'})
 d.execute('INSERT INTO vibe_link_keys VALUES(?,?,?,?)',(uid,client,digest,ident))
 return {'id':ident,'expires':expires,'already_published':bool(existing)}

def recognize(d,game):
 """Only invoked by the verified ranking award transaction, never ordinary UI wins."""
 import rankings
 thresholds=json.loads(d.execute('SELECT thresholds FROM vibe_milestone_policy WHERE id=1').fetchone()[0]);p=rankings.policy(d)['config']['placements'];position=0
 for r in d.execute("SELECT r.* FROM gb_ratings r JOIN gb_identity_meta m ON m.uid=r.uid AND m.game=r.game WHERE r.game=? AND m.state='active' ORDER BY r.rating DESC,r.played DESC,r.uid",(game,)).fetchall():
  if rankings.placements(d,r['uid'],game)<p:continue
  position+=1
  h=d.execute('SELECT id FROM gb_rank_history WHERE uid=? AND game=? ORDER BY id DESC LIMIT 1',(r['uid'],game)).fetchone()
  if not h:continue
  for threshold in thresholds:
   if position<=threshold:d.execute('INSERT OR IGNORE INTO vibe_rank_milestones VALUES(?,?,?,?,?,?)',(uuid.uuid4().hex,r['uid'],game,threshold,h[0],int(time.time())))

def prompts(d,uid,include_shared=False):
 candidates=[]
 for r in d.execute("SELECT id,game FROM leagues WHERE champion=? AND state='finished'",(uid,)):candidates.append(('trophy',r['id'],r['game']))
 for r in d.execute("SELECT DISTINCT l.id,l.game FROM sl_leagues l JOIN sl_standings s ON s.league=l.id WHERE s.uid=? AND l.state IN ('COMPLETED','ARCHIVED')",(uid,)):candidates.append(('sponsored',r['id'],r['game']))
 for r in d.execute('SELECT id,game FROM vibe_rank_milestones WHERE uid=?',(uid,)):candidates.append(('milestone',r['id'],r['game']))
 output=[]
 for kind,source,game in candidates:
  if not include_shared and (d.execute('SELECT 1 FROM vibe_prompt_dismissals WHERE uid=? AND kind=? AND source=?',(uid,kind,source)).fetchone() or d.execute('SELECT 1 FROM vibe_links l JOIN vibe_items i ON i.id=l.item WHERE i.uid=? AND l.kind=? AND l.source=?',(uid,kind,source)).fetchone()):continue
  try:output.append(resolve(d,uid,uid,kind,source,game))
  except (ValueError,PermissionError):continue
 return output
