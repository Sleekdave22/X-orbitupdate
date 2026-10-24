"""Additive recurring availability, mutual schedule requests and persistent reminder outbox."""
import datetime as dt,json,time,uuid
from zoneinfo import ZoneInfo
UTC=dt.timezone.utc
OFFSETS=(1800,900,0)
CLOSED={'confirmed','verified','void','walkover','cancelled'}
def row(d,sql,args=()):
 r=d.execute(sql,args).fetchone();return dict(r) if r else None
def init(server):
 with server.db() as d:
  d.executescript('''
  CREATE TABLE IF NOT EXISTS gb_play_availability(uid TEXT,game TEXT,tz TEXT,weekly TEXT,unavailable INTEGER,updated INTEGER,PRIMARY KEY(uid,game));
  CREATE TABLE IF NOT EXISTS gb_open_schedule(fixture TEXT PRIMARY KEY,proposer TEXT,proposed INTEGER,scheduled INTEGER,confirmed_a INTEGER DEFAULT 0,confirmed_b INTEGER DEFAULT 0,reschedules INTEGER DEFAULT 0,ready_a INTEGER DEFAULT 0,ready_b INTEGER DEFAULT 0,reminded INTEGER DEFAULT 0,version INTEGER DEFAULT 0);
  CREATE TABLE IF NOT EXISTS gb_schedule_requests(id TEXT PRIMARY KEY,kind TEXT,match_id TEXT,proposer TEXT,at INTEGER,base INTEGER,state TEXT,created INTEGER,expires INTEGER,decided INTEGER);
  CREATE UNIQUE INDEX IF NOT EXISTS gb_pending_schedule ON gb_schedule_requests(kind,match_id) WHERE state='pending';
  CREATE TABLE IF NOT EXISTS gb_match_reminders(kind TEXT,match_id TEXT,version INTEGER,uid TEXT,lead INTEGER,due INTEGER,state TEXT DEFAULT 'pending',notice INTEGER,PRIMARY KEY(kind,match_id,version,uid,lead));
  CREATE INDEX IF NOT EXISTS gb_reminder_due ON gb_match_reminders(state,due);
  CREATE TABLE IF NOT EXISTS gb_notice_links(notice INTEGER PRIMARY KEY,kind TEXT,match_id TEXT,version INTEGER,expires INTEGER,purpose TEXT,request_id TEXT);
  ''')
  if 'request_id' not in {r[1] for r in d.execute('PRAGMA table_info(gb_notice_links)')}:d.execute('ALTER TABLE gb_notice_links ADD COLUMN request_id TEXT')
  if 'version' not in {r[1] for r in d.execute('PRAGMA table_info(gb_schedule)')}:d.execute('ALTER TABLE gb_schedule ADD COLUMN version INTEGER DEFAULT 0')
  for kind,t in [('fixture','gb_schedule'),('open','gb_open_schedule')]:
   for old in d.execute('SELECT * FROM '+t+' WHERE proposed IS NOT NULL AND proposer IS NOT NULL').fetchall():
    if not d.execute("SELECT 1 FROM gb_schedule_requests WHERE kind=? AND match_id=? AND state='pending'",(kind,old['fixture'])).fetchone():
     now=int(time.time());expires=min(old['proposed']-1,now+86400)
     if old['scheduled']:expires=min(expires,old['scheduled']-match(d,kind,old['fixture'])['rules']['checkin_seconds'])
     d.execute('INSERT INTO gb_schedule_requests VALUES(?,?,?,?,?,?,?, ?,?,NULL)',(uuid.uuid4().hex,kind,old['fixture'],old['proposer'],old['proposed'],old['version'],'pending' if expires>now else 'expired',now,expires))
     if expires<=now:d.execute('UPDATE '+t+' SET proposed=NULL WHERE fixture=?',(old['fixture'],))
  # Seed only future events for already agreed fixtures; INSERT IGNORE makes restart safe.
  for s in d.execute('SELECT * FROM gb_schedule WHERE scheduled IS NOT NULL').fetchall():
   try:m=match(d,'fixture',s['fixture']);jobs(d,m,dict(s),int(time.time()))
   except ValueError:pass

