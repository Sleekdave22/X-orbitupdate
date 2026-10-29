"""Durable Vibe reactions use existing private conversations and request consent.

No Vibe media/captions are copied into a message. A reference remains meaningful
after ordinary expiry, while opening its source still requires current permission.
Unfamiliar senders never gain a normal conversation on the recipient's behalf.
"""

import hashlib
import time


def schema(d):
    """Create additive delivery records; d is a SQLite connection; return None.

    Raises sqlite3.Error on failure. The unique key deduplicates legacy native
    clients that do not supply retry IDs as well as simultaneous browser retries.
    """
    d.execute('''CREATE TABLE IF NOT EXISTS vibe_reaction_deliveries(
        item TEXT,sender TEXT,emoji TEXT,recipient TEXT NOT NULL,
        created INTEGER NOT NULL,message_id INTEGER,
        visibility TEXT NOT NULL DEFAULT 'private',
        PRIMARY KEY(item,sender,emoji))''')
    # An earlier checkpoint may already have six-column delivery records. Keep
    # every row/message ID and conservatively retain private visibility when the
    # original has expired. CREATE IF NOT EXISTS alone cannot perform this upgrade.
    columns = {row['name'] for row in d.execute('PRAGMA table_info(vibe_reaction_deliveries)')}
    if 'visibility' not in columns:
        d.execute("ALTER TABLE vibe_reaction_deliveries ADD COLUMN visibility TEXT NOT NULL DEFAULT 'private'")
        d.execute('''UPDATE vibe_reaction_deliveries SET visibility=COALESCE(
            (SELECT visibility FROM vibe_items WHERE id=vibe_reaction_deliveries.item),
            (SELECT visibility FROM vibe_replies WHERE message_id=vibe_reaction_deliveries.message_id),
            'private')''')


def deliver(d, delivery):
    """Materialize one accepted reaction message inside the caller's transaction.

    Args: d (sqlite3.Connection), delivery (dict|Row): Stored reaction/recipient key.
    Returns: int message ID. Repeated delivery returns the same existing message.
    Raises: ValueError on a conflicting retry key; SQLite errors roll back caller.
    No contact creation, read receipt, media preview or source reopening occurs.
    """
    client = 'vreact:' + hashlib.sha256((delivery['item'] + ':' + delivery['sender'] + ':' + delivery['emoji']).encode()).hexdigest()
    text = '↪ Reply to Vibe\n' + delivery['emoji']
    previous = d.execute('SELECT id,recipient,text FROM messages WHERE sender=? AND client_id=?',
                         (delivery['sender'], client)).fetchone()
    if previous:
        if previous['recipient'] != delivery['recipient'] or previous['text'] != text:
            raise ValueError('This retry key belongs to another message')
        mid = previous['id']
    else:
        mid = d.execute('INSERT INTO messages(sender,recipient,text,time,client_id,size) VALUES(?,?,?,?,?,0)',
                        (delivery['sender'], delivery['recipient'], text, delivery['created'] * 1000, client)).lastrowid
    vibe = d.execute('SELECT visibility FROM vibe_items WHERE id=?', (delivery['item'],)).fetchone()
    d.execute('INSERT OR IGNORE INTO vibe_replies VALUES(?,?,?,?,?)',
              (mid, delivery['item'], vibe['visibility'] if vibe else delivery['visibility'], delivery['sender'], client))
    d.execute('UPDATE vibe_reaction_deliveries SET message_id=? WHERE item=? AND sender=? AND emoji=?',
              (mid, delivery['item'], delivery['sender'], delivery['emoji']))
    d.execute('DELETE FROM chat_hidden WHERE owner=? AND peer=?', (delivery['recipient'], delivery['sender']))
    return mid


