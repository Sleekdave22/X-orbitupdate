"""Appeal holds protect private evidence without silently rewriting final results.

All times are Unix seconds. Callers own the database transaction; cleanup and
appeal submission both use BEGIN IMMEDIATE so bytes cannot disappear mid-request.
The existing match's frozen retention policy also supplies its appeal window.
"""

import json
import time


def init(d):
    """Create additive retention/appeal tables on a SQLite connection; return None.

    Args: d (sqlite3.Connection): Startup connection, owned by the caller.
    Raises: sqlite3.Error: Schema failure; initialization must not report success.
    """
    d.executescript('''
        CREATE TABLE IF NOT EXISTS result_evidence_retention(
          kind TEXT,match_id TEXT,appeal_until INTEGER NOT NULL,
          PRIMARY KEY(kind,match_id));
        CREATE TABLE IF NOT EXISTS result_evidence_appeals(
          kind TEXT,match_id TEXT,uid TEXT,reason TEXT NOT NULL,
          created INTEGER NOT NULL,state TEXT NOT NULL DEFAULT 'open',
          reviewer TEXT,decision TEXT,resolved INTEGER,
          PRIMARY KEY(kind,match_id,uid));
    ''')


def schedule(d, m, seconds, now=None):
    """Freeze the appeal deadline and align all evidence expiry with it.

    Args:
        d (sqlite3.Connection): Caller-owned write transaction.
        m (dict): Match with kind/id, already finalized by the authoritative path.
        seconds (int): Frozen competition retention policy in seconds.
        now (int|None): Test clock; defaults to current Unix seconds.
    Returns: None. Repeated finalization cannot extend the original deadline.
    Raises: sqlite3.Error: Persistence failure rolls back the finalization.
    """
    now = int(time.time()) if now is None else now
    d.execute('INSERT OR IGNORE INTO result_evidence_retention VALUES(?,?,?)',
              (m['kind'], m['id'], now + seconds))
    deadline = d.execute('SELECT appeal_until FROM result_evidence_retention WHERE kind=? AND match_id=?',
                         (m['kind'], m['id'])).fetchone()[0]
    d.execute('UPDATE result_review_videos SET expires=? WHERE kind=? AND match_id=?',
              (deadline, m['kind'], m['id']))
    if m['kind'] == 'open':
        d.execute('UPDATE gb_evidence SET expires=? WHERE match=?', (deadline, m['id']))
    else:
        d.execute('INSERT OR REPLACE INTO gb_comp_retention VALUES(?,?)', (m['id'], deadline))


def held(d, kind, match_id):
    """Return bool for an unresolved appeal; propagate SQLite errors.

    Args: d (sqlite3.Connection), kind (str), match_id (str): Exact evidence key.
    Holds include correction requests: closing a screen must never release proof.
    """
    return bool(d.execute("SELECT 1 FROM result_evidence_appeals WHERE kind=? AND match_id=? AND state IN ('open','correction_required')",
                          (kind, match_id)).fetchone())


def status(d, m, uid, now=None):
    """Return participant-safe appeal metadata; never include the opponent's reason.

    Args: d (sqlite3.Connection), m (dict), uid (str), now (int|None): Read context.
    Returns: dict with deadline, own appeal state, hold flag and filing eligibility.
    Raises: sqlite3.Error: Query failure; no state changes are performed.
    """
    now = int(time.time()) if now is None else now
    policy = d.execute('SELECT appeal_until FROM result_evidence_retention WHERE kind=? AND match_id=?',
                       (m['kind'], m['id'])).fetchone()
    own = d.execute('SELECT state FROM result_evidence_appeals WHERE kind=? AND match_id=? AND uid=?',
                    (m['kind'], m['id'], uid)).fetchone()
    deadline = policy[0] if policy else None
    return {'appeal_until': deadline, 'appeal_state': own[0] if own else None,
            'evidence_held': held(d, m['kind'], m['id']),
            'can_appeal': bool(uid in (m['a'], m['b']) and m['state'] in ('verified', 'confirmed')
                               and deadline and now <= deadline and not own)}


def reviewer(d, m, uid):
    """Require an independent authorized reviewer, returning None on success.

    Args: d (sqlite3.Connection), m (dict), uid (str): Match and authenticated actor.
    Raises: PermissionError: Participant or actor outside existing moderator roles.
    SQLite failures propagate; no new role or permission is introduced.
    """
    import gaming
    allowed = gaming.admin(d, uid)
    if m['kind'] == 'fixture':
        league = d.execute('SELECT * FROM leagues WHERE id=?', (m['league'],)).fetchone()
        allowed = bool(league and gaming.mod(d, dict(league), uid))
    if uid in (m['a'], m['b']) or not allowed:
        raise PermissionError('Evidence is private to an independent authorised reviewer')