def availability(d,uid,game):
 identity=row(d,'SELECT tz,availability FROM gb_game_ids WHERE uid=? AND game=?',(uid,game))
 if not identity:raise ValueError('Register this game in My games first')
 a=row(d,'SELECT * FROM gb_play_availability WHERE uid=? AND game=?',(uid,game))
 return {'tz':a['tz'] if a else identity['tz'],'weekly':json.loads(a['weekly']) if a else {},'unavailable':bool(a and a['unavailable']),'dated_windows':json.loads(identity['availability'])}
def temporarily_unavailable(d,uid,game):
 a=d.execute('SELECT unavailable FROM gb_play_availability WHERE uid=? AND game=?',(uid,game)).fetchone();return bool(a and a[0])
def minute(value):
 if not isinstance(value,str) or len(value)!=5 or value[2]!=':':raise ValueError('Use HH:MM times')
 try:h,m=map(int,value.split(':'))
 except ValueError:raise ValueError('Use HH:MM times')
 if not 0<=h<24 or not 0<=m<60:raise ValueError('Invalid playing time')
 return h*60+m
def validate_weekly(w):
 if type(w)!=dict or len(w)>7:raise ValueError('Choose up to seven playing days')
 intervals=[]
 for day,windows in w.items():
  if day not in list('0123456') or type(windows)!=list or len(windows)>6:raise ValueError('Use up to six windows per day')
  for v in windows:
   if type(v)!=dict or set(v)!={'start','end'}:raise ValueError('Each window needs a start and end')
   a,z=minute(v['start']),minute(v['end'])
   if a==z:raise ValueError('A playing window must have a duration')
   start=int(day)*1440+a;end=int(day)*1440+z+(1440 if z<a else 0)
   intervals.append((start,end))
 # Include the previous/next week when detecting overnight Sunday overlaps.
 all_intervals=sorted((a+shift,b+shift) for a,b in intervals for shift in (-10080,0,10080))
 if any(b>c for (_,b),(c,_) in zip(all_intervals,all_intervals[1:])):raise ValueError('Playing windows must not overlap')
def wall_time(value,tz):
 try:local=dt.datetime.fromisoformat(value);zone=ZoneInfo(tz)
 except (ValueError,TypeError,KeyError):raise ValueError('Enter a date/time and valid time zone')
 if local.tzinfo:raise ValueError('Enter local time without a UTC offset')
 candidates={int(local.replace(tzinfo=zone,fold=f).timestamp()) for f in (0,1) if local.replace(tzinfo=zone,fold=f).astimezone(UTC).astimezone(zone).replace(tzinfo=None)==local}
 if len(candidates)!=1:raise ValueError('This local time is missing or ambiguous during a clock change; choose another time')
 return candidates.pop()
def intervals(a,start,end):
 if a['unavailable']:return []
 out=[(max(start,s['start']),min(end,s['end'])) for s in a['dated_windows'] if s['end']>start and s['start']<end]
 zone=ZoneInfo(a['tz']);first=dt.datetime.fromtimestamp(start,zone).date()-dt.timedelta(days=1);last=dt.datetime.fromtimestamp(end,zone).date()
 day=first
 while day<=last:
  for w in a['weekly'].get(str(day.weekday()),[]):
   stop=day+dt.timedelta(days=minute(w['end'])<minute(w['start']))
   try:x=wall_time(day.isoformat()+'T'+w['start'],a['tz']);y=wall_time(stop.isoformat()+'T'+w['end'],a['tz'])
   except ValueError:continue
   if y>start and x<end:out.append((max(start,x),min(end,y)))
  day+=dt.timedelta(days=1)
 return sorted((a,b) for a,b in out if a<b)
