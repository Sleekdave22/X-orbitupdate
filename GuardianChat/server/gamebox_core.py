"""Versioned Gamebox Studio and open-match workflows. Does not edit chat/media security."""
import json,time,uuid,re,math,hashlib,base64
DEFAULT={'accept_seconds':300,'checkin_seconds':600,'result_seconds':3600,'evidence_seconds':86400,'retention_seconds':259200,'reminder_seconds':900,'open_schedule_seconds':604800,'reschedules':1,'group_size':10,'round_days':3,'max_pair_daily':2,'rating_gap':400,'league_cup_slots':4,'open_cup_slots':4,'weekly_min_matches':5,'weekly_min_opponents':3,'theme':{'accent':'#7C3AED','surface':'#131932','paper':'#0B1520','ink':'#F1F5F9','radius':16,'tab_padding':12,'font_size':14,'font_family':'system-ui'},'layout':['stats','competitions','players','matches'],'announcement':'','show_stats':True}
DEFAULT['presentation']={'chat_order':['search','tabs','gaming','list'],'game_tabs':['leagues','seasons','open','schedule','fixtures','players','live','table','card','profile','streams'],'custom_sections':[],'custom_games':{},'labels':{'brand':'X ORBIT','slogan':'Your world your connection','search':'Search X ORBIT','gaming':'Gamebox'}}
LEGACY_DEFAULT_THEME={'accent': '#921b37', 'surface': '#252525', 'paper': '#101010', 'ink': '#f4f4f4', 'radius': 8, 'tab_padding': 12, 'font_size': 14, 'font_family': 'system-ui'}
LIMITS={'accept_seconds':(60,1800),'checkin_seconds':(120,3600),'result_seconds':(1800,7200),'evidence_seconds':(3600,259200),'retention_seconds':(3600,2592000),'reminder_seconds':(60,3600),'open_schedule_seconds':(3600,1209600),'reschedules':(0,1),'group_size':(6,16),'round_days':(1,14),'max_pair_daily':(1,3),'rating_gap':(100,800),'league_cup_slots':(0,8),'open_cup_slots':(0,8),'weekly_min_matches':(1,20),'weekly_min_opponents':(1,10)}
def init(server):
 with server.db() as d:
  d.executescript('''
  CREATE TABLE IF NOT EXISTS gb_comp_retention(fixture TEXT PRIMARY KEY,expires INTEGER);
  CREATE TABLE IF NOT EXISTS gb_walkovers(fixture TEXT PRIMARY KEY,winner TEXT,reason TEXT,actor TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_result_signals(id INTEGER PRIMARY KEY,room TEXT,uid TEXT,kind TEXT,payload TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_result_comments(id INTEGER PRIMARY KEY,room TEXT,uid TEXT,text TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_game_catalog(key TEXT PRIMARY KEY,name TEXT);
  CREATE TABLE IF NOT EXISTS gb_schedule(fixture TEXT PRIMARY KEY,proposer TEXT,proposed INTEGER,scheduled INTEGER,confirmed_a INTEGER DEFAULT 0,confirmed_b INTEGER DEFAULT 0,reschedules INTEGER DEFAULT 0,ready_a INTEGER DEFAULT 0,ready_b INTEGER DEFAULT 0,reminded INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS gb_cup_eligibility(league TEXT,uid TEXT,source TEXT,PRIMARY KEY(league,uid));
  CREATE TABLE IF NOT EXISTS gb_qualified_cups(league TEXT PRIMARY KEY,version INTEGER,week INTEGER);
  CREATE TABLE IF NOT EXISTS gb_seasons(id TEXT PRIMARY KEY,name TEXT,game TEXT,tier INTEGER,opens INTEGER,closes INTEGER,state TEXT,owner TEXT,version INTEGER,rules TEXT);
  CREATE TABLE IF NOT EXISTS gb_season_entries(season TEXT,uid TEXT,game_id TEXT,availability TEXT,registered INTEGER,PRIMARY KEY(season,uid));
  CREATE TABLE IF NOT EXISTS gb_season_availability(season TEXT,uid TEXT,snapshot TEXT NOT NULL,PRIMARY KEY(season,uid));
  CREATE TABLE IF NOT EXISTS gb_season_groups(season TEXT,league TEXT,number INTEGER,PRIMARY KEY(season,league));
  CREATE TABLE IF NOT EXISTS gb_versions(id INTEGER PRIMARY KEY,config TEXT,actor TEXT,reason TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_draft(id INTEGER PRIMARY KEY CHECK(id=1),base INTEGER,config TEXT);
  CREATE TABLE IF NOT EXISTS gb_game_ids(uid TEXT,game TEXT,game_id TEXT,region TEXT,tz TEXT,availability TEXT,reminders INTEGER DEFAULT 1,PRIMARY KEY(uid,game));
  CREATE TABLE IF NOT EXISTS gb_rating_events(fixture TEXT PRIMARY KEY,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_ratings(uid TEXT,game TEXT,rating REAL DEFAULT 1500,played INTEGER DEFAULT 0,activity INTEGER DEFAULT 0,PRIMARY KEY(uid,game));
  CREATE TABLE IF NOT EXISTS gb_queue(uid TEXT PRIMARY KEY,game TEXT,region TEXT,priority INTEGER DEFAULT 0,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_matches(id TEXT PRIMARY KEY,game TEXT,a TEXT,b TEXT,gid_a TEXT,gid_b TEXT,state TEXT,created INTEGER,deadline INTEGER,accepted_a INTEGER DEFAULT 0,accepted_b INTEGER DEFAULT 0,ready_a INTEGER DEFAULT 0,ready_b INTEGER DEFAULT 0,score_a INTEGER,score_b INTEGER,version INTEGER,rules TEXT,verified INTEGER,rated INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS gb_reports(match TEXT,uid TEXT,a INTEGER,b INTEGER,PRIMARY KEY(match,uid));
  CREATE TABLE IF NOT EXISTS gb_evidence(match TEXT,uid TEXT,image BLOB,mime TEXT,digest TEXT,reading TEXT,expires INTEGER,PRIMARY KEY(match,uid));
  CREATE TABLE IF NOT EXISTS gb_events(id INTEGER PRIMARY KEY,match TEXT,actor TEXT,action TEXT,old TEXT,new TEXT,reason TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_notice_delivery(id INTEGER PRIMARY KEY,attempts INTEGER DEFAULT 0,next_attempt INTEGER DEFAULT 0,delivered INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS gb_notices(id INTEGER PRIMARY KEY,uid TEXT,text TEXT,created INTEGER,seen INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS gb_room_messages(id INTEGER PRIMARY KEY,match TEXT,uid TEXT,text TEXT,created INTEGER);
  CREATE TABLE IF NOT EXISTS gb_sanctions(uid TEXT,game TEXT,until INTEGER,reason TEXT,PRIMARY KEY(uid,game));
  ''')
  d.execute('CREATE INDEX IF NOT EXISTS gb_match_a_state ON gb_matches(a,state)');d.execute('CREATE INDEX IF NOT EXISTS gb_match_b_state ON gb_matches(b,state)');d.execute('CREATE INDEX IF NOT EXISTS gb_match_game_created ON gb_matches(game,created)');d.execute('CREATE INDEX IF NOT EXISTS gb_event_match ON gb_events(match,created)');d.execute('CREATE INDEX IF NOT EXISTS gb_room_match ON gb_room_messages(match,id)')
  if not d.execute('SELECT 1 FROM gb_versions').fetchone():d.execute('INSERT INTO gb_versions(config,actor,reason,created) VALUES(?,?,?,?)',(json.dumps(DEFAULT),'system','Initial supported defaults',int(time.time())))
  else:
   existing=row(d,'SELECT * FROM gb_versions ORDER BY id DESC LIMIT 1');old=json.loads(existing['config']);merged=dict(DEFAULT,**old);merged['theme']=dict(DEFAULT['theme'],**old.get('theme',{}));merged['presentation']=dict(DEFAULT['presentation'],**old.get('presentation',{}))
   if old.get('theme')==LEGACY_DEFAULT_THEME:merged['theme']=dict(DEFAULT['theme'])
   if merged!=old:d.execute('INSERT INTO gb_versions(config,actor,reason,created) VALUES(?,?,?,?)',(json.dumps(merged),'migration','Add supported controls while preserving published customisations',int(time.time())))
 __import__("competition_context").init(server)
