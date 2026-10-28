"""Real decoding and isolated HTTP checks for short evidence and appeal privacy."""

import base64
import io
import time
import unittest
import urllib.error
from unittest.mock import patch

import av
from PIL import Image

import result_retention
import result_reviews
import result_video
import test_media_processing as media
import test_result_reviews as previous


class ShortVideoTest(unittest.TestCase):
    """Use actual encoded clips; OCR accuracy is deliberately outside these tests."""

    def test_three_five_and_ten_second_clips_supply_three_distinct_samples(self):
        """No args/return; assert real short clips decode to proportional JPEGs."""
        for seconds in (3, 5, 10):
            with self.subTest(seconds=seconds):
                raw = media.movie(seconds, fps=10)
                result = result_reviews.inspect_video(raw, frames=True)
                self.assertAlmostEqual(result['duration'], seconds, places=2)
                self.assertEqual(len(result['frames']), 3)
                self.assertEqual(len(set(result['frames'])), 3)
                for sample in result['frames']:
                    with Image.open(io.BytesIO(base64.b64decode(sample))) as image:
                        self.assertEqual(image.format, 'JPEG')

    def test_new_limit_rejects_long_clips_but_stored_legacy_can_be_read(self):
        """No args/return; assert new cap without discarding older stored proof."""
        for seconds in (11, 12):
            raw = media.movie(seconds, fps=10)
            with self.assertRaises(ValueError):
                result_reviews.inspect_video(raw)
            result = result_reviews.inspect_video(raw, frames=True, max_seconds=60)
            self.assertEqual(len(result['frames']), 3)
        with self.assertRaises(ValueError):
            result_reviews.inspect_video(media.movie(2))
        with self.assertRaises(ValueError):
            result_video.inspect(b'not a video', max_seconds=100)

    def test_slow_camera_can_supply_last_sample_without_a_nonexistent_final_frame(self):
        """No args/return; a three-second, one-frame/second clip has frames at 0,1,2."""
        result = result_video.inspect(media.movie(3, fps=1), frames=True)
        self.assertEqual(len(result['frames']), 3)
        self.assertAlmostEqual(result['duration'], 3)

    def test_phone_webm_without_duration_header_and_subprocess_probe(self):
        """No args/return; assert live WebM duration is measured from decoded frames."""
        output = io.BytesIO()
        with av.open(output, 'w', format='webm', options={'live': '1'}) as container:
            stream = container.add_stream('libvpx', rate=10)
            stream.width, stream.height, stream.pix_fmt = 160, 90, 'yuv420p'
            for index in range(30):
                frame = av.VideoFrame.from_image(Image.new('RGB', (160, 90), (index * 7, 50, 80)))
                for packet in stream.encode(frame):
                    container.mux(packet)
            for packet in stream.encode():
                container.mux(packet)
        result = result_reviews.video_probe(output.getvalue(), frames=True)
        self.assertEqual(result['mime'], 'video/webm')
        self.assertAlmostEqual(result['duration'], 3, places=2)
        self.assertEqual(len(result['frames']), 3)


