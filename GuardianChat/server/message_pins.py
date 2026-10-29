"""Shared private-message pins, separate from each user's existing chat-list pins.

Pins reference authoritative messages; previews are computed on each read. This
prevents deleted, personally hidden or protected content leaking through a stale
copy. Neither listing nor changing a pin acknowledges a message as read.
"""
import time

import social


def init(server):
    """Create additive storage without rewriting messages or personal chat pins.

    Args: server (ChatServer): Existing database owner.
    Returns: None. SQLite initialization errors propagate.
    """
    with server.db() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS message_pins(
            message_id INTEGER PRIMARY KEY, pinned_by TEXT NOT NULL,
            created INTEGER NOT NULL)''')


def visible(db, uid, peer):
    """Read current, authorized pin previews in stable newest-pin order.

    Args: db (Connection): Caller-owned database; uid/peer (str): Participants.
    Returns: list[dict] of safe message IDs, labels, actors and timestamps.
    Raises: PermissionError for blocked interactions; SQLite errors propagate.
    No file IDs, private captions or media bytes enter a pin preview.
    """
    social.ensure(db, uid, peer)
    rows = db.execute('''SELECT m.*,p.pinned_by,p.created AS pinned_at,
        u.name AS sender_name FROM message_pins p JOIN messages m ON m.id=p.message_id
        JOIN users u ON u.id=m.sender
        WHERE ((m.sender=? AND m.recipient=?) OR (m.sender=? AND m.recipient=?))
        AND m.deleted_all=0 AND m.kind='message'
        AND NOT EXISTS(SELECT 1 FROM message_hidden h WHERE h.user_id=? AND h.message_id=m.id)
        ORDER BY p.created DESC,m.id DESC''', (uid, peer, peer, uid, uid))
    result = []
    for row in rows:
        preview = ('Protected media' if row['protected_media'] else
                   'View-once content' if row['view_once'] else
                   (row['text'] or row['filename'] or 'Message')[:140])
        result.append(dict(id=row['id'], sender=row['sender'], name=row['sender_name'],
                           preview=preview, time=row['time'], pinned_by=row['pinned_by'],
                           pinned_at=row['pinned_at']))
    return result


def get(server, uid, peer):
    """Return an authenticated private conversation's visible pins.

    Args: server (ChatServer), uid/peer (str): Authenticated reader and other account.
    Returns: dict with pins list; an unknown/unrelated account reveals nothing.
    Raises: PermissionError for a blocked relationship; SQLite errors propagate.
    """
    with server.db() as db:
        return {'pins': visible(db, uid, peer)}


def set_pin(server, uid, body):
    """Idempotently pin/unpin an accessible message as either participant.

    Args: server (ChatServer), uid (str), body (dict): message_id and pinned boolean.
    Returns: dict with pinned state, peer and currently visible pin previews.
    Raises: ValueError for invalid input; LookupError for inaccessible messages;
        PermissionError for blocked accounts. SQLite errors roll back the write.
    BEGIN IMMEDIATE serializes opposite participant edits; the last committed
    action wins. A repeated pin preserves its original timestamp and actor.
    """
    mid, pinned = body.get('message_id'), body.get('pinned')
    if type(mid) is not int or mid <= 0 or type(pinned) is not bool:
        raise ValueError('Choose a message and a pin state')
    with server.db() as db:
        db.execute('BEGIN IMMEDIATE')
        row = db.execute('''SELECT * FROM messages m WHERE id=?
            AND (sender=? OR recipient=?) AND deleted_all=0 AND kind='message'
            AND NOT EXISTS(SELECT 1 FROM message_hidden h WHERE h.user_id=? AND h.message_id=m.id)''',
                         (mid, uid, uid, uid)).fetchone()
        if not row:
            raise LookupError('Message unavailable')
        peer = row['recipient'] if row['sender'] == uid else row['sender']
        social.ensure(db, uid, peer)
        if pinned:
            db.execute('INSERT OR IGNORE INTO message_pins VALUES(?,?,?)', (mid, uid, int(time.time())))
        else:
            db.execute('DELETE FROM message_pins WHERE message_id=?', (mid,))
        return {'pinned': pinned, 'peer': peer, 'pins': visible(db, uid, peer)}
