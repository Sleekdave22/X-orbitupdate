import time,threading,unittest,urllib.error
import test_market_pilot,account_notifications,market_connections

class MarketPushTest(unittest.TestCase):
 setUp=test_market_pilot.MarketPilotTest.setUp;tearDown=test_market_pilot.MarketPilotTest.tearDown;call=test_market_pilot.MarketPilotTest.call;register=test_market_pilot.MarketPilotTest.register
 def test_session_scope_dedupe_authorized_notice_and_no_private_payload(self):
  a=self.register('Buyer');b=self.register('Other');self.call('/push/register',{'push_token':'market-fake-'+'a'*45},a['token']);self.call('/push/register',{'push_token':'market-fake-'+'b'*45},b['token'])
  with self.server.db() as d:
   account_notifications.add(d,a['id'],'market','offers','Private offer details',{'offer':'test-offer'})
   ident=d.execute('SELECT max(id) FROM account_activity').fetchone()[0]
   account_notifications.add(d,b['id'],'market','offers','Other account',{})
   d.execute('DELETE FROM sessions WHERE user_id=?',(b['id'],))
  self.assertEqual(self.call('/market/activity_item?id='+str(ident),token=a['token'])['notification']['text'],'Private offer details')
  # This authorization probe needs an unrelated account, not paired contacts.
  # B's session was deliberately revoked above and cannot accept a new request.
  c=self.call('/register',{'invite':self.server.invite,'name':'Third'})
  with self.assertRaises(urllib.error.HTTPError):self.call('/market/activity_item?id='+str(ident),token=c['token'])
  class Fake:
   enabled=True
   def __init__(self):self.events=[];self.ready=threading.Event()
   def send(self,token,data):self.events.append((token,data));self.ready.set()
  fake=Fake();self.server.push=fake;market_connections.dispatch(self.server);self.assertTrue(fake.ready.wait(2))
  for _ in range(100):
   if not getattr(self.server,'market_push_busy',False):break
   time.sleep(.02)
  market_connections.dispatch(self.server)
  self.assertEqual(len(fake.events),1);token,payload=fake.events[0];self.assertEqual(payload['recipient'],a['id']);self.assertEqual(payload['event'],'market_notice');self.assertEqual(payload['notice_id'],str(ident));self.assertNotIn('Private',str(payload));self.assertEqual(set(payload),{'event','notice_id','recipient','expires_at'})

if __name__=='__main__':unittest.main()
