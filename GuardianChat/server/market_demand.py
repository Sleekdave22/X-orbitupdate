"""Categorized buyer requests, conservative grouping and durable notification work.

Uses existing Guardian identities and Plaza categories; never creates financial
eligibility or changes existing account verification rules.
"""
import hashlib
import json
import re
import time
import uuid
from market_pilot import text
from market_search import tokens, STOP

DEFAULT_POLICY = {'threshold': 5, 'daily_push_limit': 2}
EXTRA_STOP = set('need needs needed request requests wanted looking would like find purchase anyone has have can get am is it this that a good condition new'.split())


def init(server):
    with server.db() as d:
        d.executescript("""
        CREATE TABLE IF NOT EXISTS market_demand_policy(id INTEGER PRIMARY KEY CHECK(id=1),value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS market_demand_groups(
          id TEXT PRIMARY KEY,category TEXT NOT NULL,kind TEXT NOT NULL,signature TEXT NOT NULL,
          terms TEXT NOT NULL,title TEXT NOT NULL,description TEXT NOT NULL,status TEXT NOT NULL,
          created INTEGER NOT NULL,updated INTEGER NOT NULL,expires INTEGER NOT NULL);
        CREATE INDEX IF NOT EXISTS market_demand_group_match ON market_demand_groups(category,kind,status,signature);
        CREATE INDEX IF NOT EXISTS market_demand_group_expiry ON market_demand_groups(status,expires,updated);
        CREATE TABLE IF NOT EXISTS market_demand_requests(
          group_id TEXT NOT NULL,uid TEXT NOT NULL,description TEXT NOT NULL,active INTEGER NOT NULL,
          created INTEGER NOT NULL,expires INTEGER NOT NULL,PRIMARY KEY(group_id,uid));
        CREATE INDEX IF NOT EXISTS market_demand_members ON market_demand_requests(group_id,active,expires,uid);
        CREATE INDEX IF NOT EXISTS market_demand_owner ON market_demand_requests(uid,active,created);
        CREATE INDEX IF NOT EXISTS market_demand_request_rate ON market_demand_requests(uid,created);
        CREATE TABLE IF NOT EXISTS market_demand_keys(
          uid TEXT NOT NULL,client TEXT NOT NULL,fingerprint TEXT NOT NULL,group_id TEXT NOT NULL,created INTEGER NOT NULL,PRIMARY KEY(uid,client));
        CREATE INDEX IF NOT EXISTS market_demand_key_rate ON market_demand_keys(uid,created);
        CREATE TABLE IF NOT EXISTS market_demand_preferences(uid TEXT PRIMARY KEY,updates INTEGER NOT NULL,categories TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS market_demand_notices(
          group_id TEXT NOT NULL,uid TEXT NOT NULL,kind TEXT NOT NULL,listing TEXT NOT NULL,notice INTEGER NOT NULL,
          PRIMARY KEY(group_id,uid,kind,listing));
        CREATE TABLE IF NOT EXISTS market_demand_push_budget(
          uid TEXT NOT NULL,day INTEGER NOT NULL,notice INTEGER NOT NULL,PRIMARY KEY(uid,day,notice));
        CREATE TABLE IF NOT EXISTS market_demand_jobs(
          kind TEXT NOT NULL,item TEXT NOT NULL,attempts INTEGER NOT NULL DEFAULT 0,
          next_attempt INTEGER NOT NULL DEFAULT 0,PRIMARY KEY(kind,item));
        """)


def policy(d):
    row = d.execute('SELECT value FROM market_demand_policy WHERE id=1').fetchone()
    return DEFAULT_POLICY | (json.loads(row[0]) if row else {})


def normalized(d, value):
    words = tokens(re.sub(r'(?<=[a-z])(?=\d)', ' ', value.lower()))
    synonyms = {r['term']: r['replacement'] for r in d.execute('SELECT * FROM market_synonyms')}
    result = set()
    for word in words:
        if word in STOP or word in EXTRA_STOP:
            continue
        word = synonyms.get(word, word)
        result.add(word)
    return sorted(result)[:32]


def compatible(a, b, coverage=False):
    a, b = set(a), set(b)
    numbers = lambda words: {w for w in words if any(c.isdigit() for c in w)}
    if not a or not b or (not numbers(a).issubset(numbers(b)) if coverage else numbers(a) != numbers(b)):
        return False
    return len(a & b) / len(a if coverage else a | b) >= (.8 if coverage else .6)


def count(d, ident, now):
    return d.execute('SELECT count(*) FROM market_demand_requests WHERE group_id=? AND active=1 AND expires>?', (ident, now)).fetchone()[0]


