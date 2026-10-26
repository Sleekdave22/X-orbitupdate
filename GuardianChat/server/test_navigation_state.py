import unittest,time,urllib.error
import test_vibes_activity

class NavigationStateTest(unittest.TestCase):
 setUp=test_vibes_activity.VibeTest.setUp;tearDown=test_vibes_activity.VibeTest.tearDown;call=test_vibes_activity.VibeTest.call;register=test_vibes_activity.VibeTest.register
 photo=test_vibes_activity.VibeTest.photo;publish=test_vibes_activity.VibeTest.publish
 def state(self,u):return self.call('/navigation/state',token=u['token'])
 def test_unread_is_account_scoped_and_clears_only_on_read(self):
  a=self.register('Sender');b=self.register('Reader');c=self.register('Other')
  for i in range(2):self.call('/messages',dict(peer=b['id'],text='Unread '+str(i),client_id='nav-'+str(i)),a['token'])
  self.assertEqual(self.state(a)['unread_messages'],0);self.assertEqual(self.state(b)['unread_messages'],2);self.assertEqual(self.state(c)['unread_messages'],0)
  rows=self.call('/messages?peer='+a['id'],token=b['token'])['messages'];self.assertEqual(self.state(b)['unread_messages'],2,'Fetching must not mark messages read')
  self.call('/read',{'peer':a['id'],'through':rows[-1]['id']},b['token']);self.assertEqual(self.state(b)['unread_messages'],0)
  with self.assertRaises(urllib.error.HTTPError):self.call('/navigation/state')
 def test_vibe_indicator_has_latest_reference_and_selected_audience_only(self):
  a=self.register('Author');b=self.register('Allowed');c=self.register('Excluded')
  x=self.publish(a,'private',audience=[b['id']]);y=self.publish(a,'private',audience=[b['id']]);badge=self.state(b)['vibes'][a['id']]
  self.assertEqual(badge['count'],2);self.assertEqual(badge['item'],y['id']);self.assertEqual(badge['visibility'],'private');self.assertNotIn(a['id'],self.state(c)['vibes'])
  self.assertEqual(self.call('/vibe/media?id='+x['id']+'&protected=1',token=b['token'])['next_id'],y['id'])
  self.assertIsNone(self.call('/vibe/media?id='+y['id']+'&protected=1',token=b['token'])['next_id'])
  with self.server.db() as d:d.execute('UPDATE vibe_items SET expires=1 WHERE uid=?',(a['id'],))
  self.assertNotIn(a['id'],self.state(b)['vibes'])
 def test_hidden_deleted_and_blocked_messages_do_not_badge(self):
  a=self.register('Sender');b=self.register('Reader');mid=self.call('/messages',dict(peer=b['id'],text='Hidden unread',client_id='nav-hidden'),a['token'])['id']
  with self.server.db() as d:d.execute('INSERT INTO message_hidden(user_id,message_id) VALUES(?,?)',(b['id'],mid))
  self.assertEqual(self.state(b)['unread_messages'],0)
  deleted=self.call('/messages',dict(peer=b['id'],text='Deleted unread',client_id='nav-deleted'),a['token'])['id']
  with self.server.db() as d:d.execute('UPDATE messages SET deleted_all=1 WHERE id=?',(deleted,))
  self.assertEqual(self.state(b)['unread_messages'],0)
  self.call('/messages',dict(peer=b['id'],text='Blocked unread',client_id='nav-blocked'),a['token']);self.call('/social/block',{'target':a['id']},b['token'])
  self.assertEqual(self.state(b)['unread_messages'],0);self.assertNotIn(a['id'],self.state(b)['vibes'])

if __name__=='__main__':unittest.main()
