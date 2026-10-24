"""Gamebox pilot: account-bound competitions and auditable match results."""
import base64,hashlib,json,re,time,uuid,subprocess
from pathlib import Path
TIERS=["Open","Division 2","Division 3","Premier"]
BUILTIN_GAMES={'efootball':'eFootball','fc_mobile':'EA FC Mobile','codm':'CODM 1v1'}
GAMES=dict(BUILTIN_GAMES)
def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS game_stream_responses(room TEXT,uid TEXT,state TEXT,PRIMARY KEY(room,uid));
 CREATE TABLE IF NOT EXISTS game_stream_members(room TEXT,uid TEXT,PRIMARY KEY(room,uid));
 CREATE TABLE IF NOT EXISTS game_stream_comments(id INTEGER PRIMARY KEY,room TEXT,uid TEXT,text TEXT,created INTEGER);
 CREATE TABLE IF NOT EXISTS game_stream_likes(room TEXT,uid TEXT,PRIMARY KEY(room,uid));
 CREATE TABLE IF NOT EXISTS game_stream_rooms(id TEXT PRIMARY KEY,a TEXT,b TEXT,created INTEGER);
 CREATE TABLE IF NOT EXISTS game_stream_signals(id INTEGER PRIMARY KEY,room TEXT,sender TEXT,kind TEXT,payload TEXT,time INTEGER);
 CREATE TABLE IF NOT EXISTS game_admin(uid TEXT PRIMARY KEY);
 CREATE TABLE IF NOT EXISTS game_profiles(uid TEXT PRIMARY KEY,tag TEXT NOT NULL,game_id TEXT NOT NULL,handle TEXT NOT NULL DEFAULT '',feature INTEGER NOT NULL DEFAULT 0,adult INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS leagues(id TEXT PRIMARY KEY,name TEXT NOT NULL,game TEXT NOT NULL,owner TEXT NOT NULL,state TEXT NOT NULL DEFAULT 'enrolling',created INTEGER NOT NULL,sponsor TEXT NOT NULL DEFAULT '',sponsor_url TEXT NOT NULL DEFAULT '',reward TEXT NOT NULL DEFAULT 'Recognition and winner feature; no cash prize',champion TEXT);
 CREATE TABLE IF NOT EXISTS league_members(league TEXT,uid TEXT,game_id TEXT NOT NULL DEFAULT '',PRIMARY KEY(league,uid));
 CREATE TABLE IF NOT EXISTS game_moderators(league TEXT,uid TEXT,PRIMARY KEY(league,uid));
 CREATE TABLE IF NOT EXISTS fixtures(id TEXT PRIMARY KEY,league TEXT,round INTEGER,a TEXT,b TEXT,opens INTEGER,due INTEGER,state TEXT DEFAULT 'scheduled',score_a INTEGER,score_b INTEGER,stage TEXT DEFAULT 'league');
 CREATE TABLE IF NOT EXISTS game_reports(fixture TEXT,uid TEXT,score_a INTEGER,score_b INTEGER,image BLOB,mime TEXT,digest TEXT UNIQUE,ocr TEXT,PRIMARY KEY(fixture,uid));
 CREATE TABLE IF NOT EXISTS game_comments(id INTEGER PRIMARY KEY,fixture TEXT,uid TEXT,text TEXT,time INTEGER);
 CREATE TABLE IF NOT EXISTS game_qualification(uid TEXT,game TEXT,tier INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(uid,game));
 CREATE TABLE IF NOT EXISTS game_promotions(league TEXT,uid TEXT,old_tier INTEGER,new_tier INTEGER,PRIMARY KEY(league,uid));
 CREATE TABLE IF NOT EXISTS game_audit(id INTEGER PRIMARY KEY,fixture TEXT,actor TEXT,action TEXT,details TEXT,time INTEGER);
 ''')
 with server.db() as d:
  if 'game_id' not in {r[1] for r in d.execute('PRAGMA table_info(league_members)')}:d.execute("ALTER TABLE league_members ADD COLUMN game_id TEXT NOT NULL DEFAULT ''")
  admin_file=server.data/'admin_account.txt'
  if admin_file.exists():
   target=admin_file.read_text().strip()
   if not d.execute('SELECT 1 FROM users WHERE id=?',(target,)).fetchone():raise ValueError('Configured administrator account does not exist')
   d.execute('DELETE FROM game_admin');d.execute('INSERT INTO game_admin VALUES(?)',(target,))
  if 'policy_snapshot' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute("ALTER TABLE leagues ADD COLUMN policy_snapshot TEXT NOT NULL DEFAULT ''")
  if 'verification' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute("ALTER TABLE leagues ADD COLUMN verification TEXT NOT NULL DEFAULT 'legacy'")
  if 'capacity' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute('ALTER TABLE leagues ADD COLUMN capacity INTEGER NOT NULL DEFAULT 8')
  if 'round_days' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute('ALTER TABLE leagues ADD COLUMN round_days INTEGER NOT NULL DEFAULT 4')
  if 'tier' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute('ALTER TABLE leagues ADD COLUMN tier INTEGER NOT NULL DEFAULT 0')
  if 'hidden' not in {r[1] for r in d.execute('PRAGMA table_info(game_comments)')}:d.execute('ALTER TABLE game_comments ADD COLUMN hidden INTEGER NOT NULL DEFAULT 0')
  if 'format' not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute("ALTER TABLE leagues ADD COLUMN format TEXT NOT NULL DEFAULT 'league'")
  for name in ('sponsor_art','sponsor_week'):
   if name not in {r[1] for r in d.execute('PRAGMA table_info(leagues)')}:d.execute('ALTER TABLE leagues ADD COLUMN '+name+" TEXT NOT NULL DEFAULT ''")
  if 'slot' not in {r[1] for r in d.execute('PRAGMA table_info(league_members)')}:
   d.execute('ALTER TABLE league_members ADD COLUMN slot INTEGER')
   for league in d.execute('SELECT id FROM leagues').fetchall():
    for slot,member in enumerate(d.execute('SELECT uid FROM league_members WHERE league=? ORDER BY rowid',(league[0],)).fetchall(),1):d.execute('UPDATE league_members SET slot=? WHERE league=? AND uid=?',(slot,league[0],member[0]))
  d.execute("CREATE UNIQUE INDEX IF NOT EXISTS league_game_identity ON league_members(league,game_id COLLATE NOCASE) WHERE game_id!=''")
 import gamebox_core
 gamebox_core.init(server)
 __import__("game_identities").init(server)
 __import__("rankings").init(server);__import__('match_scheduling').init(server)
 __import__('match_streams').init(server)
 __import__('result_reviews').init(server)

def row(d,sql,args=()):
 r=d.execute(sql,args).fetchone();return dict(r) if r else None
def admin(d,uid):return bool(d.execute('SELECT 1 FROM game_admin WHERE uid=?',(uid,)).fetchone())
def mod(d,l,uid):return admin(d,uid)
def audit(d,f,uid,action,details=''):d.execute('INSERT INTO game_audit(fixture,actor,action,details,time) VALUES(?,?,?,?,?)',(f,uid,action,details,int(time.time())))
def standings(d,l):
 people=[dict(r)|{'played':0,'wins':0,'draws':0,'losses':0,'gf':0,'ga':0,'points':0} for r in d.execute('SELECT p.uid,p.tag,p.handle,p.feature FROM game_profiles p JOIN league_members m ON m.uid=p.uid WHERE m.league=?',(l,))];lookup={r['uid']:r for r in people}
 for r in people:
  if not r['feature']:r['handle']=''
 fmt=row(d,'SELECT format FROM leagues WHERE id=?',(l,))['format']
 for f in d.execute("SELECT * FROM fixtures WHERE league=? AND state IN ('confirmed','walkover') AND (?='cup' OR stage='league')",(l,fmt)):
  if f['state']=='walkover':
   winner=row(d,'SELECT winner FROM gb_walkovers WHERE fixture=?',(f['id'],))['winner'];lookup[winner]['points']+=3;lookup[winner]['wins']+=1;continue
  for uid,own,other in ((f['a'],f['score_a'],f['score_b']),(f['b'],f['score_b'],f['score_a'])):
   r=lookup[uid];r['played']+=1;r['gf']+=own;r['ga']+=other;r['wins']+=own>other;r['draws']+=own==other;r['losses']+=own<other;r['points']+=3 if own>other else 1 if own==other else 0
 return sorted(people,key=lambda r:(-r['points'],-(r['gf']-r['ga']),-r['gf'],-r['wins'],r['tag'].lower(),r['uid']))
def summary(server,uid,lid=None):
 with server.db() as d:
  import gamebox_core
  gamebox_core.current(d)
  profile=row(d,'SELECT * FROM game_profiles WHERE uid=?',(uid,));leagues=[dict(r) for r in d.execute('SELECT * FROM leagues ORDER BY created DESC')];result={'stream_rooms':[dict(r) for r in d.execute('SELECT id,a,b,created FROM game_stream_rooms WHERE (a=? OR b=? OR id IN (SELECT room FROM game_stream_members WHERE uid=?)) AND created>? ORDER BY created DESC',(uid,uid,uid,int(time.time())-7200))],'can_admin':admin(d,uid),'profile':profile,'leagues':leagues,'games':GAMES,'champions':[],'stats':counters(d),'player_stats':playerstats(d,uid),'stream_viewers':__import__('stream_lifecycle').total(d,uid),'tiers':TIERS,'qualification':{game:qualification(d,uid,game) for game in GAMES}}
  for room in result['stream_rooms']:
   room['players']=[{'id':pid,'name':row(d,'SELECT name FROM users WHERE id=?',(pid,))['name']} for pid in (room['a'],room['b'])]
   response=row(d,'SELECT state FROM game_stream_responses WHERE room=? AND uid=?',(room['id'],uid));room['invitation']=response['state'] if response else ('accepted' if uid==room['a'] else 'invited')
  result['stream_rooms']=[r for r in result['stream_rooms'] if r['invitation']!='declined']
  visible_rooms=[]
  for room in result['stream_rooms']:
   try:
    __import__('social').ensure(d,uid,room['a'])
    if __import__('match_streams').linked(d,room['id']):
     link=__import__('match_streams').linked(d,room['id']);m=__import__('match_streams').match(d,link['kind'],link['match_id'])
     for player in (m['a'],m['b']):__import__('social').ensure(d,uid,player)
     # A pending public room is the host's setup, not another invitation for
     # the already matched opponent. Other people discover it only once live.
     if uid!=room['a'] and not d.execute('SELECT 1 FROM game_stream_members WHERE room=? AND uid=?',(room['id'],uid)).fetchone():continue
    visible_rooms.append(__import__('match_streams').describe(d,server,uid,room))
   except PermissionError:continue
  result['stream_rooms']=visible_rooms
  for l in leagues:
   if l['champion']:
    p=row(d,'SELECT uid,tag,handle,feature FROM game_profiles WHERE uid=?',(l['champion'],))
    if p and p['feature']:result['champions'].append(p|{'league':l['name'],'league_id':l['id'],'game':GAMES[l['game']]})
  if lid:
   l=row(d,'SELECT * FROM leagues WHERE id=?',(lid,))
   if not l:raise ValueError('League not found')
   fixtures=[dict(r) for r in d.execute('SELECT f.*,pa.tag name_a,pb.tag name_b FROM fixtures f JOIN game_profiles pa ON pa.uid=f.a JOIN game_profiles pb ON pb.uid=f.b WHERE league=? ORDER BY opens,round',(lid,))]
   for f in fixtures:
    f['schedule']=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(f['id'],))
    f['can_report']=uid in (f['a'],f['b']) and f['state'] not in ('confirmed','void','walkover')
    if uid in (f['a'],f['b']):f['evidence_review']=__import__('result_reviews').status(d,dict(f,kind='fixture'),uid)
    reports=[dict(r) for r in d.execute('SELECT uid,score_a,score_b,mime,ocr FROM game_reports WHERE fixture=?',(f['id'],))] if uid in (f['a'],f['b']) or mod(d,l,uid) else []
    if l['verification']=='typed' and f['state'] not in ('confirmed','disputed','void','walkover') and uid in (f['a'],f['b']) and not any(r['uid']==uid for r in reports):reports=[{'uid':r['uid'],'submitted':True,'mime':None,'ocr':''} for r in reports]
    if uid in (f['a'],f['b']):reports=[{'uid':r['uid'],'submitted':True,**({'score_a':r.get('score_a'),'score_b':r.get('score_b')} if r['uid']==uid else {})} for r in reports]
    f['reports']=reports;f['game_ids']={r['uid']:r['game_id'] for r in d.execute('SELECT uid,game_id FROM league_members WHERE league=? AND uid IN (?,?)',(lid,f['a'],f['b']))} if uid in (f['a'],f['b']) or mod(d,l,uid) else {};f['can_review']=mod(d,l,uid) and uid not in (f['a'],f['b']);f['audit']=[dict(r) for r in d.execute('SELECT action,details,time FROM game_audit WHERE fixture=? ORDER BY id',(f['id'],))] if f['can_review'] else []
    if f['can_review']:
     f['video_evidence']=[dict(r) for r in d.execute('SELECT uid,mime,created FROM result_review_videos WHERE kind=\'fixture\' AND match_id=? AND video IS NOT NULL',(f['id'],))]
     f['evidence_review']=__import__('result_reviews').status(d,dict(f,kind='fixture'),uid)
   result['slots']=[dict(r) for r in d.execute('SELECT m.slot,m.uid,p.tag FROM league_members m JOIN game_profiles p ON p.uid=m.uid WHERE m.league=? ORDER BY m.slot',(lid,))]
   table=standings(d,lid)
   for player in table:
    player['stats']=playerstats(d,player['uid'],l['game'])
    avatar=row(d,'SELECT avatar,avatar_mime FROM users WHERE id=?',(player['uid'],))
    player['avatar']=avatar['avatar'] if avatar and (player['feature'] or player['uid']==uid) else ''
    player['avatar_mime']=avatar['avatar_mime'] if player['avatar'] else ''
   result.update(league=l,table=table,fixtures=fixtures,organiser=mod(d,l,uid),owner=admin(d,uid),joined=bool(d.execute('SELECT 1 FROM league_members WHERE league=? AND uid=?',(lid,uid)).fetchone()))
  return result

def scan(server,image,mime):
 try:
  from gaming_ocr import read
  return read(image)
 except Exception:return {'available':False,'text':'','scores':[],'note':'Automatic reading unavailable; enter the visible score manually.'}

def image(body):
 raw=base64.b64decode(body.get('image',''),validate=True)
 if not 0<len(raw)<=5*1024*1024:raise ValueError('Screenshot must be under 5 MB')
 mime='image/png' if raw.startswith(b'\x89PNG\r\n\x1a\n') else 'image/jpeg' if raw.startswith(b'\xff\xd8\xff') else None
 if not mime:raise ValueError('Use a PNG or JPEG screenshot')
 return raw,mime

def post(server,uid,action,b):
 import gamebox_core
 if action=='report' and b.get('image'):return __import__('result_reviews').submit(server,uid,b)
 if action=='scan':
  raw,mime=image(b);return scan(server,raw,mime)
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  gamebox_core.current(d)
  if action=='stream_create':
   if not admin(d,uid):raise PermissionError('Only the administrator may create a test stream room')
   other=row(d,'SELECT id FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(b.get('identity'),str(b.get('identity','')).lstrip('@')))
   if not other or other['id']==uid:raise ValueError('Choose a different test account')
   mode=b.get('broadcaster','self')
   if mode not in ('self','invited'):raise ValueError('Choose the current account or invited player as broadcaster')
   __import__('social').ensure(d,uid,other['id'])
   host,viewer=(uid,other['id']) if mode=='self' else (other['id'],uid)
   if mode=='invited' and not d.execute('SELECT 1 FROM game_profiles WHERE uid=? AND adult=1',(host,)).fetchone():raise ValueError('The broadcaster must first create an adult gaming profile')
   if d.execute('SELECT COUNT(*) FROM game_stream_rooms WHERE (a=? OR b=?) AND created>?',(host,host,int(time.time())-7200)).fetchone()[0]>=3:raise ValueError('Use an existing test room; rooms expire after two hours')
   rid=uuid.uuid4().hex;d.execute('INSERT INTO game_stream_rooms VALUES(?,?,?,?)',(rid,host,viewer,int(time.time())))
   if __import__('match_streams').relay_available(server):d.execute("INSERT INTO game_stream_transport VALUES(?,'relay')",(rid,))
   d.execute('INSERT OR REPLACE INTO game_stream_responses VALUES(?,?,?)',(rid,viewer,'accepted' if viewer==uid else 'invited'))
   gamebox_core.notice(d,other['id'],'A private OrbitPlay room is ready. '+('You are the broadcaster: open Live streams, open the room and choose camera or gameplay sharing.' if host==other['id'] else 'Open Live streams to accept and watch.'))
   gamebox_core.event(d,rid,uid,'stream_room_created',new={'broadcaster':host,'viewer':viewer})
   return {'id':rid,'broadcaster':host,'viewer':viewer}
  if action in ('stream_begin','stream_end','stream_watch'):
   import stream_lifecycle as life
   rid=str(b.get('room',''))
   if action=='stream_end':
    r=row(d,'SELECT * FROM game_stream_rooms WHERE id=?',(rid,))
    if not r:return {'ended':True}
    if r['a']!=uid:raise PermissionError('Only the broadcaster can end this session')
    life.finish(d,rid,server);return {'ended':True,'total_viewers':life.total(d,uid)}
   stream_access(d,uid,rid)
   if action=='stream_begin':
    __import__('match_streams').access(d,uid,rid,publish=True)
    return life.begin(d,uid,rid)
   if __import__('match_streams').linked(d,rid) and not __import__('match_streams').ready(server,rid):raise PermissionError('This livestream is not broadcasting right now')
   return life.watch(d,uid,rid)
  if action in ('stream_accept','stream_decline'):
   rid=b.get('room');room=row(d,'SELECT * FROM game_stream_rooms WHERE id=?',(rid,))
   if not room or room['created']<time.time()-7200 or uid==room['a'] or (uid!=room['b'] and not row(d,'SELECT uid FROM game_stream_members WHERE room=? AND uid=?',(rid,uid))):raise PermissionError('This invitation is unavailable')
   state='accepted' if action=='stream_accept' else 'declined';d.execute('INSERT OR REPLACE INTO game_stream_responses VALUES(?,?,?)',(rid,uid,state));gamebox_core.notice(d,room['a'],'Your live-stream invitation was '+state+'.');return {'ok':True}
  if action=='stream_react':
   room=stream_access(d,uid,b.get('room'));__import__('stream_lifecycle').active(d,room['id'])
   __import__('live_reactions').emit(room['id'],uid,b.get('emoji'));return {'ok':True}
  if action in ('stream_invite','stream_comment','stream_like'):
   room=stream_access(d,uid,b.get('room'))
   if action=='stream_invite':
    if uid!=room['a']:raise PermissionError('Only the broadcaster may invite viewers')
    other=row(d,'SELECT id FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(b.get('identity'),str(b.get('identity','')).lstrip('@')))
    if not other:raise ValueError('Account not found')
    import social
    social.ensure(d,uid,other['id'])
    relay=d.execute('SELECT 1 FROM game_stream_transport WHERE room=?',(room['id'],)).fetchone()
    if not relay and d.execute('SELECT COUNT(*) FROM game_stream_members WHERE room=?',(room['id'],)).fetchone()[0]>=4:raise ValueError('This older direct room supports five viewers; create a relay room for more viewers')
    d.execute('INSERT OR IGNORE INTO game_stream_members VALUES(?,?)',(room['id'],other['id']));d.execute('INSERT OR REPLACE INTO game_stream_responses VALUES(?,?,?)',(room['id'],other['id'],'invited'));gamebox_core.notice(d,other['id'],'You are invited to a live camera stream. Open Gamebox → Live streams.')
   elif action=='stream_comment':
    __import__('stream_lifecycle').active(d,room['id'])
    text=str(b.get('text','')).strip()
    if not 1<=len(text)<=500:raise ValueError('Comment must be 1–500 characters')
    if d.execute('SELECT COUNT(*) FROM game_stream_comments WHERE room=? AND uid=? AND created>?',(room['id'],uid,int(time.time())-10)).fetchone()[0]>=5:raise ValueError('Please slow down')
    d.execute('INSERT INTO game_stream_comments(room,uid,text,created) VALUES(?,?,?,?)',(room['id'],uid,text,int(time.time())))
   else:
    __import__('stream_lifecycle').active(d,room['id'])
    d.execute('INSERT OR IGNORE INTO game_stream_likes VALUES(?,?)',(room['id'],uid))
   return {'ok':True}
  if action=='stream_signal':
   room=stream_access(d,uid,b.get('room'))
   kind=b.get('kind');payload=b.get('payload');encoded=json.dumps(payload)
   if kind not in ('join','offer','answer','ice','end') or len(encoded)>100000:raise ValueError('Invalid stream signal')
   target=payload.get('target') if isinstance(payload,dict) else None
   if not target:raise ValueError('Choose the stream recipient')
   if target not in (room['a'],room['b']) and not row(d,'SELECT uid FROM game_stream_members WHERE room=? AND uid=?',(room['id'],target)):raise PermissionError('Recipient is not invited')
   if uid!=room['a'] and target!=room['a']:raise PermissionError('Viewers signal only to the broadcaster')
   d.execute('INSERT INTO game_stream_signals(room,sender,kind,payload,time) VALUES(?,?,?,?,?)',(room['id'],uid,kind,encoded,int(time.time())))
   d.execute('DELETE FROM game_stream_signals WHERE room=? AND id NOT IN (SELECT id FROM game_stream_signals WHERE room=? ORDER BY id DESC LIMIT 200)',(room['id'],room['id']));return {'ok':True}
  if action=='profile':
   if b.get('adult') is not True:raise ValueError('This pilot is for adults aged 18 and over')
   tag=str(b.get('tag','')).strip();gid=str(b.get('game_id','')).strip();handle=str(b.get('handle','')).strip()
   if not 2<=len(tag)<=30 or not 2<=len(gid)<=60 or len(handle)>80:raise ValueError('Enter a gaming nickname and game account ID')
   d.execute('INSERT INTO game_profiles VALUES(?,?,?,?,?,1) ON CONFLICT(uid) DO UPDATE SET tag=excluded.tag,game_id=excluded.game_id,handle=excluded.handle,feature=excluded.feature,adult=1',(uid,tag,gid,handle,int(b.get('feature') is True)));return {'ok':True}
  if action in ('create','rename','sponsor','moderator','remove_moderator','start','finals','review','hide_comment') and not admin(d,uid):raise PermissionError('Administration is restricted to the authorised account')
  if action=='create':
   if not row(d,'SELECT * FROM game_profiles WHERE uid=?',(uid,)):raise ValueError('Set up your gaming profile first')
   name=str(b.get('name','')).strip();game=b.get('game')
   if not 3<=len(name)<=60 or game not in GAMES:raise ValueError('Enter a league name and supported game')
   if d.execute("SELECT COUNT(*) FROM leagues WHERE owner=? AND state!='finished'",(uid,)).fetchone()[0]>=3:raise ValueError('Finish an existing league before creating another')
   fmt=b.get('format','league')
   if fmt not in ('league','cup'):raise ValueError('Choose league or cup')
   tier=b.get('tier',0)
   if type(tier)!=int or not 0<=tier<len(TIERS):raise ValueError('Choose a valid division')
   capacity=b.get('capacity',8);round_days=b.get('round_days',4)
   if type(capacity)!=int or not 6<=capacity<=16 or fmt=='cup' and capacity!=8 or type(round_days)!=int or not 1<=round_days<=14:raise ValueError('Choose 6–16 league players, or 8 cup players, and 1–14 days per round')
   lid=uuid.uuid4().hex;d.execute('INSERT INTO leagues(id,name,game,owner,created,format,tier,capacity,round_days,verification,policy_snapshot) VALUES(?,?,?,?,?,?,?,?,?,?,?)',(lid,name,game,uid,int(time.time()),fmt,tier,capacity,round_days,'typed',d.execute('SELECT config FROM gb_versions ORDER BY id DESC LIMIT 1').fetchone()[0]));return {'id':lid}
  l=row(d,'SELECT * FROM leagues WHERE id=?',(b.get('league'),))
  if not l:raise ValueError('League not found')
  if action=='join':
   existing=row(d,'SELECT slot FROM league_members WHERE league=? AND uid=?',(l['id'],uid))
   if existing:return {'ok':True,'slot':existing['slot']}
   if l['state']!='enrolling':raise ValueError('Enrolment is closed')
   if d.execute('SELECT 1 FROM gb_qualified_cups WHERE league=?',(l['id'],)).fetchone() and not d.execute('SELECT 1 FROM gb_cup_eligibility WHERE league=? AND uid=?',(l['id'],uid)).fetchone():raise ValueError('This major cup is restricted to verified league/open qualifiers')
   if not row(d,'SELECT * FROM game_profiles WHERE uid=?',(uid,)):raise ValueError('Set up your gaming profile first')
   if d.execute('SELECT COUNT(*) FROM league_members WHERE league=?',(l['id'],)).fetchone()[0]>=l['capacity']:raise ValueError('This division is full')
   if l['format']=='league' and qualification(d,uid,l['game'])!=l['tier']:raise ValueError('Your qualified division is '+TIERS[qualification(d,uid,l['game'])])
   if l['format']=='league' and d.execute("SELECT 1 FROM league_members m JOIN leagues other ON other.id=m.league WHERE m.uid=? AND other.game=? AND other.format='league' AND other.state IN ('active','finals') AND other.id!=?",(uid,l['game'],l['id'])).fetchone():raise ValueError('Finish your active league for this game first')
   identity=row(d,'SELECT game_id FROM gb_game_ids WHERE uid=? AND game=?',(uid,l['game']))
   if l['verification']=='typed' and not identity:raise ValueError('Register a separate gaming ID for this game in Find a match first')
   if identity and (__import__('game_identities').meta(d,uid,l['game']) or {}).get('state')!='active':raise ValueError('This game registration is inactive or needs review')
   gid=identity['game_id'] if identity else row(d,'SELECT game_id FROM game_profiles WHERE uid=?',(uid,))['game_id']
   if d.execute('SELECT 1 FROM league_members WHERE league=? AND game_id=? COLLATE NOCASE AND uid!=?',(l['id'],gid,uid)).fetchone():raise ValueError('That game account is already registered in this division')
   slot=d.execute('SELECT COALESCE(MAX(slot),0)+1 FROM league_members WHERE league=?',(l['id'],)).fetchone()[0]
   d.execute('INSERT INTO league_members(league,uid,game_id,slot) VALUES(?,?,?,?)',(l['id'],uid,gid,slot));return {'ok':True,'slot':slot}
  if action=='hide_comment':
   if not mod(d,l,uid):raise PermissionError('Only assigned moderators may manage comments')
   c=row(d,'SELECT c.id,c.fixture FROM game_comments c JOIN fixtures f ON f.id=c.fixture WHERE c.id=? AND f.league=?',(b.get('comment'),l['id']))
   reason=str(b.get('reason','')).strip()
   if not c or not 5<=len(reason)<=500:raise ValueError('Select a comment and explain the moderation decision')
   d.execute('UPDATE game_comments SET hidden=1 WHERE id=?',(c['id'],));audit(d,c['fixture'],uid,'comment_hidden',str(c['id'])+': '+reason);return {'ok':True}
  if action=='rename':
   if not admin(d,uid):raise PermissionError('Only the organiser may rename this competition')
   name=str(b.get('name','')).strip()
   if l['state']!='enrolling' or not 3<=len(name)<=60:raise ValueError('Names can change only before the competition starts')
   d.execute('UPDATE leagues SET name=? WHERE id=?',(name,l['id']));audit(d,l['id'],uid,'competition_renamed',name);return {'ok':True}
  if action in ('start','sponsor','moderator','remove_moderator','finals'):
   if not admin(d,uid):raise PermissionError('Only the league organiser can do this')
   if action in ('moderator','remove_moderator'):
    target=row(d,'SELECT id FROM users WHERE id=? OR nickname=? COLLATE NOCASE',(b.get('identity'),str(b.get('identity','')).lstrip('@')))
    if not target:raise ValueError('Moderator account not found')
    if action=='moderator':d.execute('INSERT OR IGNORE INTO game_moderators VALUES(?,?)',(l['id'],target['id']))
    else:d.execute('DELETE FROM game_moderators WHERE league=? AND uid=?',(l['id'],target['id']))
    audit(d,l['id'],uid,action,target['id']);return {'ok':True}
   if action=='sponsor':
    sponsor=str(b.get('sponsor','')).strip();url=str(b.get('url','')).strip()
    if len(sponsor)>60 or len(url)>300 or url and not re.fullmatch(r'https://[^\s]+',url):raise ValueError('Sponsor link must start with https://')
    reward=str(b.get('reward',l['reward'])).strip()
    if not 1<=len(reward)<=250:raise ValueError('Describe the confirmed reward in 250 characters or fewer')
    if reward!=l['reward'] and (l['state']!='enrolling' or b.get('funded') is not True):raise ValueError('Only secured rewards may be announced before the division starts')
    art=l['sponsor_art'];week=str(b.get('week',l['sponsor_week'])).strip()
    if week and not re.fullmatch(r'\d{4}-W(0[1-9]|[1-4]\d|5[0-3])',week):raise ValueError('Choose a valid sponsor week')
    if b.get('art'):
     raw,mime=image({'image':b['art']})
     if len(raw)>1024*1024:raise ValueError('Sponsor logo must be under 1 MB')
     from PIL import Image
     import io
     with Image.open(io.BytesIO(raw)) as logo:
      if logo.width*logo.height>4000000:raise ValueError('Sponsor logo is too large')
      logo.verify()
     art='data:'+mime+';base64,'+base64.b64encode(raw).decode()
    d.execute('UPDATE leagues SET sponsor=?,sponsor_url=?,reward=?,sponsor_art=?,sponsor_week=? WHERE id=?',(sponsor,url,reward,art,week,l['id']));audit(d,l['id'],uid,'sponsor_updated',json.dumps({'sponsor':sponsor,'week':week,'reward':reward}));return {'ok':True}
   if action=='start':
    if l['state']!='enrolling':raise ValueError('League has already started')
    ids=[r[0] for r in d.execute('SELECT uid FROM league_members WHERE league=? ORDER BY slot',(l['id'],))]
    if len(ids)!=l['capacity']:raise ValueError(str(l['capacity'])+' players are required')
    if l['format']=='league' and any(qualification(d,u,l['game'])!=l['tier'] for u in ids):raise ValueError('A player qualification changed; contact the organiser before starting')
    if l['format']=='league':
     for player in ids:
      if d.execute("SELECT 1 FROM league_members m JOIN leagues other ON other.id=m.league WHERE m.uid=? AND other.game=? AND other.format='league' AND other.state IN ('active','finals') AND other.id!=?",(player,l['game'],l['id'])).fetchone():raise ValueError('A player is already in another active league for this game')
    now=int(time.time())
    if l['format']=='cup':
     for i in range(0,8,2):d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,stage) VALUES(?,?,?,?,?,?,?,'quarter')",(uuid.uuid4().hex,l['id'],1,ids[i],ids[i+1],now,now+4*86400))
     d.execute("UPDATE leagues SET state='finals' WHERE id=?",(l['id'],));return {'ok':True}
    if len(ids)%2:ids.append(None)
    rounds=len(ids)-1;days=l['round_days']
    for n in range(rounds):
     for i in range(len(ids)//2):
      if ids[i] is not None and ids[-1-i] is not None:d.execute('INSERT INTO fixtures(id,league,round,a,b,opens,due) VALUES(?,?,?,?,?,?,?)',(uuid.uuid4().hex,l['id'],n+1,ids[i],ids[-1-i],now+n*days*86400,now+(n+1)*days*86400))
     ids=[ids[0],ids[-1],*ids[1:-1]]
    d.execute("UPDATE leagues SET state='active' WHERE id=?",(l['id'],));return {'ok':True}
   if action=='finals':
    if l['state']!='active' or d.execute("SELECT COUNT(*) FROM fixtures WHERE league=? AND stage='league' AND state NOT IN ('confirmed','walkover','void')",(l['id'],)).fetchone()[0]:raise ValueError('Confirm every league fixture before seeding finals')
    top=standings(d,l['id'])[:4];now=int(time.time())
    for a,z in ((0,3),(1,2)):d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,stage) VALUES(?,?,?,?,?,?,?,'semi')",(uuid.uuid4().hex,l['id'],8,top[a]['uid'],top[z]['uid'],now,now+3*86400))
    d.execute("UPDATE leagues SET state='finals' WHERE id=?",(l['id'],));return {'ok':True}
  f=row(d,'SELECT * FROM fixtures WHERE id=? AND league=?',(b.get('fixture'),l['id']))
  if not f:raise ValueError('Fixture not found')
  if action=='comment':
   if f['state'] in ('confirmed','void','walkover') or time.time()<f['opens']:raise ValueError('This match room is not active')
   text=str(b.get('text','')).strip()
   if not 1<=len(text)<=1000:raise ValueError('Write a comment under 1000 characters')
   last=d.execute('SELECT MAX(time) FROM game_comments WHERE uid=?',(uid,)).fetchone()[0]
   if last and time.time()-last<1:raise ValueError('Please wait a moment before commenting again')
   d.execute('INSERT INTO game_comments(fixture,uid,text,time) VALUES(?,?,?,?)',(f['id'],uid,text,int(time.time())));return {'ok':True}
  if action in ('report','confirm','dispute'):
   if uid not in (f['a'],f['b']):raise PermissionError('Only the scheduled players may submit this result')
   if f['state'] in ('confirmed','void','walkover'):raise ValueError('Result is already closed')
   if action in ('report','confirm') and __import__('result_reviews').active(d,dict(f,kind='fixture')):raise ValueError('Private evidence is awaiting review; original reports are locked')
   if time.time()<f['opens']:raise ValueError('This match window has not opened')
   if l['verification']=='typed' and action in ('report','confirm'):
    scheduled=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(f['id'],))
    if not scheduled or not scheduled['ready_a'] or not scheduled['ready_b']:raise ValueError('Both players must agree a time and check in before reporting')
    policy=json.loads(l['policy_snapshot'] or d.execute('SELECT config FROM gb_versions ORDER BY id DESC LIMIT 1').fetchone()[0]);first=d.execute("SELECT MIN(time) FROM game_audit WHERE fixture=? AND action='submitted'",(f['id'],)).fetchone()[0]
    if first and time.time()>first+policy['result_seconds']:raise ValueError('The result submission window expired. Ask for evidence review.')
   if action=='dispute':
    reason=str(b.get('reason','')).strip()
    if len(reason)<5 or len(reason)>500:raise ValueError('Describe the disagreement')
    d.execute("UPDATE fixtures SET state='disputed' WHERE id=?",(f['id'],));audit(d,f['id'],uid,'disputed',reason);return {'ok':True}
   if action=='confirm':
    if l['verification']=='typed':raise ValueError('Submit your own independent score in the fixed player order')
    r=row(d,'SELECT * FROM game_reports WHERE fixture=? AND uid!=?',(f['id'],uid))
    if not r:raise ValueError('The opponent must submit first')
    if f['state']=='disputed':raise ValueError('A moderator must settle the dispute')
    d.execute('INSERT INTO game_reports(fixture,uid,score_a,score_b) VALUES(?,?,?,?) ON CONFLICT(fixture,uid) DO UPDATE SET score_a=excluded.score_a,score_b=excluded.score_b',(f['id'],uid,r['score_a'],r['score_b']));audit(d,f['id'],uid,'confirmed_by_opponent')
   else:
    a=b.get('score_a');z=b.get('score_b')
    if type(a)!=int or type(z)!=int or not 0<=a<=99 or not 0<=z<=99:raise ValueError('Scores must be whole numbers from 0 to 99')
    if f['stage']!='league' and a==z:raise ValueError('Knockout matches need a winner after the agreed tie-break')
    existing_report=row(d,'SELECT * FROM game_reports WHERE fixture=? AND uid=?',(f['id'],uid))
    if l['verification']=='typed' and existing_report:
     if existing_report['image'] is not None or not b.get('image'):raise ValueError('Your independent score is already submitted')
     if (a,z)!=(existing_report['score_a'],existing_report['score_b']):raise ValueError('Attach evidence without changing your original score')
    raw=mime=digest=None
    if b.get('image'):raw,mime=image(b);digest=hashlib.sha256(raw).hexdigest()
    elif l['verification']=='legacy' or f['state']=='disputed':raise ValueError('Original screenshot evidence is required for this disputed or legacy match')
    previous=row(d,'SELECT fixture,uid FROM game_reports WHERE digest=?',(digest,))
    if previous and (previous['fixture']!=f['id'] or previous['uid']!=uid):raise ValueError('This screenshot was already submitted. Use your original evidence.')
    d.execute('INSERT INTO game_reports VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(fixture,uid) DO UPDATE SET score_a=excluded.score_a,score_b=excluded.score_b,image=excluded.image,mime=excluded.mime,digest=excluded.digest,ocr=excluded.ocr',(f['id'],uid,a,z,raw,mime,digest,str(b.get('ocr',''))[:6000]));audit(d,f['id'],uid,'submitted')
   reports=list(d.execute('SELECT score_a,score_b FROM game_reports WHERE fixture=?',(f['id'],)))
   if len(reports)==2 and tuple(reports[0])==tuple(reports[1]) and f['state']!='disputed':
    d.execute("UPDATE fixtures SET state='confirmed',score_a=?,score_b=? WHERE id=?",(*reports[0],f['id']));audit(d,f['id'],uid,'result_counted');advance(d,l)
   elif len(reports)==2:d.execute("UPDATE fixtures SET state='disputed' WHERE id=?",(f['id'],))
   else:d.execute("UPDATE fixtures SET state='pending' WHERE id=?",(f['id'],))
   return {'ok':True}
  if action=='review':
   if not mod(d,l,uid) or uid in (f['a'],f['b']):raise PermissionError('An independent league moderator must review this match')
   if f['state'] not in ('pending','disputed'):raise ValueError('This result is not awaiting review')
   reason=str(b.get('reason','')).strip();a=b.get('score_a');z=b.get('score_b')
   if len(reason)<5 or len(reason)>500 or type(a)!=int or type(z)!=int or not 0<=a<=99 or not 0<=z<=99 or f['stage']!='league' and a==z:raise ValueError('Enter the reviewed score and decision reason')
   if not d.execute('SELECT 1 FROM game_reports WHERE fixture=? AND image IS NOT NULL',(f['id'],)).fetchone() and not d.execute('SELECT 1 FROM result_review_videos WHERE kind=\'fixture\' AND match_id=? AND video IS NOT NULL',(f['id'],)).fetchone():raise ValueError('Camera evidence is required')
   __import__('result_reviews').require_both(d,dict(f,kind='fixture'))
   finalize_review(d,f,a,z,uid,reason);return {'ok':True}
  raise ValueError('Unknown gaming action')
def advance(d,l):
 if l['verification']=='typed':
  import gamebox_core
  gamebox_core.rate_competition_results(d,l)
 quarters=[dict(r) for r in d.execute("SELECT * FROM fixtures WHERE league=? AND stage='quarter' ORDER BY rowid",(l['id'],))]
 if len(quarters)==4 and all(f['state']=='confirmed' for f in quarters) and not d.execute("SELECT 1 FROM fixtures WHERE league=? AND stage='semi'",(l['id'],)).fetchone():
  winners=[f['a'] if f['score_a']>f['score_b'] else f['b'] for f in quarters];now=int(time.time())
  for i in (0,2):d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,stage) VALUES(?,?,?,?,?,?,?,'semi')",(uuid.uuid4().hex,l['id'],2,winners[i],winners[i+1],now,now+4*86400))
 semis=[dict(r) for r in d.execute("SELECT * FROM fixtures WHERE league=? AND stage='semi' ORDER BY rowid",(l['id'],))]
 if len(semis)==2 and all(f['state']=='confirmed' for f in semis) and not d.execute("SELECT 1 FROM fixtures WHERE league=? AND stage='final'",(l['id'],)).fetchone():
  winners=[f['a'] if f['score_a']>f['score_b'] else f['b'] for f in semis];now=int(time.time());d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,stage) VALUES(?,?,?,?,?,?,?,'final')",(uuid.uuid4().hex,l['id'],9,*winners,now,now+3*86400))
 final=row(d,"SELECT * FROM fixtures WHERE league=? AND stage='final' AND state='confirmed'",(l['id'],))
 if final:d.execute("UPDATE leagues SET state='finished',champion=? WHERE id=?",(final['a'] if final['score_a']>final['score_b'] else final['b'],l['id']))

 if final and l['format']=='league':
  table=standings(d,l['id'])
  for index,p in enumerate(table):
   if d.execute('SELECT 1 FROM game_promotions WHERE league=? AND uid=?',(l['id'],p['uid'])).fetchone():continue
   old=qualification(d,p['uid'],l['game']);new=max(0,min(len(TIERS)-1,old+(1 if index<3 else -1 if index>=len(table)-3 else 0)))
   d.execute('INSERT INTO game_promotions VALUES(?,?,?,?)',(l['id'],p['uid'],old,new));d.execute('INSERT INTO game_qualification VALUES(?,?,?) ON CONFLICT(uid,game) DO UPDATE SET tier=excluded.tier',(p['uid'],l['game'],new));audit(d,l['id'],p['uid'],'division_updated',TIERS[old]+' → '+TIERS[new])

def evidence(server,uid,fid,player):
 with server.db() as d:
  f=row(d,'SELECT * FROM fixtures WHERE id=?',(fid,));l=row(d,'SELECT * FROM leagues WHERE id=?',(f['league'],)) if f else None
  if not f or uid in (f['a'],f['b']) or not mod(d,l,uid):raise PermissionError('Evidence is private to an independent authorised reviewer')
  r=row(d,'SELECT image,mime FROM game_reports WHERE fixture=? AND uid=?',(fid,player))
  if not r or not r['image']:raise ValueError('Screenshot unavailable')
  return r['image'],r['mime']

def finalize_review(d,f,a,b,actor,reason):
 if f['state'] in ('confirmed','void','walkover'):raise ValueError('Result is already closed')
 l=row(d,'SELECT * FROM leagues WHERE id=?',(f['league'],))
 d.execute("UPDATE fixtures SET state='confirmed',score_a=?,score_b=? WHERE id=?",(a,b,f['id']))
 audit(d,f['id'],actor,'moderator_approved' if actor!='system:local-ocr' else 'automatic_evidence_approved',json.dumps({'reason':reason,'approved_score':[a,b],'original_reports':[dict(r) for r in d.execute('SELECT uid,score_a,score_b FROM game_reports WHERE fixture=?',(f['id'],))]}))
 advance(d,l)
 rules=json.loads(l['policy_snapshot'] or __import__('gamebox_core').current(d)['config'])
 d.execute('INSERT OR REPLACE INTO gb_comp_retention VALUES(?,?)',(f['id'],int(time.time())+rules['retention_seconds']))
 __import__('result_reviews').finalized(d,'fixture',f['id'],a,b,actor,reason)
 for uid in (f['a'],f['b']):__import__('gamebox_core').notice(d,uid,'Reviewed match result confirmed. Relevant competition standings and progression have updated.')

def room(server,uid,fid):
 with server.db() as d:
  f=row(d,'SELECT f.*,a.tag name_a,b.tag name_b FROM fixtures f JOIN game_profiles a ON a.uid=f.a JOIN game_profiles b ON b.uid=f.b WHERE f.id=?',(fid,))
  if not f:raise ValueError('Match not found')
  comments=[dict(r) for r in d.execute('SELECT c.id,c.uid,c.text,c.time,COALESCE(p.tag,u.nickname) tag FROM game_comments c JOIN users u ON u.id=c.uid LEFT JOIN game_profiles p ON p.uid=c.uid WHERE fixture=? AND c.hidden=0 ORDER BY c.id DESC LIMIT 100',(fid,))]
  return {'fixture':f,'comments':list(reversed(comments)),'player':uid in (f['a'],f['b']),'active':f['state'] not in ('confirmed','void','walkover') and time.time()>=f['opens']}

def administration(server,uid,lid=None):
 with server.db() as d:
  if not admin(d,uid):raise PermissionError('Administration is restricted to the authorised account')
  allowed=[dict(r) for r in d.execute('SELECT * FROM leagues ORDER BY created DESC')]
  result={'stats':counters(d),'competitions':allowed,'controls':['Competition name before start','Sponsor artwork and placement','Funded rewards before start','Moderator assignment','Evidence review','Comment moderation'],'protected':['Submitted screenshots and game IDs','Confirmed scores and champions','Messages, protected media and passwords','Audit history','Security and GuardianLab detection settings']}
  if lid:
   l=next((l for l in allowed if l['id']==lid),None)
   if not l:raise PermissionError('You are not assigned to administer this competition')
   result['moderators']=[dict(r) for r in d.execute('SELECT p.uid,p.tag FROM game_moderators m LEFT JOIN game_profiles p ON p.uid=m.uid WHERE m.league=?',(lid,))]
   result['audit']=[dict(r) for r in d.execute('SELECT a.*,COALESCE(p.tag,u.nickname) actor_name FROM game_audit a LEFT JOIN users u ON u.id=a.actor LEFT JOIN game_profiles p ON p.uid=a.actor WHERE a.fixture=? OR a.fixture IN (SELECT id FROM fixtures WHERE league=?) ORDER BY a.id DESC LIMIT 200',(lid,lid))]
   result['comments']=[dict(r) for r in d.execute('SELECT c.*,COALESCE(p.tag,u.nickname) tag FROM game_comments c JOIN fixtures f ON f.id=c.fixture JOIN users u ON u.id=c.uid LEFT JOIN game_profiles p ON p.uid=c.uid WHERE f.league=? ORDER BY c.id DESC LIMIT 100',(lid,))]
  return result

def qualification(d,uid,game):
 r=d.execute('SELECT tier FROM game_qualification WHERE uid=? AND game=?',(uid,game)).fetchone();return r[0] if r else 0

def counters(d):
 count=lambda sql:d.execute(sql).fetchone()[0]
 return {'guardianchat_users':count('SELECT COUNT(*) FROM users'),'gamers':count('SELECT COUNT(*) FROM game_profiles'),'registered_players':count('SELECT COUNT(*) FROM (SELECT uid FROM league_members UNION SELECT uid FROM gb_season_entries)'),'registrations':count('SELECT COUNT(*) FROM league_members'),'competitions':count('SELECT COUNT(*) FROM leagues'),'active_competitions':count("SELECT COUNT(*) FROM leagues WHERE state IN ('active','finals')"),'completed_competitions':count("SELECT COUNT(*) FROM leagues WHERE state='finished'"),'league_winners':count("SELECT COUNT(*) FROM leagues WHERE champion IS NOT NULL AND format='league'"),'cup_winners':count("SELECT COUNT(*) FROM leagues WHERE champion IS NOT NULL AND format='cup'"),'unique_winners':count('SELECT COUNT(DISTINCT champion) FROM leagues'),'scheduled_matches':count('SELECT COUNT(*) FROM fixtures')+count('SELECT COUNT(*) FROM gb_matches'),'confirmed_matches':count("SELECT COUNT(*) FROM fixtures WHERE state='confirmed'")+count("SELECT COUNT(*) FROM gb_matches WHERE state='verified'"),'disputes':count("SELECT COUNT(*) FROM fixtures WHERE state='disputed'")+count("SELECT COUNT(*) FROM gb_matches WHERE state IN ('disputed','review')"),'pending_results':count("SELECT COUNT(*) FROM fixtures WHERE state='pending'"),'proof_uploads':count('SELECT COUNT(*) FROM game_reports WHERE image IS NOT NULL'),'promotions':count('SELECT COUNT(*) FROM game_promotions WHERE new_tier>old_tier'),'relegations':count('SELECT COUNT(*) FROM game_promotions WHERE new_tier<old_tier'),'moderators':count('SELECT COUNT(DISTINCT uid) FROM game_moderators'),'room_comments':count('SELECT COUNT(*) FROM game_comments')+count('SELECT COUNT(*) FROM gb_room_messages'),'official_game_id_registrations':count('SELECT COUNT(*) FROM gb_game_ids'),'players_in_match_queue':count('SELECT COUNT(*) FROM gb_queue'),'open_match_proposals':count("SELECT COUNT(*) FROM gb_matches WHERE state='proposed'"),'open_matches_in_progress':count("SELECT COUNT(*) FROM gb_matches WHERE state='in_progress'"),'open_results_awaiting':count("SELECT COUNT(*) FROM gb_matches WHERE state='awaiting_results'"),'seasons':count('SELECT COUNT(*) FROM gb_seasons'),'season_registrations':count('SELECT COUNT(*) FROM gb_season_entries'),'season_registration_windows':count("SELECT COUNT(*) FROM gb_seasons WHERE state='enrolling'"),'completed_seasons':count("SELECT COUNT(*) FROM gb_seasons WHERE state='finished'"),'reviewed_walkovers':count('SELECT COUNT(*) FROM gb_walkovers WHERE winner IS NOT NULL'),'double_no_shows':count('SELECT COUNT(*) FROM gb_walkovers WHERE winner IS NULL')}

def playerstats(d,uid,game=None):
 params=[uid,uid];sql="SELECT f.*,l.game,l.name competition,(SELECT COALESCE(MAX(time),0) FROM game_audit WHERE fixture=f.id AND action IN ('result_counted','moderator_approved')) verified_time FROM fixtures f JOIN leagues l ON l.id=f.league WHERE f.state='confirmed' AND (f.a=? OR f.b=?)"
 if game:sql+=' AND l.game=?';params.append(game)
 sql+=" ORDER BY (SELECT COALESCE(MAX(time),0) FROM game_audit WHERE fixture=f.id AND action IN ('result_counted','moderator_approved')) DESC,f.rowid DESC"
 matches=[dict(r) for r in d.execute(sql,params)]
 open_sql="SELECT *,game,'Open match' competition,verified verified_time FROM gb_matches WHERE state='verified' AND (a=? OR b=?)";open_params=[uid,uid]
 if game:open_sql+=' AND game=?';open_params.append(game)
 matches.extend(dict(r) for r in d.execute(open_sql,open_params));matches.sort(key=lambda r:(r['verified_time'] or 0,r['id']),reverse=True);results=[]
 for f in matches:
  own=f['score_a'] if f['a']==uid else f['score_b'];other=f['score_b'] if f['a']==uid else f['score_a'];results.append('W' if own>other else 'L' if own<other else 'D')
 recent=results[:5]
 return {'stream_viewers':__import__('stream_lifecycle').total(d,uid),'played':len(results),'wins':results.count('W'),'losses':results.count('L'),'draws':results.count('D'),'last_five':recent,'recent_summary':'Won '+str(recent.count('W'))+' of last '+str(len(recent))+' matches' if recent else 'No confirmed matches yet','titles':d.execute('SELECT COUNT(*) FROM leagues WHERE champion=?'+(' AND game=?' if game else ''),[uid]+([game] if game else [])).fetchone()[0],'divisions':{g:(TIERS[qualification(d,uid,g)] if d.execute('SELECT 1 FROM game_promotions p JOIN leagues l ON l.id=p.league WHERE p.uid=? AND l.game=?',(uid,g)).fetchone() else 'Unranked') for g in GAMES}}

def stream_access(d,uid,rid):
 return __import__('match_streams').access(d,uid,rid)

def stream_signals(server,uid,rid,after=0):
 with server.db() as d:
  room=stream_access(d,uid,rid)
  import stream_lifecycle as life
  live=life.state(d,rid)
  if live['active'] and uid==room['a']:d.execute('UPDATE live_sessions SET heartbeat=? WHERE room=?',(int(time.time()),rid))
  signals=[]
  for r in d.execute('SELECT id,sender,kind,payload FROM game_stream_signals WHERE room=? AND sender!=? AND id>? ORDER BY id LIMIT 200',(rid,uid,after)):
   payload=json.loads(r['payload'])
   if payload.get('target')==uid:signals.append(dict(r)|{'payload':payload})
  comments=[dict(r) for r in d.execute('SELECT c.id,c.uid,c.text,c.created,u.name FROM game_stream_comments c JOIN users u ON u.id=c.uid WHERE room=? ORDER BY c.id DESC LIMIT 100',(rid,))]
  return {'reactions':__import__('live_reactions').read(rid),'live':live,'signals':signals,'comments':list(reversed(comments)),'likes':d.execute('SELECT COUNT(*) FROM game_stream_likes WHERE room=?',(rid,)).fetchone()[0],'liked':bool(row(d,'SELECT uid FROM game_stream_likes WHERE room=? AND uid=?',(rid,uid)))}
