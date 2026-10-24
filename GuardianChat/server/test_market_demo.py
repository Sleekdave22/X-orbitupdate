import unittest,urllib.error,uuid,sqlite3
from concurrent.futures import ThreadPoolExecutor
import test_market_pilot

class MarketDemoTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register;shop=test_market_pilot.MarketPilotTest.shop;body=test_market_pilot.MarketPilotTest.body;save=test_market_pilot.MarketPilotTest.save
 def post(self,u,endpoint,**b):return self.call('/market/'+endpoint,dict(client_id=uuid.uuid4().hex,**b),u['token'])
 def prepare(self):
  a=self.shop();b=self.register('Buyer');i=self.save(a,self.body())['id'];o=self.post(b,'offer_create',listing=i,price='100000')['id'];self.post(a,'offer_action',id=o,action='accept',revision=1);order=self.post(b,'demo_order_create',offer=o)['id'];return a,b,i,order
 def step(self,u,order,operation):
  o=self.call('/market/demo_order?id='+order,token=u['token'])['order'];return self.post(u,'demo_order_action',id=order,action=operation,revision=o['revision'])
 def wallet(self,u):return self.call('/market/demo_wallet',token=u['token'])
 def test_delivery_requires_buyer_confirmation_and_isolated_ledger(self):
  a,b,i,o=self.prepare()
  with self.server.db() as d:before={t:[tuple(r) for r in d.execute('SELECT * FROM '+t)] for t in ['fin_accounts','fin_journals','fin_postings']}
  self.post(b,'demo_deposit',currency='NGN',price='200000');self.step(b,o,'secure');self.step(a,o,'fulfill');self.step(a,o,'deliver')
  self.assertEqual(self.wallet(a)['balances'][0]['available_minor'],0);self.assertEqual(self.wallet(b)['balances'][0]['held_minor'],10000000)
  with self.assertRaises(urllib.error.HTTPError):self.step(a,o,'confirm')
  self.step(b,o,'confirm');self.assertEqual(self.wallet(a)['balances'][0]['available_minor'],10000000);self.assertEqual(self.wallet(b)['balances'][0]['held_minor'],0)
  self.assertEqual(self.call('/market/listing?id='+i,token=b['token'])['listing']['state'],'SOLD')
  with self.server.db() as d:
   self.assertEqual(before,{t:[tuple(r) for r in d.execute('SELECT * FROM '+t)] for t in before})
   self.assertEqual([r[0] for r in d.execute('SELECT sum(amount) FROM market_demo_postings GROUP BY journal')],[0,0,0])
 def test_funding_and_order_actions_idempotent_and_concurrency_safe(self):
  a,b,i,o=self.prepare();body={'currency':'NGN','price':'200000','client_id':'fund'}
  with ThreadPoolExecutor(2) as p:results=list(p.map(lambda _:self.call('/market/demo_deposit',body,b['token']),range(2)))
  self.assertEqual(results[0]['journal'],results[1]['journal']);self.assertEqual(self.wallet(b)['balances'][0]['available_minor'],20000000)
  def secure(n):
   try:self.call('/market/demo_order_action',{'id':o,'revision':1,'action':'secure','client_id':'secure-'+str(n)},b['token']);return True
   except urllib.error.HTTPError:return False
  with ThreadPoolExecutor(2) as p:results=list(p.map(secure,range(2)))
  self.assertEqual(results.count(True),1);self.assertEqual(self.wallet(b)['balances'][0]['available_minor'],10000000)
  self.assertFalse(self.wallet(b)['real_payments_enabled'])
 def test_insufficient_demo_balance_and_immutable_postings(self):
  a,b,i,o=self.prepare()
  with self.assertRaises(urllib.error.HTTPError):self.step(b,o,'secure')
  self.post(b,'demo_deposit',currency='NGN',price='1')
  for sql in ['UPDATE market_demo_journals SET kind=\'changed\'','DELETE FROM market_demo_journals','UPDATE market_demo_postings SET amount=1','DELETE FROM market_demo_postings']:
   with self.assertRaises(sqlite3.IntegrityError):
    with self.server.db() as d:d.execute(sql)
  self.assertEqual(self.wallet(b)['balances'][0]['available_minor'],100)
  with self.assertRaises(urllib.error.HTTPError):self.post(b,'demo_withdraw',currency='NGN',price='2')
 def test_dispute_controlled_refund_and_private_order_access(self):
  a,b,i,o=self.prepare();c=self.register('Other');self.post(b,'demo_deposit',currency='NGN',price='100000');self.step(b,o,'secure');self.post(b,'demo_order_action',id=o,action='dispute',reason='Demo item not as described',revision=2)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/demo_order?id='+o,token=c['token'])
  with self.assertRaises(urllib.error.HTTPError):self.post(c,'demo_order_action',id=o,action='resolve_refund',reason='Review',revision=3)
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(c['id'],))
  self.post(c,'demo_order_action',id=o,action='resolve_refund',reason='Reviewed demo evidence; refund',revision=3)
  self.assertEqual(self.wallet(b)['balances'][0]['available_minor'],10000000);self.assertEqual(self.wallet(a)['balances'][0]['available_minor'],0)
  self.assertEqual(self.call('/market/listing?id='+i,token=b['token'])['listing']['state'],'ACTIVE')
  with self.assertRaises(urllib.error.HTTPError):self.post(c,'demo_order_action',id=o,action='resolve_release',reason='Repeated',revision=4)

if __name__=='__main__':unittest.main()
