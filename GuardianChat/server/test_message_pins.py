"""Shared pins exercise actual authenticated HTTP handlers on disposable data."""
import base64
import concurrent.futures
import unittest
import urllib.error

import message_pins
import test_server as fixtures


class MessagePinsTest(unittest.TestCase):
    setUp = fixtures.ChatTest.setUp
    tearDown = fixtures.ChatTest.tearDown
    call = fixtures.ChatTest.call
    register = fixtures.ChatTest.register

    def send(self, sender, recipient, text='Pinned message', key='one', **flags):
        """Return a real message ID; HTTP failures propagate to the assertion."""
        return self.call('/messages', dict(peer=recipient['id'], text=text, client_id=key, **flags), sender['token'])['id']

    def pins(self, reader, peer):
        """Return safe previews for this reader; never mark the source message read."""
        return self.call('/messages/pins?peer='+peer['id'], token=reader['token'])['pins']

    def test_both_participants_pin_unpin_idempotently_and_survive_initialization(self):
        """Either participant controls the shared state; personal chat pins stay separate."""
        a,b=self.register('Author'),self.register('Reader')
        first=self.send(a,b);second=self.send(b,a,key='two')
        body=dict(message_id=first,pinned=True)
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda user:self.call('/messages/pin',body,user['token']),[a,b]))
        original=self.pins(a,b)[0]
        self.call('/messages/pin',body,a['token'])
        self.assertEqual(self.pins(a,b)[0],original)
        self.call('/messages/pin',dict(message_id=second,pinned=True),b['token'])
        message_pins.init(self.server)
        self.assertEqual([r['id'] for r in self.pins(a,b)],[second,first])
        self.assertEqual(self.pins(a,b),self.pins(b,a))
        self.call('/messages/pin',dict(message_id=first,pinned=False),b['token'])
        self.call('/messages/pin',dict(message_id=first,pinned=False),a['token'])
        self.assertEqual([r['id'] for r in self.pins(b,a)],[second])
        with self.server.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM chat_pins').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT SUM(read_at)+SUM(delivered_at) FROM messages').fetchone()[0],0)

    def test_deleted_hidden_and_blocked_pins_are_not_exposed(self):
        """Preview authorization is rechecked, including personal deletion and blocking."""
        a,b=self.register('Author'),self.register('Reader');mid=self.send(a,b)
        self.call('/messages/pin',dict(message_id=mid,pinned=True),a['token'])
        self.call('/messages/delete',dict(message_id=mid,scope='me'),b['token'])
        self.assertEqual(self.pins(b,a),[]);self.assertEqual(len(self.pins(a,b)),1)
        self.call('/social/block',dict(target=b['id']),a['token'])
        with self.assertRaises(urllib.error.HTTPError):self.pins(b,a)
        self.assertEqual(self.call('/messages?peer='+b['id'],token=a['token'])['pins'],[])
        self.call('/social/unblock',dict(target=b['id']),a['token'])
        self.call('/messages/delete',dict(message_id=mid,scope='everyone'),a['token'])
        self.assertEqual(self.pins(a,b),[])

    def test_stranger_invalid_and_protected_previews(self):
        """No participant bypass, read side effect, source bytes or private caption leak."""
        a,b,c=self.register('Author'),self.register('Reader'),self.register('Other');mid=self.send(a,b)
        for user,body in [(c,dict(message_id=mid,pinned=True)),(a,dict(message_id=True,pinned=True)),(a,dict(message_id=mid,pinned='yes'))]:
            with self.assertRaises(urllib.error.HTTPError):self.call('/messages/pin',body,user['token'])
        with self.assertRaises(urllib.error.HTTPError):self.call('/messages/pin',dict(message_id=mid,pinned=True))
        self.assertEqual(self.pins(c,a),[])
        for i,flag in enumerate(['view_once','protected_media']):
            special=self.send(a,b,'Private caption',key=flag,**{flag:True,'data':base64.b64encode(b'private').decode(),'mime':'image/png','filename':'secret.png'})
            result=self.call('/messages/pin',dict(message_id=special,pinned=True),a['token'])
            preview=next(p for p in result['pins'] if p['id']==special)
            self.assertEqual(preview['preview'],['View-once content','Protected media'][i])
            self.assertNotIn('fileid',preview);self.assertNotIn('secret',str(preview))
        self.assertEqual(len(self.call('/messages?peer='+a['id'],token=b['token'])['pins']),2)


if __name__=='__main__':
    unittest.main()
