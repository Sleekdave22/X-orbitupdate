import unittest,urllib.error
import test_market_pilot,market_admin

class MarketAdminTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register;shop=test_market_pilot.MarketPilotTest.shop;body=test_market_pilot.MarketPilotTest.body;save=test_market_pilot.MarketPilotTest.save
 def admin(self):
  u=self.register('Moderator')
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(u['id'],))
  return u
 def test_roles_configuration_review_and_legacy_cannot_bypass(self):
  a=self.shop();m=self.admin();cfg=dict(market_admin.DEFAULTS)|{'review_required':True,'max_new_hour':2}
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/admin',token=a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/admin_config',{'config':cfg,'reason':'Policy'},a['token'])
  self.call('/market/admin_config',{'config':cfg,'reason':'Review pilot listings'},m['token']);i=self.save(a,self.body())['id']
  self.assertEqual(self.call('/market/listing?id='+i,token=a['token'])['listing']['state'],'PENDING_REVIEW')
  legacy=self.call('/market/post_ad',{'title':'Legacy advert','category':'Gaming'},a['token'])['id']
  self.assertEqual(self.call('/market/listing?id='+legacy,token=a['token'])['listing']['state'],'PENDING_REVIEW')
  self.call('/market/admin_restore',{'id':i,'reason':'Inspected product image and details'},m['token']);self.assertEqual(self.call('/market/listing?id='+i,token=a['token'])['listing']['state'],'ACTIVE')
  with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body()|{'title':'One too many'})
  audit=self.call('/market/admin',token=m['token'])['audit'];self.assertEqual({a['action'] for a in audit},{'admin_config','admin_restore'})
 def test_stable_categories_synonyms_restrictions_featured_and_audit(self):
  a=self.shop();m=self.admin();i=self.save(a,self.body())['id'];self.call('/market/admin_feature',{'id':i,'featured':True,'reason':'Selected for pilot'},m['token'])
  self.assertEqual(self.call('/market/listing?id='+i,token=a['token'])['listing']['featured'],1)
  cat={'id':'collectibles','name':'Collectibles','icon':'📦','subcategories':['Cards','Art'],'attributes':['year','condition_note'],'enabled':True,'reason':'New pilot category'}
  self.call('/market/admin_category',cat,m['token']);self.assertIn('collectibles',[c['id'] for c in self.call('/market/catalog',token=a['token'])['categories']])
  self.call('/market/admin_synonym',{'term':'smartphone','replacement':'phone','reason':'Buyer vocabulary'},m['token'])
  self.assertEqual(self.call('/market/listings?q=smartphone',token=a['token'])['total'],1)
  self.call('/market/admin_seller',{'uid':a['id'],'restricted':True,'reason':'Review repeated reports'},m['token'])
  self.assertEqual(self.call('/market/listings',token=m['token'])['listings'],[]);self.assertEqual(self.call('/market/ads',token=m['token'])['ads'],[])
  with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body()|{'title':'Another listing'})
  self.call('/market/admin_seller',{'uid':a['id'],'restricted':False,'reason':'Review cleared'},m['token']);self.assertEqual(self.call('/market/listings',token=m['token'])['total'],1)
  self.assertEqual(len(self.call('/market/admin',token=m['token'])['audit']),5)
 def test_notifications_setting_and_shipping_codes(self):
  a=self.shop();m=self.admin();cfg=dict(market_admin.DEFAULTS)|{'notifications_enabled':False};self.call('/market/admin_config',{'config':cfg,'reason':'Pilot notification pause'},m['token'])
  with self.assertRaises(urllib.error.HTTPError):self.save(a,self.body()|{'delivery':['shipping'],'delivery_regions':['ZZ']})
  i=self.save(a,self.body()|{'delivery':['shipping'],'delivery_regions':['NG','GH']})['id'];self.assertEqual(self.call('/market/listing?id='+i,token=m['token'])['listing']['delivery_regions'],['NG','GH'])
  self.assertEqual(self.call('/market/activity',token=a['token'])['unread'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/admin_config',{'config':cfg,'reason':''},m['token'])

if __name__=='__main__':unittest.main()
