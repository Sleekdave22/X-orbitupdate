import unittest,urllib.error
import test_market_pilot
from market_search import search

class MarketSearchTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register;shop=test_market_pilot.MarketPilotTest.shop;body=test_market_pilot.MarketPilotTest.body;save=test_market_pilot.MarketPilotTest.save
 def test_typo_word_order_attributes_synonyms_and_model_safeguards(self):
  a=self.shop();i=self.save(a,self.body())['id']
  for q in ['samsng s21 ultra','black 256 samsung','handset samsung','s21 used']:
   r=self.call('/market/listings?q='+q.replace(' ','%20'),token=a['token']);self.assertEqual([v['id'] for v in r['listings']],[i],q)
  r=self.call('/market/listings?q=samsng%20s21',token=a['token']);self.assertIn('samsung',r['interpretation']);self.assertFalse(r['semantic_enabled'])
  self.assertEqual(self.call('/market/listings?q=samsng&original=1',token=a['token'])['listings'],[])
  for q in ['s22 ultra','512 samsung','2013 samsung']:
   r=self.call('/market/listings?q='+q.replace(' ','%20'),token=a['token']);self.assertEqual(r['listings'],[]);self.assertEqual(r['related'],[])
  r=self.call('/market/listings?q=green%20samsung',token=a['token']);self.assertEqual(r['listings'],[]);self.assertEqual(len(r['related']),1)
 def test_locations_prices_and_preferences_are_account_scoped(self):
  a=self.shop();b=self.register('Buyer');self.save(a,self.body())
  self.call('/market/search_preferences',{'mode':'near','country':'NG','city':'Lagos'},b['token'])
  self.assertEqual(self.call('/market/listings',token=b['token'])['total'],1)
  self.assertEqual(self.call('/market/listings?location=near&country=NG&city=Abuja',token=b['token'])['total'],0)
  self.assertEqual(self.call('/market/listings?location=worldwide&country=US',token=b['token'])['total'],1)
  self.assertEqual(self.call('/market/listings?currency=NGN&max_price=100000',token=b['token'])['total'],0)
  self.assertEqual(self.call('/market/listings?currency=USD',token=b['token'])['total'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/listings?min_price=100',token=b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/search_preferences',{'mode':'near','country':'NG'},b['token'])
  self.assertEqual(self.call('/market/catalog',token=a['token'])['discovery'],{})
 def test_stable_pagination_and_budget_ranking(self):
  a=self.shop();template=self.body();items=[]
  for n in range(45):items.append(dict(id=str(n),title='HP gaming laptop',description='Portable notebook',attributes={'brand':'HP'},category='Computers',subcategory='Laptops',condition='used',shop_name='Store',nickname='seller',city='Lagos',country='NG',currency='NGN',amount_minor=(45-n)*100,category_id='computers',created=100+n))
  with self.server.db() as d:
   first=search(d,a['id'],items,{'q':['cheap gaming hp laptop']});second=search(d,a['id'],items,{'q':['cheap gaming hp laptop'],'offset':['20']})
  self.assertEqual(first['total'],45);self.assertTrue(first['more']);self.assertEqual(first['listings'][0]['id'],'44');self.assertFalse({v['id'] for v in first['listings']}&{v['id'] for v in second['listings']})

if __name__=='__main__':unittest.main()