def row(d,sql,args=()):
 r=d.execute(sql,args).fetchone();return dict(r) if r else None
def current(d):
 result=row(d,'SELECT * FROM gb_versions ORDER BY id DESC LIMIT 1')
 import gaming
 config=json.loads(result['config']);custom=config.get('presentation',{}).get('custom_games',{})
 for key,name in custom.items():d.execute('INSERT OR IGNORE INTO gb_game_catalog VALUES(?,?)',(key,name))
 gaming.GAMES=dict(gaming.BUILTIN_GAMES,**{r['key']:r['name'] for r in d.execute('SELECT * FROM gb_game_catalog')})
 return result
def authorised(d,uid):
 import gaming
 if not gaming.admin(d,uid):raise PermissionError('Administration is restricted to the authorised account')
def event(d,mid,uid,action,old=None,new=None,reason=''):
 d.execute('INSERT INTO gb_events(match,actor,action,old,new,reason,created) VALUES(?,?,?,?,?,?,?)',(mid,uid,action,json.dumps(old),json.dumps(new),reason,int(time.time())))
def notice(d,uid,text):return d.execute('INSERT INTO gb_notices(uid,text,created) VALUES(?,?,?)',(uid,text,int(time.time()))).lastrowid
def validate(c):
 if type(c)!=dict or set(c)!=set(DEFAULT):raise ValueError('Only supported Studio controls may be changed')
 for k,(lo,hi) in LIMITS.items():
  if type(c[k])!=int or not lo<=c[k]<=hi:raise ValueError(k+' must be between '+str(lo)+' and '+str(hi))
 t=c['theme']
 if type(t)!=dict or set(t)!=set(DEFAULT['theme']):raise ValueError('Unsupported theme controls')
 for k in ['accent','surface','paper','ink']:
  if not re.fullmatch(r'#[0-9a-fA-F]{6}',str(t[k])):raise ValueError('Use six-digit colour values')
 for k,lo,hi in [('radius',0,24),('tab_padding',8,24),('font_size',12,20)]:
  if type(t[k])!=int or not lo<=t[k]<=hi:raise ValueError('Invalid theme sizing')
 if c['league_cup_slots']+c['open_cup_slots']!=8:raise ValueError('League and open qualification slots must total eight')
 if type(c['layout'])!=list or sorted(c['layout'])!=sorted(DEFAULT['layout']):raise ValueError('Reorder existing components only')
 if t['font_family'] not in ('system-ui','sans-serif','serif','monospace'):raise ValueError('Choose a supported built-in font')
 if type(c['show_stats'])!=bool:raise ValueError('Choose whether statistics should be displayed')
 if type(c['announcement'])!=str or len(c['announcement'])>500:raise ValueError('Announcement must be under 500 characters')
 p=c['presentation']
 if type(p)!=dict or set(p)!=set(DEFAULT['presentation']):raise ValueError('Unsupported presentation controls')
 for key in ('chat_order','game_tabs'):
  if type(p[key])!=list or sorted(p[key])!=sorted(DEFAULT['presentation'][key]):raise ValueError('Reorder the supported sections only')
 if type(p['labels'])!=dict or set(p['labels'])!=set(DEFAULT['presentation']['labels']):raise ValueError('Unsupported app labels')
 for value in p['labels'].values():
  if type(value)!=str or not 1<=len(value.strip())<=80:raise ValueError('App labels must be 1–80 characters')
 games=p['custom_games'];sections=p['custom_sections']
 if type(games)!=dict or len(games)>20:raise ValueError('At most 20 custom games')
 for key,name in games.items():
  if not re.fullmatch(r'custom_[a-z0-9_]{3,40}',key) or type(name)!=str or not 2<=len(name.strip())<=60:raise ValueError('Invalid custom game')
 if type(sections)!=list or len(sections)>20:raise ValueError('At most 20 custom sections')
 ids=set()
 for section in sections:
  if type(section)!=dict or set(section)!={'id','title','kind','content','target'}:raise ValueError('Unsupported section fields')
  if not re.fullmatch(r'custom_[a-z0-9_]{3,40}',str(section['id'])) or section['id'] in ids:raise ValueError('Invalid section ID')
  ids.add(section['id'])
  if type(section['title'])!=str or not 1<=len(section['title'].strip())<=60 or type(section['content'])!=str or len(section['content'])>4000:raise ValueError('Invalid section text')
  kind=section['kind'];target=section['target']
  if kind not in ('page','feature','link','game') or type(target)!=str:raise ValueError('Choose a supported button function')
  if kind=='feature' and target not in DEFAULT['presentation']['game_tabs']:raise ValueError('Choose a supported feature')
  if kind=='game' and target not in games:raise ValueError('Choose a custom game')
  if kind=='link':
   from urllib.parse import urlparse
   u=urlparse(target)
   if u.scheme!='https' or not u.hostname or u.username or u.password:raise ValueError('Use a valid HTTPS website address')
 return c
def eligible(d,uid,game):
 import gaming
 if game not in gaming.GAMES:raise ValueError('Choose a supported game')
 if __import__('match_scheduling').temporarily_unavailable(d,uid,game):raise ValueError('Your gaming availability is temporarily unavailable')
 if not d.execute('SELECT 1 FROM game_profiles WHERE uid=? AND adult=1',(uid,)).fetchone():raise ValueError('Create your adult gaming profile first')
 if d.execute('SELECT 1 FROM gb_sanctions WHERE uid=? AND game=? AND until>?',(uid,game,int(time.time()))).fetchone():raise ValueError('Gaming access is suspended; contact administration for review')
 identity=row(d,'SELECT * FROM gb_game_ids WHERE uid=? AND game=?',(uid,game))
 if identity and (__import__('game_identities').meta(d,uid,game) or {}).get('state')!='active':raise ValueError('This game registration is inactive or needs review')
 return identity
def participant(d,uid,mid):
 m=row(d,'SELECT * FROM gb_matches WHERE id=?',(mid,))
 if not m or uid not in (m['a'],m['b']):raise PermissionError('Only the match participants may do this')
 return m

def summary(server,uid):
 with server.db() as d:
  version=current(d);config=json.loads(version['config'])
  matches=[dict(r) for r in d.execute('SELECT m.*,pa.tag name_a,pb.tag name_b FROM gb_matches m JOIN game_profiles pa ON pa.uid=m.a JOIN game_profiles pb ON pb.uid=m.b WHERE a=? OR b=? ORDER BY created DESC LIMIT 30',(uid,uid))]
  for m in matches:
   m.update(__import__('competition_context').decorate(d,m));m.pop('rules',None);m['reports']=[dict(r) for r in d.execute('SELECT * FROM gb_reports WHERE match=?',(m['id'],))]
   m['evidence_review']=__import__('result_reviews').status(d,dict(m,kind='open'),uid)
   if m['state']=='awaiting_results' and not any(r['uid']==uid for r in m['reports']):m['reports']=[{'uid':r['uid'],'submitted':True} for r in m['reports']]
  return {'seasons':[dict(r)|{'registered':d.execute('SELECT COUNT(*) FROM gb_season_entries WHERE season=?',(r['id'],)).fetchone()[0],'joined':bool(d.execute('SELECT 1 FROM gb_season_entries WHERE season=? AND uid=?',(r['id'],uid)).fetchone()),'groups':[x[0] for x in d.execute('SELECT league FROM gb_season_groups WHERE season=? ORDER BY number',(r['id'],))]} for r in d.execute('SELECT id,name,game,tier,opens,closes,state FROM gb_seasons ORDER BY closes DESC LIMIT 30')],'version':version['id'],'config':config,'ids':[dict(r) for r in d.execute("SELECT i.* FROM gb_game_ids i JOIN gb_identity_meta m ON m.uid=i.uid AND m.game=i.game WHERE i.uid=? AND m.state='active'",(uid,))],'ratings':[dict(r)|__import__('rankings').stats(d,uid,r['game']) for r in d.execute('SELECT * FROM gb_ratings WHERE uid=?',(uid,))],'queue':row(d,'SELECT * FROM gb_queue WHERE uid=?',(uid,)),'matches':matches,'notices':__import__('match_scheduling').visible_notices(d,uid)}