class AppealTest(unittest.TestCase):
    """Reuse only fixture helpers; do not rerun the legacy test class by inheritance."""

    setUp = previous.ReviewTest.setUp
    tearDown = previous.ReviewTest.tearDown
    call = previous.ReviewTest.call
    register = previous.ReviewTest.register
    players = previous.ReviewTest.players
    match = previous.ReviewTest.match
    ready = previous.ReviewTest.ready
    disputed = previous.ReviewTest.disputed
    upload = previous.ReviewTest.upload
    state = previous.ReviewTest.state
    queue = previous.ReviewTest.queue

    def finalized(self):
        """Return (accounts, match) after isolated successful evidence finalization."""
        users, match = self.queue()
        result_reviews.process_one(self.server, int(time.time()) + 61,
                                   reader=lambda _: previous.reading(match))
        return users, match

    def file(self, user, match):
        """Return appeal response; user/match are fixture dictionaries; HTTP errors propagate."""
        return self.call('/gamebox/evidence_appeal',
                         {'room': match['id'], 'reason': 'Please independently recheck the score and both identities.'}, user['token'])

    def appoint(self, user):
        """Grant fixture admin role; user is a test account; returns None; SQLite errors propagate."""
        with self.server.db() as d:
            d.execute('DELETE FROM game_admin')
            d.execute('INSERT INTO game_admin VALUES(?)', (user['id'],))

    def test_summary_is_private_and_contains_reports_findings_and_audit(self):
        """No args/return; assert authorized findings without exposing them to players."""
        users, match = self.finalized()
        for user in users:
            with self.assertRaises(urllib.error.HTTPError):
                self.call('/gamebox/review-summary?room=' + match['id'], token=user['token'])
        self.appoint(users[0])
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/gamebox/review-summary?room=' + match['id'], token=users[0]['token'])
        self.appoint(users[2])
        summary = self.call('/gamebox/review-summary?room=' + match['id'], token=users[2]['token'])
        self.assertEqual(len(summary['reports']), 2)
        self.assertEqual(len(summary['findings']), 2)
        self.assertEqual(summary['findings'][0]['analysis']['score'], [3, 1])
        self.assertEqual(summary['decision']['score'], [3, 1])
        self.assertTrue(summary['audit'])
        self.assertIn('do not establish', summary['limitation'])
        self.assertNotIn('image', summary)

    def test_appeal_is_idempotent_and_holds_cleanup_without_changing_rankings(self):
        """No args/return; assert hold survives normal tick and retains bytes/metadata."""
        import gamebox_core
        users, match = self.finalized()
        before = self.state(users[0], match)['evidence_review']
        self.assertTrue(before['can_appeal'])
        self.file(users[0], match)
        self.assertTrue(self.file(users[0], match)['already_submitted'])
        with self.assertRaises(urllib.error.HTTPError):
            self.file(users[2], match)
        with self.server.db() as d:
            d.execute('UPDATE gb_evidence SET expires=1 WHERE match=?', (match['id'],))
            d.execute("INSERT INTO result_review_videos VALUES('open',?,?,?,'video/webm','synthetic-held-video',1,1)",
                      (match['id'], users[0]['id'], b'previously validated proof'))
        gamebox_core.tick(self.server)
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_evidence WHERE image IS NOT NULL').fetchone()[0], 2)
            self.assertIsNotNone(d.execute('SELECT video FROM result_review_videos').fetchone()[0])
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0], 1)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM result_evidence_appeals').fetchone()[0], 1)
        receipt = self.state(users[0], match)['evidence_review']
        self.assertTrue(receipt['evidence_held'])
        self.assertFalse(receipt['can_appeal'])
        peer = self.state(users[1], match)['evidence_review']
        self.assertIsNone(peer['appeal_state'])

    def test_only_independent_admin_can_decide_and_correction_keeps_hold(self):
        """No args/return; correction requests cannot bypass audited rating reversal."""
        users, match = self.finalized()
        self.file(users[0], match)
        body = {'room': match['id'], 'player': users[0]['id'], 'outcome': 'correction_required',
                'reason': 'Independent evidence requires an audited correction review.'}
        self.appoint(users[0])
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/gamebox/evidence_appeal_decide', body, users[0]['token'])
        self.appoint(users[2])
        self.call('/gamebox/evidence_appeal_decide', body, users[2]['token'])
        self.assertTrue(self.call('/gamebox/evidence_appeal_decide', body, users[2]['token'])['already_decided'])
        final = self.state(users[0], match)
        self.assertEqual(final['final_score'], [3, 1])
        self.assertTrue(final['evidence_review']['evidence_held'])
        self.assertEqual(final['evidence_review']['appeal_state'], 'correction_required')

    def test_upheld_appeal_releases_due_bytes_but_keeps_decision_records(self):
        """No args/return; once held review completes, purge bytes without erasing history."""
        users, match = self.finalized()
        self.file(users[0], match)
        self.appoint(users[2])
        self.call('/gamebox/evidence_appeal_decide', {'room': match['id'], 'player': users[0]['id'],
                  'outcome': 'upheld', 'reason': 'The original evidence supports the recorded score.'}, users[2]['token'])
        with self.server.db() as d:
            d.execute('BEGIN IMMEDIATE')
            result_retention.purge(d, int(time.time()) + 4 * 86400)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_evidence WHERE image IS NOT NULL').fetchone()[0], 0)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM result_review_uploads WHERE analysis IS NOT NULL').fetchone()[0], 2)
            for item in d.execute('SELECT analysis FROM result_review_uploads'):
                self.assertNotIn('"text"', item['analysis'])
            self.assertEqual(d.execute("SELECT COUNT(*) FROM gb_evidence WHERE reading!=''").fetchone()[0], 0)
            self.assertEqual(d.execute('SELECT state FROM result_evidence_appeals').fetchone()[0], 'upheld')
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0], 1)

    def test_closed_window_and_unfinalized_match_cannot_be_appealed(self):
        """No args/return; invalid attempts do not create holds or alter final scores."""
        users, match = self.disputed()
        with self.assertRaises(urllib.error.HTTPError):
            self.file(users[0], match)
        self.upload(users[0], match)
        self.upload(users[1], match, 'blue')
        result_reviews.process_one(self.server, int(time.time()) + 61, reader=lambda _: previous.reading(match))
        with self.server.db() as d:
            d.execute('UPDATE result_evidence_retention SET appeal_until=1')
        with self.assertRaises(urllib.error.HTTPError):
            self.file(users[0], match)
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM result_evidence_appeals').fetchone()[0], 0)

    def test_repeated_finalization_does_not_extend_appeal_window(self):
        """No args/return; restarts and duplicate callbacks retain their original deadline."""
        users, match = self.finalized()
        with self.server.db() as d:
            full = result_reviews.match(d, match['id'])
            before = result_retention.status(d, full, users[0]['id'])['appeal_until']
            result_retention.schedule(d, full, 3 * 86400, now=int(time.time()) + 10000)
            self.assertEqual(result_retention.status(d, full, users[0]['id'])['appeal_until'], before)
        result_reviews.init(self.server)
        self.assertEqual(self.state(users[0], match)['evidence_review']['appeal_until'], before)

    def test_fixture_appeal_holds_photos_and_preserves_competition_standings(self):
        """No args/return; fixture cleanup and private summaries use the same hold policy."""
        import gamebox_core
        users = self.players()
        a, b = users[:2]
        now = int(time.time())
        with self.server.db() as d:
            d.execute("INSERT INTO leagues(id,name,game,owner,state,created,verification) VALUES('held-league','Held evidence','efootball',?,'active',?,'typed')", (users[2]['id'], now))
            for user in (a, b):
                d.execute('INSERT INTO league_members(league,uid,game_id) VALUES(?,?,?)', ('held-league', user['id'], 'game-' + user['id']))
            d.execute("INSERT INTO fixtures(id,league,round,a,b,opens,due,state) VALUES('held-fixture','held-league',1,?,?,?,?,'disputed')", (a['id'], b['id'], now-10, now+3600))
        match = {'id': 'held-fixture', 'gid_a': 'game-' + a['id'], 'gid_b': 'game-' + b['id']}
        self.upload(a, match)
        self.upload(b, match, 'blue')
        result_reviews.process_one(self.server, now+61, reader=lambda _: previous.reading(match))
        self.file(a, match)
        self.appoint(users[2])
        summary = self.call('/gamebox/review-summary?room=held-fixture', token=users[2]['token'])
        self.assertEqual(summary['kind'], 'fixture')
        self.assertEqual(len(summary['reports']), 2)
        self.assertTrue(summary['retention']['evidence_held'])
        with self.server.db() as d:
            d.execute('UPDATE gb_comp_retention SET expires=1')
        gamebox_core.tick(self.server)
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM game_reports WHERE image IS NOT NULL').fetchone()[0], 2)
            self.assertEqual(d.execute('SELECT COUNT(*) FROM gb_rank_awards').fetchone()[0], 0)
        self.call('/gamebox/evidence_appeal_decide', {'room': match['id'], 'player': a['id'], 'outcome': 'upheld',
                  'reason': 'Both captures support the original fixture decision.'}, users[2]['token'])
        gamebox_core.tick(self.server)
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM game_reports WHERE image IS NOT NULL').fetchone()[0], 0)
        table = self.call('/gaming/summary?league=held-league', token=a['token'])['table']
        self.assertEqual(next(r for r in table if r['uid']==a['id'])['points'], 3)


if __name__ == '__main__':
    unittest.main()