def appeal(server, uid, body, decide=False):
    """File an evidence hold or record an independent appeal decision atomically.

    Args:
        server (ChatServer): Database owner; authentication is supplied by HTTP.
        uid (str): Session account. Participants file, independent reviewers decide.
        body (dict): room/match, reason; decisions also require player/outcome.
        decide (bool): Resolve with upheld or correction_required, never new scores.
    Returns: dict with ok=True; exact retries are idempotent.
    Raises: ValueError: Closed window, invalid reason/outcome or conflicting retry.
        PermissionError: Nonparticipant filing or unauthorized decision.
        sqlite3.Error: Entire operation rolls back, including notifications.

    A requested correction stays on hold. Changing finalized scores requires a
    separate audited reversal/recalculation; this endpoint cannot bypass rankings.
    """
    import result_reviews as reviews
    reason = str(body.get('reason', '')).strip()
    if not 10 <= len(reason) <= 1000:
        raise ValueError('Explain the appeal or decision in 10–1000 characters')
    now = int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        m = reviews.match(d, str(body.get('room') or body.get('match') or ''))
        if decide:
            reviewer(d, m, uid)
            player = str(body.get('player', ''))
            outcome = body.get('outcome')
            if outcome not in ('upheld', 'correction_required'):
                raise ValueError('Choose uphold result or require an audited correction')
            item = d.execute('SELECT * FROM result_evidence_appeals WHERE kind=? AND match_id=? AND uid=?',
                             (m['kind'], m['id'], player)).fetchone()
            if not item:
                raise ValueError('Appeal not found')
            if item['state'] != 'open':
                if item['state'] == outcome and item['decision'] == reason:
                    return {'ok': True, 'already_decided': True}
                raise ValueError('This appeal already has a recorded decision')
            d.execute('UPDATE result_evidence_appeals SET state=?,reviewer=?,decision=?,resolved=? WHERE kind=? AND match_id=? AND uid=?',
                      (outcome, uid, reason, now, m['kind'], m['id'], player))
            action = 'evidence_appeal_decided'
            details = {'player': player, 'outcome': outcome, 'reason': reason}
            text = ('Appeal reviewed: the recorded result is upheld.' if outcome == 'upheld' else
                    'Appeal requires an audited result correction. Evidence remains protected; the recorded score has not been silently changed.')
        else:
            if uid not in (m['a'], m['b']):
                raise PermissionError('Only the assigned players may appeal this result')
            item = d.execute('SELECT reason FROM result_evidence_appeals WHERE kind=? AND match_id=? AND uid=?',
                             (m['kind'], m['id'], uid)).fetchone()
            if item:
                if item['reason'] == reason:
                    return {'ok': True, 'already_submitted': True}
                raise ValueError('Your original appeal is already recorded')
            if not status(d, m, uid, now)['can_appeal']:
                raise ValueError('The appeal window is closed or the result is not finalized')
            d.execute('INSERT INTO result_evidence_appeals(kind,match_id,uid,reason,created) VALUES(?,?,?,?,?)',
                      (m['kind'], m['id'], uid, reason, now))
            action, details = 'evidence_appeal_opened', {'reason': reason}
            text = 'A match-result appeal is awaiting independent review. Evidence is protected; the recorded score remains unchanged.'
        reviews.audit(d, m, uid, action, details)
        reviews.notify(d, m, text)
    return {'ok': True}


def summary(d, m, uid):
    """Return structured private findings to an independent reviewer only.

    Args: d (sqlite3.Connection), m (dict), uid (str): Authenticated review context.
    Returns: dict containing policy, findings, original reports, appeals and audit.
    Raises: PermissionError: Role/independence failure. SQLite/JSON errors propagate.
    Evidence bytes remain behind the separately authorized no-store media routes.
    """
    reviewer(d, m, uid)
    job = d.execute('SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',
                    (m['kind'], m['id'])).fetchone()
    uploads = []
    for row in d.execute('SELECT uid,stage,created,analysis,legacy FROM result_review_uploads WHERE kind=? AND match_id=? ORDER BY created,uid,stage',
                         (m['kind'], m['id'])):
        item = dict(row)
        item['analysis'] = json.loads(item['analysis']) if item['analysis'] else None
        uploads.append(item)
    table, key = ('gb_reports', 'match') if m['kind'] == 'open' else ('game_reports', 'fixture')
    scores = 'a AS score_a,b AS score_b' if m['kind'] == 'open' else 'score_a,score_b'
    return {'match': m['id'], 'kind': m['kind'], 'game': m['game'],
            'participants': [m['a'], m['b']], 'state': m['state'],
            'review': {key: job[key] for key in ('state', 'stage', 'policy', 'reason', 'finished', 'deadline', 'attempts')} if job else None,
            'decision': json.loads(job['decision']) if job and job['decision'] else None,
            'reports': [dict(r) for r in d.execute('SELECT uid,'+scores+' FROM '+table+' WHERE '+key+'=?', (m['id'],))],
            'findings': uploads,
            'appeals': [dict(r) for r in d.execute('SELECT uid,reason,created,state,reviewer,decision,resolved FROM result_evidence_appeals WHERE kind=? AND match_id=? ORDER BY created', (m['kind'], m['id']))],
            'retention': status(d, m, uid),
            'audit': [dict(r) for r in d.execute('SELECT actor,action,created,reason FROM gb_events WHERE match=? ORDER BY id', (m['id'],))],
            'limitation': 'OCR and selected-frame consistency checks do not establish publisher authenticity or rule out manipulation.'}