def studio(server,uid):
 with server.db() as d:
  authorised(d,uid)
  disputes=[dict(r) for r in d.execute("SELECT * FROM gb_matches WHERE state IN ('disputed','review') AND a!=? AND b!=? ORDER BY created",(uid,uid))]
  for m in disputes:
   m['evidence']=[dict(r) for r in d.execute('SELECT uid,mime,reading FROM gb_evidence WHERE match=?',(m['id'],))]
   m['video_evidence']=[dict(r) for r in d.execute('SELECT uid,mime,created FROM result_review_videos WHERE kind=\'open\' AND match_id=? AND video IS NOT NULL',(m['id'],))]
   m['evidence_review']=__import__('result_reviews').status(d,dict(m,kind='open'),uid)
   for e in m['evidence']:
    normal=re.sub(r'[^a-z0-9]','',e['reading'].lower());e['ids_read']=all(re.sub(r'[^a-z0-9]','',m[key].lower()) in normal for key in ('gid_a','gid_b'))
  return {'published':current(d),'draft':row(d,'SELECT * FROM gb_draft WHERE id=1'),'versions':[dict(r) for r in d.execute('SELECT id,actor,reason,created FROM gb_versions ORDER BY id DESC LIMIT 20')],'limits':LIMITS,'events':[dict(r) for r in d.execute('SELECT * FROM gb_events ORDER BY id DESC LIMIT 100')],'disputes':disputes,'sanctions':[dict(r) for r in d.execute('SELECT * FROM gb_sanctions')]}

def pair(d,game,region):
 candidates=[dict(r) for r in d.execute('SELECT q.*,i.game_id,COALESCE(r.rating,1500) rating FROM gb_queue q JOIN gb_game_ids i ON i.uid=q.uid AND i.game=q.game LEFT JOIN gb_ratings r ON r.uid=q.uid AND r.game=q.game WHERE q.game=? AND q.region=? ORDER BY priority DESC,q.created,q.rowid',(game,region))];version=current(d);rules=json.loads(version['config'])
 for i,a in enumerate(candidates):
  import competition_context, social, game_identities
  if competition_context.busy(d,a['uid']):continue
  try:
   if not eligible(d,a['uid'],game):continue
  except ValueError:continue
  def priority(b):
   try:return __import__('match_scheduling').overlap(d,a['uid'],b['uid'],game,int(time.time())+60,int(time.time())+604800) is None
   except ValueError:return True
  for b in sorted(candidates[i+1:],key=priority):
   if competition_context.busy(d,b['uid']) or social.blocked(d,a['uid'],b['uid']):continue
   try:
    if not eligible(d,b['uid'],game):continue
   except ValueError:continue
   ap=(game_identities.meta(d,a['uid'],game) or {}).get('platform','unspecified');bp=(game_identities.meta(d,b['uid'],game) or {}).get('platform','unspecified')
   if not __import__('sponsored_leagues').compatible(ap,bp):continue
   low,high=sorted((a['uid'],b['uid']))
   if d.execute('SELECT 1 FROM gb_match_cooldowns WHERE game=? AND low=? AND high=? AND until>?',(game,low,high,int(time.time()))).fetchone():continue
   if a['game_id'].casefold()==b['game_id'].casefold() or abs(a['rating']-b['rating'])>rules['rating_gap']:continue
   if d.execute("SELECT COUNT(*) FROM gb_matches WHERE id IN (SELECT match FROM gb_match_origins WHERE global_ranking_eligible=1) AND game=? AND state='verified' AND created>? AND ((a=? AND b=?) OR (a=? AND b=?))",(game,int(time.time())-86400,a['uid'],b['uid'],b['uid'],a['uid'])).fetchone()[0]>=rules['max_pair_daily']:continue
   mid=uuid.uuid4().hex;now=int(time.time());d.execute('INSERT INTO gb_matches(id,game,a,b,gid_a,gid_b,state,created,deadline,version,rules) VALUES(?,?,?,?,?,?,?, ?,?,?,?)',(mid,game,a['uid'],b['uid'],a['game_id'],b['game_id'],'proposed',now,now+rules['accept_seconds'],version['id'],json.dumps(rules)))
   d.execute('DELETE FROM gb_queue WHERE uid IN (?,?)',(a['uid'],b['uid']));event(d,mid,'system','match_proposed',new={'a':a['uid'],'b':b['uid'],'version':version['id']})
   for u in (a['uid'],b['uid']):notice(d,u,'Opponent found. Both players must accept the proposed match.')
   return mid
 return None

def verify(d,m,a,b,actor,reason='Matching independent typed reports'):
 if m['state']=='verified':raise ValueError('This result is already verified')
 d.execute("UPDATE gb_matches SET state='verified',score_a=?,score_b=?,verified=? WHERE id=?",(a,b,int(time.time()),m['id']))
 import competition_context
 league_match=not competition_context.is_global(d,m['id'])
 if league_match:
  __import__('sponsored_leagues').settle(d,m,a,b,actor);awarded=None
 else:awarded=__import__('rankings').award(d,'open',m)
 old=awarded['old'] if awarded else {};new=awarded['new'] if awarded else {}
 d.execute('UPDATE gb_matches SET rated=? WHERE id=?',(0 if league_match else 1,m['id']));event(d,m['id'],actor,'result_verified',old={'reports':[dict(r) for r in d.execute('SELECT * FROM gb_reports WHERE match=?',(m['id'],))],'ratings':old},new={'score':[a,b],'ratings':new},reason=reason)
 rules=json.loads(m['rules']);d.execute('UPDATE gb_evidence SET expires=? WHERE match=?',(int(time.time())+rules['retention_seconds'],m['id']))
 for uid in (m['a'],m['b']):notice(d,uid,'League result verified. League points updated; global rating unchanged.' if league_match else 'Result verified. Skill rating and participation record updated.')
 __import__('result_reviews').finalized(d,'open',m['id'],a,b,actor,reason)

