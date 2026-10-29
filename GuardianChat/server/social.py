"""Additive, account-scoped social graph. Never grants chat access."""
import time

def init(server):
 with server.db() as d:
  d.executescript('''
  CREATE TABLE IF NOT EXISTS social_profiles(uid TEXT PRIMARY KEY,private INTEGER NOT NULL DEFAULT 0,discoverable INTEGER NOT NULL DEFAULT 0,bio TEXT NOT NULL DEFAULT '',alerts INTEGER NOT NULL DEFAULT 1);
  CREATE TABLE IF NOT EXISTS social_follows(follower TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','accepted')),created INTEGER NOT NULL,PRIMARY KEY(follower,target),CHECK(follower<>target));
  CREATE INDEX IF NOT EXISTS social_follow_target ON social_follows(target,state);
  CREATE TABLE IF NOT EXISTS social_blocks(owner TEXT NOT NULL,target TEXT NOT NULL,PRIMARY KEY(owner,target),CHECK(owner<>target));
  CREATE TABLE IF NOT EXISTS social_notices(id INTEGER PRIMARY KEY,uid TEXT NOT NULL,actor TEXT NOT NULL,kind TEXT NOT NULL,created INTEGER NOT NULL,seen INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS social_reports(id INTEGER PRIMARY KEY,actor TEXT NOT NULL,target TEXT NOT NULL,reason TEXT NOT NULL,created INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'open');
  CREATE TABLE IF NOT EXISTS social_notice_delivery(id INTEGER PRIMARY KEY,attempts INTEGER NOT NULL DEFAULT 0,next_attempt INTEGER NOT NULL DEFAULT 0,delivered INTEGER NOT NULL DEFAULT 0);
  CREATE TABLE IF NOT EXISTS social_message_requests(sender TEXT NOT NULL,target TEXT NOT NULL,state TEXT NOT NULL CHECK(state IN ('pending','accepted','declined')),created INTEGER NOT NULL,PRIMARY KEY(sender,target));
  CREATE TABLE IF NOT EXISTS social_report_actions(id INTEGER PRIMARY KEY,report INTEGER NOT NULL,admin TEXT NOT NULL,state TEXT NOT NULL,note TEXT NOT NULL,created INTEGER NOT NULL);
  CREATE TABLE IF NOT EXISTS social_rate(uid TEXT PRIMARY KEY,start INTEGER NOT NULL,count INTEGER NOT NULL);
  ''')

def blocked(d,a,b):
 return bool(d.execute('SELECT 1 FROM social_blocks WHERE (owner=? AND target=?) OR (owner=? AND target=?)',(a,b,b,a)).fetchone())
def ensure(d,a,b):
 if blocked(d,a,b):raise PermissionError('Account interaction unavailable')
def settings(d,uid):
 row=d.execute('SELECT * FROM social_profiles WHERE uid=?',(uid,)).fetchone()
 return dict(row) if row else dict(uid=uid,private=0,discoverable=0,bio='',alerts=1)
def notice(d,uid,actor,kind):
 if settings(d,uid)['alerts']:d.execute('INSERT INTO social_notices(uid,actor,kind,created) VALUES(?,?,?,?)',(uid,actor,kind,int(time.time())))
def public(d,viewer,target):
 ensure(d,viewer,target)
 u=d.execute('SELECT id,name,nickname,avatar,avatar_mime FROM users WHERE id=?',(target,)).fetchone()
 if not u:raise ValueError('Account unavailable')
 p=settings(d,target);edge=d.execute('SELECT state FROM social_follows WHERE follower=? AND target=?',(viewer,target)).fetchone();allowed=viewer==target or not p['private'] or bool(edge and edge['state']=='accepted')
 result=dict(u);result.update(private=bool(p['private']),bio=p['bio'] if allowed else '',relationship=edge['state'] if edge else 'none',followers=d.execute("SELECT COUNT(*) FROM social_follows WHERE target=? AND state='accepted'",(target,)).fetchone()[0],following=d.execute("SELECT COUNT(*) FROM social_follows WHERE follower=? AND state='accepted'",(target,)).fetchone()[0],can_view_lists=allowed)
 if viewer==target:result.update(discoverable=bool(p['discoverable']),alerts=bool(p['alerts']))
 return result

