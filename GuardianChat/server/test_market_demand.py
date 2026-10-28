import time,threading,unittest,urllib.error,json
from concurrent.futures import ThreadPoolExecutor
import test_market_pilot as fixture
import market_demand,market_connections,account_notifications

class DemandTest(unittest.TestCase):
 setUp=fixture.MarketPilotTest.setUp;tearDown=fixture.MarketPilotTest.tearDown;call=fixture.MarketPilotTest.call;register=fixture.MarketPilotTest.register;body=fixture.MarketPilotTest.body;save=fixture.MarketPilotTest.save
 def request(self,u,title='Samsung Galaxy S21 Ultra',**kw):
  b={'title':title,'description':'Looking for '+title,'category_id':'electronics','listing_type':'PRODUCT','client_id':'demand-'+str(time.time_ns())}|kw
  return self.call('/market/demand_request',b,u['token'])
 def seller(self,opt=True):
  u=self.register('Seller');self.call('/market/register',{'shop_name':'Demand Store'},u['token'])
  if opt:self.call('/market/demand_preferences',{'updates':True,'categories':['electronics']},u['token'])
  return u
 def work(self):
  market_demand.maintenance(self.server);market_demand.maintenance(self.server)
 def admin(self):
  u=self.register('Moderator')
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(u['id'],))
  return u
 def test_five_distinct_accounts_synonyms_and_unresolved_notice_dedupe(self):
  seller=self.seller();buyers=[self.register('Buyer'+str(i)) for i in range(5)]
  for u,title in zip(buyers,['mobile','handset','phone','cellphone','fone']):r=self.request(u,title,description='I need a phone')
  self.work()
  feed=self.call('/market/demands',token=buyers[0]['token'])
  self.assertEqual(len(feed['demands']),1);self.assertEqual(feed['demands'][0]['requesters'],5);self.assertTrue(feed['demands'][0]['hot'])
  self.request(buyers[0],'phone',description='I need a phone');self.work()
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND section='demand'",(seller['id'],)).fetchone()[0],1)
 def test_categories_types_and_model_numbers_do_not_overmerge(self):
  u=self.register('Buyer')
  a=self.request(u,'S21 phone');b=self.request(u,'S22 phone');c=self.request(u,'S21 phone',category_id='other')
  self.assertEqual(len({a['id'],b['id'],c['id']}),3)
  with self.server.db() as d:self.assertFalse(market_demand.compatible(['phone','21'],['phone','22']))
 def test_atomic_retry_and_changed_retry_body(self):
  u=self.register('Buyer');body={'title':'phone','description':'phone','category_id':'electronics','client_id':'same'}
  with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(lambda _:self.call('/market/demand_request',body,u['token']),range(4)))
  self.assertEqual(len({r['id'] for r in results}),1)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT count(*) FROM market_demand_requests WHERE uid=?',(u['id'],)).fetchone()[0],1)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/demand_request',body|{'title':'Laptop'},u['token'])
 def test_withdrawal_is_owner_scoped_and_resolution_changes_group(self):
  a=self.register('A');b=self.register('B');r=self.request(a)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/demand_withdraw',{'id':r['id']},b['token'])
  self.call('/market/demand_withdraw',{'id':r['id']},a['token'])
  self.assertEqual(self.call('/market/demands',token=a['token'])['demands'],[])
  self.assertNotEqual(self.request(a)['id'],r['id'])
 def test_opt_in_category_and_restriction_targeting(self):
  seller=self.seller(False);other=self.register('Other seller');self.call('/market/register',{'shop_name':'Other Store'},other['token'])
  self.call('/market/demand_preferences',{'updates':True,'categories':['fashion']},other['token'])
  for i in range(5):self.request(self.register('Buyer'+str(i)),'phone')
  self.work()
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE section='demand'").fetchone()[0],0)
  self.call('/market/demand_preferences',{'updates':True,'categories':['electronics']},seller['token']);self.work()
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND section='demand'",(seller['id'],)).fetchone()[0],1)
 def test_only_available_published_listings_notify_buyers_once(self):
  seller=self.seller();buyer=self.register('Buyer');r=self.request(buyer)
  body=self.body();body['state']='DRAFT';listing=self.save(seller,body);self.work()
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND section='demand'",(buyer['id'],)).fetchone()[0],0)
  self.call('/market/listing_state',{'id':listing['id'],'revision':1,'state':'ACTIVE'},seller['token']);self.work()
  with self.server.db() as d:
   records=d.execute("SELECT * FROM account_activity WHERE uid=? AND section='demand'",(buyer['id'],)).fetchall()
   self.assertEqual(len(records),1);self.assertEqual(json.loads(records[0]['target'])['listing'],listing['id']);market_demand.enqueue(d,'listing',listing['id'])
  self.work()
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND section='demand'",(buyer['id'],)).fetchone()[0],1)
 def test_admin_policy_roles_validation_and_audit(self):
  u=self.register('User');admin=self.admin();body={'policy':{'threshold':3,'daily_push_limit':2},'reason':'Start a small pilot'}
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/admin_demand',body,u['token'])
  self.call('/market/admin_demand',body,admin['token'])
  self.assertEqual(self.call('/market/admin',token=admin['token'])['demand_policy']['threshold'],3)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/admin_demand',body|{'policy':{'threshold':1,'daily_push_limit':20}},admin['token'])
  with self.server.db() as d:self.assertEqual(d.execute("SELECT count(*) FROM market_admin_audit WHERE action='admin_demand'").fetchone()[0],1)
 def test_rate_limits_invalid_inputs_and_no_requester_identity_disclosure(self):
  u=self.register('User')
  for title in ['Camera','Phone','Keyboard']:self.request(u,title)
  with self.assertRaises(urllib.error.HTTPError):self.request(u,'Laptop')
  with self.assertRaises(urllib.error.HTTPError):self.request(u,'Phone',category_id=['electronics'])
  result=self.call('/market/demands',token=u['token']);self.assertNotIn(u['id'],json.dumps(result))
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/demand_preferences',{'updates':True,'categories':[]},u['token'])
 def test_push_limit_two_per_day_and_all_opportunities_stay_in_app(self):
  seller=self.seller();buyers=[self.register('Buyer'+str(i)) for i in range(5)]
  for title in ['Phone','Camera','Keyboard']:
   for u in buyers:self.request(u,title)
  self.work();self.call('/push/register',{'push_token':'demand-fake-'+'a'*45},seller['token'])
  class Fake:
   enabled=True
   def __init__(self):self.events=[]
   def send(self,token,data):self.events.append(data)
  fake=Fake();self.server.push=fake;market_connections.dispatch(self.server)
  for _ in range(200):
   if not getattr(self.server,'market_push_busy',False):break
   time.sleep(.01)
  self.assertEqual(len(fake.events),2)
  with self.server.db() as d:
   self.assertEqual(d.execute("SELECT count(*) FROM account_activity WHERE uid=? AND section='demand'",(seller['id'],)).fetchone()[0],3)
   self.assertEqual(d.execute('SELECT count(*) FROM market_demand_push_budget WHERE uid=?',(seller['id'],)).fetchone()[0],2)
 def test_single_push_worker_under_concurrent_maintenance(self):
  user=self.register('User');self.call('/push/register',{'push_token':'race-fake-'+'b'*45},user['token'])
  with self.server.db() as d:account_notifications.add(d,user['id'],'market','shop','Example event',{})
  class Fake:
   enabled=True
   def __init__(self):self.events=[]
   def send(self,token,data):time.sleep(.1);self.events.append(data)
  fake=Fake();self.server.push=fake
  with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda _:market_connections.dispatch(self.server),range(16)))
  for _ in range(200):
   if not getattr(self.server,'market_push_busy',False):break
   time.sleep(.01)
  self.assertEqual(len(fake.events),1)
 def test_indexes_and_retry_jobs_survive_transient_failure(self):
  u=self.register('User');r=self.request(u)
  with self.server.db() as d:
   plan=' '.join(x['detail'] for x in d.execute('EXPLAIN QUERY PLAN SELECT count(*) FROM market_demand_requests WHERE group_id=? AND active=1 AND expires>?',(r['id'],0)))
   self.assertIn('market_demand_members',plan)
  from unittest.mock import patch
  with patch('market_demand.hot',side_effect=RuntimeError('temporary')):self.work()
  with self.server.db() as d:self.assertEqual(d.execute('SELECT attempts FROM market_demand_jobs WHERE item=?',(r['id'],)).fetchone()[0],1)

 def test_every_eligible_requester_gets_private_ad_link_and_push_without_hot_threshold(self):
  seller=self.seller(False)
  first,second,withdrawn,blocked,unrelated=[self.register(name) for name in ('First','Second','Withdrawn','Blocked','Unrelated')]
  request=self.request(first)
  for buyer in (second,withdrawn,blocked):self.request(buyer)
  self.request(unrelated,'Laptop')
  self.call('/market/demand_withdraw',{'id':request['id']},withdrawn['token'])
  self.call('/social/block',{'target':seller['id']},blocked['token'])
  self.assertFalse(self.call('/market/demand?id='+request['id'],token=first['token'])['demand']['hot'])
  self.call('/push/register',{'push_token':'buyer-fake-'+'c'*45},first['token'])
  listing=self.save(seller,self.body())['id'];self.work()
  notices={}
  for buyer in (first,second,withdrawn,blocked,unrelated):
   feed=self.call('/market/activity',token=buyer['token'])
   matches=[n for n in feed['notifications'] if n['target'].get('event')=='demand_listing']
   self.assertEqual(len(matches),int(buyer in (first,second)))
   if matches:notices[buyer['id']]=matches[0]
  notice=notices[first['id']]
  self.assertEqual(notice['target'],{'demand':request['id'],'event':'demand_listing','listing':listing})
  detail=self.call('/market/activity_item?id='+str(notice['id']),token=first['token'])
  self.assertEqual(detail['notification']['target']['listing'],listing)
  self.assertEqual(self.call('/market/listing?id='+listing,token=first['token'])['listing']['id'],listing)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/activity_item?id='+str(notice['id']),token=unrelated['token'])
  class Fake:
   enabled=True
   def __init__(self):self.events=[]
   def send(self,token,data):self.events.append((token,data))
  fake=Fake();self.server.push=fake;market_connections.dispatch(self.server)
  for _ in range(200):
   if not getattr(self.server,'market_push_busy',False):break
   time.sleep(.01)
  self.assertEqual(len(fake.events),1)
  self.assertEqual(fake.events[0][1]['recipient'],first['id'])
  self.assertEqual(fake.events[0][1]['notice_id'],str(notice['id']))
  self.assertEqual(fake.events[0][1]['event'],'market_notice')
  # Editing an advert must not repeat the match alert; a different advert may.
  edit=self.body()|{'id':listing,'revision':1,'title':'Samsung Galaxy S21 Ultra available'}
  self.save(seller,edit);self.work()
  self.assertEqual(len([n for n in self.call('/market/activity',token=first['token'])['notifications'] if n['section']=='demand']),1)
  self.save(seller,self.body()|{'title':'Another Samsung Galaxy S21 Ultra'});self.work()
  self.assertEqual(len([n for n in self.call('/market/activity',token=first['token'])['notifications'] if n['section']=='demand']),2)

 def test_review_unavailable_and_expired_listings_do_not_alert_requesters(self):
  import market_admin
  seller=self.seller(False);buyer=self.register('Buyer');admin=self.admin();self.request(buyer)
  config=dict(market_admin.DEFAULTS)|{'review_required':True}
  self.call('/market/admin_config',{'config':config,'reason':'Review before publication'},admin['token'])
  listing=self.save(seller,self.body())['id'];self.work()
  self.assertEqual([n for n in self.call('/market/activity',token=buyer['token'])['notifications'] if n['section']=='demand'],[])
  self.call('/market/admin_restore',{'id':listing,'reason':'Publication approved'},admin['token']);self.work()
  self.assertEqual(len([n for n in self.call('/market/activity',token=buyer['token'])['notifications'] if n['section']=='demand']),1)
  self.call('/market/admin_config',{'config':dict(market_admin.DEFAULTS),'reason':'Return to pilot defaults'},admin['token'])
  self.save(seller,self.body()|{'title':'Unavailable Samsung Galaxy S21 Ultra','availability':'unavailable'})
  expired=self.save(seller,self.body()|{'title':'Expired Samsung Galaxy S21 Ultra'})['id']
  with self.server.db() as d:d.execute('UPDATE market_ads SET expires=1 WHERE id=?',(expired,))
  self.work()
  self.assertEqual(len([n for n in self.call('/market/activity',token=buyer['token'])['notifications'] if n['section']=='demand']),1)