def post(server,uid,action,b):
 if action in ('evidence','result_evidence'):return __import__('result_reviews').submit(server,uid,b)
 if action=='result_signal':raise ValueError('Result evidence now uses private camera review. Reopen OrbitPlay to use the current result screen.')
 if action in ('schedule_propose','schedule_confirm'):
  return __import__('match_scheduling').post(server,uid,'propose' if action=='schedule_propose' else 'accept',dict(b,kind='fixture',match=b.get('fixture')))
 if action=='evidence':
  import gaming
  raw,mime=gaming.image(b);reading=gaming.scan(server,raw,mime);b=dict(b,reading=reading.get('text',''))
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  current(d)
  if action in ('result_signal','result_comment'):
   match=result_participant(d,uid,b.get('room'));rid=match['id']
   if match['state'] in ('verified','confirmed','cancelled','void','walkover'):raise ValueError('This result is closed')
   if action=='result_comment':
    text=str(b.get('text','')).strip()
    if not 1<=len(text)<=1000:raise ValueError('Enter a message under 1000 characters')
    if d.execute('SELECT COUNT(*) FROM gb_result_comments WHERE room=? AND uid=? AND created>?',(rid,uid,int(time.time())-10)).fetchone()[0]>=5:raise ValueError('Please slow down')
    d.execute('INSERT INTO gb_result_comments(room,uid,text,created) VALUES(?,?,?,?)',(rid,uid,text,int(time.time())))
   else:
    kind=b.get('kind');payload=b.get('payload')
    if kind not in ('join','offer','answer','ice') or type(payload)!=dict or set(payload)!={'session','value'}:raise ValueError('Only connection signaling is accepted; photos must travel peer to peer')
    sid=payload['session'];value=payload['value']
    if not isinstance(sid,str) or not re.fullmatch(r'[a-zA-Z0-9-]{1,80}',sid) or type(value)!=dict:raise ValueError('Invalid connection session')
    if kind in ('offer','answer') and (set(value)!={'type','sdp'} or value['type']!=kind or not str(value['sdp']).startswith('v=0') or len(value['sdp'])>60000):raise ValueError('Invalid connection description')
    if kind=='ice' and (set(value)-{'candidate','sdpMid','sdpMLineIndex','usernameFragment'} or not str(value.get('candidate','')).startswith('candidate:') or len(str(value))>4000):raise ValueError('Invalid connection candidate')
    if kind=='join' and value:raise ValueError('Invalid join')
    if d.execute('SELECT COUNT(*) FROM gb_result_signals WHERE room=? AND uid=? AND created>?',(rid,uid,int(time.time())-60)).fetchone()[0]>=100:raise ValueError('Connection retry limit reached')
    d.execute('INSERT INTO gb_result_signals(room,uid,kind,payload,created) VALUES(?,?,?,?,?)',(rid,uid,kind,json.dumps(payload),int(time.time())))
    d.execute('DELETE FROM gb_result_signals WHERE room=? AND id NOT IN (SELECT id FROM gb_result_signals WHERE room=? ORDER BY id DESC LIMIT 300)',(rid,rid))
   return {'ok':True}
  if action=='notification_test':
   authorised(d,uid);notice(d,uid,'Test match reminder: your fixture is ready. This is a notification test only.');return {'ok':True}
  if action.startswith('studio_'):
   authorised(d,uid);version=current(d)
   if action=='studio_save':
    c=validate(b.get('config'));base=b.get('base')
    if base!=version['id']:raise ValueError('Published settings changed. Reload before saving.')
    d.execute('INSERT OR REPLACE INTO gb_draft VALUES(1,?,?)',(base,json.dumps(c)));event(d,'studio',uid,'draft_saved',new=c);return {'ok':True}
   reason=str(b.get('reason','')).strip()
   if not 5<=len(reason)<=300:raise ValueError('Explain this publish or rollback')
   if action=='studio_publish':
    draft=row(d,'SELECT * FROM gb_draft WHERE id=1')
    if not draft or draft['base']!=version['id']:raise ValueError('Save a current draft first')
    config=draft['config'];validate(json.loads(config))
   elif action=='studio_rollback':
    previous=row(d,'SELECT * FROM gb_versions WHERE id=?',(b.get('version'),))
    if not previous:raise ValueError('Version not found')
    old_config=json.loads(previous['config']);restored=dict(DEFAULT,**old_config);restored['theme']=dict(DEFAULT['theme'],**old_config.get('theme',{}));restored['presentation']=dict(DEFAULT['presentation'],**old_config.get('presentation',{}));config=json.dumps(validate(restored))
   else:raise ValueError('Unknown Studio action')
   d.execute('INSERT INTO gb_versions(config,actor,reason,created) VALUES(?,?,?,?)',(config,uid,reason,int(time.time())));d.execute('DELETE FROM gb_draft');event(d,'studio',uid,action,old=json.loads(version['config']),new=json.loads(config),reason=reason);return {'ok':True}
  if action=='qualified_cup':
   authorised(d,uid);name=str(b.get('name','')).strip();game=b.get('game');version=current(d);rules=json.loads(version['config'])
   if not 3<=len(name)<=60 or game not in __import__('gaming').GAMES:raise ValueError('Enter a cup name and supported game')
   from datetime import datetime,timedelta
   from zoneinfo import ZoneInfo
   local=datetime.now(ZoneInfo('Africa/Lagos'));week=int((local-timedelta(days=local.weekday(),hours=local.hour,minutes=local.minute,seconds=local.second,microseconds=local.microsecond)).timestamp())
   opens=weekly(d,game,week,rules);league_candidates=[]
   for l in d.execute("SELECT id FROM leagues WHERE game=? AND format='league' AND state='finished' AND created>? ORDER BY created DESC",(game,int(time.time())-60*86400)):
    league_candidates.extend(__import__('gaming').standings(d,l['id'])[:4])
   selected=[];seen=set()
   for candidates,slots,source in [(league_candidates,rules['league_cup_slots'],'league'),(opens,rules['open_cup_slots'],'weekly_open')]:
    chosen=0
    for player in candidates:
     if chosen>=slots:break
     if player['uid'] in seen:continue
     seen.add(player['uid']);selected.append((player['uid'],source));chosen+=1
    if chosen<slots:raise ValueError('Not enough distinct qualified '+source+' players yet. No unqualified placeholders will be added.')
   lid=uuid.uuid4().hex;now=int(time.time());d.execute("INSERT INTO leagues(id,name,game,owner,created,format,tier,capacity,round_days,verification,policy_snapshot) VALUES(?,?,?,?,?,'cup',0,8,3,'typed',?)",(lid,name,game,uid,now,version['config']))
   d.execute('INSERT INTO gb_qualified_cups VALUES(?,?,?)',(lid,version['id'],week))
   for player,source in selected:d.execute('INSERT INTO gb_cup_eligibility VALUES(?,?,?)',(lid,player,source));notice(d,player,'You qualified for '+name+'. Registration is optional; open the cup to join.')
   event(d,lid,uid,'qualified_cup_created',new={'slots':selected,'version':version['id'],'week':week});return {'id':lid}
  if action=='season_create':
   authorised(d,uid);name=str(b.get('name','')).strip();game=b.get('game');tier=b.get('tier',0);opens=b.get('opens');closes=b.get('closes');version=current(d)
   if not 3<=len(name)<=60 or game not in __import__('gaming').GAMES or type(tier)!=int or not 0<=tier<4 or any(type(v)!=int for v in (opens,closes)) or not time.time()-60<=opens<closes<=time.time()+30*86400:raise ValueError('Enter name, game, division and a future registration window of up to 30 days')
   if d.execute("SELECT COUNT(*) FROM gb_seasons WHERE state IN ('enrolling','review')").fetchone()[0]>=3:raise ValueError('Close an existing registration window first')
   sid=uuid.uuid4().hex;d.execute('INSERT INTO gb_seasons VALUES(?,?,?,?,?,?,?,?,?,?)',(sid,name,game,tier,opens,closes,'enrolling',uid,version['id'],version['config']));event(d,sid,uid,'season_created',new={'name':name,'opens':opens,'closes':closes,'tier':tier})
   for player in d.execute('SELECT uid FROM game_profiles WHERE adult=1'):
    if __import__('gaming').qualification(d,player['uid'],game)==tier:notice(d,player['uid'],'Registration opens for '+name+'. Opt in and register your availability before the deadline.')
   return {'id':sid}
  if action=='season_extend':
   authorised(d,uid);season=row(d,'SELECT * FROM gb_seasons WHERE id=?',(b.get('season'),));closes=b.get('closes');reason=str(b.get('reason','')).strip()
   if not season or season['state'] not in ('enrolling','review') or type(closes)!=int or not time.time()+60<closes<time.time()+30*86400 or len(reason)<10:raise ValueError('Only an unstarted registration window may be extended, with a reason')
   d.execute("UPDATE gb_seasons SET closes=?,state='enrolling' WHERE id=?",(closes,season['id']));event(d,season['id'],uid,'registration_extended',old={'closes':season['closes']},new={'closes':closes},reason=reason)
   for entry in d.execute('SELECT uid FROM gb_season_entries WHERE season=?',(season['id'],)):notice(d,entry['uid'],'Registration deadline changed for '+season['name']+'. '+reason)
   return {'ok':True}
  if action in ('season_register','season_leave'):
   season=row(d,'SELECT * FROM gb_seasons WHERE id=?',(b.get('season'),))
   if not season or season['state']!='enrolling' or not season['opens']<=time.time()<season['closes']:raise ValueError('The season registration window is closed')
   if action=='season_leave':d.execute('DELETE FROM gb_season_availability WHERE season=? AND uid=?',(season['id'],uid));d.execute('DELETE FROM gb_season_entries WHERE season=? AND uid=?',(season['id'],uid));event(d,season['id'],uid,'season_left');return {'ok':True}
   identity=eligible(d,uid,season['game'])
   if not identity:raise ValueError('Register the official game ID before joining a season')
   availability=__import__('match_scheduling').availability(d,uid,season['game'])
   if not availability['dated_windows'] and not any(availability['weekly'].values()):raise ValueError('Save weekly or dated playing availability before joining a season')
   if __import__('gaming').qualification(d,uid,season['game'])!=season['tier']:raise ValueError('This season is for a different qualified division')
   d.execute('INSERT INTO gb_season_availability VALUES(?,?,?) ON CONFLICT(season,uid) DO UPDATE SET snapshot=excluded.snapshot',(season['id'],uid,json.dumps(availability)))
   old=row(d,'SELECT * FROM gb_season_entries WHERE season=? AND uid=?',(season['id'],uid));d.execute('INSERT INTO gb_season_entries VALUES(?,?,?,?,?) ON CONFLICT(season,uid) DO UPDATE SET game_id=excluded.game_id,availability=excluded.availability',(season['id'],uid,identity['game_id'],identity['availability'],int(time.time())));event(d,season['id'],uid,'season_registered',old=old,new={'game_id':identity['game_id']});return {'ok':True}
  if action=='simulate':
   authorised(d,uid);entrants=b.get('entrants');size=b.get('group_size');days=b.get('round_days')
   if any(type(v)!=int for v in (entrants,size,days)) or not 6<=entrants<=100000 or not 6<=size<=16 or not 1<=days<=14:raise ValueError('Simulate 6–100,000 entrants, groups of 6–16, and 1–14 days per round')
   groups=math.ceil(entrants/size);small=entrants//groups;large=small+1;nlarge=entrants%groups;nsmall=groups-nlarge
   if small<6:raise ValueError('Too few players to form groups of at least six; choose a larger group target')
   fixtures=nsmall*small*(small-1)//2+nlarge*large*(large-1)//2;maximum=large if nlarge else small;rounds=maximum if maximum%2 else maximum-1
   return {'entrants':entrants,'groups':groups,'group_distribution':{str(small):nsmall,str(large):nlarge},'fixtures':fixtures,'rounds':rounds,'estimated_days':rounds*days,'note':'Estimate only. Requires mutually available time slots and moderation capacity.'}
  if action=='walkover':
   authorised(d,uid);f=row(d,'SELECT * FROM fixtures WHERE id=?',(b.get('fixture'),));schedule=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(b.get('fixture'),));league=row(d,'SELECT * FROM leagues WHERE id=?',(f['league'],)) if f else None;rules=json.loads(league['policy_snapshot'] or current(d)['config']) if league else DEFAULT;reason=str(b.get('reason','')).strip()
   if not f or f['stage']!='league' or uid in (f['a'],f['b']) or f['state'] in ('confirmed','void','walkover') or not schedule or not schedule['scheduled'] or time.time()<=schedule['scheduled']+rules['checkin_seconds'] or len(reason)<10:raise PermissionError('An independent administrator may review a documented no-show only after the check-in deadline')
   if schedule['ready_a'] and schedule['ready_b']:raise ValueError('Both players checked in. This is not a no-show')
   winner=f['a'] if schedule['ready_a'] else f['b'] if schedule['ready_b'] else None
   d.execute('INSERT INTO gb_walkovers VALUES(?,?,?,?,?)',(f['id'],winner,reason,uid,int(time.time())))
   d.execute('UPDATE fixtures SET state=? WHERE id=?',('walkover' if winner else 'void',f['id']));event(d,f['id'],uid,'walkover_reviewed',old=schedule,new={'winner':winner,'no_rating_change':True},reason=reason);return {'ok':True}
  if action=='identity':return __import__('game_identities').save(d,uid,b)
  if action=='invite':
   game=b.get('game');other=row(d,'SELECT id,name FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(b.get('identity'),str(b.get('identity','')).lstrip('@')))
   if not other or other['id']==uid:raise ValueError('Choose another registered player')
   import social
   social.ensure(d,uid,other['id'])
   a=eligible(d,uid,game);z=eligible(d,other['id'],game)
   if not a or not z:raise ValueError('Both players must register an official ID for this game')
   ap=(__import__('game_identities').meta(d,uid,game) or {}).get('platform','unspecified');bp=(__import__('game_identities').meta(d,other['id'],game) or {}).get('platform','unspecified')
   if not __import__('sponsored_leagues').compatible(ap,bp):raise ValueError('Choose a player with a compatible gaming platform')
   if a['game_id'].casefold()==z['game_id'].casefold():raise ValueError('Players need different official game IDs')
   if a['region']!=z['region']:raise ValueError('Choose a player in the same game region')
   if d.execute("SELECT 1 FROM gb_matches WHERE (a IN (?,?) OR b IN (?,?)) AND state NOT IN ('verified','cancelled')",(uid,other['id'],uid,other['id'])).fetchone():raise ValueError('A player already has an active invitation or match')
   version=current(d);rules=json.loads(version['config']);now=int(time.time())
   if d.execute('SELECT COUNT(*) FROM gb_events WHERE actor=? AND action=? AND created>?',(uid,'game_invited',now-3600)).fetchone()[0]>=10:raise ValueError('Invitation limit reached. Try again later')
   if d.execute("SELECT COUNT(*) FROM gb_matches WHERE id IN (SELECT match FROM gb_match_origins WHERE global_ranking_eligible=1) AND game=? AND state='verified' AND created>? AND ((a=? AND b=?) OR (a=? AND b=?))",(game,now-86400,uid,other['id'],other['id'],uid)).fetchone()[0]>=rules['max_pair_daily']:raise ValueError('Daily rated matches against this opponent reached')
   mid=uuid.uuid4().hex;d.execute('INSERT INTO gb_matches(id,game,a,b,gid_a,gid_b,state,created,deadline,version,rules,accepted_a) VALUES(?,?,?,?,?,?,?,?,?,?,?,1)',(mid,game,uid,other['id'],a['game_id'],z['game_id'],'proposed',now,now+rules['accept_seconds'],version['id'],json.dumps(rules)))
   d.execute('DELETE FROM gb_queue WHERE uid IN (?,?)',(uid,other['id']));name=row(d,'SELECT name FROM users WHERE id=?',(uid,))['name'];notice(d,other['id'],name+' invited you to '+__import__('gaming').GAMES[game]+'. Open Gamebox → Find a match to accept or decline.');event(d,mid,uid,'game_invited',new={'recipient':other['id'],'game':game});return {'match':mid}
  if action=='queue':
   game=b.get('game');identity=eligible(d,uid,game)
   if not identity:raise ValueError('Register your official ID for this game first')
   if d.execute("SELECT 1 FROM gb_matches WHERE (a=? OR b=?) AND state NOT IN ('verified','cancelled')",(uid,uid)).fetchone():raise ValueError('Finish your active match first')
   d.execute('INSERT OR IGNORE INTO gb_queue VALUES(?,?,?,0,?)',(uid,game,identity['region'],int(time.time())));return {'match':pair(d,game,identity['region'])}
  if action=='queue_leave':d.execute('DELETE FROM gb_queue WHERE uid=?',(uid,));return {'ok':True}
  if action=='notices_read':d.execute('UPDATE gb_notices SET seen=1 WHERE uid=?',(uid,));return {'ok':True}
  if action=='sanction':
   authorised(d,uid);target=str(b.get('uid',''));game=b.get('game');reason=str(b.get('reason','')).strip();until=b.get('until')
   if not d.execute('SELECT 1 FROM game_profiles WHERE uid=?',(target,)).fetchone() or game not in __import__('gaming').GAMES or type(until)!=int or not int(time.time())<=until<=time.time()+30*86400 or len(reason)<5:raise ValueError('Choose player, game, expiry (up to 30 days) and reason')
   old=row(d,'SELECT * FROM gb_sanctions WHERE uid=? AND game=?',(target,game));d.execute('INSERT OR REPLACE INTO gb_sanctions VALUES(?,?,?,?)',(target,game,until,reason));d.execute('DELETE FROM gb_queue WHERE uid=?',(target,));event(d,'sanction',uid,'sanction_updated',old=old,new=b,reason=reason);notice(d,target,'Gaming eligibility changed: '+reason);return {'ok':True}
  if action=='review':
   authorised(d,uid);m=row(d,'SELECT * FROM gb_matches WHERE id=?',(b.get('match'),))
   if not m or uid in (m['a'],m['b']) or m['state'] not in ('review','disputed'):raise PermissionError('Only an independent administrator may review this unresolved match')
   if not d.execute('SELECT 1 FROM gb_evidence WHERE match=? AND image IS NOT NULL',(m['id'],)).fetchone() and not d.execute('SELECT 1 FROM result_review_videos WHERE kind=\'open\' AND match_id=? AND video IS NOT NULL',(m['id'],)).fetchone():raise ValueError('Evidence is required for review')
   __import__('result_reviews').require_both(d,dict(m,kind='open'))
   reason=str(b.get('reason','')).strip();a,z=b.get('a'),b.get('b')
   if len(reason)<10 or any(type(v)!=int or not 0<=v<=99 for v in (a,z)):raise ValueError('Enter scores and a reason')
   verify(d,m,a,z,uid,reason);return {'ok':True}
  if action=='fixture_checkin':
   f=row(d,'SELECT * FROM fixtures WHERE id=?',(b.get('fixture'),))
   if not f or uid not in (f['a'],f['b']):raise PermissionError('Only these opponents may check in')
   if f['state'] in ('confirmed','void','walkover'):raise ValueError('This fixture is closed')
   side='a' if uid==f['a'] else 'b';scheduled=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(f['id'],));league=row(d,'SELECT * FROM leagues WHERE id=?',(f['league'],));rules=json.loads(league['policy_snapshot'] or current(d)['config'])
   if not scheduled or not scheduled['scheduled'] or not scheduled['scheduled']-rules['checkin_seconds']<=time.time()<=scheduled['scheduled']+rules['checkin_seconds']:raise ValueError('Check in near the mutually scheduled time')
   d.execute('UPDATE gb_schedule SET ready_'+side+'=1 WHERE fixture=?',(f['id'],));event(d,f['id'],uid,'fixture_checked_in');return {'ok':True}
  m=participant(d,uid,b.get('match'));side='a' if uid==m['a'] else 'b';rules=json.loads(m['rules'])
  if action=='accept':
   if m['state']!='proposed' or time.time()>m['deadline']:raise ValueError('The acceptance window is closed')
   d.execute('UPDATE gb_matches SET accepted_'+side+'=1 WHERE id=?',(m['id'],));updated=row(d,'SELECT * FROM gb_matches WHERE id=?',(m['id'],))
   if updated['accepted_a'] and updated['accepted_b']:
    d.execute("UPDATE gb_matches SET state='awaiting_checkin',deadline=? WHERE id=?",(int(time.time())+rules['checkin_seconds'],m['id']))
    for player in (m['a'],m['b']):notice(d,player,'Game invitation accepted. Open Find a match and check in when ready.')
  elif action=='checkin':
   scheduled=row(d,'SELECT * FROM gb_open_schedule WHERE fixture=?',(m['id'],))
   if scheduled and scheduled['scheduled'] and not scheduled['scheduled']-rules['checkin_seconds']<=time.time()<=scheduled['scheduled']+rules['checkin_seconds']:raise ValueError('Check in near the agreed kickoff')
   if scheduled:d.execute('UPDATE gb_open_schedule SET ready_'+side+'=1 WHERE fixture=?',(m['id'],))
   if m['state']!='awaiting_checkin' or time.time()>m['deadline']:raise ValueError('Check-in is closed')
   d.execute('UPDATE gb_matches SET ready_'+side+'=1 WHERE id=?',(m['id'],));updated=row(d,'SELECT * FROM gb_matches WHERE id=?',(m['id'],))
   if updated['ready_a'] and updated['ready_b']:d.execute("UPDATE gb_matches SET state='in_progress',deadline=? WHERE id=?",(int(time.time())+4*3600,m['id']))
  elif action=='complete':
   if m['state']!='in_progress':raise ValueError('The match has not started')
   d.execute("UPDATE gb_matches SET state='awaiting_results',deadline=? WHERE id=?",(int(time.time())+rules['result_seconds'],m['id']))
   for u in (m['a'],m['b']):notice(d,u,'Do not close the game result screen until the result is confirmed. Keep both gaming IDs and the score visible. Disputes may require camera photo/video proof; the evidence response deadline is 15 minutes.')
  elif action=='report':
   if __import__('result_reviews').active(d,dict(m,kind='open')):raise ValueError('Private evidence is awaiting review; original reports are locked')
   previous=row(d,'SELECT * FROM gb_reports WHERE match=? AND uid=?',(m['id'],uid))
   if previous and (previous['a'],previous['b'])==(b.get('a'),b.get('b')):return {'ok':True,'already_submitted':True}
   if m['state']!='awaiting_results' or time.time()>m['deadline']:raise ValueError('This result needs review; the submission window is closed')
   a,z=b.get('a'),b.get('b')
   if any(type(v)!=int or not 0<=v<=99 for v in (a,z)):raise ValueError('Enter whole-number scores')
   old=row(d,'SELECT * FROM gb_reports WHERE match=? AND uid=?',(m['id'],uid))
   if old:raise ValueError('Your independent report is already submitted')
   d.execute('INSERT INTO gb_reports VALUES(?,?,?,?)',(m['id'],uid,a,z));reports=[dict(r) for r in d.execute('SELECT * FROM gb_reports WHERE match=?',(m['id'],))]
   if len(reports)==2:
    if (reports[0]['a'],reports[0]['b'])==(reports[1]['a'],reports[1]['b']):verify(d,m,a,z,uid)
    else:
     d.execute("UPDATE gb_matches SET state='disputed',deadline=? WHERE id=?",(int(time.time())+rules['evidence_seconds'],m['id']))
     for u in (m['a'],m['b']):notice(d,u,'Scores disagree. Both players may submit screenshots showing final score and both gaming IDs.')
  elif action=='evidence':
   if m['state'] not in ('disputed','review'):raise ValueError('Evidence is collected for disputed or reviewed matches')
   import gaming
   raw,mime=gaming.image(b);digest=hashlib.sha256(raw).hexdigest();other=d.execute('SELECT 1 FROM gb_evidence WHERE digest=? AND (match!=? OR uid!=?)',(digest,m['id'],uid)).fetchone()
   if other:raise ValueError('This evidence was already used')
   if d.execute('SELECT 1 FROM gb_evidence WHERE match=? AND uid=?',(m['id'],uid)).fetchone():raise ValueError('Original evidence cannot be overwritten')
   d.execute('INSERT INTO gb_evidence VALUES(?,?,?,?,?,?,NULL)',(m['id'],uid,raw,mime,digest,str(b.get('reading',''))[:6000]))
  elif action=='comment':
   text=str(b.get('text','')).strip()
   if not 1<=len(text)<=1000:raise ValueError('Message must be under 1000 characters')
   d.execute('INSERT INTO gb_room_messages(match,uid,text,created) VALUES(?,?,?,?)',(m['id'],uid,text,int(time.time())))
  elif action=='cancel':
   if m['state'] not in ('proposed','awaiting_checkin'):raise ValueError('Active matches cannot be silently cancelled')
   d.execute("UPDATE gb_matches SET state='cancelled' WHERE id=?",(m['id'],))
   notice(d,m['b'] if side=='a' else m['a'],'Game invitation declined or cancelled. No score or rating changed.')
   __import__('sponsored_leagues').cancelled(d,m,int(time.time()),uid)
   if __import__('competition_context').is_global(d,m['id']) and d.execute("SELECT 1 FROM gb_events WHERE match=? AND action='match_proposed'",(m['id'],)).fetchone():
    other=m['b'] if side=='a' else m['a'];identity=row(d,'SELECT * FROM gb_game_ids WHERE uid=? AND game=?',(other,m['game']));low,high=sorted((uid,other));d.execute('INSERT OR REPLACE INTO gb_match_cooldowns VALUES(?,?,?,?)',(m['game'],low,high,int(time.time())+300))
    if identity:d.execute('INSERT OR IGNORE INTO gb_queue VALUES(?,?,?,1,?)',(other,m['game'],identity['region'],int(time.time())))
  else:raise ValueError('Unknown match action')
  event(d,m['id'],uid,action,old={'state':m['state']},new={k:v for k,v in b.items() if k not in ('image','reading')});return {'ok':True}