def get(server,uid,action,q):
 with server.db() as d:
  target=q.get('id',[uid])[0]
  if action=='search':
   query=q.get('q',[''])[0].strip().removeprefix('@')
   if not 2<=len(query)<=60:raise ValueError('Enter 2–60 characters to search')
   offset=int(q.get('offset',['0'])[0])
   if not 0<=offset<=10000:raise ValueError('Invalid search page')
   literal=query.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')
   # Discovery is opt-in. Exact public identifiers also work for private accounts,
   # exposing only their existing public card, never granting conversation access.
   rows=d.execute('''SELECT u.id,u.name,u.nickname,u.avatar,u.avatar_mime,
    EXISTS(SELECT 1 FROM contacts c WHERE c.owner=? AND c.peer=u.id) AS contact
    FROM users u LEFT JOIN social_profiles p ON p.uid=u.id
    WHERE u.id<>? AND NOT EXISTS(SELECT 1 FROM social_blocks b
     WHERE (b.owner=? AND b.target=u.id) OR (b.owner=u.id AND b.target=?))
    AND (u.id=? COLLATE NOCASE OR u.nickname=? COLLATE NOCASE OR
     (p.discoverable=1 AND p.private=0 AND
      (u.name LIKE ? ESCAPE '\\' OR u.nickname LIKE ? ESCAPE '\\')))
    ORDER BY CASE WHEN u.id=? COLLATE NOCASE OR u.nickname=? COLLATE NOCASE THEN 0 ELSE 1 END,
     u.name COLLATE NOCASE,u.id LIMIT 21 OFFSET ?''',
    (uid,uid,uid,uid,query,query,'%'+literal+'%','%'+literal+'%',query,query,offset)).fetchall()
   return {'users':[dict(r) for r in rows[:20]],'next_offset':offset+20 if len(rows)>20 else None}
  if action=='suggestions':
   rows=d.execute('SELECT u.id,u.name,u.nickname,u.avatar,u.avatar_mime FROM users u JOIN social_profiles p ON p.uid=u.id WHERE p.discoverable=1 AND p.private=0 AND u.id<>? ORDER BY u.id LIMIT 100',(uid,))
   return {'users':[dict(r) for r in rows if not blocked(d,uid,r['id']) and not d.execute("SELECT 1 FROM social_follows WHERE follower=? AND target=?",(uid,r['id'])).fetchone()][:20]}
  if action=='profile':return public(d,uid,target)
  if action in ('followers','following'):
   if not public(d,uid,target)['can_view_lists']:raise PermissionError('This account is private')
   offset=max(0,int(q.get('offset',['0'])[0]));column,other=('target','follower') if action=='followers' else ('follower','target')
   rows=d.execute(f"SELECT u.id,u.name,u.nickname FROM social_follows f JOIN users u ON u.id=f.{other} WHERE f.{column}=? AND state='accepted' ORDER BY f.created DESC,u.id LIMIT 50 OFFSET ?",(target,offset))
   return {'users':[dict(r) for r in rows if not blocked(d,uid,r['id'])]}
  if action=='message_requests':return {'users':__import__('message_requests').previews(d,uid)}
  if action=='requests':return {'users':[dict(r) for r in d.execute("SELECT u.id,u.name,u.nickname FROM social_follows f JOIN users u ON u.id=f.follower WHERE target=? AND state='pending' ORDER BY created DESC LIMIT 100",(uid,))]}
  if action=='blocks':return {'users':[dict(r) for r in d.execute('SELECT u.id,u.name,u.nickname FROM social_blocks b JOIN users u ON u.id=b.target WHERE owner=?',(uid,))]}
  if action=='notices':return {'notices':[dict(r) for r in d.execute('SELECT n.id,n.kind,n.created,n.seen,u.id AS actor,u.name FROM social_notices n JOIN users u ON u.id=n.actor WHERE n.uid=? AND n.id>? ORDER BY n.id DESC LIMIT 100',(uid,int(q.get('after',['0'])[0]))) if not blocked(d,uid,r['actor'])]}
  if action=='report_history':
   import gaming
   if not gaming.admin(d,uid):raise PermissionError('Administration unavailable')
   return {'actions':[dict(r) for r in d.execute('SELECT * FROM social_report_actions WHERE report=? ORDER BY id',(int(q.get('report',['0'])[0]),))]}
  if action=='reports':
   import gaming
   if not gaming.admin(d,uid):raise PermissionError('Administration unavailable')
   return {'reports':[dict(r) for r in d.execute('SELECT * FROM social_reports ORDER BY id DESC LIMIT 100')]}
  raise ValueError('Unknown social action')