def available(d,uid,game,at):
 return bool(intervals(availability(d,uid,game),at,at+1))
def overlap(d,a,b,game,start,end):
 aa=intervals(availability(d,a,game),start,end);bb=intervals(availability(d,b,game),start,end)
 for x,y in aa:
  for z,t in bb:
   if max(x,z)<min(y,t):return max(x,z)
 return None

def match(d,kind,mid):
 if kind=='fixture':
  m=row(d,'SELECT f.*,l.game,l.name context,l.policy_snapshot rules FROM fixtures f JOIN leagues l ON l.id=f.league WHERE f.id=?',(mid,))
 elif kind=='open':
  m=row(d,"SELECT *, 'Open match' context FROM gb_matches WHERE id=?",(mid,))
 else:raise ValueError('Choose an open match or competition fixture')
 if not m:raise ValueError('Match not found')
 m['kind']=kind;m['rules']=json.loads(m['rules'] or __import__('gamebox_core').current(d)['config']);return m
def table(kind):return 'gb_schedule' if kind=='fixture' else 'gb_open_schedule'
def schedule(d,m):return row(d,'SELECT * FROM '+table(m['kind'])+' WHERE fixture=?',(m['id'],))
def participant(m,uid):
 if uid not in (m['a'],m['b']):raise PermissionError('Only these two players may change the schedule')
def eligible(m):
 return m['state'] not in CLOSED and (m['kind']=='fixture' and m['state'] not in ('pending','disputed') or m['kind']=='open' and m['state']=='awaiting_checkin')
def validate_proposal(d,m,s,at,now):
 if not eligible(m):raise ValueError('This match cannot be scheduled now')
 if type(at)!=int:raise ValueError('Choose a valid kickoff')
 if m['kind']=='fixture':lower=max(now+60,m['opens']);upper=m['due']
 else:lower=now+60;upper=m['created']+m['rules'].get('open_schedule_seconds',604800)
 if not lower<=at<upper:raise ValueError('Choose a future kickoff within the match scheduling window')
 if s and (s['ready_a'] or s['ready_b']):raise ValueError('A player has already checked in')
 if s and s['scheduled']:
  if now>s['scheduled']-m['rules']['checkin_seconds'] or s['reschedules']>=m['rules']['reschedules']:raise ValueError('The reschedule limit or cutoff was reached')
 elif m['kind']=='open' and now>=m['deadline']:raise ValueError('The original check-in window has expired')
 if any(not available(d,u,m['game'],at) for u in (m['a'],m['b'])):raise ValueError('Kickoff must be inside both players’ saved availability')
def invalidate(d,m):
 d.execute("UPDATE gb_match_reminders SET state='invalidated' WHERE kind=? AND match_id=? AND state='pending'",(m['kind'],m['id']))
 d.execute('UPDATE gb_notices SET seen=1 WHERE id IN (SELECT notice FROM gb_notice_links WHERE kind=? AND match_id=?)',(m['kind'],m['id']))
def notice(d,m,uid,text,purpose,expires,version=None,request_id=None):
 if version is None:version=(schedule(d,m) or {}).get('version',0)
 cursor=d.execute('INSERT INTO gb_notices(uid,text,created) VALUES(?,?,?)',(uid,text,int(time.time())))
 d.execute('INSERT INTO gb_notice_links(notice,kind,match_id,version,expires,purpose,request_id) VALUES(?,?,?,?,?,?,?)',(cursor.lastrowid,m['kind'],m['id'],version,expires,purpose,request_id));return cursor.lastrowid
def jobs(d,m,s,now):
 if not s['scheduled'] or not eligible(m):return
 for uid in (m['a'],m['b']):
  for lead in OFFSETS:
   due=s['scheduled']-lead
   if due>now:d.execute('INSERT OR IGNORE INTO gb_match_reminders(kind,match_id,version,uid,lead,due) VALUES(?,?,?,?,?,?)',(m['kind'],m['id'],s['version'],uid,lead,due))
