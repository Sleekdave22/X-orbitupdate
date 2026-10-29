"""Consent-gated introductions, separate from ordinary unread/read message state.

Existing contacts and established histories remain accepted. New introductions
stay outside messages/files/receipts until the recipient accepts. Declines are
private; reporting does not automatically block or change the request state.
"""
import hashlib
import time

import social


def init(server):
    """Add introduction/retry storage without rewriting existing conversations.

    Args: server (ChatServer): Database owner. Returns: None.
    Raises: SQLite errors; no credentials or private media are stored here.
    """
    with server.db() as db:
        db.executescript('''CREATE TABLE IF NOT EXISTS message_request_previews(
            sender TEXT NOT NULL,target TEXT NOT NULL,client_id TEXT NOT NULL,
            text TEXT NOT NULL,created INTEGER NOT NULL,message_id INTEGER,
            PRIMARY KEY(sender,client_id));
            CREATE INDEX IF NOT EXISTS request_previews_target ON message_request_previews(target,sender,created);
            CREATE TABLE IF NOT EXISTS message_request_reports(
            owner TEXT NOT NULL,client_id TEXT NOT NULL,target TEXT NOT NULL,
            reason TEXT NOT NULL,report_id INTEGER NOT NULL,PRIMARY KEY(owner,client_id));''')


def accepted(db, sender, target):
    """Preserve established conversation consent, including older stored histories.

    Args: db (Connection), sender/target (str). Returns: bool.
    Raises: SQLite errors. Following alone never grants conversation access.
    """
    return bool(db.execute('''SELECT 1 FROM contacts WHERE (owner=? AND peer=?) OR (owner=? AND peer=?)
        UNION ALL SELECT 1 FROM messages WHERE (sender=? AND recipient=?) OR (sender=? AND recipient=?)
        UNION ALL SELECT 1 FROM social_message_requests WHERE state='accepted'
        AND ((sender=? AND target=?) OR (sender=? AND target=?)) LIMIT 1''',
        (sender,target,target,sender,sender,target,target,sender,sender,target,target,sender)).fetchone())


def connect(db, a, b):
    """Materialize an accepted relationship in the existing contacts table.

    Args: db (Connection), a/b (str). Returns: None. SQLite errors propagate.
    Called only for recipient acceptance or preserved legacy consent.
    """
    db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(a,b))
    db.execute('INSERT OR IGNORE INTO contacts VALUES(?,?)',(b,a))


def request(db, sender, target, body):
    """Create/retry a pending introduction in the caller's write transaction.

    Args: db (Connection), sender/target (str), body (dict): Optional text/client_id.
    Returns: dict with accepted/pending state; declined is never disclosed.
    Raises: ValueError for invalid/reused input or too many introductions;
        PermissionError for blocks. SQLite errors roll back with the caller.
    """
    social.ensure(db,sender,target)
    text=body.get('text','');client=body.get('client_id','')
    if not isinstance(text,str) or len(text)>4000:
        raise ValueError('Introductions must be at most 4000 characters')
    text=text.strip()
    if text and (not isinstance(client,str) or not 1<=len(client)<=80):
        raise ValueError('Retry this introduction with its original request ID')
    if accepted(db,sender,target):
        connect(db,sender,target)
        return {'state':'accepted'}
    now=int(time.time())
    old=db.execute('SELECT state FROM social_message_requests WHERE sender=? AND target=?',(sender,target)).fetchone()
    if not old:
        db.execute("INSERT INTO social_message_requests VALUES(?,?,'pending',?)",(sender,target,now))
        social.notice(db,target,sender,'message_request')
    # A recipient's decline cannot be undone or inferred by sending new text.
    if old and old['state']=='declined':
        return {'state':'pending'}
    if text:
        prior=db.execute('SELECT * FROM message_request_previews WHERE sender=? AND client_id=?',(sender,client)).fetchone()
        if prior and (prior['target']!=target or prior['text']!=text):
            raise ValueError('This introduction ID was already used for different content')
        if not prior:
            count=db.execute('SELECT COUNT(*) FROM message_request_previews WHERE sender=? AND target=? AND message_id IS NULL',(sender,target)).fetchone()[0]
            if count>=3:
                raise ValueError('Wait for acceptance before sending more introductions')
            db.execute('INSERT INTO message_request_previews VALUES(?,?,?,?,?,NULL)',(sender,target,client,text,now))
    return {'state':'pending'}