def post(server,uid,action,b):
 """Apply an authenticated social action atomically, returning its response dict.

 Args: server (ChatServer), uid (str), action (str), b (dict): HTTP action context.
 Raises ValueError/PermissionError for validation, privacy or rate failures;
 SQLite errors roll back relationship and pending Vibe delivery changes together.
 """
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  now=int(time.time());r=d.execute('SELECT * FROM social_rate WHERE uid=?',(uid,)).fetchone();count=r['count']+1 if r and r['start']>now-60 else 1;start=r['start'] if r and r['start']>now-60 else now
  if count>30:raise PermissionError('Too many social actions; try again shortly')
  d.execute('INSERT OR REPLACE INTO social_rate VALUES(?,?,?)',(uid,start,count))
  if action=='settings':
   p=settings(d,uid)
   for k in ('private','discoverable','alerts'):
    if k in b:
     if type(b[k]) is not bool:raise ValueError('Choose a valid privacy setting')
     p[k]=int(b[k])
   if 'bio' in b:
    if type(b['bio']) is not str or len(b['bio'])>300:raise ValueError('Biography must be at most 300 characters')
    p['bio']=b['bio'].strip()
   d.execute('INSERT OR REPLACE INTO social_profiles VALUES(?,?,?,?,?)',(uid,p['private'],p['discoverable'],p['bio'],p['alerts']))
   return public(d,uid,uid)
  if action=='resolve_report':
   import gaming
   if not gaming.admin(d,uid):raise PermissionError('Administration unavailable')
   report=int(b.get('report',0));state=b.get('state');note=b.get('note','')
   if state not in ('reviewing','resolved','dismissed') or not isinstance(note,str) or not 5<=len(note.strip())<=1000:raise ValueError('Choose a review state and explain the decision')
   if not d.execute('SELECT 1 FROM social_reports WHERE id=?',(report,)).fetchone():raise ValueError('Report unavailable')
   d.execute('UPDATE social_reports SET state=? WHERE id=?',(state,report))
   d.execute('INSERT INTO social_report_actions(report,admin,state,note,created) VALUES(?,?,?,?,?)',(report,uid,state,note.strip(),now));return {'saved':True}
  if action=='seen':d.execute('UPDATE social_notices SET seen=1 WHERE uid=? AND id<=?',(uid,int(b.get('through',0))));return {'saved':True}
  target=str(b.get('target',''))
  if target==uid or not d.execute('SELECT 1 FROM users WHERE id=?',(target,)).fetchone():raise ValueError('Choose another account')
  if action=='message_report':return __import__('message_requests').report(d,uid,target,b)
  if action=='message_decline_block':
   existing=d.execute('SELECT state FROM social_message_requests WHERE sender=? AND target=?',(target,uid)).fetchone()
   if not existing:raise PermissionError('Message request unavailable')
   if existing['state']=='accepted':return {'state':'accepted'}
   d.execute("UPDATE social_message_requests SET state='declined' WHERE sender=? AND target=?",(target,uid))
   d.execute('INSERT OR IGNORE INTO social_blocks VALUES(?,?)',(uid,target))
   d.execute('DELETE FROM social_follows WHERE (follower=? AND target=?) OR (follower=? AND target=?)',(uid,target,target,uid))
   return {'state':'declined','blocked':True}
  if action=='block':
   d.execute('INSERT OR IGNORE INTO social_blocks VALUES(?,?)',(uid,target));d.execute('DELETE FROM social_follows WHERE (follower=? AND target=?) OR (follower=? AND target=?)',(uid,target,target,uid));return {'blocked':True}
  if action=='unblock':d.execute('DELETE FROM social_blocks WHERE owner=? AND target=?',(uid,target));return {'blocked':False}
  ensure(d,uid,target)
  if action=='message_request':return __import__('message_requests').request(d,uid,target,b)
  if action in ('message_accept','message_decline'):
   state='accepted' if action=='message_accept' else 'declined'
   existing=d.execute('SELECT state FROM social_message_requests WHERE sender=? AND target=?',(target,uid)).fetchone()
   if not existing:raise PermissionError('Message request unavailable')
   if existing['state']!='pending':return {'state':existing['state']}
   cur=d.execute("UPDATE social_message_requests SET state=? WHERE sender=? AND target=? AND state='pending'",(state,target,uid))
   if cur.rowcount and state=='accepted':
    d.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(uid,target));d.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(target,uid));notice(d,target,uid,'message_accepted')
    __import__('message_requests').deliver(d,target,uid)
   return {'state':state}
  if action=='follow':
   state='pending' if settings(d,target)['private'] else 'accepted';cur=d.execute('INSERT OR IGNORE INTO social_follows VALUES(?,?,?,?)',(uid,target,state,now))
   if cur.rowcount:notice(d,target,uid,'follow_request' if state=='pending' else 'new_follower')
  elif action=='unfollow':d.execute('DELETE FROM social_follows WHERE follower=? AND target=?',(uid,target))
  elif action in ('accept','decline'):
   if action=='accept':
    cur=d.execute("UPDATE social_follows SET state='accepted' WHERE follower=? AND target=? AND state='pending'",(target,uid))
    if cur.rowcount:notice(d,target,uid,'request_accepted')
   else:d.execute("DELETE FROM social_follows WHERE follower=? AND target=? AND state='pending'",(target,uid))
  elif action=='report':
   reason=b.get('reason','')
   if type(reason) is not str or not 5<=len(reason.strip())<=1000:raise ValueError('Explain the report in 5–1000 characters')
   d.execute('INSERT INTO social_reports(actor,target,reason,created) VALUES(?,?,?,?)',(uid,target,reason.strip(),now));return {'reported':True}
  else:raise ValueError('Unknown social action')
  return public(d,uid,target)

