"""Small account-scoped navigation summary; no private Vibe media is exposed."""
import time
import vibes

def get(server,uid):
 with server.db() as d:
  unread=d.execute("""SELECT COUNT(*) FROM messages m JOIN contacts c ON c.owner=m.recipient AND c.peer=m.sender
   WHERE m.recipient=? AND m.read_at=0 AND m.kind!='call' AND m.deleted_all=0
   AND NOT EXISTS(SELECT 1 FROM message_hidden h WHERE h.user_id=? AND h.message_id=m.id)
   AND NOT EXISTS(SELECT 1 FROM chat_hidden h WHERE h.owner=? AND h.peer=m.sender AND h.through_id>=m.id)
   AND NOT EXISTS(SELECT 1 FROM social_blocks b WHERE (b.owner=? AND b.target=m.sender) OR (b.owner=m.sender AND b.target=?))""",(uid,uid,uid,uid,uid)).fetchone()[0]
  active={}
  for r in d.execute("""SELECT i.id,i.uid,i.visibility,i.created,i.expires,1 AS media FROM vibe_items i JOIN users u ON u.id=i.uid
   WHERE i.expires>? AND i.media IS NOT NULL AND (i.uid=? OR EXISTS(SELECT 1 FROM contacts c WHERE c.owner=? AND c.peer=i.uid)
    OR EXISTS(SELECT 1 FROM social_follows f WHERE f.follower=? AND f.target=i.uid AND f.state='accepted')) ORDER BY i.created,i.rowid""",(int(time.time()),uid,uid,uid)):
   if not vibes.allowed(d,uid,r) or __import__('vibe_privacy').muted(d,uid,r['uid']):continue
   prior=active.get(r['uid']);count=(prior['count'] if prior else 0)+1
   active[r['uid']]={'count':count,'item':r['id'],'visibility':r['visibility'],'expires':r['expires']}
  return {'account':uid,'unread_messages':unread,'vibes':active}
