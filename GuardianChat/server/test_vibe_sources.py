import concurrent.futures, time, unittest, urllib.error
from unittest.mock import patch
import test_market_pilot, test_phase_b, vibe_sources, vibes

class UnifiedVibeTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register
 shop=test_market_pilot.MarketPilotTest.shop;body=test_market_pilot.MarketPilotTest.body;save=test_market_pilot.MarketPilotTest.save
 user=test_phase_b.PhaseBTest.user;identity=test_phase_b.PhaseBTest.identity;rated=test_phase_b.PhaseBTest.rated
 def share(self,u,kind,source,**extra):return self.call('/vibe/share',dict(kind=kind,source=source,visibility='public',client_id='share-'+str(time.time_ns()))|extra,u['token'])
 def test_market_journey_source_reference_follow_inquiry_and_expiration(self):
  seller=self.shop();buyer=self.register('Buyer');listing=self.save(seller,self.body())['id'];post=self.share(seller,'market',listing)
  with self.server.db() as d:
   self.assertEqual(d.execute('SELECT media FROM vibe_items WHERE id=?',(post['id'],)).fetchone()[0],b'')
   self.assertEqual(d.execute('SELECT source FROM vibe_links WHERE item=?',(post['id'],)).fetchone()[0],listing)
  media=self.call('/vibe/media?id='+post['id'],token=buyer['token']);self.assertEqual(media['source']['title'],'Samsung Galaxy S21 Ultra');self.assertTrue(media['source']['image']);self.assertEqual(media['relationship'],'none')
  self.call('/vibe/view',{'id':post['id']},buyer['token']);self.call('/social/follow',{'target':seller['id']},buyer['token'])
  self.assertEqual(self.call('/social/profile?id='+seller['id'],token=buyer['token'])['relationship'],'accepted')
  for _ in range(2):self.assertEqual(self.call('/market/inquiry',{'id':listing},buyer['token'])['state'],'accepted')
  with self.server.db() as d:
   self.assertEqual(d.execute('SELECT COUNT(*) FROM market_inquiries WHERE buyer=? AND listing=?',(buyer['id'],listing)).fetchone()[0],1)
   d.execute('UPDATE vibe_items SET expires=1 WHERE id=?',(post['id'],))
  vibes.purge(self.server)
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+post['id'],token=buyer['token'])
  self.assertEqual(self.call('/market/listing?id='+listing,token=buyer['token'])['listing']['state'],'ACTIVE')
 def test_listing_status_cannot_leak_and_no_photo_legacy_card(self):
  seller=self.shop();viewer=self.register('Viewer');listing=self.call('/market/post_ad',{'title':'Legacy item','price':'Ask seller','category':'Gaming'},seller['token'])['id'];post=self.share(seller,'market',listing)
  self.assertFalse(self.call('/vibe/media?id='+post['id'],token=viewer['token'])['source']['image'])
  modern=self.save(seller,self.body())['id'];v=self.share(seller,'market',modern)
  self.call('/market/listing_state',{'id':modern,'revision':1,'state':'SOLD'},seller['token'])
  self.assertFalse(self.call('/vibe/media?id='+v['id'],token=viewer['token'])['source']['can_message'])
  self.call('/market/listing_state',{'id':modern,'revision':2,'state':'REMOVED','confirmed':True},seller['token'])
  source=self.call('/vibe/media?id='+v['id'],token=viewer['token'])['source'];self.assertFalse(source['available']);self.assertNotIn('title',source.get('private',{}));self.assertNotIn('image',source)
 def test_private_audience_ownership_and_concurrent_deduplication(self):
  seller=self.shop();a=self.register('Alice');b=self.register('Bob');listing=self.save(seller,self.body())['id']
  body=dict(kind='market',source=listing,visibility='private',audience=[a['id']],client_id='retry-share-1')
  with concurrent.futures.ThreadPoolExecutor(2) as pool:r=list(pool.map(lambda _:self.call('/vibe/share',body,seller['token']),range(2)))
  self.assertEqual(r[0]['id'],r[1]['id']);again=self.call('/vibe/share',body|{'client_id':'other-device'},seller['token']);self.assertEqual(again['id'],r[0]['id'])
  for changed in [body|{'audience':[b['id']]},body|{'visibility':'public'}]:
   with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/share',changed,seller['token'])
  for url in ['/vibe/preview?id=','/vibe/media?id=']:
   with self.assertRaises(urllib.error.HTTPError):self.call(url+r[0]['id'],token=a['token'])
  self.assertTrue(self.call('/vibe/media?id='+r[0]['id']+'&protected=1',token=a['token'])['source']['available'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+r[0]['id']+'&protected=1',token=b['token'])
  with self.assertRaises(urllib.error.HTTPError):self.share(a,'market',listing)
  self.call('/social/block',{'target':a['id']},seller['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/media?id='+r[0]['id']+'&protected=1',token=a['token'])
 def test_linked_expiry_is_24h_and_same_second_upload_order_is_insertion_order(self):
  a=self.shop();first=self.save(a,self.body())['id'];second=self.save(a,self.body()|{'title':'Another phone'})['id']
  self.call('/vibe/preferences',{'public_hours':12,'private_hours':48},a['token'])
  now=int(time.time())
  with patch('time.time',return_value=now):
   x=self.share(a,'market',first);y=self.share(a,'market',second)
   self.assertEqual(y['expires'],now+86400)
   feed=self.call('/vibe/feed',token=a['token']);self.assertEqual([r['id'] for r in feed['groups'][0]['items']],[x['id'],y['id']])
 def test_gaming_profile_privacy_and_verified_milestones(self):
  a=self.user('Alpha');b=self.user('Beta');self.identity(a);self.identity(b)
  p=self.share(a,'profile',a['id'],game='efootball');self.assertEqual(self.call('/vibe/media?id='+p['id'],token=b['token'])['source']['gaming_id'],'game-'+a['id'])
  self.assertEqual(self.call('/vibe/prompts',token=a['token'])['prompts'],[])
  for _ in range(10):last=self.rated(a,b)
  prompts=self.call('/vibe/prompts',token=a['token'])['prompts'];self.assertEqual({r['title'] for r in prompts},{'Number 1','Top 10','Top 50','Top 100'})
  source=prompts[0];post=self.share(a,'milestone',source['source'],game='efootball');self.assertEqual(self.call('/vibe/media?id='+post['id'],token=b['token'])['source']['status'],'Ranking achievement')
  with self.server.db() as d:d.execute("UPDATE gb_matches SET state='disputed' WHERE id=?",(last,))
  self.assertFalse(self.call('/vibe/media?id='+post['id'],token=b['token'])['source']['available'])
  self.call('/social/settings',{'private':True,'discoverable':False,'bio':'','alerts':True},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.share(a,'profile',a['id'],game='efootball')
 def test_policy_requires_admin_and_personal_private_retry_keeps_audience(self):
  a=self.register('Alpha');b=self.register('Beta')
  with self.assertRaises(urllib.error.HTTPError):self.call('/vibe/milestone_policy',{'thresholds':[5],'reason':'New policy'},a['token'])
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(a['id'],))
  self.call('/vibe/milestone_policy',{'thresholds':[5,20],'reason':'Season launch thresholds'},a['token']);self.assertEqual(self.call('/vibe/milestone_policy',token=a['token'])['thresholds'],[5,20])
 def test_championship_validation_sharing_and_correction_preserve_original(self):
  import gaming,uuid
  a=self.user('Champion');b=self.user('Runner');self.identity(a);self.identity(b)
  with self.server.db() as d:d.execute('INSERT INTO game_admin VALUES(?)',(a['id'],))
  lid=self.call('/gaming/create',{'game':'efootball','name':'Vibe Championship'},a['token'])['id'];fid=uuid.uuid4().hex
  with self.server.db() as d:
   d.execute("INSERT INTO fixtures(id,league,round,a,b,state,score_a,score_b,stage) VALUES(?,?,9,?,?,'disputed',3,1,'final')",(fid,lid,a['id'],b['id']))
  self.assertEqual(self.call('/vibe/prompts',token=a['token'])['prompts'],[])
  with self.server.db() as d:
   d.execute("UPDATE fixtures SET state='confirmed' WHERE id=?",(fid,));league=dict(d.execute('SELECT * FROM leagues WHERE id=?',(lid,)).fetchone());gaming.advance(d,league)
  prompt=self.call('/vibe/prompts',token=a['token'])['prompts'][0];self.assertEqual(prompt['kind'],'trophy')
  post=self.share(a,'trophy',lid,game='efootball');media=self.call('/vibe/media?id='+post['id'],token=b['token']);self.assertEqual(media['source']['status'],'Verified trophy')
  self.assertEqual(len(self.call('/vibe/achievements?id='+a['id']+'&game=efootball',token=b['token'])['achievements']),1)
  with self.server.db() as d:d.execute('UPDATE leagues SET champion=? WHERE id=?',(b['id'],lid))
  self.assertFalse(self.call('/vibe/media?id='+post['id'],token=b['token'])['source']['available'])
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=1 WHERE id=?',(post['id'],))
  vibes.purge(self.server)
  with self.server.db() as d:self.assertEqual(d.execute('SELECT champion FROM leagues WHERE id=?',(lid,)).fetchone()[0],b['id'])
 def test_private_follow_requires_acceptance_and_profile_acl_remains_enforced(self):
  a=self.user('Private');b=self.user('Follower');self.identity(a);self.identity(b)
  self.call('/contacts',{'code':b['id']},a['token'])
  self.call('/social/settings',{'private':True,'discoverable':False,'bio':'','alerts':True},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.share(a,'profile',a['id'],game='efootball',visibility='private',audience=[b['id']])
  self.call('/social/follow',{'target':a['id']},b['token']);self.assertEqual(self.call('/social/profile?id='+a['id'],token=b['token'])['relationship'],'pending')
  self.call('/social/accept',{'target':b['id']},a['token'])
  post=self.share(a,'profile',a['id'],game='efootball',visibility='private',audience=[b['id']]);self.assertTrue(self.call('/vibe/media?id='+post['id']+'&protected=1',token=b['token'])['source']['available'])

if __name__=='__main__':unittest.main()
