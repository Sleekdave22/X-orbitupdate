"""Unspendable Market simulation, separate from every fin_* gaming wallet table."""
import hashlib,json,time,uuid
from market_pilot import amount,CURRENCIES,text
from market_connections import emit,offer_view,release

class PaymentProvider:
 """Future adapter contract. No external provider is enabled or invoked."""
 def initiate(self,*args):raise NotImplementedError('Real payments disabled')
 def confirm(self,*args):raise NotImplementedError('Real payments disabled')
 def hold(self,*args):raise NotImplementedError('Real payments disabled')
 def authorize_release(self,*args):raise NotImplementedError('Real payments disabled')
 def settle(self,*args):raise NotImplementedError('Real payments disabled')
 def refund(self,*args):raise NotImplementedError('Real payments disabled')
 def dispute(self,*args):raise NotImplementedError('Real payments disabled')
 def verify_webhook(self,*args):raise NotImplementedError('Real payments disabled')
 def reconcile(self,*args):raise NotImplementedError('Real payments disabled')

def init(server):
 with server.db() as d:d.executescript('''
 CREATE TABLE IF NOT EXISTS market_demo_orders(id TEXT PRIMARY KEY,offer TEXT NOT NULL UNIQUE,listing TEXT NOT NULL,buyer TEXT NOT NULL,seller TEXT NOT NULL,amount_minor INTEGER NOT NULL,currency TEXT NOT NULL,state TEXT NOT NULL,revision INTEGER NOT NULL,created INTEGER NOT NULL,updated INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS market_demo_order_events(id INTEGER PRIMARY KEY,order_id TEXT NOT NULL,actor TEXT NOT NULL,action TEXT NOT NULL,reason TEXT NOT NULL DEFAULT '',created INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS market_demo_journals(id TEXT PRIMARY KEY,actor TEXT NOT NULL,kind TEXT NOT NULL,order_id TEXT NOT NULL,currency TEXT NOT NULL,created INTEGER NOT NULL,sealed INTEGER NOT NULL DEFAULT 0);
 CREATE TABLE IF NOT EXISTS market_demo_postings(id INTEGER PRIMARY KEY,journal TEXT NOT NULL,account TEXT NOT NULL,amount INTEGER NOT NULL CHECK(amount<>0));
 CREATE INDEX IF NOT EXISTS market_demo_account ON market_demo_postings(account,journal);
 CREATE TRIGGER IF NOT EXISTS market_demo_journal_immutable BEFORE UPDATE ON market_demo_journals WHEN OLD.sealed=1 BEGIN SELECT RAISE(ABORT,'Sealed demo journal is immutable');END;
 CREATE TRIGGER IF NOT EXISTS market_demo_journal_nodelete BEFORE DELETE ON market_demo_journals BEGIN SELECT RAISE(ABORT,'Demo journal cannot be deleted');END;
 CREATE TRIGGER IF NOT EXISTS market_demo_posting_noedit BEFORE UPDATE ON market_demo_postings BEGIN SELECT RAISE(ABORT,'Demo posting is immutable');END;
 CREATE TRIGGER IF NOT EXISTS market_demo_posting_nodelete BEFORE DELETE ON market_demo_postings BEGIN SELECT RAISE(ABORT,'Demo posting cannot be deleted');END;
 CREATE TRIGGER IF NOT EXISTS market_demo_posting_guard BEFORE INSERT ON market_demo_postings WHEN NOT EXISTS(SELECT 1 FROM market_demo_journals WHERE id=NEW.journal AND sealed=0) BEGIN SELECT RAISE(ABORT,'Demo journal unavailable');END;
 CREATE TRIGGER IF NOT EXISTS market_demo_seal BEFORE UPDATE OF sealed ON market_demo_journals WHEN NEW.sealed=1 AND ((SELECT count(*) FROM market_demo_postings WHERE journal=NEW.id)<2 OR (SELECT coalesce(sum(amount),0) FROM market_demo_postings WHERE journal=NEW.id)<>0) BEGIN SELECT RAISE(ABORT,'Demo journal must balance');END;
 ''')

def balance(d,account,currency):
 return d.execute('SELECT coalesce(sum(p.amount),0) FROM market_demo_postings p JOIN market_demo_journals j ON j.id=p.journal WHERE p.account=? AND j.currency=? AND j.sealed=1',(account,currency)).fetchone()[0]

