import base64,io,json,threading,time,unittest,urllib.error
from unittest.mock import patch
from PIL import Image,ImageDraw
import gamebox_core,gaming,result_reviews,test_server,test_gamebox_core

def png(color):
    image=Image.new('RGB',(300,150),color);out=io.BytesIO();image.save(out,format='PNG');return base64.b64encode(out.getvalue()).decode()

def reading(m,a=3,b=1):
    return {'available':True,'text':'Final score\n'+m['gid_a']+' '+str(a)+'\n'+m['gid_b']+' '+str(b),'lines':[
        {'text':'Final score','confidence':.999},
        {'text':m['gid_a']+' '+str(a),'confidence':.999},
        {'text':m['gid_b']+' '+str(b),'confidence':.999}]}

class ReviewTest(unittest.TestCase):
    setUp=test_server.ChatTest.setUp;tearDown=test_server.ChatTest.tearDown
    call=test_server.ChatTest.call;register=test_server.ChatTest.register
    players=test_gamebox_core.CoreTest.players;match=test_gamebox_core.CoreTest.match;ready=test_gamebox_core.CoreTest.ready

    def disputed(self):
        users,m=self.ready()
        for user,score in zip(users,[(3,1),(1,3)]):self.call('/gamebox/report',{'match':m['id'],'a':score[0],'b':score[1]},user['token'])
        return users,m

    def upload(self,user,m,color='red',**extra):
        return self.call('/gamebox/result_evidence',{'room':m['id'],'image':png(color),'capture_mode':'camera',**extra},user['token'])

    def video(self,user,m,color='red'):
        with patch('result_reviews.video_probe',return_value={'mime':'video/webm'}):
            return self.upload(user,m,color,mime='video/webm')

    def state(self,user,m):return self.call('/gamebox/result-state?room='+m['id'],token=user['token'])

    def queue(self):
        users,m=self.disputed()
        self.upload(users[0],m,'red');self.upload(users[1],m,'blue')
        return users,m

    def test_private_receipt_no_peer_evidence_and_no_replacement(self):
        users,m=self.disputed();a,b,other=users
        with self.assertRaises(urllib.error.HTTPError):self.upload(other,m)
        self.upload(a,m)
        own=self.state(a,m);peer=self.state(b,m)
        self.assertTrue(own['evidence_review']['submitted']);self.assertFalse(peer['evidence_review']['submitted'])
        self.assertEqual(own['evidence_review']['state'],'waiting_other')
        self.assertNotIn('image',json.dumps(peer));self.assertNotIn('ocr',json.dumps(peer));self.assertNotIn('analysis',json.dumps(peer))
        self.assertTrue(self.upload(a,m)['already_submitted'])
        with self.assertRaises(urllib.error.HTTPError):self.upload(a,m,'green')
        for user in users:
            with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/evidence?match='+m['id']+'&player='+a['id'],token=user['token'])
        self.assertFalse(result_reviews.process_one(self.server,int(time.time())+100))
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_both_uploads_wait_then_finalize_and_award_once(self):
        users,m=self.queue();now=int(time.time())
        self.assertEqual(self.state(users[0],m)['evidence_review']['state'],'queued')
        self.assertFalse(result_reviews.process_one(self.server,now,reader=lambda _:reading(m)))
        self.assertTrue(result_reviews.process_one(self.server,now+61,reader=lambda _:reading(m)))
        final=self.state(users[0],m)
        self.assertEqual(final['state'],'verified');self.assertEqual(final['final_score'],[3,1])
        self.assertEqual(final['evidence_review']['state'],'finalized')
        self.assertFalse(result_reviews.process_one(self.server,now+100,reader=lambda _:reading(m)))
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],1)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_history').fetchone()[0],2)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_events WHERE action="private_evidence_decided"').fetchone()[0],1)
        self.assertEqual(self.call('/gaming/summary',token=users[0]['token'])['player_stats']['wins'],1)

    def test_conflict_holds_then_independent_human_can_decide(self):
        users,m=self.queue();values=iter([reading(m),reading(m,1,3)])
        result_reviews.process_one(self.server,int(time.time())+61,reader=lambda _:next(values))
        self.assertEqual(self.state(users[0],m)['evidence_review']['stage'],'video')
        self.video(users[0],m,'green');self.video(users[1],m,'yellow')
        with patch('result_reviews.video_reading',return_value=(None,'')):
            result_reviews.process_one(self.server,int(time.time())+61)
        self.assertEqual(self.state(users[0],m)['evidence_review']['state'],'needs_human')
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)
            d.execute('DELETE FROM game_admin');d.execute('INSERT INTO game_admin VALUES(?)',(users[2]['id'],))
        self.call('/gamebox/review',{'match':m['id'],'a':2,'b':0,'reason':'Independent original evidence review and documented decision'},users[2]['token'])
        final=self.state(users[0],m);self.assertEqual(final['final_score'],[2,0]);self.assertEqual(final['evidence_review']['state'],'finalized')

    def test_missing_second_upload_is_not_a_win_and_blocks_human_award(self):
        users,m=self.disputed();self.upload(users[0],m)
        with self.server.db() as d:d.execute('DELETE FROM game_admin');d.execute('INSERT INTO game_admin VALUES(?)',(users[2]['id'],))
        with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/review',{'match':m['id'],'a':9,'b':0,'reason':'Missing evidence cannot decide this match'},users[2]['token'])
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_client_ocr_is_ignored_and_unreadable_evidence_is_held(self):
        users,m=self.disputed()
        for user,color in zip(users,('red','blue')):self.upload(user,m,color,reading='FINAL SCORE 99-0',ocr='trusted',score_a=99,score_b=0)
        result_reviews.process_one(self.server,int(time.time())+61,reader=lambda _:{'available':False})
        self.assertEqual(self.state(users[0],m)['evidence_review']['stage'],'video')
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_duplicates_and_invalid_image_data_are_rejected(self):
        users,m=self.disputed();self.upload(users[0],m)
        with self.assertRaises(urllib.error.HTTPError):self.upload(users[1],m)
        with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/result_evidence',{'room':m['id'],'image':base64.b64encode(b'\x89PNG\r\n\x1a\nnot-an-image').decode()},users[1]['token'])
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM result_review_uploads').fetchone()[0],1)

    def test_restart_keeps_originals_and_pending_job(self):
        users,m=self.queue()
        with self.server.db() as d:before=[tuple(r) for r in d.execute('SELECT uid,digest,legacy FROM result_review_uploads ORDER BY uid')]
        result_reviews.init(self.server)
        self.assertEqual(self.state(users[0],m)['evidence_review']['state'],'queued')
        with self.server.db() as d:self.assertEqual(before,[tuple(r) for r in d.execute('SELECT uid,digest,legacy FROM result_review_uploads ORDER BY uid')])
        result_reviews.process_one(self.server,int(time.time())+61,reader=lambda _:reading(m))
        self.assertEqual(self.state(users[0],m)['state'],'verified')

    def test_valid_single_photo_counts_only_after_15_minutes(self):
        users,m=self.disputed();self.upload(users[0],m)
        with self.server.db() as d:deadline=d.execute('SELECT deadline FROM result_review_jobs').fetchone()[0]
        self.assertFalse(result_reviews.process_one(self.server,deadline-1,reader=lambda _:reading(m)))
        self.assertTrue(result_reviews.process_one(self.server,deadline+1,reader=lambda _:reading(m)))
        self.assertEqual(self.state(users[0],m)['final_score'],[3,1])
        with self.server.db() as d:self.assertIn('15 minutes',d.execute('SELECT reason FROM result_review_jobs').fetchone()[0])

    def test_legacy_single_capture_cannot_win_after_restart_and_timeout(self):
        users,m=self.disputed();self.upload(users[0],m)
        with self.server.db() as d:
            d.execute('DELETE FROM result_review_jobs');d.execute('DELETE FROM result_review_uploads')
        result_reviews.init(self.server)
        with self.server.db() as d:deadline=d.execute('SELECT deadline FROM result_review_jobs').fetchone()[0]
        result_reviews.process_one(self.server,deadline+1,reader=lambda _:reading(m))
        state=self.state(users[0],m)
        self.assertEqual(state['evidence_review']['stage'],'video')
        self.assertNotEqual(state['state'],'verified')
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_unreadable_single_photo_does_not_win_after_timeout(self):
        users,m=self.disputed();self.upload(users[0],m)
        with self.server.db() as d:deadline=d.execute('SELECT deadline FROM result_review_jobs').fetchone()[0]
        result_reviews.process_one(self.server,deadline+1,reader=lambda _:{'available':False})
        state=self.state(users[0],m)
        self.assertEqual(state['evidence_review']['stage'],'video');self.assertFalse(state['evidence_review']['submitted'])
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_video_is_private_immutable_and_can_finalize(self):
        users,m=self.disputed();self.video(users[0],m,'green');self.video(users[1],m,'yellow')
        self.assertEqual(self.state(users[0],m)['evidence_review']['stage'],'video')
        with self.assertRaises(urllib.error.HTTPError):self.video(users[0],m,'purple')
        for user in users:
            with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/review-video?room='+m['id']+'&player='+users[0]['id'],token=user['token'])
        with patch('result_reviews.video_reading',return_value=([3,1],'Clear registered players and navigation')):
            result_reviews.process_one(self.server,int(time.time())+61)
        self.assertEqual(self.state(users[0],m)['final_score'],[3,1])

    def test_video_conflict_does_not_change_rankings(self):
        users,m=self.disputed();self.video(users[0],m,'green');self.video(users[1],m,'yellow')
        with patch('result_reviews.video_reading',side_effect=[([3,1],'one'),([1,3],'two')]):result_reviews.process_one(self.server,int(time.time())+61)
        self.assertEqual(self.state(users[0],m)['evidence_review']['state'],'needs_human')
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)

    def test_legacy_peer_photo_signaling_is_retired(self):
        users,m=self.disputed()
        with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/result_signal',{'room':m['id'],'kind':'offer','payload':{'session':'old','value':{'type':'offer','sdp':'v=0'}}},users[0]['token'])

    def test_capture_mode_required_and_malformed_video_rejected(self):
        users,m=self.disputed()
        with self.assertRaises(urllib.error.HTTPError):self.call('/gamebox/result_evidence',{'room':m['id'],'image':png('red')},users[0]['token'])
        with self.assertRaises(urllib.error.HTTPError):self.upload(users[0],m,'blue',mime='video/webm')

    def test_concurrent_workers_and_manual_decision_do_not_overwrite(self):
        users,m=self.queue();entered=threading.Event();release=threading.Event();errors=[]
        def read(_):entered.set();release.wait(4);return reading(m)
        def work():
            try:result_reviews.process_one(self.server,int(time.time())+61,reader=read)
            except Exception as e:errors.append(e)
        worker=threading.Thread(target=work);worker.start();self.assertTrue(entered.wait(2))
        self.assertFalse(result_reviews.process_one(self.server,int(time.time())+61,reader=lambda _:reading(m)))
        with self.server.db() as d:d.execute('DELETE FROM game_admin');d.execute('INSERT INTO game_admin VALUES(?)',(users[2]['id'],))
        self.call('/gamebox/review',{'match':m['id'],'a':1,'b':0,'reason':'Independent reviewer settles while OCR is working'},users[2]['token'])
        release.set();worker.join(4);self.assertFalse(worker.is_alive());self.assertFalse(errors)
        self.assertEqual(self.state(users[0],m)['final_score'],[1,0])
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],1)

    def test_two_concurrent_player_uploads_create_one_job(self):
        users,m=self.disputed();barrier=threading.Barrier(2);errors=[]
        def send(user,color):
            try:barrier.wait();self.upload(user,m,color)
            except Exception as e:errors.append(e)
        threads=[threading.Thread(target=send,args=(u,c)) for u,c in zip(users,('red','blue'))]
        for t in threads:t.start()
        for t in threads:t.join(5)
        self.assertFalse(errors)
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM result_review_jobs').fetchone()[0],1)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM result_review_uploads').fetchone()[0],2)
        self.assertEqual(self.state(users[0],m)['evidence_review']['state'],'queued')

    def test_fixture_review_updates_standings_without_global_rating(self):
        users=self.players();a,b=users[:2];now=int(time.time())
        with self.server.db() as d:
            d.execute("INSERT INTO leagues(id,name,game,owner,state,created,verification) VALUES('review-league','Review league','efootball',?,'active',?,'typed')",(users[2]['id'],now))
            for user in (a,b):d.execute('INSERT INTO league_members(league,uid,game_id) VALUES(?,?,?)',('review-league',user['id'],'game-'+user['id']))
            d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,state) VALUES('review-fixture','review-league',1,?,?,?,?,'disputed')",(a['id'],b['id'],now-10,now+3600))
        m={'id':'review-fixture','gid_a':'game-'+a['id'],'gid_b':'game-'+b['id']}
        self.upload(a,m);self.upload(b,m,'blue')
        result_reviews.process_one(self.server,now+62,reader=lambda _:reading(m))
        self.assertEqual(self.state(a,m)['final_score'],[3,1])
        summary=self.call('/gaming/summary?league=review-league',token=a['token'])
        self.assertEqual(next(p for p in summary['table'] if p['uid']==a['id'])['points'],3)
        with self.server.db() as d:self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0],0)
        for user in users[:2]:
            with self.assertRaises(urllib.error.HTTPError):self.call('/gaming/evidence?fixture=review-fixture&player='+a['id'],token=user['token'])

