"""Reaction delivery/consent tests using isolated HTTP accounts and persisted rows."""
import concurrent.futures
import sqlite3
import unittest
import urllib.error
from unittest.mock import patch

import vibes
import vibe_messages
import test_vibes_activity as fixtures


class VibeDeliveryTest(unittest.TestCase):
    """Reuse fixture helpers without inheriting unrelated tests."""
    setUp = fixtures.VibeTest.setUp
    tearDown = fixtures.VibeTest.tearDown
    call = fixtures.VibeTest.call
    register = fixtures.VibeTest.register
    publish = fixtures.VibeTest.publish
    photo = fixtures.VibeTest.photo

    def test_reaction_reaches_owner_chat_both_directions_and_push_dispatch(self):
        """No args/return; assert persisted direction/context and existing notification use."""
        author, viewer = self.register('Author'), self.register('Viewer')
        for source, sender in [(author, viewer), (viewer, author)]:
            item = self.publish(source)
            with patch('message_notifications.dispatch') as push:
                result = self.call('/vibe/react', {'id': item['id'], 'emoji': '🔥'}, sender['token'])
                self.assertEqual(result['state'], 'sent')
                push.assert_called_once_with(self.server, result['message_id'])
                retry = self.call('/vibe/react', {'id': item['id'], 'emoji': '🔥'}, sender['token'])
                self.assertEqual(retry['message_id'], result['message_id'])
                self.assertEqual(push.call_count, 1)
            rows = self.call('/messages?peer=' + sender['id'], token=source['token'])['messages']
            message = next(m for m in rows if m['id'] == result['message_id'])
            self.assertEqual(message['sender'], sender['id'])
            self.assertEqual(message['recipient'], source['id'])
            self.assertEqual(message['text'], '↪ Reply to Vibe\n🔥')
            self.assertEqual(message['vibe']['id'], item['id'])
            self.assertEqual(message['vibe']['kind'], 'reaction')
            self.assertNotIn('caption', message['vibe'])
            notices = self.call('/notifications?category=vibe', token=source['token'])['notifications']
            self.assertTrue(any(n['target'].get('message') == result['message_id'] for n in notices))

    def test_simultaneous_retries_and_emoji_changes_do_not_duplicate_chat_delivery(self):
        """No args/return; concurrency cannot create duplicate reaction messages."""
        author, viewer = self.register('Author'), self.register('Viewer')
        item = self.publish(author)
        body = {'id': item['id'], 'emoji': '😂'}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.call('/vibe/react', body, viewer['token']), range(2)))
        self.assertEqual(results[0]['message_id'], results[1]['message_id'])
        self.call('/vibe/react', dict(body, emoji='❤️'), viewer['token'])
        self.call('/vibe/react', body, viewer['token'])
        with self.server.db() as d:
            self.assertEqual(d.execute('SELECT COUNT(*) FROM messages').fetchone()[0], 2)
            self.assertEqual(d.execute('SELECT emoji FROM vibe_reactions').fetchone()[0], '😂')
        vibes.init(self.server)
        self.assertEqual(len(self.call('/messages?peer=' + viewer['id'], token=author['token'])['messages']), 2)

    def test_unfamiliar_reaction_waits_for_recipient_consent_without_inbox_leak(self):
        """No args/return; acceptance materializes original reactions once and unread."""
        author = self.register('Author')
        stranger = self.call('/register', {'invite': self.server.invite, 'name': 'Unfamiliar'})
        item = self.publish(author)
        result = self.call('/vibe/react', {'id': item['id'], 'emoji': '👏'}, stranger['token'])
        self.assertEqual(result['state'], 'pending')
        self.assertIsNone(result['message_id'])
        self.assertEqual(self.call('/messages?peer=' + stranger['id'], token=author['token'])['messages'], [])
        self.assertFalse(any(user['id'] == stranger['id'] for user in self.call('/users', token=author['token'])['users']))
        requests = self.call('/social/message_requests', token=author['token'])['users']
        self.assertEqual(requests[0]['id'], stranger['id'])
        self.call('/social/message_accept', {'target': stranger['id']}, author['token'])
        self.call('/social/message_accept', {'target': stranger['id']}, author['token'])
        rows = self.call('/messages?peer=' + stranger['id'], token=author['token'])['messages']
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['text'], '↪ Reply to Vibe\n👏')
        self.assertEqual(rows[0]['read_at'], 0)

    def test_private_reaction_never_exposes_caption_and_block_expiry_reject_delivery(self):
        """No args/return; denied actions cannot create messages or leak private bytes."""
        author, viewer = self.register('Author'), self.register('Viewer')
        private = self.publish(author, 'private', audience=[viewer['id']], caption='Private caption must not leak')
        result = self.call('/vibe/react', {'id': private['id'], 'emoji': '❤️'}, viewer['token'])
        row = self.call('/messages?peer=' + author['id'], token=viewer['token'])['messages'][0]
        self.assertEqual(row['vibe']['visibility'], 'private')
        self.assertNotIn('Private caption', row['text'])
        self.call('/social/block', {'target': viewer['id']}, author['token'])
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/vibe/react', {'id': private['id'], 'emoji': '😂'}, viewer['token'])
        self.call('/social/unblock', {'target': viewer['id']}, author['token'])
        with self.server.db() as d:
            d.execute('UPDATE vibe_items SET expires=1 WHERE id=?', (private['id'],))
        with self.assertRaises(urllib.error.HTTPError):
            self.call('/vibe/react', {'id': private['id'], 'emoji': '😂'}, viewer['token'])
        self.assertEqual(result['state'], 'sent')

    def test_decline_does_not_restart_request_or_leak_decline_to_sender(self):
        """No args/return; later reactions cannot silently undo a recipient's decline."""
        author = self.register('Author')
        stranger = self.call('/register', {'invite': self.server.invite, 'name': 'Unfamiliar'})
        item = self.publish(author)
        self.call('/vibe/react', {'id': item['id'], 'emoji': '🔥'}, stranger['token'])
        self.call('/social/message_decline', {'target': stranger['id']}, author['token'])
        result = self.call('/vibe/react', {'id': item['id'], 'emoji': '👏'}, stranger['token'])
        self.assertEqual(result['state'], 'pending')
        self.assertEqual(self.call('/social/message_requests', token=author['token'])['users'], [])
        self.assertEqual(self.call('/messages?peer=' + stranger['id'], token=author['token'])['messages'], [])