def tick(server,now=None):
 now=int(time.time()) if now is None else now
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  d.execute('DELETE FROM game_stream_signals WHERE room IN (SELECT id FROM game_stream_rooms WHERE created<?)',(now-7200,));d.execute('DELETE FROM game_stream_rooms WHERE created<?',(now-7200,))
  for finished in d.execute("SELECT s.id FROM gb_seasons s WHERE s.state='active' AND EXISTS(SELECT 1 FROM gb_season_groups g WHERE g.season=s.id) AND NOT EXISTS(SELECT 1 FROM gb_season_groups g JOIN leagues l ON l.id=g.league WHERE g.season=s.id AND l.state!='finished')").fetchall():d.execute("UPDATE gb_seasons SET state='finished' WHERE id=?",(finished['id'],));event(d,finished['id'],'system','season_completed')
  for season in [dict(r) for r in d.execute("SELECT * FROM gb_seasons WHERE state='enrolling' AND closes<=?",(now,))]:
   entries=[dict(r) for r in d.execute('SELECT e.*,COALESCE(r.rating,1500) rating FROM gb_season_entries e LEFT JOIN gb_ratings r ON r.uid=e.uid AND r.game=? WHERE season=? ORDER BY rating DESC,e.registered,e.uid',(season['game'],season['id']))]
   rules=json.loads(season['rules']);size=rules['group_size'];groups=math.ceil(len(entries)/size) if entries else 0
   conflict=any(d.execute('SELECT 1 FROM gb_sanctions WHERE uid=? AND game=? AND until>?',(e['uid'],season['game'],now)).fetchone() or d.execute("SELECT 1 FROM league_members m JOIN leagues l ON l.id=m.league WHERE m.uid=? AND l.game=? AND l.state IN ('active','finals') AND l.format='league'",(e['uid'],season['game'])).fetchone() or __import__('gaming').qualification(d,e['uid'],season['game'])!=season['tier'] for e in entries)
   if not groups or len(entries)//groups<6 or conflict:
    d.execute("UPDATE gb_seasons SET state='review' WHERE id=?",(season['id'],));event(d,season['id'],'system','registration_needs_review',new={'entrants':len(entries),'active_conflict':conflict},reason='Too few eligible entrants or an active league conflict; no opponents substituted')
    notice(d,season['owner'],'Season registration needs review: '+season['name']);continue
   small=len(entries)//groups;extra=len(entries)%groups;offset=0
   for group in range(groups):
    members=entries[offset:offset+small+(1 if group<extra else 0)];offset+=len(members);lid=uuid.uuid4().hex
    d.execute("INSERT INTO leagues(id,name,game,owner,created,format,tier,capacity,round_days,verification,policy_snapshot,state) VALUES(?,?,?,?,?,'league',?,?,?,'typed',?,'active')",(lid,season['name']+' · Group '+str(group+1),season['game'],season['owner'],now,season['tier'],len(members),rules['round_days'],season['rules']))
    d.execute('INSERT INTO gb_season_groups VALUES(?,?,?)',(season['id'],lid,group+1))
    ids=[]
    for slot,member in enumerate(members,1):d.execute('INSERT INTO league_members(league,uid,game_id,slot) VALUES(?,?,?,?)',(lid,member['uid'],member['game_id'],slot));ids.append(member['uid']);notice(d,member['uid'],'Season group and fixtures are ready: '+season['name']+' · Group '+str(group+1))
    if len(ids)%2:ids.append(None)
    for round_index in range(len(ids)-1):
     for pair_index in range(len(ids)//2):
      a,b=ids[pair_index],ids[-1-pair_index]
      if a and b:d.execute('INSERT INTO fixtures(id,league,round,a,b,opens,due) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,lid,round_index+1,a,b,now+round_index*rules['round_days']*86400,now+(round_index+1)*rules['round_days']*86400))
     ids=[ids[0],ids[-1],*ids[1:-1]]
   d.execute("UPDATE gb_seasons SET state='active' WHERE id=?",(season['id'],));event(d,season['id'],'system','season_groups_generated',new={'entrants':len(entries),'groups':groups})
  for m in [dict(r) for r in d.execute("SELECT * FROM gb_matches WHERE deadline<? AND state IN ('proposed','awaiting_checkin','in_progress','awaiting_results')",(now,))]:
   if m['state'] in ('in_progress','awaiting_results'):
    d.execute("UPDATE gb_matches SET state='review',deadline=? WHERE id=?",(now+json.loads(m['rules'])['evidence_seconds'],m['id']))
    for u in (m['a'],m['b']):notice(d,u,'Result deadline reached. Review is required; silence does not award a win.')
   else:
    d.execute("UPDATE gb_matches SET state='cancelled' WHERE id=?",(m['id'],))
    for side in ('a','b'):
     u=m[side];ready=m['ready_'+side] if m['state']=='awaiting_checkin' else m['accepted_'+side]
     notice(d,u,'Match proposal expired. No rating change.')
     if ready:
      identity=row(d,'SELECT * FROM gb_game_ids WHERE uid=? AND game=?',(u,m['game']))
      if identity and __import__('competition_context').is_global(d,m['id']):d.execute('INSERT OR IGNORE INTO gb_queue VALUES(?,?,?,1,?)',(u,m['game'],identity['region'],now))
   if m['state'] in ('proposed','awaiting_checkin'):__import__('sponsored_leagues').cancelled(d,m,now)
   event(d,m['id'],'system','deadline_processed',old=m['state'],new='review' if m['state'] in ('in_progress','awaiting_results') else 'cancelled')
  for group in d.execute('SELECT DISTINCT game,region FROM gb_queue').fetchall():pair(d,group['game'],group['region'])
  for pending in [dict(r) for r in d.execute("SELECT f.id,f.a,f.b,l.policy_snapshot,MIN(a.time) submitted FROM fixtures f JOIN leagues l ON l.id=f.league JOIN game_audit a ON a.fixture=f.id AND a.action='submitted' WHERE f.state='pending' AND l.verification='typed' GROUP BY f.id")]:
   rules=json.loads(pending['policy_snapshot'] or current(d)['config'])
   if pending['submitted']+rules['result_seconds']<now:
    d.execute("UPDATE fixtures SET state='disputed' WHERE id=?",(pending['id'],));event(d,pending['id'],'system','competition_submission_expired',reason='Silence is not proof; evidence and independent review required')
    for u in (pending['a'],pending['b']):notice(d,u,'League score response deadline passed. Both players may supply evidence for review.')
  for expired_fixture in [dict(r) for r in d.execute("SELECT r.fixture FROM gb_comp_retention r JOIN fixtures f ON f.id=r.fixture WHERE r.expires<? AND f.state='confirmed'",(now,))]:
   d.execute('UPDATE game_reports SET image=NULL WHERE fixture=?',(expired_fixture['fixture'],));d.execute('DELETE FROM gb_comp_retention WHERE fixture=?',(expired_fixture['fixture'],));event(d,expired_fixture['fixture'],'system','ordinary_competition_evidence_expired')
  expired=[dict(r) for r in d.execute('SELECT e.match,e.uid FROM gb_evidence e JOIN gb_matches m ON m.id=e.match WHERE e.image IS NOT NULL AND e.expires<? AND m.state=\'verified\'',(now,))]
  for e in expired:d.execute('UPDATE gb_evidence SET image=NULL WHERE match=? AND uid=?',(e['match'],e['uid']));event(d,e['match'],'system','ordinary_evidence_expired',new={'uid':e['uid']})

def rate_competition_results(d,league):
 for f in [dict(r) for r in d.execute("SELECT * FROM fixtures WHERE league=? AND state='confirmed' AND id NOT IN (SELECT fixture FROM gb_rating_events)",(league['id'],))]:
  awarded=__import__('rankings').award(d,'fixture',f);old=awarded['old'] if awarded else {}
  d.execute('INSERT OR IGNORE INTO gb_comp_retention VALUES(?,?)',(f['id'],int(time.time())+json.loads(league['policy_snapshot'] or current(d)['config'])['retention_seconds']));d.execute('INSERT INTO gb_rating_events VALUES(?,?)',(f['id'],int(time.time())));event(d,f['id'],'system','competition_rating_updated',old=old,reason='Confirmed played result; no walkover rating')

def dispatch_notices(server):
 if not getattr(server.push,'enabled',False):return
 pending=[];now=int(time.time())
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  for n in [dict(r) for r in d.execute('SELECT n.* FROM gb_notices n LEFT JOIN gb_notice_delivery p ON p.id=n.id WHERE n.seen=0 AND n.created>? AND COALESCE(p.delivered,0)=0 AND COALESCE(p.attempts,0)<3 AND COALESCE(p.next_attempt,0)<=? ORDER BY n.id LIMIT 20',(now-3600,now))]:
   if not __import__('match_scheduling').valid_notice(d,n,now):continue
   n=__import__('match_scheduling').public_notice(d,n)
   targets=[r[0] for r in d.execute('SELECT token FROM push_devices p JOIN sessions s ON s.token_hash=p.session_hash AND s.user_id=p.user_id WHERE p.user_id=?',(n['uid'],))]
   if not targets:continue
   d.execute('INSERT INTO gb_notice_delivery(id,attempts,next_attempt) VALUES(?,1,?) ON CONFLICT(id) DO UPDATE SET attempts=attempts+1,next_attempt=excluded.next_attempt',(n['id'],now+300));pending.append((n,targets))
 if not pending:return
 def send():
  for n,targets in pending:
   success=False
   for token in targets:
    try:
     with server.db() as check:
      if not __import__('match_scheduling').valid_notice(check,n):continue
     server.push.send(token,{'event':'gamebox_notice','notice_id':str(n['id']),'recipient':n['uid'],'expires_at':str(min(n.get('expires',now+600),now+600))});success=True
    except Exception as error:print('Gamebox notice push failed: '+type(error).__name__,flush=True)
   if success:
    with server.db() as d:d.execute('UPDATE gb_notice_delivery SET delivered=1 WHERE id=?',(n['id'],))
 import threading
 threading.Thread(target=send,daemon=True).start()

def weekly(d,game,week,rules):
 players={}
 for match in d.execute("SELECT * FROM gb_matches WHERE id IN (SELECT match FROM gb_match_origins WHERE global_ranking_eligible=1) AND game=? AND state='verified' AND verified>=?",(game,week)):
  for uid,opponent,own,other in [(match['a'],match['b'],match['score_a'],match['score_b']),(match['b'],match['a'],match['score_b'],match['score_a'])]:
   if uid not in players:players[uid]={'uid':uid,'matches':0,'wins':0,'points':0,'opponents':set()}
   player=players[uid];player['matches']+=1;player['wins']+=own>other;player['points']+=3 if own>other else 1 if own==other else 0;player['opponents'].add(opponent)
 return sorted([p|{'opponents':len(p['opponents'])} for p in players.values() if p['matches']>=rules['weekly_min_matches'] and len(p['opponents'])>=rules['weekly_min_opponents']],key=lambda p:(-p['points'],-p['wins'],p['uid']))

def result_participant(d,uid,rid):
 match=row(d,'SELECT * FROM gb_matches WHERE id=?',(rid,))
 kind='open'
 if not match:match=row(d,'SELECT * FROM fixtures WHERE id=?',(rid,));kind='fixture'
 if not match or not match['a'] or not match['b'] or uid not in (match['a'],match['b']):raise PermissionError('Only the two assigned match players may enter the result chat')
 return match|{'kind':kind}

def result_state(server,uid,rid,after):
 with server.db() as d:
  m=result_participant(d,uid,rid)
  if m['kind']=='open':reports=[dict(r) for r in d.execute('SELECT uid,a score_a,b score_b FROM gb_reports WHERE match=?',(rid,))];verification='typed'
  else:
   reports=[dict(r) for r in d.execute('SELECT uid,score_a,score_b FROM game_reports WHERE fixture=?',(rid,))];verification=row(d,'SELECT verification FROM leagues WHERE id=?',(m['league'],))['verification']
  if not any(r['uid']==uid for r in reports):reports=[]
  names={u:row(d,'SELECT name FROM users WHERE id=?',(u,))['name'] for u in (m['a'],m['b'])}
  game_ids={m['a']:m['gid_a'],m['b']:m['gid_b']} if m['kind']=='open' else {r['uid']:r['game_id'] for r in d.execute('SELECT uid,game_id FROM league_members WHERE league=? AND uid IN (?,?)',(m['league'],m['a'],m['b']))}
  signals=[dict(r)|{'payload':json.loads(r['payload'])} for r in d.execute('SELECT id,kind,payload FROM gb_result_signals WHERE room=? AND uid!=? AND id>? AND created>? ORDER BY id LIMIT 300',(rid,uid,after,int(time.time())-1800))]
  comments=[dict(r) for r in d.execute('SELECT c.id,c.text,u.name FROM gb_result_comments c JOIN users u ON u.id=c.uid WHERE c.room=? ORDER BY c.id DESC LIMIT 100',(rid,))]
  schedule=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(rid,)) if m['kind']=='fixture' else None
  can_report=(m['state']=='awaiting_results') if m['kind']=='open' else (m['state'] not in ('confirmed','void','walkover','disputed') and time.time()>=m['opens'] and (verification=='legacy' or bool(schedule and schedule['ready_a'] and schedule['ready_b'])))
  review=__import__('result_reviews').status(d,m,uid)
  if review['state']!='not_submitted':reports=[r for r in reports if r['uid']==uid]
  return {'game_ids':game_ids,'can_report':can_report,'id':rid,'kind':m['kind'],'a':m['a'],'b':m['b'],'names':names,'state':m['state'],'verification':verification,'reports':reports,'evidence_review':review,'final_score':[m['score_a'],m['score_b']] if m['state'] in ('verified','confirmed') else None,'signals':signals,'comments':list(reversed(comments))}
