import unittest,urllib.error,time
from collections import Counter
import test_server,result_reviews
from server import account_qr
class GamingTest(unittest.TestCase):
 setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown;call=test_server.ChatTest.call;registerBase=test_server.ChatTest.register
 def call(self,path,body=None,token=''):
  result=test_server.ChatTest.call(self,path,body,token)
  if path=='/gaming/profile' and body and body.get('adult') is True:
   # Competition fixtures now explicitly register their per-game identity.
   owner=test_server.ChatTest.call(self,'/profile',token=token)['id']
   with self.server.db() as d:exists=d.execute('SELECT 1 FROM gb_game_ids WHERE uid=? AND game=?',(owner,'efootball')).fetchone()
   if not exists:test_server.ChatTest.call(self,'/gamebox/identity',{'game':'efootball','game_id':body['game_id'],'region':'Nigeria','tz':'Africa/Lagos','availability':[]},token)
  return result
 def register(self,name):
  user=self.registerBase(name)
  with self.server.db() as d:
   if not d.execute('SELECT 1 FROM game_admin').fetchone():d.execute('INSERT INTO game_admin VALUES(?)',(user['id'],))
  return user
 def league(self):
  us=[self.register('Player'+str(n)) for n in range(9)]
  with self.server.db() as d:d.execute('DELETE FROM game_admin');d.execute('INSERT INTO game_admin VALUES(?)',(us[0]['id'],))
  for u in us:self.call('/gaming/profile',{'tag':u['name'],'game_id':'player-'+u['id'],'adult':True,'feature':True,'handle':'@'+u['name']},u['token'])
  l=self.call('/gaming/create',{'name':'Test division','game':'efootball'},us[0]['token'])['id']
  with self.server.db() as d:d.execute("UPDATE leagues SET verification='legacy' WHERE id=?",(l,))
  for u in us[:8]:self.call('/gaming/join',{'league':l},u['token'])
  self.call('/gaming/moderator',{'league':l,'identity':us[8]['id']},us[0]['token']);self.call('/gaming/start',{'league':l},us[0]['token']);return us,l
 def view(self,l,u):return self.call('/gaming/summary?league='+l,token=u['token'])
 def result(self,f,us,l):
  users={u['id']:u for u in us}
  for uid in (f['a'],f['b']):self.call('/gamebox/result_evidence',{'room':f['id'],'image':account_qr(f['id']+uid),'capture_mode':'camera'},users[uid]['token'])
  with self.server.db() as d:
   gids={r['uid']:r['game_id'] for r in d.execute('SELECT uid,game_id FROM league_members WHERE league=?',(l,))}
  reading={'available':True,'text':'Final score','lines':[{'text':'Final score','confidence':.999},{'text':gids[f['a']]+' 3','confidence':.999},{'text':gids[f['b']]+' 1','confidence':.999}]}
  result_reviews.process_one(self.server,int(time.time())+61,reader=lambda _:reading)
 def test_scheduler_and_capacity(self):
  us,l=self.league();fs=self.view(l,us[0])['fixtures'];self.assertEqual(len(fs),28);self.assertEqual(len({tuple(sorted((f['a'],f['b']))) for f in fs}),28);self.assertEqual(set(Counter(p for f in fs for p in (f['a'],f['b'])).values()),{7})
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/join',{'league':l},us[8]['token'])
 def test_pending_permissions_and_confirmation(self):
  us,l=self.league();f=next(f for f in self.view(l,us[0])['fixtures'] if us[0]['id'] not in (f['a'],f['b']));users={u['id']:u for u in us};self.call('/gamebox/result_evidence',{'room':f['id'],'image':account_qr(f['id']+f['a']),'capture_mode':'camera'},users[f['a']]['token']);self.assertTrue(all(r['points']==0 for r in self.view(l,us[0])['table']))
  stranger=next(u for u in us[:8] if u['id'] not in (f['a'],f['b'],us[0]['id']))
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/evidence?fixture='+f['id']+'&player='+f['a'],token=stranger['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/confirm',{'league':l,'fixture':f['id']},stranger['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/confirm',{'league':l,'fixture':f['id']},users[f['b']]['token'])
  self.result(f,us,l);self.assertEqual(self.view(l,us[0])['table'][0]['points'],3)
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/confirm',{'league':l,'fixture':f['id']},users[f['b']]['token'])
 def test_dispute_review(self):
  us,l=self.league();f=next(f for f in self.view(l,us[0])['fixtures'] if us[0]['id'] not in (f['a'],f['b']));users={u['id']:u for u in us};self.call('/gamebox/result_evidence',{'room':f['id'],'image':account_qr(f['id']),'capture_mode':'camera'},users[f['a']]['token']);self.call('/gaming/dispute',{'league':l,'fixture':f['id'],'reason':'Wrong score shown'},users[f['b']]['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/confirm',{'league':l,'fixture':f['id']},users[f['b']]['token'])
  self.call('/gamebox/result_evidence',{'room':f['id'],'image':account_qr(f['id']+'other'),'capture_mode':'camera'},users[f['b']]['token'])
  self.call('/gaming/review',{'league':l,'fixture':f['id'],'score_a':2,'score_b':1,'reason':'Checked screenshot and both players'},us[0]['token']);self.assertEqual(next(x for x in self.view(l,us[0])['fixtures'] if x['id']==f['id'])['state'],'confirmed')
 def test_complete_final_and_consent(self):
  us,l=self.league()
  with self.server.db() as d:d.execute('UPDATE fixtures SET opens=0 WHERE league=?',(l,))
  for f in self.view(l,us[0])['fixtures']:self.result(f,us,l)
  self.call('/gaming/finals',{'league':l},us[0]['token'])
  for f in [f for f in self.view(l,us[0])['fixtures'] if f['stage']=='semi']:self.result(f,us,l)
  final=next(f for f in self.view(l,us[0])['fixtures'] if f['stage']=='final');self.result(final,us,l);state=self.view(l,us[0]);self.assertEqual(state['league']['state'],'finished');self.assertEqual(len(state['champions']),1);u=next(u for u in us if u['id']==state['league']['champion']);self.call('/gaming/profile',{'tag':u['name'],'game_id':'gamer','adult':True,'feature':False},u['token']);self.assertEqual(self.view(l,u)['champions'],[])
 def test_age_auth_and_sponsor_url(self):
  a=self.register('Adult')
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/profile',{'tag':'gamer','game_id':'id','adult':False},a['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/summary')
  us,l=self.league()
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/sponsor',{'league':l,'sponsor':'Brand','url':'javascript:alert(1)'},us[0]['token'])
 def test_reward_requires_funding_and_freezes_after_start(self):
  a=self.register('Organiser');self.call('/gaming/profile',{'tag':'organiser','game_id':'gamer','adult':True},a['token']);l=self.call('/gaming/create',{'name':'Reward test','game':'efootball'},a['token'])['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/sponsor',{'league':l,'reward':'10000 NGN','funded':False},a['token'])
  self.call('/gaming/sponsor',{'league':l,'reward':'10000 NGN','funded':True},a['token'])
  with self.server.db() as d:d.execute("UPDATE leagues SET state='active' WHERE id=?",(l,))
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/sponsor',{'league':l,'reward':'No prize','funded':True},a['token'])
 def test_duplicate_screenshot_is_rejected(self):
  us,l=self.league();fs=self.view(l,us[0])['fixtures'][:2];users={u['id']:u for u in us};proof=account_qr('same-proof')
  self.call('/gaming/report',{'league':l,'fixture':fs[0]['id'],'score_a':2,'score_b':1,'image':proof,'capture_mode':'camera'},users[fs[0]['a']]['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/report',{'league':l,'fixture':fs[1]['id'],'score_a':2,'score_b':1,'image':proof,'capture_mode':'camera'},users[fs[1]['a']]['token'])
 def test_organiser_cannot_approve_own_match(self):
  us,l=self.league();f=next(f for f in self.view(l,us[0])['fixtures'][:4] if us[0]['id'] in (f['a'],f['b']));users={u['id']:u for u in us};self.call('/gaming/report',{'league':l,'fixture':f['id'],'score_a':2,'score_b':1,'image':account_qr(f['id']),'capture_mode':'camera'},users[f['a']]['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/review',{'league':l,'fixture':f['id'],'score_a':2,'score_b':1,'reason':'I approve myself'},us[0]['token'])
 def test_static_gaming_page_does_not_require_bearer(self):
  page=self.call('/gaming.html');self.assertIn(b'OrbitPlay',page)
 def test_snapshot_game_ids_survive_profile_changes(self):
  us,l=self.league();u=us[1];original='player-'+u['id'];self.call('/gaming/profile',{'tag':'Changed','game_id':'new-id','adult':True},u['token']);f=next(f for f in self.view(l,u)['fixtures'] if u['id'] in (f['a'],f['b']));self.assertEqual(f['game_ids'][u['id']],original)

 def test_cup_slots_and_automatic_advancement(self):
  us=[self.register('Cup'+str(n)) for n in range(8)]
  for u in us:self.call('/gaming/profile',{'tag':u['name'],'game_id':'cup-'+u['id'],'adult':True},u['token'])
  l=self.call('/gaming/create',{'name':'Cup test','game':'efootball','format':'cup'},us[0]['token'])['id']
  for n,u in enumerate(us,1):self.assertEqual(self.call('/gaming/join',{'league':l},u['token'])['slot'],n)
  self.assertEqual(self.call('/gaming/join',{'league':l},us[0]['token'])['slot'],1)
  self.assertEqual(len(self.view(l,us[0])['slots']),8)
  with self.server.db() as d:d.execute("UPDATE leagues SET verification='legacy' WHERE id=?",(l,))
  self.call('/gaming/start',{'league':l},us[0]['token'])
  q=self.view(l,us[0])['fixtures'];self.assertEqual(len(q),4);self.assertEqual((q[0]['a'],q[0]['b']),(us[0]['id'],us[1]['id']))
  for f in q:self.result(f,us,l)
  semis=[f for f in self.view(l,us[0])['fixtures'] if f['stage']=='semi'];self.assertEqual(len(semis),2)
  for f in semis:self.result(f,us,l)
  final=[f for f in self.view(l,us[0])['fixtures'] if f['stage']=='final'];self.assertEqual(len(final),1);self.result(final[0],us,l)
  summary=self.view(l,us[0]);self.assertEqual(summary['league']['champion'],us[0]['id']);self.assertEqual(summary['league']['state'],'finished')

 def test_match_room_comments_and_closed_room(self):
  us,l=self.league();f=self.view(l,us[0])['fixtures'][0]
  self.call('/gaming/comment',{'league':l,'fixture':f['id'],'text':'Good luck!'},us[8]['token'])
  r=self.call('/gaming/room?fixture='+f['id'],token=us[0]['token']);self.assertEqual(r['comments'][0]['text'],'Good luck!');self.assertTrue(r['active'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/room?fixture='+f['id'])
  self.result(f,us,l)
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/comment',{'league':l,'fixture':f['id'],'text':'Late comment'},us[8]['token'])
 def test_weekly_sponsor_art_and_profile_picture_consent(self):
  us,l=self.league();avatar=account_qr('rank-picture')
  self.call('/profile',{'name':us[0]['name'],'nickname':'player0','avatar':avatar,'avatar_mime':'image/png'},us[0]['token'])
  table=self.view(l,us[1])['table'];self.assertEqual(next(r for r in table if r['uid']==us[0]['id'])['avatar'],avatar)
  self.call('/gaming/profile',{'tag':us[0]['name'],'game_id':'player-'+us[0]['id'],'adult':True,'feature':False},us[0]['token'])
  self.assertEqual(next(r for r in self.view(l,us[1])['table'] if r['uid']==us[0]['id'])['avatar'],'')
  self.assertEqual(next(r for r in self.view(l,us[0])['table'] if r['uid']==us[0]['id'])['avatar'],avatar)
  self.call('/gaming/sponsor',{'league':l,'sponsor':'GuardianLab','week':'2026-W42','art':avatar},us[0]['token'])
  league=self.view(l,us[0])['league'];self.assertEqual(league['sponsor_week'],'2026-W42');self.assertTrue(league['sponsor_art'].startswith('data:image/png;base64,'))
 def test_admin_scoping_and_comment_audit(self):
  us,l=self.league();f=self.view(l,us[0])['fixtures'][0]
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/admin',token=us[1]['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/admin?league='+l,token=us[1]['token'])
  self.call('/gaming/comment',{'league':l,'fixture':f['id'],'text':'Test moderation'},us[1]['token'])
  admin=self.call('/gaming/admin?league='+l,token=us[0]['token']);cid=admin['comments'][0]['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/hide_comment',{'league':l,'comment':cid,'reason':'Test reason'},us[1]['token'])
  self.call('/gaming/hide_comment',{'league':l,'comment':cid,'reason':'Test reason'},us[0]['token'])
  self.assertEqual(self.call('/gaming/room?fixture='+f['id'],token=us[1]['token'])['comments'],[])
  audit=self.call('/gaming/admin?league='+l,token=us[0]['token']);self.assertTrue(audit['comments'][0]['hidden']);self.assertIn('comment_hidden',[r['action'] for r in audit['audit']])
 def test_stats_and_three_up_three_down(self):
  us,l=self.league()
  with self.server.db() as d:
   d.execute('UPDATE fixtures SET opens=0 WHERE league=?',(l,));d.execute('UPDATE leagues SET tier=1 WHERE id=?',(l,))
   for u in us[:8]:d.execute('INSERT INTO game_qualification VALUES(?,?,1)',(u['id'],'efootball'))
  for f in self.view(l,us[0])['fixtures']:self.result(f,us,l)
  self.call('/gaming/finals',{'league':l},us[0]['token'])
  for f in [f for f in self.view(l,us[0])['fixtures'] if f['stage']=='semi']:self.result(f,us,l)
  final=next(f for f in self.view(l,us[0])['fixtures'] if f['stage']=='final');self.result(final,us,l)
  state=self.view(l,us[0]);self.assertEqual(state['stats']['promotions'],3);self.assertEqual(state['stats']['relegations'],3)
  for i,r in enumerate(state['table']):
   u=next(u for u in us if u['id']==r['uid']);v=self.view(l,u);self.assertEqual(v['qualification']['efootball'],2 if i<3 else 0 if i>=5 else 1);self.assertEqual(len(v['player_stats']['last_five']),5)
  self.assertEqual(state['stats']['confirmed_matches'],31)
  profile=self.call('/profile',token=us[0]['token']);self.assertGreaterEqual(profile['gaming_stats']['played'],7)
 def test_stream_room_is_private_and_signal_only(self):
  a=self.register('Admin');b=self.register('Viewer');c=self.register('Stranger')
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_create',{'identity':a['id']},b['token'])
  rid=self.call('/gaming/stream_create',{'identity':b['id']},a['token'])['id']
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream-signals?room='+rid,token=b['token'])
  self.call('/gaming/stream_accept',{'room':rid},b['token'])
  self.call('/gaming/stream_begin',{'room':rid},a['token'])
  self.call('/gaming/stream_signal',{'room':rid,'kind':'offer','payload':{'target':b['id'],'value':{'type':'offer','sdp':'test'}}},a['token'])
  self.assertEqual(len(self.call('/gaming/stream-signals?room='+rid,token=b['token'])['signals']),1)
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream-signals?room='+rid,token=c['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_signal',{'room':rid,'kind':'end','payload':{}},c['token'])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_comment',{'room':rid,'text':'Unauthorized'},c['token'])
  self.call('/gaming/stream_invite',{'room':rid,'identity':c['id']},a['token'])
  self.call('/gaming/stream_accept',{'room':rid},c['token'])
  self.call('/gaming/stream_comment',{'room':rid,'text':'Nice stream'},c['token'])
  for _ in range(2):self.call('/gaming/stream_like',{'room':rid},c['token'])
  result=self.call('/gaming/stream-signals?room='+rid,token=c['token'])
  self.assertEqual(result['likes'],1);self.assertEqual(result['comments'][0]['text'],'Nice stream');self.assertEqual(result['signals'],[])
  with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_invite',{'room':rid,'identity':a['id']},c['token'])
  self.assertEqual(self.call('/gaming/summary',token=b['token'])['stats']['confirmed_matches'],0)
 def test_stream_cleanup_and_cumulative_viewers(self):
  a=self.register('Broadcaster');b=self.register('Audience')
  for expected in (1,2):
   rid=self.call('/gaming/stream_create',{'identity':b['id']},a['token'])['id']
   self.call('/gaming/stream_accept',{'room':rid},b['token'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_comment',{'room':rid,'text':'Too early'},b['token'])
   self.call('/gaming/stream_begin',{'room':rid},a['token'])
   for _ in range(3):self.call('/gaming/stream_watch',{'room':rid},b['token'])
   self.call('/gaming/stream_watch',{'room':rid},a['token'])
   live=self.call('/gaming/stream-signals?room='+rid,token=b['token'])['live']
   self.assertEqual(live['viewers'],1);self.assertEqual(live['session_viewers'],1)
   self.call('/gaming/stream_comment',{'room':rid,'text':'Ephemeral'},b['token'])
   self.call('/gaming/stream_like',{'room':rid},b['token'])
   for _ in range(6):self.call('/gaming/stream_react',{'room':rid,'emoji':'❤️'},b['token'])
   with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_react',{'room':rid,'emoji':'❤️'},b['token'])
   reactions=self.call('/gaming/stream-signals?room='+rid,token=b['token'])['reactions'];self.assertEqual(len(reactions),6);self.assertEqual(set(reactions[0]),{'id','emoji'})
   with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream_end',{'room':rid},b['token'])
   self.call('/gaming/stream_end',{'room':rid},a['token'])
   self.call('/gaming/stream_end',{'room':rid},a['token'])
   self.assertEqual(__import__('live_reactions').read(rid),[])
   summary=self.call('/gaming/summary',token=a['token'])
   self.assertEqual(summary['player_stats']['stream_viewers'],expected)
   with self.server.db() as d:
    for table in ('game_stream_comments','game_stream_likes','game_stream_signals','game_stream_members','game_stream_responses','live_viewers','live_sessions'):
     self.assertEqual(d.execute('SELECT COUNT(*) FROM '+table+' WHERE room=?',(rid,)).fetchone()[0],0)
   with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/stream-signals?room='+rid,token=b['token'])
 def test_stream_expiry_cleans_abandoned_session(self):
  import stream_lifecycle
  a=self.register('Host');b=self.register('Guest')
  rid=self.call('/gaming/stream_create',{'identity':b['id']},a['token'])['id']
  self.call('/gaming/stream_accept',{'room':rid},b['token'])
  self.call('/gaming/stream_begin',{'room':rid},a['token'])
  self.call('/gaming/stream_watch',{'room':rid},b['token'])
  with self.server.db() as d:d.execute('UPDATE live_sessions SET heartbeat=0 WHERE room=?',(rid,))
  stream_lifecycle.expire(self.server);stream_lifecycle.expire(self.server)
  self.assertEqual(self.call('/gaming/summary',token=a['token'])['stream_viewers'],1)
if __name__=='__main__':unittest.main()