class DeliveryMigrationTest(unittest.TestCase):
    """Prove the six-column schema upgrades without touching any real database."""

    def test_existing_private_records_and_message_ids_survive_repeated_migration(self):
        """No args/return; in-memory legacy rows keep identity, visibility and retry keys."""
        d = sqlite3.connect(':memory:')
        d.row_factory = sqlite3.Row
        self.addCleanup(d.close)
        d.executescript('''CREATE TABLE vibe_items(id TEXT PRIMARY KEY,visibility TEXT);
            CREATE TABLE vibe_replies(message_id INTEGER PRIMARY KEY,visibility TEXT);
            CREATE TABLE vibe_reaction_deliveries(item TEXT,sender TEXT,emoji TEXT,
                recipient TEXT,created INTEGER,message_id INTEGER,PRIMARY KEY(item,sender,emoji));
            INSERT INTO vibe_items VALUES('public-post','public');
            INSERT INTO vibe_replies VALUES(7,'private');
            INSERT INTO vibe_reaction_deliveries VALUES('public-post','a','🔥','b',123,6);
            INSERT INTO vibe_reaction_deliveries VALUES('expired-private','c','❤️','d',124,7);
            INSERT INTO vibe_reaction_deliveries VALUES('missing-source','e','👏','f',125,NULL);''')
        before = [tuple(row) for row in d.execute('SELECT * FROM vibe_reaction_deliveries ORDER BY item')]
        vibe_messages.schema(d)
        vibe_messages.schema(d)
        after = list(d.execute('SELECT * FROM vibe_reaction_deliveries ORDER BY item'))
        self.assertEqual([tuple(row)[:6] for row in after], before)
        self.assertEqual({row['item']: row['visibility'] for row in after},
                         {'public-post': 'public', 'expired-private': 'private', 'missing-source': 'private'})


if __name__ == '__main__':
    unittest.main()