def book(d,actor,kind,currency,minor,source,target,order=''):
 if type(minor)!=int or minor<=0 or source==target or currency not in CURRENCIES:raise ValueError('Invalid demo posting')
 if not source.startswith('simulation:') and balance(d,source,currency)<minor:raise ValueError('Insufficient demo balance')
 ident=uuid.uuid4().hex;d.execute('INSERT INTO market_demo_journals(id,actor,kind,order_id,currency,created) VALUES(?,?,?,?,?,?)',(ident,actor,kind,order,currency,int(time.time())))
 for account,delta in [(source,-minor),(target,minor)]:d.execute('INSERT INTO market_demo_postings(journal,account,amount) VALUES(?,?,?)',(ident,account,delta))
 d.execute('UPDATE market_demo_journals SET sealed=1 WHERE id=?',(ident,));return ident

def order_view(d,uid,ident,admin=False):
 r=d.execute('SELECT * FROM market_demo_orders WHERE id=?',(ident,)).fetchone()
 if not r or not admin and uid not in (r['buyer'],r['seller']):raise ValueError('Demo order unavailable')
 out=dict(r);out['simulation']=True;out['events']=[dict(x) for x in d.execute('SELECT actor,action,reason,created FROM market_demo_order_events WHERE order_id=? ORDER BY id',(ident,))];out['journals']=[dict(x) for x in d.execute('SELECT id,kind,currency,created FROM market_demo_journals WHERE order_id=? AND sealed=1 ORDER BY created,id',(ident,))];return out

def get(server,uid,path,q):
 with server.db() as d:
  if path=='/market/demo_order':return {'order':order_view(d,uid,q.get('id',[''])[0])}
  if path=='/market/demo_orders':return {'orders':[order_view(d,uid,r['id']) for r in d.execute('SELECT id FROM market_demo_orders WHERE buyer=? OR seller=? ORDER BY created DESC LIMIT 100',(uid,uid))]}
  if path=='/market/demo_wallet':
   currencies=[r[0] for r in d.execute('SELECT DISTINCT j.currency FROM market_demo_journals j JOIN market_demo_postings p ON p.journal=j.id WHERE p.account=?',('available:'+uid,))]
   currencies += [r[0] for r in d.execute('SELECT DISTINCT currency FROM market_demo_orders WHERE buyer=? OR seller=?',(uid,uid))]
   currencies=sorted(set(currencies)|{'NGN'})
   balances=[]
   for currency in currencies:
    held=d.execute("SELECT coalesce(sum(amount_minor),0) FROM market_demo_orders WHERE buyer=? AND currency=? AND state IN ('SECURED','FULFILLING','DELIVERED','DISPUTED')",(uid,currency)).fetchone()[0]
    pending=d.execute("SELECT coalesce(sum(amount_minor),0) FROM market_demo_orders WHERE seller=? AND currency=? AND state IN ('SECURED','FULFILLING','DELIVERED','DISPUTED')",(uid,currency)).fetchone()[0]
    balances.append({'currency':currency,'available_minor':balance(d,'available:'+uid,currency),'held_minor':held,'pending_sales_minor':pending})
   rows=d.execute('SELECT j.id,j.kind,j.currency,j.created,j.order_id,p.amount FROM market_demo_postings p JOIN market_demo_journals j ON j.id=p.journal WHERE j.sealed=1 AND p.account=? ORDER BY j.created DESC,j.id DESC LIMIT 100',('available:'+uid,)).fetchall()
   return {'simulation':True,'real_payments_enabled':False,'balances':balances,'transactions':[dict(r) for r in rows]}
 raise ValueError('Unknown demo route')

