import base64,io,time,unittest,urllib.error
from concurrent.futures import ThreadPoolExecutor
from PIL import Image
import test_server,market

class MarketPilotTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call;register=test_server.ChatTest.register
 def shop(self):
  a=self.register('Seller');self.call('/market/register',{'shop_name':'Pilot Store'},a['token']);return a
 def body(self,**kw):
  raw=io.BytesIO();Image.new('RGB',(30,20),'blue').save(raw,'PNG')
  return dict(title='Samsung Galaxy S21 Ultra',description='Black phone 256 GB, used carefully',category_id='electronics',subcategory='Phones',price='125000.50',currency='NGN',condition='used',country='NG',city='Lagos',availability='in_stock',attributes={'brand':'Samsung','model':'S21 Ultra','storage':'256GB','color':'black'},delivery=['pickup'],state='ACTIVE',images=[{'data':base64.b64encode(raw.getvalue()).decode()}],client_id='create-'+str(time.time_ns()),**kw)
 def save(self,u,b):return self.call('/market/save_listing',b,u['token'])
 def listing(self,u,i):return self.call('/market/listing?id='+i,token=u['token'])['listing']
 def test_catalog_and_cross_account_persistence_images_store(self):
  a=self.shop();b=self.register('Buyer');r=self.save(a,self.body());v=self.listing(b,r['id']);self.assertEqual(v['amount_minor'],12500050);self.assertEqual(v['currency'],'NGN');self.assertEqual(v['state'],'ACTIVE')
  self.assertEqual(len(self.call('/market/catalog',token=b['token'])['categories']),12)
  im=self.call('/market/image?id='+v['images'][0],token=b['token']);self.assertEqual(im['mime'],'image/jpeg');self.assertTrue(base64.b64decode(im['data']).startswith(b'\xff\xd8'))
  store=self.call('/market/store?id='+a['id'],token=b['token']);self.assertFalse(store['seller']['verified']);self.assertIsNone(store['seller']['reviews']);self.assertEqual(store['listings'][0]['id'],r['id'])
  market.init(self.server);market.init(self.server);self.assertEqual(self.listing(b,r['id'])['title'],v['title'])
 def test_draft_and_image_access_private_to_owner(self):
  a=self.shop();b=self.register('Buyer');body=self.body();body['state']='DRAFT';r=self.save(a,body);v=self.listing(a,r['id'])
  self.assertEqual(self.call('/market/listings',token=b['token'])['listings'],[])
  for path in ['/market/listing?id='+r['id'],'/market/image?id='+v['images'][0]]:
   with self.assertRaises(urllib.error.HTTPError):self.call(path,token=b['token'])
  self.assertEqual(self.call('/market/store?id='+a['id'],token=b['token'])['listings'],[])
 def test_owner_revision_and_listing_lifecycle(self):
  a=self.shop();b=self.register('Buyer');body=self.body();r=self.save(a,body);i=r['id'];edit=body|{'id':i,'revision':1,'title':'Samsung S21 Ultra updated'}
  with self.assertRaises(urllib.error.HTTPError):self.save(b,edit)
  self.save(a,edit)
  with self.assertRaises(urllib.error.HTTPError):self.save(a,edit)
  self.call('/market/listing_state',{'id':i,'revision':2,'state':'PAUSED'},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.listing(b,i)
  with self.server.db() as d:d.execute('UPDATE market_ads SET expires=1 WHERE id=?',(i,))
  self.call('/market/listing_state',{'id':i,'revision':3,'state':'ACTIVE'},a['token']);self.assertEqual(self.listing(b,i)['state'],'ACTIVE')
  self.call('/market/listing_state',{'id':i,'revision':4,'state':'SOLD'},a['token']);self.assertEqual(self.listing(b,i)['state'],'SOLD')
  self.assertEqual(self.call('/market/listings',token=b['token'])['listings'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/listing_state',{'id':i,'revision':5,'state':'REMOVED'},a['token'])
  self.call('/market/listing_state',{'id':i,'revision':5,'state':'REMOVED','confirmed':True},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.listing(b,i)
 def test_bad_images_money_attributes_and_duplicates_rejected(self):
  a=self.shop()
  for change in [{'images':[{'data':base64.b64encode(b'not image').decode()}]},{'images':[]},{'price':'NaN'},{'price':'1.001'},{'country':'ZZ'},{'currency':'ZZZ'},{'attributes':{'unsafe':'x'}},{'subcategory':'unknown'},{'delivery':[]}]:
   with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body()|change)
  self.save(a,self.body())
  with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body())
 def test_create_idempotency_under_concurrency(self):
  a=self.shop();body=self.body()
  with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:self.save(a,body),range(2)))
  self.assertEqual(results[0]['id'],results[1]['id']);self.assertEqual(len(self.call('/market/mine',token=a['token'])['listings']),1)
  with self.assertRaises(urllib.error.HTTPError):self.save(a,body|{'title':'Different request'})
 def test_legacy_routes_and_moderation_remain_coherent(self):
  a=self.shop();b=self.register('Buyer');legacy=self.call('/market/post_ad',{'title':'Legacy item','price':'Ask seller','category':'Gaming'},a['token'])['id'];v=self.listing(b,legacy);self.assertTrue(v['legacy']);self.assertIsNone(v['amount_minor']);self.assertEqual(v['price'],'Ask seller')
  modern=self.save(a,self.body())['id'];self.call('/market/remove_ad',{'id':modern},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.listing(b,modern)
  item=self.save(a,self.body()|{'title':'Other Samsung phone'})['id']
  reporters=[b,self.register('Other1'),self.register('Other2')]
  for p in reporters:self.call('/market/report',{'id':item,'reason':'Policy review'},p['token'])
  self.assertEqual(self.listing(a,item)['state'],'PENDING_REVIEW')
  with self.assertRaises(urllib.error.HTTPError):self.listing(b,item)
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(b['id'],))
  self.call('/market/admin_restore',{'id':item},b['token']);self.assertEqual(self.listing(b,item)['state'],'ACTIVE')

if __name__=='__main__':unittest.main()
