"""Connection consent and introduction tests use disposable authenticated accounts."""
import concurrent.futures
import unittest
import urllib.error

import message_requests
import test_server as fixtures


class MessageRequestsTest(unittest.TestCase):
    setUp=fixtures.ChatTest.setUp
    tearDown=fixtures.ChatTest.tearDown
    call=fixtures.ChatTest.call

    def register(self,name):
        """Return an unpaired disposable account; HTTP failures propagate."""
        return self.call('/register',dict(invite=self.server.invite,name=name))

    def act(self,user,action,**body):
        """Execute an authenticated social action; HTTP errors reach assertions."""
        return self.call('/social/'+action,body,user['token'])

    def test_contact_codes_request_acceptance_and_preserve_existing_histories(self):
        """New codes wait; repeated acceptance and legacy histories remain usable."""
        a,b=self.register('Requester'),self.register('Recipient')
        result=self.call('/contacts',dict(code=b['id']),a['token']);self.assertEqual(result['state'],'pending')
        self.assertEqual(self.call('/users',token=a['token'])['users'],[])
        with self.assertRaises(urllib.error.HTTPError):self.call('/messages',dict(peer=b['id'],text='No bypass',client_id='blocked'),a['token'])
        self.act(b,'message_accept',target=a['id']);self.act(b,'message_accept',target=a['id'])
        self.assertEqual(self.call('/contacts',dict(code=b['id']),a['token'])['state'],'accepted')
        c=self.register('Legacy')
        with self.server.db() as db:db.execute('INSERT INTO messages(sender,recipient,text,time,client_id) VALUES(?,?,?,?,?)',(a['id'],c['id'],'Legacy history',1000,'legacy'))
        self.assertEqual(self.call('/contacts',dict(code=c['id']),a['token'])['state'],'accepted')

    def test_preview_acceptance_is_atomic_idempotent_and_has_no_pending_receipts(self):
        """Only acceptance materializes originals; preview reads reveal no receipts."""
        a,b=self.register('Requester'),self.register('Recipient')
        body=dict(target=b['id'],text='An introduction',client_id='intro-one')
        self.act(a,'message_request',**body);self.act(a,'message_request',**body)
        preview=self.call('/social/message_requests',token=b['token'])['users'][0]['previews'][0]
        self.assertEqual(preview['text'],'An introduction');self.assertNotIn('read_at',preview)
        self.assertEqual(self.call('/messages?peer='+a['id'],token=b['token'])['messages'],[])
        self.assertEqual(self.call('/inbox',token=b['token'])['ids'],[])
        with self.assertRaises(urllib.error.HTTPError):self.act(a,'message_request',**dict(body,text='Changed'))
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _:self.act(b,'message_accept',target=a['id']),range(2)))
        message_requests.init(self.server)
        rows=self.call('/messages?peer='+a['id'],token=b['token'])['messages']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['text'],'An introduction');self.assertEqual(rows[0]['read_at'],0)

    def test_decline_private_block_prevents_bypass_and_report_stays_separate(self):
        """Reporting does not decline; declined senders cannot infer or undo refusal."""
        a,b,c=self.register('Requester'),self.register('Recipient'),self.register('Other')
        self.act(a,'message_request',target=b['id'],text='Hello',client_id='intro')
        with self.assertRaises(urllib.error.HTTPError):self.act(c,'message_report',target=a['id'],reason='No authority',client_id='report')
        report=self.act(b,'message_report',target=a['id'],reason='Test moderation reason',client_id='report')
        self.assertEqual(self.act(b,'message_report',target=a['id'],reason='Test moderation reason',client_id='report'),report)
        self.assertEqual(len(self.call('/social/message_requests',token=b['token'])['users']),1)
        self.act(b,'message_decline',target=a['id'])
        self.assertEqual(self.act(a,'message_request',target=b['id'],text='Another',client_id='second')['state'],'pending')
        self.assertEqual(self.call('/social/message_requests',token=b['token'])['users'],[])
        self.act(b,'message_decline_block',target=a['id']);self.act(b,'message_decline_block',target=a['id'])
        for path,body in [('/contacts',dict(code=b['id'])),('/social/message_request',dict(target=b['id']))]:
            with self.assertRaises(urllib.error.HTTPError):self.call(path,body,a['token'])
        with self.server.db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM social_reports').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)


if __name__=='__main__':
    unittest.main()