def expire_requests(d,now):
 for r in d.execute("SELECT * FROM gb_schedule_requests WHERE state='pending' AND expires<=?",(now,)).fetchall():
  d.execute("UPDATE gb_schedule_requests SET state='expired',decided=? WHERE id=?",(now,r['id']))
  d.execute('UPDATE '+table(r['kind'])+' SET proposed=NULL WHERE fixture=?',(r['match_id'],))
def change(d,uid,action,b,now=None):
 now=int(time.time()) if now is None else now;expire_requests(d,now)
 m=match(d,b.get('kind','fixture'),b.get('match') or b.get('fixture'));participant(m,uid);s=schedule(d,m)
 pending=row(d,"SELECT * FROM gb_schedule_requests WHERE kind=? AND match_id=? AND state='pending'",(m['kind'],m['id']))
 if action=='propose':
  tz=availability(d,uid,m['game'])['tz'];at=b.get('at') if 'at' in b else wall_time(b.get('local_at'),tz)
  if pending:
   if pending['proposer']==uid and pending['at']==at:return {'request':pending['id'],'state':'pending'}
   raise ValueError('Accept, decline or withdraw the pending request first')
  validate_proposal(d,m,s,at,now)
  if s and s['scheduled']==at:raise ValueError('This is already the confirmed kickoff')
  cutoff=s['scheduled']-m['rules']['checkin_seconds'] if s and s['scheduled'] else (m['due'] if m['kind']=='fixture' else m['deadline'])
  expires=min(at-1,cutoff,now+86400)
  if expires<=now:raise ValueError('The scheduling request window has closed')
  rid=uuid.uuid4().hex;base=s['version'] if s else 0
  d.execute('INSERT INTO gb_schedule_requests VALUES(?,?,?,?,?,?,\'pending\',?,?,NULL)',(rid,m['kind'],m['id'],uid,at,base,now,expires))
  d.execute('INSERT INTO '+table(m['kind'])+'(fixture,proposer,proposed) VALUES(?,?,?) ON CONFLICT(fixture) DO UPDATE SET proposer=excluded.proposer,proposed=excluded.proposed',(m['id'],uid,at))
  notice(d,m,m['b'] if uid==m['a'] else m['a'],'Your opponent requested a match time change. Open the match to accept or decline.','request',expires,base,rid)
  __import__('gamebox_core').event(d,m['id'],uid,'schedule_requested',new={'request':rid,'at':at});return {'request':rid,'state':'pending'}
 if not pending or b.get('request',pending['id'])!=pending['id']:raise ValueError('This request is no longer pending; refresh the match')
 if action=='withdraw' and pending['proposer']!=uid or action in ('accept','decline') and pending['proposer']==uid:raise PermissionError('Only the proposer withdraws; only the opponent accepts or declines')
 if action not in ('accept','decline','withdraw'):raise ValueError('Unknown schedule action')
 if action=='accept':
  if pending['base']!=s['version']:raise ValueError('The official schedule changed; refresh first')
  validate_proposal(d,m,s,pending['at'],now);invalidate(d,m);changed=int(bool(s['scheduled'] and s['scheduled']!=pending['at']))
  d.execute('UPDATE '+table(m['kind'])+' SET scheduled=?,proposed=NULL,confirmed_a=1,confirmed_b=1,reschedules=reschedules+?,ready_a=0,ready_b=0,reminded=1,version=version+1 WHERE fixture=?',(pending['at'],changed,m['id']))
  if m['kind']=='open':d.execute('UPDATE gb_matches SET deadline=?,ready_a=0,ready_b=0 WHERE id=?',(pending['at']+m['rules']['checkin_seconds'],m['id']))
  s=schedule(d,m);jobs(d,m,s,now)
  for player in (m['a'],m['b']):notice(d,m,player,'Match time confirmed. Open your match for the new kickoff and check-in.','confirmation',pending['at']+m['rules']['checkin_seconds'])
 else:
  d.execute('UPDATE '+table(m['kind'])+' SET proposed=NULL WHERE fixture=?',(m['id'],))
  for player in (m['a'],m['b']):notice(d,m,player,'Schedule request '+('declined' if action=='decline' else 'withdrawn')+'. The original confirmed time is unchanged.','decision',now+86400)
 state={'accept':'accepted','decline':'declined','withdraw':'withdrawn'}[action]
 d.execute('UPDATE gb_schedule_requests SET state=?,decided=? WHERE id=?',(state,now,pending['id']))
 __import__('gamebox_core').event(d,m['id'],uid,'schedule_'+state,new={'request':pending['id']});return {'state':state,'schedule':schedule(d,m)}