def preferences(d, uid):
    row = d.execute('SELECT * FROM market_demand_preferences WHERE uid=?', (uid,)).fetchone()
    return {'updates': bool(row['updates']), 'categories': json.loads(row['categories'])} if row else {'updates': False, 'categories': []}


def enqueue(d, kind, ident):
    d.execute('INSERT INTO market_demand_jobs(kind,item) VALUES(?,?) ON CONFLICT(kind,item) DO UPDATE SET attempts=0,next_attempt=0', (kind, ident))


def describe(d, r, uid, now):
    total = count(d, r['id'], now)
    mine = d.execute('SELECT 1 FROM market_demand_requests WHERE group_id=? AND uid=? AND active=1 AND expires>?', (r['id'], uid, now)).fetchone()
    return {k: r[k] for k in ('id','category','kind','title','description','updated','expires')} | {'requesters': total, 'hot': total >= policy(d)['threshold'], 'mine': bool(mine)}


def get(server, uid, path, q):
    now = int(time.time())
    with server.db() as d:
        if path == '/market/demand_preferences':
            return preferences(d, uid)
        if path == '/market/demand':
            r = d.execute("SELECT * FROM market_demand_groups WHERE id=? AND status='open' AND expires>?", (q.get('id',[''])[0], now)).fetchone()
            if not r or not count(d, r['id'], now):
                raise ValueError('This request is no longer active')
            return {'demand': describe(d, r, uid, now)}
        offset = int(q.get('offset',['0'])[0])
        if not 0 <= offset <= 100000:
            raise ValueError('Choose a valid request page')
        category = q.get('category',[''])[0]
        rows = d.execute("""SELECT g.* FROM market_demand_groups g
          JOIN market_demand_requests r ON r.group_id=g.id AND r.active=1 AND r.expires>?
          WHERE g.status='open' AND g.expires>?""" + (' AND g.category=?' if category else '') +
          ' GROUP BY g.id ORDER BY count(*) DESC,g.updated DESC,g.id LIMIT 21 OFFSET ?',
          (now,now,category,offset) if category else (now,now,offset)).fetchall()
        mine = d.execute("""SELECT g.* FROM market_demand_groups g JOIN market_demand_requests r ON r.group_id=g.id
          WHERE r.uid=? AND r.active=1 AND r.expires>? AND g.status='open' AND g.expires>? ORDER BY r.created DESC LIMIT 10""", (uid,now,now)).fetchall()
        return {'demands':[describe(d,r,uid,now) for r in rows[:20]], 'more':len(rows)>20,
                'mine':[describe(d,r,uid,now) for r in mine], 'preferences':preferences(d,uid), 'policy':policy(d)}