def post(server,uid,action,b):
 now=int(time.time());key=text(b.get('client_id',''),80,True);fingerprint=hashlib.sha256(json.dumps({'action':action,'body':b},sort_keys=True).encode()).hexdigest()
 with server.db() as d:
  d.execute('BEGIN IMMEDIATE');__import__('market_connections').expire(d)
  old=d.execute('SELECT * FROM market_operations WHERE uid=? AND key=?',(uid,key)).fetchone()
  if old:
   if old['fingerprint']!=fingerprint:raise ValueError('Retry key already used for different content')
   return json.loads(old['result'])
  if action in ('demo_deposit','demo_withdraw'):
   currency=b.get('currency');minor=amount(b.get('price'),currency)
   factor=1 if currency=='JPY' else 100
   if minor<=0 or minor>1_000_000*factor:raise ValueError('Choose a demo amount between zero and 1,000,000 currency units')
   if d.execute('SELECT count(*) FROM market_demo_journals WHERE actor=? AND created>?',(uid,now-3600)).fetchone()[0]>=100:raise ValueError('Demo transaction rate limit reached')
   if action=='demo_deposit':
    if balance(d,'available:'+uid,currency)+minor>10_000_000*factor:raise ValueError('Demo balance limit reached')
    journal=book(d,uid,'demo_deposit',currency,minor,'simulation:source','available:'+uid)
   else:journal=book(d,uid,'demo_withdraw',currency,minor,'available:'+uid,'simulation:sink')
   result={'ok':True,'simulation':True,'journal':journal}
  elif action=='demo_order_create':
   o=offer_view(d,uid,b.get('offer'));r=d.execute('SELECT * FROM market_reservations WHERE offer=?',(o['id'],)).fetchone()
   if uid!=o['buyer'] or o['state']!='ACCEPTED' or not r:raise ValueError('An accepted, reserved offer is required')
   existing=d.execute('SELECT id FROM market_demo_orders WHERE offer=?',(o['id'],)).fetchone()
   if existing:raise ValueError('This offer already has a demo order')
   ident=uuid.uuid4().hex;d.execute("INSERT INTO market_demo_orders VALUES(?,?,?,?,?,?,?,'CREATED',1,?,?)",(ident,o['id'],o['listing'],o['buyer'],o['seller'],o['amount_minor'],o['currency'],now,now));d.execute('UPDATE market_reservations SET expires=? WHERE offer=?',(9223372036854770000,o['id']))
   d.execute("INSERT INTO market_demo_order_events(order_id,actor,action,created) VALUES(?,?,'CREATED',?)",(ident,uid,now));emit(d,o['seller'],'orders','Demo order created — no real payment',{'order':ident,'event':'demo_created'});result={'ok':True,'simulation':True,'id':ident}
  elif action=='demo_order_action':
   from market import is_admin
   admin=is_admin(d,uid);o=order_view(d,uid,b.get('id'),admin);ident=o['id'];operation=b.get('action');reason=text(b.get('reason',''),500)
   if b.get('revision')!=o['revision']:raise ValueError('Demo order changed. Reopen it.')
   buyer=uid==o['buyer'];seller=uid==o['seller'];state=o['state'];held='held:'+ident;available='available:'+o['buyer'];target='available:'+o['seller'];journal=None
   if operation=='secure' and buyer and state=='CREATED':journal=book(d,uid,'demo_hold',o['currency'],o['amount_minor'],available,held,ident);new='SECURED'
   elif operation=='fulfill' and seller and state=='SECURED':new='FULFILLING'
   elif operation=='deliver' and seller and state=='FULFILLING':new='DELIVERED'
   elif operation=='confirm' and buyer and state=='DELIVERED':journal=book(d,uid,'demo_release',o['currency'],o['amount_minor'],held,target,ident);new='RELEASED'
   elif operation=='cancel' and buyer and state=='CREATED':new='CANCELLED'
   elif operation=='dispute' and (buyer or seller) and state in ('SECURED','FULFILLING','DELIVERED') and reason:new='DISPUTED'
   elif operation=='refund' and seller and state in ('SECURED','FULFILLING','DELIVERED','DISPUTED') and reason:journal=book(d,uid,'demo_refund',o['currency'],o['amount_minor'],held,available,ident);new='REFUNDED'
   elif operation in ('resolve_refund','resolve_release') and admin and state=='DISPUTED' and reason:
    journal=book(d,uid,'demo_'+operation,o['currency'],o['amount_minor'],held,available if operation=='resolve_refund' else target,ident);new='REFUNDED' if operation=='resolve_refund' else 'RELEASED'
   else:raise ValueError('That action is not authorized for the current demo order state; disputes/refunds require a reason')
   d.execute('UPDATE market_demo_orders SET state=?,revision=revision+1,updated=? WHERE id=?',(new,now,ident));d.execute('INSERT INTO market_demo_order_events(order_id,actor,action,reason,created) VALUES(?,?,?,?,?)',(ident,uid,new,reason,now))
   if new in ('RELEASED','REFUNDED','CANCELLED'):
    reservation=d.execute('SELECT * FROM market_reservations WHERE offer=?',(o['offer'],)).fetchone()
    if reservation:release(d,reservation)
    if new!='RELEASED':d.execute("UPDATE market_offers SET state='CANCELLED',revision=revision+1 WHERE id=?",(o['offer'],))
    if new=='RELEASED':d.execute("UPDATE market_ads SET status='sold' WHERE id=?",(o['listing'],));d.execute("UPDATE market_listing_meta SET state='SOLD',revision=revision+1,updated=? WHERE id=?",(now,o['listing']))
   for target_uid in (o['buyer'],o['seller']):emit(d,target_uid,'orders','Demo order '+new.lower()+' — simulated funds only',{'order':ident,'event':'demo_'+new.lower()})
   result={'ok':True,'simulation':True,'id':ident,'state':new,'journal':journal}
  else:raise ValueError('Unknown demo action')
  d.execute('INSERT INTO market_operations VALUES(?,?,?,?)',(uid,key,fingerprint,json.dumps(result)));return result