def purge(d, now):
    """Remove due finalized evidence bytes, retaining decision/audit metadata.

    Args: d (sqlite3.Connection): Caller-owned write transaction; now (int): Unix time.
    Returns: None. Unresolved matches and open/correction appeals are never purged.
    Raises: sqlite3.Error: Caller must roll back; partial cleanup is not success.
    Legacy final results without appeal metadata retain their original expiry.
    """
    import gamebox_core
    for item in d.execute("SELECT e.match,e.uid FROM gb_evidence e JOIN gb_matches m ON m.id=e.match WHERE e.image IS NOT NULL AND e.expires<? AND m.state='verified'", (now,)).fetchall():
        if not held(d, 'open', item['match']):
            d.execute("UPDATE gb_evidence SET image=NULL,reading='' WHERE match=? AND uid=?", (item['match'], item['uid']))
            forget_reading(d, 'open', item['match'], item['uid'], 'photo')
            gamebox_core.event(d, item['match'], 'system', 'ordinary_evidence_expired', new={'uid': item['uid']})
    for item in d.execute("SELECT r.fixture FROM gb_comp_retention r JOIN fixtures f ON f.id=r.fixture WHERE r.expires<? AND f.state='confirmed'", (now,)).fetchall():
        if not held(d, 'fixture', item['fixture']):
            d.execute("UPDATE game_reports SET image=NULL,ocr='' WHERE fixture=?", (item['fixture'],))
            for report in d.execute('SELECT uid FROM game_reports WHERE fixture=?', (item['fixture'],)).fetchall():
                forget_reading(d, 'fixture', item['fixture'], report['uid'], 'photo')
            d.execute('DELETE FROM gb_comp_retention WHERE fixture=?', (item['fixture'],))
            gamebox_core.event(d, item['fixture'], 'system', 'ordinary_competition_evidence_expired')
    for item in d.execute('SELECT kind,match_id,uid FROM result_review_videos WHERE expires<? AND video IS NOT NULL', (now,)).fetchall():
        if held(d, item['kind'], item['match_id']):
            continue
        table = 'gb_matches' if item['kind'] == 'open' else 'fixtures'
        match = d.execute('SELECT state FROM '+table+' WHERE id=?', (item['match_id'],)).fetchone()
        if match and match['state'] in ('verified', 'confirmed', 'void', 'cancelled', 'walkover'):
            d.execute('UPDATE result_review_videos SET video=NULL WHERE kind=? AND match_id=? AND uid=?',
                      (item['kind'], item['match_id'], item['uid']))
            forget_reading(d, item['kind'], item['match_id'], item['uid'], 'video')


def forget_reading(d, kind, match_id, uid, stage):
    """Discard extracted raw text when corresponding evidence bytes expire.

    Args: d (sqlite3.Connection), kind/match_id/uid/stage (str): Exact upload key.
    Returns: None; retains score, reason, policy, digest and original submission time.
    Raises: SQLite/JSON errors: Caller rolls back cleanup rather than losing audit.
    Full OCR text can include unrelated screen details and is not a decision record.
    """
    item = d.execute('SELECT analysis FROM result_review_uploads WHERE kind=? AND match_id=? AND uid=? AND stage=?',
                     (kind, match_id, uid, stage)).fetchone()
    if item and item['analysis']:
        analysis = json.loads(item['analysis'])
        analysis.pop('text', None)
        d.execute('UPDATE result_review_uploads SET analysis=? WHERE kind=? AND match_id=? AND uid=? AND stage=?',
                  (json.dumps(analysis), kind, match_id, uid, stage))