def post(server, uid, action, b):
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        if action == 'admin_demand':
            import market_admin
            market_admin.authorize(d, uid)
            value = b.get('policy')
            if not isinstance(value,dict) or set(value) != set(DEFAULT_POLICY):
                raise ValueError('Supply the complete Demand policy')
            if type(value['threshold']) != int or not 3 <= value['threshold'] <= 5 or type(value['daily_push_limit']) != int or not 0 <= value['daily_push_limit'] <= 2:
                raise ValueError('Use 3–5 requesters and at most two Hot Demand pushes per day')
            reason = text(b.get('reason'),500,True)
            old = policy(d)
            d.execute('INSERT INTO market_demand_policy VALUES(1,?) ON CONFLICT(id) DO UPDATE SET value=excluded.value', (json.dumps(value),))
            market_admin.audit(d,uid,action,'demand',reason,old,value)
            for r in d.execute("SELECT id FROM market_demand_groups WHERE status='open' AND expires>?", (now,)):
                enqueue(d,'hot',r['id'])
            return {'ok':True}
        if action == 'demand_preferences':
            updates, categories = b.get('updates'), b.get('categories')
            if type(updates) != bool or not isinstance(categories,list) or len(categories)>20 or any(not isinstance(c,str) for c in categories):
                raise ValueError('Choose valid request notification preferences')
            valid = {r[0] for r in d.execute('SELECT id FROM market_categories WHERE enabled=1')}
            if not set(categories).issubset(valid):
                raise ValueError('Choose existing categories')
            if updates:
                __import__('market_pilot').seller(d,uid)
            d.execute('INSERT INTO market_demand_preferences VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET updates=excluded.updates,categories=excluded.categories',
                      (uid,int(updates),json.dumps(sorted(set(categories)))))
            for r in d.execute("SELECT id FROM market_demand_groups WHERE status='open' AND expires>?", (now,)):
                enqueue(d,'hot',r['id'])
            return {'ok':True}
        if action == 'demand_withdraw':
            ident = text(b.get('id'),40,True)
            changed = d.execute('UPDATE market_demand_requests SET active=0 WHERE group_id=? AND uid=?', (ident,uid)).rowcount
            if not changed:
                raise ValueError('This request does not belong to your account')
            if not count(d,ident,now):
                d.execute("UPDATE market_demand_groups SET status='closed',updated=? WHERE id=?", (now,ident))
            return {'ok':True}
        title, description = text(b.get('title'),80,True), text(b.get('description'),1000,True)
        category, kind, client = b.get('category_id'), b.get('listing_type','PRODUCT'), text(b.get('client_id'),80,True)
        if not isinstance(category,str) or not isinstance(kind,str) or not d.execute('SELECT 1 FROM market_categories WHERE id=? AND enabled=1',(category,)).fetchone() or kind not in __import__('market_listing_types').TYPES:
            raise ValueError('Choose an available category and listing type')
        fingerprint = hashlib.sha256(json.dumps([title,description,category,kind]).encode()).hexdigest()
        prior = d.execute('SELECT * FROM market_demand_keys WHERE uid=? AND client=?',(uid,client)).fetchone()
        if prior:
            if prior['fingerprint'] != fingerprint:
                raise ValueError('This retry key belongs to another request')
            return {'ok':True,'id':prior['group_id'],'already_requested':True}
        if d.execute('SELECT count(*) FROM market_demand_keys WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0] >= 30:
            raise ValueError('Please slow down before sending more request retries')
        terms = normalized(d,title+' '+description)
        if not terms:
            raise ValueError('Describe the item or service you need')
        signature = hashlib.sha256(json.dumps(terms).encode()).hexdigest()
        match = d.execute("SELECT * FROM market_demand_groups WHERE category=? AND kind=? AND status='open' AND signature=? AND expires>?",(category,kind,signature,now)).fetchone()
        if not match:
            for candidate in d.execute("SELECT * FROM market_demand_groups WHERE category=? AND kind=? AND status='open' AND expires>? ORDER BY updated DESC LIMIT 200",(category,kind,now)):
                if compatible(terms,json.loads(candidate['terms'])):
                    match = candidate
                    break
        ident = match['id'] if match else uuid.uuid4().hex
        member = d.execute('SELECT * FROM market_demand_requests WHERE group_id=? AND uid=?',(ident,uid)).fetchone()
        already = member is not None and member['active'] and member['expires'] > now
        if not already:
            if d.execute('SELECT count(*) FROM market_demand_requests WHERE uid=? AND created>?',(uid,now-3600)).fetchone()[0] >= 3:
                raise ValueError('Please wait before creating more requests')
            if d.execute('SELECT count(*) FROM market_demand_requests WHERE uid=? AND active=1 AND expires>?',(uid,now)).fetchone()[0] >= 10:
                raise ValueError('Withdraw an old request before adding another')
            if not match:
                d.execute("INSERT INTO market_demand_groups VALUES(?,?,?,?,?,?,?,'open',?,?,?)",(ident,category,kind,signature,json.dumps(terms),title,description,now,now,now+30*86400))
            d.execute('INSERT INTO market_demand_requests VALUES(?,?,?,1,?,?) ON CONFLICT(group_id,uid) DO UPDATE SET description=excluded.description,active=1,created=excluded.created,expires=excluded.expires',(ident,uid,description,now,now+30*86400))
            d.execute('UPDATE market_demand_groups SET updated=?,expires=max(expires,?) WHERE id=?',(now,now+30*86400,ident))
            enqueue(d,'hot',ident)
        d.execute('INSERT INTO market_demand_keys VALUES(?,?,?,?,?)',(uid,client,fingerprint,ident,now))
        return {'ok':True,'id':ident,'already_requested':bool(already),'requesters':count(d,ident,now)}


def notice(d, group, uid, kind, message, listing=''):
    if not __import__('market_admin').settings(d)['notifications_enabled']:
        return
    if d.execute('SELECT 1 FROM market_demand_notices WHERE group_id=? AND uid=? AND kind=? AND listing=?',(group,uid,kind,listing)).fetchone():
        return
    __import__('account_notifications').add(d,uid,'market','demand',message,{'demand':group,'event':kind}|({'listing':listing} if listing else {}))
    ident = d.execute('SELECT last_insert_rowid()').fetchone()[0]
    d.execute('INSERT INTO market_demand_notices VALUES(?,?,?,?,?)',(group,uid,kind,listing,ident))


def hot(d, ident, now):
    group = d.execute("SELECT * FROM market_demand_groups WHERE id=? AND status='open' AND expires>?",(ident,now)).fetchone()
    if not group or count(d,ident,now) < policy(d)['threshold']:
        return
    for seller in d.execute("""SELECT p.* FROM market_demand_preferences p JOIN market_accounts a ON a.uid=p.uid
      LEFT JOIN market_seller_meta s ON s.uid=p.uid WHERE p.updates=1 AND coalesce(s.restricted,0)=0"""):
        categories = json.loads(seller['categories']) or [r[0] for r in d.execute("""SELECT DISTINCT m.category_id FROM market_listing_meta m
          JOIN market_ads a ON a.id=m.id WHERE a.uid=? AND a.status='active' AND a.expires>? AND m.state='ACTIVE'""",(seller['uid'],now))]
        if group['category'] in categories:
            notice(d,ident,seller['uid'],'hot_demand','Hot Demand: '+group['title'])


def listing(d, ident, now):
    import market_pilot
    try:
        raw = market_pilot.row(d,ident)
    except ValueError:
        return
    restricted = d.execute('SELECT restricted FROM market_seller_meta WHERE uid=?',(raw['uid'],)).fetchone()
    row = market_pilot.view(d,raw,raw['uid'])
    if row['status']!='active' or row['expires']<=now or row['state']!='ACTIVE' or (restricted and restricted[0]) or row['availability'] in ('unavailable','out_of_stock') or not row['application_open'] or row['type_details'].get('work_availability')=='unavailable':
        return
    words = normalized(d,row['title']+' '+row['description']+' '+json.dumps(row['attributes'])+' '+json.dumps(row['type_details']))
    for group in d.execute("SELECT * FROM market_demand_groups WHERE category=? AND kind=? AND status='open' AND expires>?",(row['category_id'],row['listing_type'],now)):
        enqueue(d,'hot',group['id'])
        if not compatible(json.loads(group['terms']),words,coverage=True):
            continue
        for buyer in d.execute('SELECT uid FROM market_demand_requests WHERE group_id=? AND active=1 AND expires>? AND uid<>?',(group['id'],now,row['uid'])):
            if not __import__('social').blocked(d,buyer['uid'],row['uid']):
                notice(d,group['id'],buyer['uid'],'demand_listing','A listing matches your request: '+row['title'],ident)


def maintenance(server):
    now = int(time.time())
    with server.db() as d:
        jobs = [dict(r) for r in d.execute('SELECT * FROM market_demand_jobs WHERE attempts<6 AND next_attempt<=? LIMIT 10',(now,))]
    for job in jobs:
        try:
            with server.db() as d:
                d.execute('BEGIN IMMEDIATE')
                if job['kind']=='hot':
                    hot(d,job['item'],now)
                else:
                    listing(d,job['item'],now)
                d.execute('DELETE FROM market_demand_jobs WHERE kind=? AND item=?',(job['kind'],job['item']))
        except Exception as error:
            with server.db() as d:
                d.execute('UPDATE market_demand_jobs SET attempts=attempts+1,next_attempt=? WHERE kind=? AND item=?',(now+60,job['kind'],job['item']))
            print('Demand notification retry: '+type(error).__name__,flush=True)


def push_allowed(d, notice_row, now):
    target = json.loads(notice_row['target'])
    if target.get('event') != 'hot_demand':
        return True
    uid, day = notice_row['uid'], now//86400
    pref=preferences(d,uid)
    group=d.execute("SELECT * FROM market_demand_groups WHERE id=? AND status='open' AND expires>?",(target.get('demand',''),now)).fetchone()
    restricted=d.execute('SELECT restricted FROM market_seller_meta WHERE uid=?',(uid,)).fetchone()
    if not pref['updates'] or not group or count(d,group['id'],now)<policy(d)['threshold'] or (restricted and restricted[0]) or not policy(d)['daily_push_limit']:
        return False
    categories=pref['categories'] or [r[0] for r in d.execute("SELECT DISTINCT m.category_id FROM market_listing_meta m JOIN market_ads a ON a.id=m.id WHERE a.uid=? AND a.status='active' AND a.expires>? AND m.state='ACTIVE'",(uid,now))]
    if group['category'] not in categories:
        return False
    if d.execute('SELECT 1 FROM market_demand_push_budget WHERE uid=? AND day=? AND notice=?',(uid,day,notice_row['id'])).fetchone():
        return True
    if d.execute('SELECT count(*) FROM market_demand_push_budget WHERE uid=? AND day=?',(uid,day)).fetchone()[0] >= policy(d)['daily_push_limit']:
        return False
    d.execute('INSERT INTO market_demand_push_budget VALUES(?,?,?)',(uid,day,notice_row['id']))
    return True