def valid_notice(d,n,now=None):
 now=int(time.time()) if now is None else now;l=row(d,'SELECT * FROM gb_notice_links WHERE notice=?',(n['id'],))
 if not l:return True
 if l['expires']<=now:return False
 try:m=match(d,l['kind'],l['match_id'])
 except ValueError:return False
 if m['state'] in CLOSED or l['purpose'] in ('request','reminder') and not eligible(m):return False
 s=schedule(d,m)
 if (s or {}).get('version',0)!=l['version']:return False
 if l['purpose']=='request':return bool(d.execute("SELECT 1 FROM gb_schedule_requests WHERE id=? AND kind=? AND match_id=? AND state='pending' AND expires>?",(l['request_id'],l['kind'],l['match_id'],now)).fetchone())
 return True
def public_notice(d,n):
 l=row(d,'SELECT kind,match_id,version,expires FROM gb_notice_links WHERE notice=?',(n['id'],));r=row(d,'SELECT target FROM gb_activity_targets WHERE notice=?',(n['id'],));extra=json.loads(r['target']) if r else {};return dict(n,**(dict(l) if l else {}),**({'match_id':extra['match'],'kind':extra['kind'],'result':True} if extra else {}))
def visible_notices(d,uid):return [public_notice(d,n) for n in d.execute('SELECT * FROM gb_notices WHERE uid=? AND seen=0 ORDER BY id DESC LIMIT 100',(uid,)) if valid_notice(d,n)][:30]
def tick(server,now=None):
 now=int(time.time()) if now is None else now
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE');expire_requests(d,now)
  d.execute("UPDATE gb_match_reminders SET state='suppressed' WHERE state='pending' AND kind='open' AND EXISTS(SELECT 1 FROM gb_matches m WHERE m.id=match_id AND m.state!='awaiting_checkin')")
  d.execute("UPDATE gb_match_reminders SET state='suppressed' WHERE state='pending' AND kind='fixture' AND EXISTS(SELECT 1 FROM fixtures f WHERE f.id=match_id AND f.state IN ('confirmed','void','walkover','pending','disputed','cancelled'))")
  for j in d.execute("SELECT * FROM gb_match_reminders WHERE state='pending' AND due<=? ORDER BY due LIMIT 200",(now,)).fetchall():
   state='suppressed';nid=None
   try:
    m=match(d,j['kind'],j['match_id']);s=schedule(d,m);identity=d.execute('SELECT reminders FROM gb_game_ids WHERE uid=? AND game=?',(j['uid'],m['game'])).fetchone()
    if eligible(m) and s and s['version']==j['version'] and now-j['due']<=60 and identity and identity[0]:
     other=m['b'] if j['uid']==m['a'] else m['a'];name=d.execute('SELECT nickname FROM gb_identity_meta WHERE uid=? AND game=?',(other,m['game'])).fetchone();name=name[0] if name else 'your opponent'
     tz=availability(d,j['uid'],m['game'])['tz'];when=dt.datetime.fromtimestamp(s['scheduled'],ZoneInfo(tz)).strftime('%d %b %Y %H:%M %Z')
     game=__import__('gaming').GAMES.get(m['game'],m['game']);message='starts in '+str(j['lead']//60)+' minutes' if j['lead'] else 'is scheduled to start now. Open the match and check in'
     expiry=s['scheduled']-(900 if j['lead']==1800 else 0) if j['lead'] else s['scheduled']+m['rules']['checkin_seconds']
     nid=notice(d,m,j['uid'],game+' vs '+name+' · '+m['context']+' · '+when+' · Your match '+message+'.','reminder',expiry,j['version']);state='queued'
   except ValueError:pass
   d.execute('UPDATE gb_match_reminders SET state=?,notice=? WHERE kind=? AND match_id=? AND version=? AND uid=? AND lead=?',(state,nid,j['kind'],j['match_id'],j['version'],j['uid'],j['lead']))

def post(server,uid,action,b):
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  if action=='availability':
   game=b.get('game');old=availability(d,uid,game);tz=b.get('tz',old['tz']);w=b.get('weekly',old['weekly']);unavailable=b.get('unavailable',old['unavailable'])
   if type(tz)!=str or len(tz)>60:raise ValueError('Choose a valid time zone')
   try:ZoneInfo(tz)
   except (KeyError,ValueError):raise ValueError('Choose a valid time zone')
   if type(unavailable)!=bool:raise ValueError('Choose available or temporarily unavailable')
   validate_weekly(w)
   d.execute('INSERT INTO gb_play_availability VALUES(?,?,?,?,?,?) ON CONFLICT(uid,game) DO UPDATE SET tz=excluded.tz,weekly=excluded.weekly,unavailable=excluded.unavailable,updated=excluded.updated',(uid,game,tz,json.dumps(w),int(unavailable),int(time.time())))
   d.execute('UPDATE gb_game_ids SET tz=? WHERE uid=? AND game=?',(tz,uid,game))
   if unavailable:d.execute('DELETE FROM gb_queue WHERE uid=? AND game=?',(uid,game))
   __import__('gamebox_core').event(d,'availability',uid,'availability_saved',old=old,new=b);return {'saved':True}
  return change(d,uid,action,b)
def get(server,uid,action,q):
 with server.db() as d:
  if action=='availability':return availability(d,uid,q.get('game',[''])[0])
  if action=='notice':
   n=row(d,'SELECT * FROM gb_notices WHERE id=? AND uid=?',(q.get('id',[''])[0],uid))
   if not n or not valid_notice(d,n):raise PermissionError('This notification is no longer active')
   return public_notice(d,n)
  if action=='admin':
   __import__('gamebox_core').authorised(d,uid)
   return {'offsets':list(OFFSETS),'jobs':[dict(r) for r in d.execute('SELECT j.*,p.attempts,p.delivered provider_accepted FROM gb_match_reminders j LEFT JOIN gb_notice_delivery p ON p.id=j.notice ORDER BY due DESC LIMIT 100')]}
  if action!='match':raise ValueError('Unknown scheduling view')
  m=match(d,q.get('kind',['fixture'])[0],q.get('match',[''])[0]);participant(m,uid)
  names={u:d.execute('SELECT tag FROM game_profiles WHERE uid=?',(u,)).fetchone()[0] for u in (m['a'],m['b'])}
  s=schedule(d,m);now=int(time.time());start=max(now+120,m.get('opens',now));end=min(m.get('due',now+604800),now+604800)
  try:suggest=overlap(d,m['a'],m['b'],m['game'],start,end)
  except ValueError:suggest=None
  return {'match':m,'schedule':s,'requests':[dict(r) for r in d.execute('SELECT * FROM gb_schedule_requests WHERE kind=? AND match_id=? ORDER BY created DESC LIMIT 20',(m['kind'],m['id']))],'availability':availability(d,uid,m['game']),'names':names,'suggested':suggest,'can_schedule':eligible(m)}