def previews(db, uid):
    """List recipient-owned requests with safe text/reaction previews, without reads.

    Args: db (Connection), uid (str). Returns: list[dict] public sender cards.
    Raises: SQLite errors. Private Vibe media/captions and read timestamps omitted.
    """
    rows=db.execute('''SELECT u.id,u.name,u.nickname,r.created FROM social_message_requests r
        JOIN users u ON u.id=r.sender WHERE r.target=? AND r.state='pending'
        ORDER BY r.created DESC,u.id LIMIT 100''',(uid,)).fetchall()
    result=[]
    for row in rows:
        if social.blocked(db,uid,row['id']):
            continue
        item=dict(row)
        texts=db.execute('SELECT text,created FROM message_request_previews WHERE sender=? AND target=? AND message_id IS NULL ORDER BY created,client_id',(row['id'],uid)).fetchall()
        reactions=db.execute('SELECT emoji,created FROM vibe_reaction_deliveries WHERE sender=? AND recipient=? AND message_id IS NULL ORDER BY created',(row['id'],uid)).fetchall()
        item['previews']=sorted([dict(text=r['text'],time=r['created'],kind='introduction') for r in texts]+
            [dict(text='Reply to Vibe · '+r['emoji'],time=r['created'],kind='vibe_reaction') for r in reactions],key=lambda p:p['time'])
        result.append(item)
    return result


def deliver(db, sender, recipient):
    """Convert introductions to ordinary messages only after recipient acceptance.

    Args: db (Connection), sender/recipient (str). Returns: None.
    Raises: SQLite errors; the enclosing acceptance transaction rolls back.
    Stable internal client IDs prevent repeat acceptance duplicating a message.
    """
    for row in db.execute('SELECT * FROM message_request_previews WHERE sender=? AND target=? AND message_id IS NULL ORDER BY created,client_id',(sender,recipient)).fetchall():
        client='mreq:'+hashlib.sha256((sender+':'+row['client_id']).encode()).hexdigest()
        db.execute('INSERT OR IGNORE INTO messages(sender,recipient,text,time,client_id) VALUES(?,?,?,?,?)',
                   (sender,recipient,row['text'],row['created']*1000,client))
        mid=db.execute('SELECT id FROM messages WHERE sender=? AND client_id=?',(sender,client)).fetchone()[0]
        existing=db.execute('SELECT recipient,text FROM messages WHERE id=?',(mid,)).fetchone()
        if existing['recipient']!=recipient or existing['text']!=row['text']:
            raise ValueError('Introduction retry conflicts with another message')
        db.execute('UPDATE message_request_previews SET message_id=? WHERE sender=? AND client_id=?',(mid,sender,row['client_id']))
    __import__('vibe_messages').accept_pending(db,sender,recipient)


def report(db, uid, target, body):
    """Record a request report once using the existing moderation queue.

    Args: db (Connection), uid/target (str), body (dict): reason and client_id.
    Returns: dict with reported flag/report ID. No implicit block/decline occurs.
    Raises: ValueError for invalid/reused input; PermissionError for non-recipients.
    """
    reason=body.get('reason','');client=body.get('client_id','')
    if not isinstance(reason,str) or not 5<=len(reason.strip())<=1000 or not isinstance(client,str) or not 1<=len(client)<=80:
        raise ValueError('Explain the report in 5–1000 characters')
    reason=reason.strip()
    if not db.execute('SELECT 1 FROM social_message_requests WHERE sender=? AND target=?',(target,uid)).fetchone():
        raise PermissionError('Message request unavailable')
    prior=db.execute('SELECT * FROM message_request_reports WHERE owner=? AND client_id=?',(uid,client)).fetchone()
    if prior:
        if prior['target']!=target or prior['reason']!=reason:
            raise ValueError('Report retry content changed')
        return {'reported':True,'report_id':prior['report_id']}
    mid=db.execute('INSERT INTO social_reports(actor,target,reason,created) VALUES(?,?,?,?)',(uid,target,reason,int(time.time()))).lastrowid
    db.execute('INSERT INTO message_request_reports VALUES(?,?,?,?,?)',(uid,client,target,reason,mid))
    return {'reported':True,'report_id':mid}