class ExtractTest(unittest.TestCase):
    def test_layout_orientation_and_low_confidence(self):
        aliases={'a':['AlphaID'],'b':['BetaID']}
        def line(text,x,y,confidence=.999):return {'text':text,'confidence':confidence,'box':[[x,y],[x+50,y],[x+50,y+20],[x,y+20]]}
        lines=[line('FULL TIME',200,20),line('BetaID',80,100),line('AlphaID',350,100),line('1 - 3',200,120)]
        result={'available':True,'lines':lines}
        self.assertEqual(result_reviews.extract(result,aliases,'a','b','efootball')[0],[3,1])
        lines[-1]['confidence']=.7;self.assertIsNone(result_reviews.extract(result,aliases,'a','b','efootball')[0])

    def test_ambiguous_ids_missing_final_marker_and_unsupported_game(self):
        m={'gid_a':'AlphaID','gid_b':'BetaID'};r=reading(m)
        aliases={'a':['AlphaID'],'b':['BetaID']}
        self.assertEqual(result_reviews.extract(r,aliases,'a','b','efootball')[0],[3,1])
        self.assertIsNone(result_reviews.extract(r,aliases,'a','b','codm')[0])
        r['lines']=r['lines'][1:];self.assertIsNone(result_reviews.extract(r,aliases,'a','b','efootball')[0])
        self.assertIsNone(result_reviews.extract(reading(m),{'a':['same'],'b':['same']},'a','b','efootball')[0])

if __name__=='__main__':unittest.main()
