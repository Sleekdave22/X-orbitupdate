"""Separate unread activity by product; seen receipts never accept an invitation."""
import json,time

def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS account_activity(id INTEGER PRIMARY KEY,uid TEXT NOT NULL,category TEXT NOT NULL,section TEXT NOT NULL,text TEXT NOT NULL,created INTEGER NOT NULL,seen INTEGER NOT NULL DEFAULT 0,target TEXT NOT NULL DEFAULT '{}');
 CREATE TABLE IF NOT EXISTS gb_activity_targets(notice INTEGER PRIMARY KEY,section TEXT NOT NULL,target TEXT NOT NULL);
 CREATE INDEX IF NOT EXISTS account_activity_owner ON account_activity(uid,category,seen,id);
 ''')

def add(d,uid,category,section,text,target=None):
 d.execute('INSERT INTO account_activity(uid,category,section,text,created,target) VALUES(?,?,?,?,?,?)',(uid,category,section,text,int(time.time()),json.dumps(target or {})))

def link_play(d,notice,section,match_id,kind):
 d.execute('INSERT OR REPLACE INTO gb_activity_targets VALUES(?,?,?)',(notice,section,json.dumps({'match':match_id,'kind':kind,'result':True})))

def section(text):
 value=text.lower()
 return 'streams' if 'stream' in value else 'seasons' if 'registration' in value or 'season' in value else 'profile' if 'identity' in value else 'open'

def list_items(d,uid,category=None):
 import match_scheduling
 items=[]
 if category in (None,'play'):
  for raw in match_scheduling.visible_notices(d,uid):
   n=dict(raw);r=d.execute('SELECT * FROM gb_activity_targets WHERE notice=?',(n['id'],)).fetchone()
   target=json.loads(r['target']) if r else {'match':n.get('match_id'),'kind':n.get('kind'),'tab':section(n['text'])}
   items.append({'id':n['id'],'category':'play','section':r['section'] if r else section(n['text']),'text':n['text'],'created':n['created'],'target':target})
 if category!='play':
  for n in d.execute('SELECT * FROM account_activity WHERE uid=? AND seen=0'+(' AND category=?' if category else '')+' ORDER BY id DESC LIMIT 100',(uid,category) if category else (uid,)):
   items.append(dict(n)|{'target':json.loads(n['target'])})
 return sorted(items,key=lambda n:(n['created'],n['id']),reverse=True)

def get(server,uid,category):
 if category and category not in ('play','market','vibe'):raise ValueError('Unknown notification category')
 with server.db() as d:
  items=list_items(d,uid,category);counts={}
  for n in list_items(d,uid):
   for key in (n['category'],n['category']+':'+n['section']):counts[key]=counts.get(key,0)+1
  return {'notifications':items,'counts':counts}

def seen(server,uid,body):
 category=body.get('category');ids=body.get('ids',[])
 if category not in ('play','market','vibe') or not isinstance(ids,list) or len(ids)>100 or any(type(i)!=int or i<1 for i in ids):raise ValueError('Choose valid notification receipts')
 with server.db() as d:
  for ident in ids:
   if category=='play':d.execute('UPDATE gb_notices SET seen=1 WHERE uid=? AND id=?',(uid,ident))
   else:d.execute('UPDATE account_activity SET seen=1 WHERE uid=? AND category=? AND id=?',(uid,category,ident))
 return {'ok':True}
