"""Account-scoped counters shared by browser and Android navigation.

Polling does not acknowledge content: message reads, displayed-call receipts and
Vibe views have separate write paths. Only stale-call expiry is triggered here.
Vibe summaries contain references and counts, never private media bytes.
"""
import time

import vibes


def init(server):
    """Keep call acknowledgments durable without deleting the call history."""
    with server.db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS navigation_call_views(
                uid TEXT NOT NULL,
                call_id TEXT NOT NULL,
                PRIMARY KEY(uid,call_id)
            )
        """)


def calls_seen(server, uid, body):
    """Acknowledge only the recipient's displayed snapshot, all or nothing."""
    ids = body.get('ids')
    if (
        not isinstance(ids, list)
        or len(ids) > 200
        or any(not isinstance(ident, str) or not 1 <= len(ident) <= 128 for ident in ids)
    ):
        raise ValueError('Choose the displayed missed calls')

    unique_ids = set(ids)
    with server.db() as db:
        # A mixed authorized/unauthorized snapshot must roll back every receipt.
        # BEGIN IMMEDIATE also serializes concurrent acknowledgments with writers.
        db.execute('BEGIN IMMEDIATE')
        for ident in unique_ids:
            available = db.execute("""
                SELECT 1 FROM call_history
                WHERE id=? AND recipient=? AND ended IS NOT NULL
                  AND outcome IN ('missed','cancelled')
            """, (ident, uid)).fetchone()
            if not available:
                raise PermissionError('Missed call unavailable to this account')
            db.execute(
                'INSERT OR IGNORE INTO navigation_call_views(uid,call_id) VALUES(?,?)',
                (uid, ident),
            )
    return {'seen': len(unique_ids)}


def _unread_messages(db, uid):
    """Count visible incoming messages from contacts, excluding call records."""
    # A hidden-chat boundary suppresses old messages, not future arrivals.
    # Blocks are symmetric: either account can make the interaction unavailable.
    return db.execute("""
        SELECT COUNT(*) FROM messages m
        JOIN contacts c ON c.owner=m.recipient AND c.peer=m.sender
        WHERE m.recipient=? AND m.read_at=0 AND m.kind!='call' AND m.deleted_all=0
          AND NOT EXISTS(
              SELECT 1 FROM message_hidden h WHERE h.user_id=? AND h.message_id=m.id
          )
          AND NOT EXISTS(
              SELECT 1 FROM chat_hidden h
              WHERE h.owner=? AND h.peer=m.sender AND h.through_id>=m.id
          )
          AND NOT EXISTS(
              SELECT 1 FROM social_blocks b
              WHERE (b.owner=? AND b.target=m.sender) OR (b.owner=m.sender AND b.target=?)
          )
    """, (uid, uid, uid, uid, uid)).fetchone()[0]


def _missed_calls(db, uid):
    """Count unseen ended incoming calls, keeping calls separate from messages."""
    return db.execute("""
        SELECT COUNT(*) FROM call_history h
        WHERE h.recipient=? AND h.ended IS NOT NULL AND h.outcome IN ('missed','cancelled')
          AND NOT EXISTS(
              SELECT 1 FROM navigation_call_views v WHERE v.uid=? AND v.call_id=h.id
          )
          AND NOT EXISTS(
              SELECT 1 FROM social_blocks b
              WHERE (b.owner=? AND b.target=h.caller) OR (b.owner=h.caller AND b.target=?)
          )
    """, (uid, uid, uid, uid)).fetchone()[0]


def _vibe_summary(db, uid):
    """Return unseen post count and the latest permitted reference per author."""
    # allowed() expects a non-null media field. The constant below satisfies that
    # metadata contract after SQL excludes absent media, without loading the blob.
    # Oldest-first ordering lets each later row replace the author's reference;
    # rowid breaks ties when uploads share the same creation second.
    rows = db.execute("""
        SELECT i.id,i.uid,i.visibility,i.created,i.expires,1 AS media,
          EXISTS(SELECT 1 FROM vibe_views v WHERE v.item=i.id AND v.uid=?) AS viewed,
          (i.uid=? OR EXISTS(SELECT 1 FROM contacts c WHERE c.owner=? AND c.peer=i.uid)
            OR EXISTS(SELECT 1 FROM social_follows f
                      WHERE f.follower=? AND f.target=i.uid AND f.state='accepted')) AS connected
        FROM vibe_items i JOIN users u ON u.id=i.uid
        WHERE i.expires>? AND i.media IS NOT NULL ORDER BY i.created,i.rowid
    """, (uid, uid, uid, uid, int(time.time())))
    active = {}
    unseen = 0
    for item in rows:
        if not vibes.allowed(db, uid, item) or __import__('vibe_privacy').muted(db, uid, item['uid']):
            continue
        # Public visibility alone is insufficient for a contact-feed badge.
        if not item['connected']:
            continue
        if item['uid'] != uid and not item['viewed']:
            unseen += 1
        prior = active.get(item['uid'])
        count = (prior['count'] if prior else 0) + 1
        active[item['uid']] = {
            'count': count,
            'item': item['id'],
            'visibility': item['visibility'],
            'expires': item['expires'],
        }
    return unseen, active


def get(server, uid):
    """Read badge state without acknowledging messages, calls or Vibes."""
    # Expiry may finalize call state; retain its existing lock and read-side effect.
    with server.call_lock:
        server.expire_calls()
    with server.db() as db:
        unread = _unread_messages(db, uid)
        missed = _missed_calls(db, uid)
        unseen, active = _vibe_summary(db, uid)
        return {
            'account': uid,
            'unread_messages': unread,
            'missed_calls': missed,
            'unseen_vibes': unseen,
            'vibes': active,
        }