def dispatch_notices(server):
 """Session-scoped push wakeups; payload contains no profile or relationship data."""
 if not getattr(server.push,'enabled',False):return
 now=int(time.time());pending=[]
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE')
  rows=d.execute('SELECT n.* FROM social_notices n LEFT JOIN social_notice_delivery p ON p.id=n.id WHERE n.seen=0 AND n.created>? AND COALESCE(p.delivered,0)=0 AND COALESCE(p.attempts,0)<3 AND COALESCE(p.next_attempt,0)<=? ORDER BY n.id LIMIT 20',(now-3600,now)).fetchall()
  for n in rows:
   if not settings(d,n['uid'])['alerts'] or blocked(d,n['uid'],n['actor']):continue
   tokens=[r[0] for r in d.execute('SELECT p.token FROM push_devices p JOIN sessions s ON s.token_hash=p.session_hash AND s.user_id=p.user_id WHERE p.user_id=?',(n['uid'],))]
   if not tokens:continue
   d.execute('INSERT INTO social_notice_delivery(id,attempts,next_attempt) VALUES(?,1,?) ON CONFLICT(id) DO UPDATE SET attempts=attempts+1,next_attempt=excluded.next_attempt',(n['id'],now+300));pending.append((dict(n),tokens))
 def send():
  for n,tokens in pending:
   success=False
   for token in tokens:
    try:server.push.send(token,{'event':'social_notice','notice_id':str(n['id']),'recipient':n['uid'],'expires_at':str(now+600)});success=True
    except Exception:pass
   if success:
    with server.db() as d:d.execute('UPDATE social_notice_delivery SET delivered=1 WHERE id=?',(n['id'],))
 if pending:
  import threading
  threading.Thread(target=send,daemon=True).start()
