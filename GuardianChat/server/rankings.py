"""One rating award path over existing gb_ratings; versioned placements and grades."""
import json,time,threading
_cache={};_cache_lock=threading.Lock()
DEFAULT={'k':24,'placements':10,'grades':[{'name':n,'minimum':v} for n,v in [('Bronze',0),('Silver',1300),('Gold',1500),('Platinum',1700),('Diamond',1900),('Elite',2100)]]}
def init(server):
 with server.db() as d:
  d.executescript('''
  CREATE TABLE IF NOT EXISTS gb_rank_policies(id INTEGER PRIMARY KEY,config TEXT NOT NULL,actor TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS gb_rank_bindings(kind TEXT,id TEXT,policy INTEGER NOT NULL,PRIMARY KEY(kind,id));
  CREATE TABLE IF NOT EXISTS gb_rank_baselines(uid TEXT,game TEXT,rating REAL,played INTEGER,placements INTEGER,created INTEGER,PRIMARY KEY(uid,game));
  CREATE TABLE IF NOT EXISTS gb_rank_awards(kind TEXT,id TEXT,game TEXT,a TEXT,b TEXT,score_a INTEGER,score_b INTEGER,policy INTEGER,before_a REAL,before_b REAL,after_a REAL,after_b REAL,created INTEGER,PRIMARY KEY(kind,id));
  CREATE TABLE IF NOT EXISTS gb_rank_history(id INTEGER PRIMARY KEY,uid TEXT,game TEXT,kind TEXT,source TEXT,rating_before REAL,rating_after REAL,policy INTEGER,created INTEGER,UNIQUE(uid,kind,source));
  CREATE INDEX IF NOT EXISTS gb_rank_history_game ON gb_rank_history(game,uid);
  CREATE INDEX IF NOT EXISTS gb_identity_game ON gb_game_ids(game,uid);
  CREATE INDEX IF NOT EXISTS gb_rank_history_player ON gb_rank_history(uid,game,id);
  ''')
  if not d.execute('SELECT 1 FROM gb_rank_policies').fetchone():d.execute('INSERT INTO gb_rank_policies(config,actor,reason,created) VALUES(?,?,?,?)',(json.dumps(DEFAULT),'system','Initial master Phase B policy',int(time.time())))
  for r in d.execute('SELECT * FROM gb_ratings').fetchall():
   verified=d.execute("SELECT COUNT(*) FROM gb_matches WHERE game=? AND rated=1 AND state='verified' AND (a=? OR b=?)",(r['game'],r['uid'],r['uid'])).fetchone()[0]+d.execute("SELECT COUNT(*) FROM gb_rating_events e JOIN fixtures f ON f.id=e.fixture JOIN leagues l ON l.id=f.league WHERE l.game=? AND f.state='confirmed' AND (f.a=? OR f.b=?)",(r['game'],r['uid'],r['uid'])).fetchone()[0]
   # Once-only migration baseline; subsequent awards have their own history.
   if not d.execute('SELECT 1 FROM gb_rank_history WHERE uid=? AND game=?',(r['uid'],r['game'])).fetchone():d.execute('INSERT OR IGNORE INTO gb_rank_baselines VALUES(?,?,?,?,?,?)',(r['uid'],r['game'],r['rating'],r['played'],min(r['played'],verified),int(time.time())))
  for kind,table in [('open','gb_matches'),('league','leagues')]:d.execute('INSERT OR IGNORE INTO gb_rank_bindings SELECT ?,id,(SELECT MAX(id) FROM gb_rank_policies) FROM '+table,(kind,))
  d.executescript('''CREATE TRIGGER IF NOT EXISTS gb_rank_bind_match AFTER INSERT ON gb_matches BEGIN INSERT INTO gb_rank_bindings VALUES('open',NEW.id,(SELECT MAX(id) FROM gb_rank_policies)); END;
  CREATE TRIGGER IF NOT EXISTS gb_rank_bind_league AFTER INSERT ON leagues BEGIN INSERT INTO gb_rank_bindings VALUES('league',NEW.id,(SELECT MAX(id) FROM gb_rank_policies)); END;''')
def policy(d,version=None):
 r=d.execute('SELECT * FROM gb_rank_policies '+('WHERE id=?' if version else 'ORDER BY id DESC LIMIT 1'),(version,) if version else ()).fetchone()
 if not r:raise ValueError('Ranking policy unavailable')
 return dict(r)|{'config':json.loads(r['config'])}
def placements(d,uid,game):
 r=d.execute('SELECT placements FROM gb_rank_baselines WHERE uid=? AND game=?',(uid,game)).fetchone()
 return (r[0] if r else 0)+d.execute('SELECT COUNT(*) FROM gb_rank_history WHERE uid=? AND game=?',(uid,game)).fetchone()[0]
