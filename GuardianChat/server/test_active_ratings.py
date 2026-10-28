"""Current ranking contracts; legacy test_rating.py is retained for migration review."""
import unittest,time,uuid
import test_phase_b as fixture
import rankings,gamebox_core

class ActiveRatingTest(unittest.TestCase):
 setUp=fixture.PhaseBTest.setUp;tearDown=fixture.PhaseBTest.tearDown;call=fixture.PhaseBTest.call
 user=fixture.PhaseBTest.user;identity=fixture.PhaseBTest.identity;rated=fixture.PhaseBTest.rated;rank=fixture.PhaseBTest.rank
 def players(self):
  a,b=self.user('Alpha'),self.user('Beta');self.identity(a);self.identity(b);return a,b
 def test_equal_verified_win_and_loss(self):
  a,b=self.players();self.rated(a,b)
  self.assertEqual(self.rank(a)['my_rank']['rating'],1512);self.assertEqual(self.rank(b)['my_rank']['rating'],1488)
 def test_equal_draw_does_not_move_rating(self):
  a,b=self.players();self.rated(a,b,score=(2,2));self.assertEqual(self.rank(a)['my_rank']['rating'],1500)
 def test_underdog_win_changes_more(self):
  a,b=self.players()
  with self.server.db() as d:d.execute("INSERT INTO gb_ratings(uid,game,rating) VALUES(?,'efootball',1000)",(a['id'],));d.execute("INSERT INTO gb_ratings(uid,game,rating) VALUES(?,'efootball',1400)",(b['id'],))
  self.rated(a,b);self.assertGreater(self.rank(a)['my_rank']['rating']-1000,12)
 def test_favorite_win_changes_less(self):
  a,b=self.players()
  with self.server.db() as d:d.execute("INSERT INTO gb_ratings(uid,game,rating) VALUES(?,'efootball',1400)",(a['id'],));d.execute("INSERT INTO gb_ratings(uid,game,rating) VALUES(?,'efootball',1000)",(b['id'],))
  self.rated(a,b);self.assertLess(self.rank(a)['my_rank']['rating']-1400,12)
 def test_game_specific_records_remain_separate(self):
  a,b=self.players();self.identity(a,'fc_mobile');self.identity(b,'fc_mobile');self.rated(a,b)
  self.assertEqual(self.rank(a,'fc_mobile')['my_rank']['rating'],1500)
 def test_verified_award_is_once_only(self):
  a,b=self.players();mid=self.rated(a,b)
  with self.server.db() as d:
   r=dict(d.execute('SELECT * FROM gb_matches WHERE id=?',(mid,)).fetchone());before=[tuple(x) for x in d.execute('SELECT * FROM gb_rank_history')]
   self.assertIsNone(rankings.award(d,'open',r|{'score_a':99}));self.assertEqual([tuple(x) for x in d.execute('SELECT * FROM gb_rank_history')],before)
 def test_unverified_result_cannot_award(self):
  a,b=self.players();mid=uuid.uuid4().hex
  with self.server.db() as d:
   version=gamebox_core.current(d);d.execute("INSERT INTO gb_matches(id,game,a,b,gid_a,gid_b,state,created,deadline,version,rules) VALUES(?,?,?,?,?,?,'awaiting_results',?,?,?,?)",(mid,'efootball',a['id'],b['id'],'a','b',int(time.time()),int(time.time())+3600,version['id'],version['config']))
   with self.assertRaises(ValueError):rankings.award(d,'open',{'id':mid,'a':a['id'],'b':b['id']})
   self.assertEqual(d.execute('SELECT count(*) FROM gb_rank_awards').fetchone()[0],0)
 def test_competition_fixture_does_not_change_global_rating(self):
  a,b=self.players()
  with self.server.db() as d:
   self.assertIsNone(rankings.award(d,'fixture',{'id':'fixture','a':a['id'],'b':b['id']}));self.assertEqual(d.execute('SELECT count(*) FROM gb_rank_awards').fetchone()[0],0)
 def test_current_defaults_and_provisional_visibility(self):
  a,b=self.players();self.rated(a,b);r=self.rank(a)['my_rank'];self.assertTrue(r['provisional']);self.assertIsNone(r['grade']);self.assertEqual(r['placement_required'],10)
  p=self.call('/rankings/policy',token=a['token']);self.assertEqual(p['config']['k'],24);self.assertEqual(len(p['config']['grades']),6)