def accept_pending(d, sender, recipient):
    """Deliver held reactions when the recipient accepts an existing request.

    Args: d (sqlite3.Connection), sender/recipient (str): Accepted request direction.
    Returns: list[int] of materialized message IDs; blocked pairs are rejected.
    Raises: PermissionError or SQLite errors, rolling back the acceptance too.
    The recipient is already engaging with the request; normal synchronization
    delivers these persisted messages on every device without false read receipts.
    """
    __import__('social').ensure(d, sender, recipient)
    if not d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?', (recipient, sender)).fetchone():
        raise PermissionError('The recipient must accept the conversation first')
    rows = d.execute('SELECT * FROM vibe_reaction_deliveries WHERE sender=? AND recipient=? AND message_id IS NULL ORDER BY created,item,emoji',
                     (sender, recipient)).fetchall()
    return [deliver(d, item) for item in rows]


def react(server, uid, body):
    """Persist a reaction and its chat delivery/request before reporting success.

    Args: server (ChatServer), uid (str): Session actor; body (dict): id and emoji.
    Returns: dict with accepted delivery state and optional private message ID.
    Raises: ValueError/PermissionError for invalid, expired, blocked or excessive
        actions; SQLite errors roll back reaction, request and message together.
    Successful contact deliveries use existing metadata-only message push.
    """
    import social
    import vibes

    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        item = vibes.item(d, uid, str(body.get('id', '')))
        emoji = body.get('emoji')
        if emoji not in vibes.EMOJI or item['uid'] == uid:
            raise ValueError('Choose an available reaction to another account')
        target = item['uid']
        prior = d.execute('SELECT * FROM vibe_reaction_deliveries WHERE item=? AND sender=? AND emoji=?',
                          (item['id'], uid, emoji)).fetchone()
        if not prior:
            if d.execute('SELECT COUNT(*) FROM vibe_reaction_deliveries WHERE sender=? AND created>?', (uid, now-60)).fetchone()[0] >= 30:
                raise ValueError('Too many reactions; try again shortly')
            d.execute('INSERT INTO vibe_reaction_deliveries(item,sender,emoji,recipient,created,message_id,visibility) VALUES(?,?,?,?,?,NULL,?)',
                      (item['id'], uid, emoji, target, now, item['visibility']))
        d.execute('INSERT INTO vibe_reactions VALUES(?,?,?,?) ON CONFLICT(item,uid) DO UPDATE SET emoji=excluded.emoji,created=excluded.created',
                  (item['id'], uid, emoji, now))
        delivery = d.execute('SELECT * FROM vibe_reaction_deliveries WHERE item=? AND sender=? AND emoji=?', (item['id'], uid, emoji)).fetchone()
        accepted = bool(d.execute('SELECT 1 FROM contacts WHERE owner=? AND peer=?', (target, uid)).fetchone())
        mid = deliver(d, delivery) if accepted else None
        if not accepted:
            request = d.execute('SELECT state FROM social_message_requests WHERE sender=? AND target=?', (uid, target)).fetchone()
            if not request:
                d.execute("INSERT INTO social_message_requests VALUES(?,?,'pending',?)", (uid, target, now))
                social.notice(d, target, uid, 'message_request')
        elif not prior:
            __import__('account_notifications').add(d, target, 'vibe', item['visibility'],
                'A contact reacted ' + emoji + ' to your Vibe.', {'item': item['id'], 'visibility': item['visibility'], 'message': mid, 'peer': uid})
    if mid and not prior:
        __import__('message_notifications').dispatch(server, mid)
    return {'ok': True, 'state': 'sent' if accepted else 'pending', 'message_id': mid}


def context(d, message_id):
    """Return minimal Vibe reference metadata for an already-authorized message.

    Args: d (sqlite3.Connection), message_id (int): Visible non-deleted message.
    Returns: dict|None; no source media, caption or public URL is exposed.
    Raises: sqlite3.Error on read failure. Caller owns message authorization.
    """
    row = d.execute('SELECT item,visibility FROM vibe_replies WHERE message_id=?', (message_id,)).fetchone()
    if not row:
        return None
    reaction = d.execute('SELECT emoji FROM vibe_reaction_deliveries WHERE message_id=?', (message_id,)).fetchone()
    return {'id': row['item'], 'visibility': row['visibility'], 'kind': 'reaction' if reaction else 'reply',
            'emoji': reaction['emoji'] if reaction else None}