def stats(d,uid,game):
 r=d.execute('SELECT * FROM gb_ratings WHERE uid=? AND game=?',(uid,game)).fetchone();p=policy(d);count=placements(d,uid,game);rating=r['rating'] if r else 1500
 grade=next((g['name'] for g in reversed(p['config']['grades']) if rating>=g['minimum']),'Bronze')
 return {'uid':uid,'game':game,'rating':rating,'played':r['played'] if r else 0,'verified_placements':count,'placement_required':p['config']['placements'],'provisional':count<p['config']['placements'],'grade':grade if count>=p['config']['placements'] else None,'confidence':'placement_complete_uncalibrated' if count>=p['config']['placements'] else 'provisional','placement_progress':min(1,count/p['config']['placements']),'policy':p['id']}
def award(d,kind,r):
 """Called only inside the existing verified-result write transaction. Never client-facing."""
 if kind not in ('open','fixture') or r['a']==r['b']:raise ValueError('Invalid ranked result')
 # Legacy competition awards remain in history; new competition outcomes are not global ranked play.
 if kind=='fixture' or not __import__('competition_context').is_global(d,r['id']):return None
 if d.execute('SELECT 1 FROM gb_rank_awards WHERE kind=? AND id=?',(kind,r['id'])).fetchone():return None
 if kind=='open':
  actual=d.execute('SELECT * FROM gb_matches WHERE id=?',(r['id'],)).fetchone()
  if not actual or actual['state']!='verified':raise ValueError('Verify this result before rating')
  if actual['rated']:return None
  binding=('open',r['id']);game=actual['game']
 else:
  actual=d.execute('SELECT f.*,l.game,l.verification FROM fixtures f JOIN leagues l ON l.id=f.league WHERE f.id=?',(r['id'],)).fetchone()
  if not actual or actual['state']!='confirmed' or actual['verification']!='typed':raise ValueError('Only confirmed typed played fixtures may be rated')
  if d.execute('SELECT 1 FROM gb_rating_events WHERE fixture=?',(r['id'],)).fetchone():return None
  binding=('league',actual['league']);game=actual['game']
 v=d.execute('SELECT policy FROM gb_rank_bindings WHERE kind=? AND id=?',binding).fetchone();p=policy(d,v[0] if v else None);old={};new={}
 for u in (actual['a'],actual['b']):
  d.execute('INSERT OR IGNORE INTO gb_ratings(uid,game) VALUES(?,?)',(u,game));old[u]=dict(d.execute('SELECT * FROM gb_ratings WHERE uid=? AND game=?',(u,game)).fetchone())
 for u,other,own,theirs in [(actual['a'],actual['b'],actual['score_a'],actual['score_b']),(actual['b'],actual['a'],actual['score_b'],actual['score_a'])]:
  outcome=1 if own>theirs else .5 if own==theirs else 0;expected=1/(1+10**((old[other]['rating']-old[u]['rating'])/400));new[u]=round(old[u]['rating']+p['config']['k']*(outcome-expected),2)
  d.execute('UPDATE gb_ratings SET rating=?,played=played+1,activity=activity+1 WHERE uid=? AND game=?',(new[u],u,game))
  d.execute('INSERT INTO gb_rank_history(uid,game,kind,source,rating_before,rating_after,policy,created) VALUES(?,?,?,?,?,?,?,?)',(u,game,kind,r['id'],old[u]['rating'],new[u],p['id'],int(time.time())))
 d.execute('INSERT INTO gb_rank_awards VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(kind,r['id'],game,actual['a'],actual['b'],actual['score_a'],actual['score_b'],p['id'],old[actual['a']]['rating'],old[actual['b']]['rating'],new[actual['a']],new[actual['b']],int(time.time())))
 # Recognition references these verified awards; it never publishes a Vibe automatically.
 if d.execute("SELECT 1 FROM sqlite_master WHERE name='vibe_rank_milestones'").fetchone():__import__('vibe_sources').recognize(d,game)
 return {'old':old,'new':new,'policy':p['id']}
def publish(d,uid,b):
 import gamebox_core
 gamebox_core.authorised(d,uid);current=policy(d)
 if b.get('base')!=current['id']:raise ValueError('Ranking policy changed; reload before publishing')
 c=b.get('config');reason=b.get('reason','')
 if not isinstance(c,dict) or set(c)!=set(DEFAULT) or type(c['k']) is not int or not 8<=c['k']<=64 or type(c['placements']) is not int or not 1<=c['placements']<=100:raise ValueError('Invalid ranking policy')
 if not isinstance(c['grades'],list) or len(c['grades'])!=6:raise ValueError('Keep the six supported grades')
 previous=-1
 for g,expected in zip(c['grades'],DEFAULT['grades']):
  if not isinstance(g,dict) or set(g)!={'name','minimum'} or g['name']!=expected['name'] or type(g['minimum']) is not int or not previous<g['minimum']<=10000:raise ValueError('Grade thresholds must rise in order')
  previous=g['minimum']
 if c['grades'][0]['minimum']!=0 or not isinstance(reason,str) or not 5<=len(reason.strip())<=500:raise ValueError('Keep Bronze at zero and explain the policy change')
 d.execute('INSERT INTO gb_rank_policies(config,actor,reason,created) VALUES(?,?,?,?)',(json.dumps(c),uid,reason.strip(),int(time.time())));gamebox_core.event(d,'ranking-policy',uid,'ranking_policy_published',old=current,new=c,reason=reason.strip());return {'saved':True}
def get(server,uid,action,q):
 import gaming,social
 with server.db() as d:
  if action=='policy':return policy(d)
  if action=='policies':
   __import__('gamebox_core').authorised(d,uid);return {'policies':[dict(r) for r in d.execute('SELECT * FROM gb_rank_policies ORDER BY id DESC LIMIT 50')]}
  game=q.get('game',[''])[0]
  if game not in gaming.GAMES:raise ValueError('Choose a supported game')
  target=q.get('id',[uid])[0]
  if action in ('profile','history','seasons'):
   social.ensure(d,uid,target)
   if target!=uid and not __import__('game_identities').visible(d,uid,target,game):raise PermissionError('This competition profile is private')
   if action=='profile':return stats(d,target,game)
   if action=='history':
    history=[]
    for h in d.execute('SELECT * FROM gb_rank_history WHERE uid=? AND game=? AND id<? ORDER BY id DESC LIMIT 25',(target,game,int(q.get('before',['9223372036854775807'])[0]))):
     item=dict(h);result=d.execute('SELECT * FROM gb_rank_awards WHERE kind=? AND id=?',(h['kind'],h['source'])).fetchone()
     if result:
      own=result['score_a'] if result['a']==target else result['score_b'];other=result['score_b'] if result['a']==target else result['score_a'];item.update(score_for=own,score_against=other,outcome='W' if own>other else 'L' if own<other else 'D')
     history.append(item)
    return {'history':history}
   return {'competitions':[dict(r) for r in d.execute('SELECT l.id,l.name,l.state,l.format,l.champion FROM league_members m JOIN leagues l ON l.id=m.league WHERE m.uid=? AND l.game=? ORDER BY l.created DESC LIMIT 50',(target,game))]}
  if action!='leaderboard':raise ValueError('Unknown rankings action')
  p=policy(d);stamp=d.execute("SELECT (SELECT COALESCE(MAX(id),0) FROM gb_rank_history),(SELECT COALESCE(MAX(id),0) FROM gb_events WHERE match='identity')").fetchone();key=(d.execute('PRAGMA database_list').fetchone()[2],game,p['id'],tuple(stamp))
  with _cache_lock:cached=_cache.get(key)
  if cached and cached[0]>time.monotonic()-3:rows=[dict(r) for r in cached[1]]
  else:
   rows=[]
   for r in d.execute("SELECT i.uid,i.region,m.country,m.nickname,m.visible,COALESCE(r.rating,1500) rating,COALESCE(r.played,0) played,COALESCE(b.placements,0)+COALESCE(h.n,0) verified_placements FROM gb_game_ids i JOIN gb_identity_meta m ON m.uid=i.uid AND m.game=i.game LEFT JOIN gb_ratings r ON r.uid=i.uid AND r.game=i.game LEFT JOIN gb_rank_baselines b ON b.uid=i.uid AND b.game=i.game LEFT JOIN (SELECT uid,COUNT(*) n FROM gb_rank_history WHERE game=? GROUP BY uid) h ON h.uid=i.uid WHERE i.game=? AND m.state='active'",(game,game)):
    v=dict(r);v.update(game=game,placement_required=p['config']['placements'],provisional=v['verified_placements']<p['config']['placements'],policy=p['id']);v['grade']=None if v['provisional'] else next((g['name'] for g in reversed(p['config']['grades']) if v['rating']>=g['minimum']),'Bronze');rows.append(v)
   with _cache_lock:
    if len(_cache)>=32:_cache.pop(next(iter(_cache)))
    _cache[key]=(time.monotonic(),[dict(r) for r in rows])
  rows.sort(key=lambda r:(r['provisional'],-r['rating'],-r['played'],r['uid']));rank=0
  for r in rows:
   if not r['provisional']:rank+=1;r['global_rank']=rank
   else:r['global_rank']=None
  mine=next((dict(r) for r in rows if r['uid']==uid),None);country=q.get('country',[''])[0].upper();friends=q.get('friends',['0'])[0]=='1'
  if country:rows=[r for r in rows if r['country']==country]
  if friends:rows=[r for r in rows if r['uid']==uid or d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?',(uid,r['uid'])).fetchone()]
  total=len(rows);offset=max(0,int(q.get('offset',['0'])[0]));limit=min(50,max(1,int(q.get('limit',['25'])[0])))
  if q.get('mine',['0'])[0]=='1':offset=next((i//limit*limit for i,r in enumerate(rows) if r['uid']==uid),0)
  output=[]
  for r in rows[offset:offset+limit]:
   if r['uid']!=uid and not __import__('game_identities').visible(d,uid,r['uid'],game):r={k:v for k,v in r.items() if k not in ('uid','nickname','region','country')};r['nickname']='Private player'
   output.append(r)
  return {'players':output,'total':total,'offset':offset,'limit':limit,'my_rank':mine,'policy':policy(d),'explanation':'Elo starts at 1500. Placement progress is a match-count indicator, not a calibrated probability. Filters keep global positions. League points and future QP are separate. No spending affects rating.'}
