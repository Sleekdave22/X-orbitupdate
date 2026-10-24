"""Private, durable screenshot review. OCR extracts evidence; rules decide or defer.

No cloud provider, peer image transfer, money movement or client-supplied OCR is used.
Images remain in the existing private evidence tables. Matching typed reports retain
their existing path; screenshot review freezes a disputed result until a decision.
"""
import base64,hashlib,io,json,re,subprocess,sys,threading,time,unicodedata,uuid
from pathlib import Path

CLOSED={'verified','confirmed','void','walkover','cancelled'}
TERMINAL={'finalized','needs_human','closed'}
QUEUE_SECONDS=60
POLICY='local-ocr-conservative-v2'
RESPONSE_SECONDS=15*60

def row(d,sql,args=()):
    r=d.execute(sql,args).fetchone()
    return dict(r) if r else None

def match(d,rid):
    m=row(d,'SELECT * FROM gb_matches WHERE id=?',(rid,))
    if m:return m|{'kind':'open'}
    m=row(d,'SELECT f.*,l.game FROM fixtures f JOIN leagues l ON l.id=f.league WHERE f.id=?',(rid,))
    if not m:raise ValueError('Match not found')
    return m|{'kind':'fixture'}

def identities(d,m):
    if m['kind']=='open':gids={m['a']:m['gid_a'],m['b']:m['gid_b']}
    else:gids={r['uid']:r['game_id'] for r in d.execute('SELECT uid,game_id FROM league_members WHERE league=?',(m['league'],))}
    aliases={}
    for uid in (m['a'],m['b']):
        gid=gids.get(uid,'');names=[gid] if gid else []
        current=row(d,'SELECT i.game_id,m.nickname FROM gb_game_ids i JOIN gb_identity_meta m ON m.uid=i.uid AND m.game=i.game WHERE i.uid=? AND i.game=?',(uid,m['game']))
        if current and norm(current['game_id'])==norm(gid) and current['nickname']:names.append(current['nickname'])
        aliases[uid]=list(dict.fromkeys(names))
    return aliases

def init(server):
    with server.db() as d:
        d.executescript('''
        CREATE TABLE IF NOT EXISTS result_review_jobs(
          kind TEXT,match_id TEXT,state TEXT NOT NULL,policy TEXT NOT NULL,
          aliases TEXT NOT NULL,created INTEGER NOT NULL,ready_at INTEGER,
          lease TEXT,lease_until INTEGER,attempts INTEGER NOT NULL DEFAULT 0,
          reason TEXT NOT NULL DEFAULT '',decision TEXT,finished INTEGER,
          stage TEXT NOT NULL DEFAULT 'photo',deadline INTEGER,response_seconds INTEGER NOT NULL DEFAULT 900,
          PRIMARY KEY(kind,match_id));
        CREATE TABLE IF NOT EXISTS result_review_uploads(
          kind TEXT,match_id TEXT,uid TEXT,digest TEXT NOT NULL,created INTEGER NOT NULL,
          analysis TEXT,legacy INTEGER NOT NULL DEFAULT 0,stage TEXT NOT NULL DEFAULT 'photo',
          PRIMARY KEY(kind,match_id,uid,stage));
        CREATE TABLE IF NOT EXISTS result_review_videos(
          kind TEXT,match_id TEXT,uid TEXT,video BLOB,mime TEXT,digest TEXT UNIQUE,
          created INTEGER,expires INTEGER,PRIMARY KEY(kind,match_id,uid));
        CREATE INDEX IF NOT EXISTS result_review_due ON result_review_jobs(state,ready_at,lease_until);
        ''')
        # Existing originals stay immutable and require a human decision. They are
        # never silently promoted into newly approved automated evidence.
        for kind,sql in (
            ('open',"SELECT e.match mid,e.uid,e.digest FROM gb_evidence e JOIN gb_matches m ON m.id=e.match WHERE e.image IS NOT NULL AND m.state IN ('review','disputed')"),
            ('fixture',"SELECT e.fixture mid,e.uid,e.digest FROM game_reports e JOIN fixtures f ON f.id=e.fixture WHERE e.image IS NOT NULL AND f.state IN ('pending','disputed')")):
            for item in d.execute(sql).fetchall():
                m=match(d,item['mid'])
                if item['uid'] not in (m['a'],m['b']):continue
                register(d,m,item['uid'],item['digest'],int(time.time()),legacy=True)
    server._result_review_lock=threading.Lock()

def audit(d,m,actor,action,details):
    import gamebox_core,gaming
    gamebox_core.event(d,m['id'],actor,action,new=details)
    if m['kind']=='fixture':gaming.audit(d,m['id'],actor,action,json.dumps(details))

def register(d,m,uid,digest,now,legacy=False,stage='photo'):
    d.execute("INSERT OR IGNORE INTO result_review_jobs(kind,match_id,state,policy,aliases,created) VALUES(?,?,'waiting_other',?,?,?)",(m['kind'],m['id'],POLICY,json.dumps(identities(d,m)),now))
    d.execute('INSERT OR IGNORE INTO result_review_uploads(kind,match_id,uid,digest,created,legacy,stage) VALUES(?,?,?,?,?,?,?)',(m['kind'],m['id'],uid,digest,now,int(legacy),stage))
    job=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],m['id']))
    if stage!=job['stage']:return
    if job['deadline'] is None:d.execute('UPDATE result_review_jobs SET deadline=? WHERE kind=? AND match_id=?',(now+job['response_seconds'],m['kind'],m['id']))
    uploads=list(d.execute('SELECT uid,legacy FROM result_review_uploads WHERE kind=? AND match_id=? AND stage=?',(m['kind'],m['id'],stage)))
    if {r['uid'] for r in uploads}=={m['a'],m['b']} and job['state']=='waiting_other':
        state='needs_human' if any(r['legacy'] for r in uploads) else 'queued'
        reason='Existing original evidence requires independent review.' if state=='needs_human' else ''
        d.execute('UPDATE result_review_jobs SET state=?,ready_at=?,reason=? WHERE kind=? AND match_id=?',(state,now+QUEUE_SECONDS,reason,m['kind'],m['id']))
        if not legacy:
            audit(d,m,'system','private_evidence_ready',{'status':state,'policy':POLICY})
            notify(d,m,'Both private screenshots received. '+('An independent reviewer is required.' if state=='needs_human' else 'Result review is queued; clear evidence is normally processed within a few minutes.'))

def notify(d,m,text):
    import gamebox_core
    for uid in (m['a'],m['b']):
        ident=gamebox_core.notice(d,uid,text)
        __import__('account_notifications').link_play(d,ident,'open',m['id'],m['kind'])

def status(d,m,uid):
    job=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],m['id']))
    stage=job['stage'] if job else 'photo'
    uploads=list(d.execute('SELECT uid,created FROM result_review_uploads WHERE kind=? AND match_id=? AND stage=?',(m['kind'],m['id'],stage)))
    own=next((r for r in uploads if r['uid']==uid),None)
    # Receipt metadata only: never return another player's image, OCR or proposed score.
    return {'state':job['state'] if job else 'not_submitted','submitted':bool(own),
            'submitted_at':own['created'] if own else None,'received':len(uploads),
            'required':2,'stage':stage,'deadline':job['deadline'] if job else None,
            'response_seconds':job['response_seconds'] if job else RESPONSE_SECONDS,
            'can_upload':not own and m['state'] not in CLOSED and (not job or not job['deadline'] or time.time()<=job['deadline']),
            'automatic':bool(job and job['state'] in ('queued','processing')),
            'score':[m['score_a'],m['score_b']] if m['state'] in ('verified','confirmed') else None}

def active(d,m):
    return bool(d.execute('SELECT 1 FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],m['id'])).fetchone())

def validated_image(body):
    import gaming
    encoded=body.get('image','')
    if not isinstance(encoded,str) or len(encoded)>7*1024*1024:raise ValueError('Choose a PNG/JPEG under 5 MB')
    try:
        raw,mime=gaming.image(body)
        from PIL import Image
        with Image.open(io.BytesIO(raw)) as image:
            if image.width*image.height>24000000 or image.format not in ('PNG','JPEG'):raise ValueError('Choose a PNG/JPEG up to 24 megapixels')
            image.verify()
    except Exception as error:raise ValueError('Choose a complete, readable PNG/JPEG under 5 MB') from error
    return raw,mime

def validated_media(body):
    capture=body.get('capture_mode')
    if capture!='camera':raise ValueError('Reopen the result screen and use its camera controls')
    if str(body.get('mime','')).startswith('video/'):
        encoded=body.get('image','')
        if not isinstance(encoded,str) or len(encoded)>28*1024*1024:raise ValueError('Record a video up to 20 MB')
        try:raw=base64.b64decode(encoded,validate=True)
        except Exception as error:raise ValueError('Invalid recording') from error
        if not 1<=len(raw)<=20*1024*1024:raise ValueError('Record a video up to 20 MB')
        info=video_probe(raw)
        return raw,info['mime'],'video'
    raw,mime=validated_image(body)
    return raw,mime,'photo'

def submit(server,uid,body):
    rid=str(body.get('room') or body.get('match') or body.get('fixture') or '')
    with server.db() as d:
        m=match(d,rid)
        if uid not in (m['a'],m['b']):raise PermissionError('Only the assigned players may submit evidence')
    raw,mime,stage=validated_media(body);digest=hashlib.sha256(raw).hexdigest();now=int(time.time())
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE');m=match(d,rid)
        if uid not in (m['a'],m['b']):raise PermissionError('Only the assigned players may submit evidence')
        job=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],rid))
        existing=row(d,'SELECT * FROM result_review_uploads WHERE kind=? AND match_id=? AND uid=? AND stage=?',(m['kind'],rid,uid,stage))
        if existing:
            if existing['digest']!=digest:raise ValueError('Your original evidence is already submitted. Await review; replacements are locked.')
            return {'ok':True,'already_submitted':True,'review':status(d,m,uid)}
        if m['state'] in CLOSED:raise ValueError('This match is closed')
        if job and job['stage']=='video' and stage=='photo':raise ValueError('Photo review is complete. Record video evidence now.')
        if job and job['stage']==stage and job['deadline'] and now>job['deadline']:raise ValueError('The response deadline passed; evidence is being reviewed')
        if m['kind']=='open' and m['state'] not in ('awaiting_results','disputed','review'):raise ValueError('Finish and check in to the match before uploading results')
        if m['kind']=='fixture':
            if now<m['opens']:raise ValueError('The match window has not opened')
            league=row(d,'SELECT * FROM leagues WHERE id=?',(m['league'],))
            check=row(d,'SELECT * FROM gb_schedule WHERE fixture=?',(rid,))
            if m['state'] not in ('disputed','pending') and league['verification']=='typed' and (not check or not check['ready_a'] or not check['ready_b']):raise ValueError('Both players must check in before reporting')
        for sql,args in (
            ('SELECT 1 FROM gb_evidence WHERE digest=? AND (match!=? OR uid!=?)',(digest,rid,uid)),
            ('SELECT 1 FROM game_reports WHERE digest=? AND (fixture!=? OR uid!=?)',(digest,rid,uid))):
            if d.execute(sql,args).fetchone():raise ValueError('This screenshot was already used. Submit your own original result screenshot.')
        if d.execute('SELECT 1 FROM result_review_videos WHERE digest=? AND (match_id!=? OR uid!=?)',(digest,rid,uid)).fetchone():raise ValueError('This recording was already used')
        if stage=='video':
            d.execute('INSERT INTO result_review_videos VALUES(?,?,?,?,?,?,?,NULL)',(m['kind'],rid,uid,raw,mime,digest,now))
            if not job:
                d.execute("INSERT INTO result_review_jobs(kind,match_id,state,policy,aliases,created,stage) VALUES(?,?,'waiting_other',?,?,?,'video')",(m['kind'],rid,POLICY,json.dumps(identities(d,m)),now))
            elif job['stage']=='photo':
                d.execute("UPDATE result_review_jobs SET stage='video',state='waiting_other',deadline=NULL,ready_at=NULL,lease=NULL,lease_until=NULL,attempts=0 WHERE kind=? AND match_id=?",(m['kind'],rid))
                notify(d,m,'Video evidence is now requested from both players. Keep both gaming IDs visible while navigating to match details and final scores.')
            table='gb_matches' if m['kind']=='open' else 'fixtures'
            d.execute('UPDATE '+table+' SET state=? WHERE id=?',('review' if m['kind']=='open' else 'disputed',rid))
        elif m['kind']=='open':
            if d.execute('SELECT 1 FROM gb_evidence WHERE match=? AND uid=?',(rid,uid)).fetchone():raise ValueError('Your original evidence is already submitted')
            d.execute('INSERT INTO gb_evidence VALUES(?,?,?,?,?,?,NULL)',(rid,uid,raw,mime,digest,''))
            d.execute("UPDATE gb_matches SET state='review' WHERE id=?",(rid,))
        else:
            prior=row(d,'SELECT * FROM game_reports WHERE fixture=? AND uid=?',(rid,uid))
            if prior and prior['image'] is not None:raise ValueError('Your original evidence is already submitted')
            d.execute("INSERT INTO game_reports(fixture,uid,image,mime,digest,ocr) VALUES(?,?,?,?,?,'') ON CONFLICT(fixture,uid) DO UPDATE SET image=excluded.image,mime=excluded.mime,digest=excluded.digest,ocr=''",(rid,uid,raw,mime,digest))
            d.execute("UPDATE fixtures SET state='disputed' WHERE id=?",(rid,))
        register(d,m,uid,digest,now,stage=stage)
        audit(d,m,uid,'private_evidence_submitted',{'digest':digest,'stage':stage,'capture_mode':body['capture_mode'],'policy':POLICY})
        notify(d,m,'Private result evidence received. Respond within 15 minutes. Validated proof may decide the result if the other player is silent. Keep the game result screen open.')
        return {'ok':True,'review':status(d,match(d,rid),uid)}

def require_both(d,m):
    job=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],m['id']))
    if not job:return
    count=d.execute('SELECT COUNT(*) FROM result_review_uploads WHERE kind=? AND match_id=? AND stage=?',(m['kind'],m['id'],job['stage'])).fetchone()[0]
    if not count or count<2 and (not job['deadline'] or time.time()<job['deadline']):raise ValueError('Wait for the other player or the 15-minute response deadline, then validate the evidence before deciding')

def finalized(d,kind,rid,a,b,actor,reason):
    previous=row(d,'SELECT state FROM result_review_jobs WHERE kind=? AND match_id=?',(kind,rid))
    d.execute("UPDATE result_review_jobs SET state='finalized',decision=?,reason=?,finished=?,lease=NULL,lease_until=NULL WHERE kind=? AND match_id=?",(json.dumps({'score':[a,b],'actor':actor}),reason[:500],int(time.time()),kind,rid))
    m=match(d,rid)
    if previous and previous['state']!='finalized':notify(d,m,'Match dispute resolved: '+str(a)+' – '+str(b)+'. Open the final result.')
    rules=json.loads(m['rules']) if kind=='open' else json.loads(row(d,'SELECT policy_snapshot FROM leagues WHERE id=?',(m['league'],))['policy_snapshot'] or __import__('gamebox_core').current(d)['config'])
    d.execute('UPDATE result_review_videos SET expires=? WHERE kind=? AND match_id=?',(int(time.time())+rules['retention_seconds'],kind,rid))

def norm(value):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKC',str(value)).casefold())

def extract(reading,aliases,a,b,game):
    """Conservative supported layout: final marker + two identities + one score.

    Confidence is a reader threshold, not a probability of authenticity. A hidden
    name, unusual layout, ambiguous orientation or conflicting number is deferred.
    """
    if game not in ('efootball','fc_mobile') or not reading.get('available'):return None,'Unsupported game or screenshot reader unavailable.'
    lines=reading.get('lines',[])[:200]
    good=[r for r in lines if isinstance(r,dict) and isinstance(r.get('text'),str) and isinstance(r.get('confidence'),(int,float)) and r['confidence']>=.95]
    if not any(re.search(r'\b(full[ -]?time|final score|match result|match ended)\b',r['text'],re.I) for r in good):return None,'Final result screen could not be established.'
    names={uid:{norm(s) for s in aliases.get(uid,[]) if len(norm(s))>=3} for uid in (a,b)}
    names[a]-=names[b];names[b]-={norm(s) for s in aliases.get(a,[]) if len(norm(s))>=3}
    found={uid:[] for uid in (a,b)}
    for line in good:
        for uid in (a,b):
            if norm(line['text']) in names[uid]:found[uid].append(line)
    # Named rows are also supported when the score is explicitly beside that ID.
    rows={uid:[] for uid in (a,b)}
    for line in good:
        if line['confidence']<.95:continue
        parsed=re.fullmatch(r'(.+?)\s+(\d{1,2})',line['text'].strip())
        if parsed:
            for uid in (a,b):
                if norm(parsed[1]) in names[uid]:rows[uid].append(int(parsed[2]))
    if all(len(set(rows[uid]))==1 for uid in (a,b)):
        return [rows[a][0],rows[b][0]],'Both final-score rows explicitly identify their registered players.'
    if not all(found[uid] for uid in (a,b)):return None,'Both registered gaming identities were not read confidently.'
    pairs=[]
    for line in lines:
        parsed=re.fullmatch(r'\s*(?:final score\s*:?\s*)?(\d{1,2})\s*[-–:]\s*(\d{1,2})\s*',str(line.get('text','')),re.I)
        if parsed:
            if line.get('confidence',0)<.95:return None,'The score is not clear enough for an automatic decision.'
            pairs.append((int(parsed[1]),int(parsed[2]),line))
    if len({(x,y) for x,y,_ in pairs})!=1:return None,'No unique final score could be extracted.'
    left,right=found[a][0],found[b][0]
    try:
        center=lambda line:(sum(p[0] for p in line['box'])/4,sum(p[1] for p in line['box'])/4)
        ax,ay=center(left);bx,by=center(right);sx,sy=center(pairs[0][2])
        if abs(ax-bx)<60 or abs(ay-by)>100 or abs(sy-(ay+by)/2)>200:raise ValueError()
    except (KeyError,TypeError,ValueError):return None,'Score orientation needs an independent reviewer.'
    x,y,_=pairs[0]
    return ([x,y] if ax<bx else [y,x]),'Registered identities and one final score agree in an unambiguous layout.'

def read_image(raw):
    # Bound inference outside the HTTP loop; do not persist images to temp files.
    code='import json,sys;from gaming_ocr import read;print(json.dumps(read(sys.stdin.buffer.read())))'
    result=subprocess.run([sys.executable,'-c',code],input=raw,capture_output=True,cwd=Path(__file__).parent,timeout=60,check=True)
    return json.loads(result.stdout)

def inspect_video(raw,frames=False):
    import av
    images=[];last=-1;count=0;start=None;next_sample=0
    with av.open(io.BytesIO(raw)) as container:
        streams=container.streams.video
        if len(streams)!=1:raise ValueError('Record one camera video')
        stream=streams[0]
        if stream.width*stream.height>1920*1080:raise ValueError('Use a recording up to 1080p')
        name=container.format.name
        mime='video/webm' if 'webm' in name or 'matroska' in name else 'video/mp4' if 'mp4' in name or 'mov' in name else None
        if not mime:raise ValueError('Use an MP4 or WebM recording')
        for frame in container.decode(stream):
            count+=1
            if count>4000 or frame.time is None:raise ValueError('Recording exceeds the supported duration')
            if start is None:start=float(frame.time)
            elapsed=float(frame.time)-start
            if elapsed<last or elapsed>65:raise ValueError('Record up to 60 seconds with normal timestamps')
            last=elapsed
            if frames and elapsed>=next_sample:
                image=frame.to_image();image.thumbnail((1280,720));out=io.BytesIO();image.save(out,format='JPEG',quality=85)
                images.append(base64.b64encode(out.getvalue()).decode());next_sample+=5
        if last<2:raise ValueError('Record at least 3 seconds showing navigation and the result')
        if frames and len(images)<3:raise ValueError('Record long enough to show navigation and final details')
        return {'mime':mime,'duration':last,'frames':[images[0],images[len(images)//2],images[-1]] if frames else []}

def video_probe(raw,frames=False):
    code='import json,sys;from result_reviews import inspect_video;print(json.dumps(inspect_video(sys.stdin.buffer.read(),'+str(frames)+')))'
    try:
        result=subprocess.run([sys.executable,'-c',code],input=raw,capture_output=True,cwd=Path(__file__).parent,timeout=25,check=True)
        return json.loads(result.stdout)
    except Exception as error:raise ValueError('Could not validate this recording. Record 12–60 seconds, up to 1080p and 20 MB.') from error

def video_reading(raw,aliases,m):
    frames=video_probe(raw,frames=True)['frames'];readings=[read_image(base64.b64decode(frame)) for frame in frames]
    decisions=[extract(r,aliases,m['a'],m['b'],m['game'])[0] for r in readings]
    texts=[str(r.get('text','')) for r in readings]
    # Simple text reading cannot prove navigation or authenticity. Only a very
    # clear supported sequence may pass; everything else goes to a human.
    navigation=[bool(re.search(r'\b(match history|match details|result details)\b',text,re.I)) for text in texts]
    valid=all(decisions) and all(score==decisions[0] for score in decisions) and any(navigation) and len(set(texts))>1
    return decisions[0] if valid else None,'\n'.join(texts)[:6000]

def process_one(server,now=None,reader=None):
    now=int(time.time()) if now is None else now;reader=reader or read_image;lease=uuid.uuid4().hex
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        job=row(d,"SELECT * FROM result_review_jobs WHERE (state='queued' AND ready_at<=?) OR (state='waiting_other' AND deadline<=?) OR (state='processing' AND lease_until<?) ORDER BY created LIMIT 1",(now,now,now))
        if not job:return False
        m=match(d,job['match_id'])
        if m['state'] in CLOSED:
            d.execute("UPDATE result_review_jobs SET state='closed' WHERE kind=? AND match_id=?",(job['kind'],m['id']));return True
        submitted=[r['uid'] for r in d.execute('SELECT uid FROM result_review_uploads WHERE kind=? AND match_id=? AND stage=?',(m['kind'],m['id'],job['stage']))]
        if not submitted:return False
        if len(submitted)<2 and (not job['deadline'] or now<job['deadline']):return False
        if d.execute('SELECT 1 FROM result_review_uploads WHERE kind=? AND match_id=? AND stage=? AND legacy=1',(m['kind'],m['id'],job['stage'])).fetchone():
            hold(d,m,'Existing pre-policy evidence cannot be automatically accepted. New camera video or independent review is required.');return True
        if job['attempts']>=3:
            hold(d,m,'Automated reader could not complete; independent review required.');return True
        d.execute("UPDATE result_review_jobs SET state='processing',lease=?,lease_until=?,attempts=attempts+1 WHERE kind=? AND match_id=?",(lease,now+600,job['kind'],m['id']))
        evidence=[]
        for uid in submitted:
            sql='SELECT video FROM result_review_videos WHERE match_id=? AND uid=? AND kind=?' if job['stage']=='video' else 'SELECT image FROM gb_evidence WHERE match=? AND uid=?' if m['kind']=='open' else 'SELECT image FROM game_reports WHERE fixture=? AND uid=?'
            image=d.execute(sql,(m['id'],uid,m['kind']) if job['stage']=='video' else (m['id'],uid)).fetchone()
            evidence.append((uid,image[0] if image else None))
    readings=[]
    for uid,raw in evidence:
        if job['stage']=='video':
            try:score,text=video_reading(raw,json.loads(job['aliases']),m);reading={'text':text}
            except Exception:score=None;reading={'text':''}
            reason='Video navigation, identities and final score require independent verification.'
        else:
            try:reading=reader(raw) if raw else {'available':False}
            except Exception:reading={'available':False}
            score,reason=extract(reading,json.loads(job['aliases']),m['a'],m['b'],m['game'])
        readings.append((uid,score,reason,str(reading.get('text',''))[:6000]))
    with server.db() as d:
        d.execute('BEGIN IMMEDIATE')
        current=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(job['kind'],m['id']))
        if current['state']!='processing' or current['lease']!=lease:return True
        m=match(d,m['id'])
        if m['state'] in CLOSED:
            d.execute("UPDATE result_review_jobs SET state='closed',lease=NULL WHERE kind=? AND match_id=?",(job['kind'],m['id']));return True
        for uid,score,reason,text in readings:
            d.execute('UPDATE result_review_uploads SET analysis=? WHERE kind=? AND match_id=? AND uid=? AND stage=?',(json.dumps({'score':score,'reason':reason,'text':text,'policy':POLICY}),m['kind'],m['id'],uid,job['stage']))
            if job['stage']=='photo':
                if m['kind']=='open':d.execute('UPDATE gb_evidence SET reading=? WHERE match=? AND uid=?',(text,m['id'],uid))
                else:d.execute('UPDATE game_reports SET ocr=? WHERE fixture=? AND uid=?',(text,m['id'],uid))
        first=readings[0][1];second=readings[1][1] if len(readings)==2 else first
        if first is None or second is None or first!=second:
            hold(d,m,'Screenshots disagree or cannot establish both identities and final scores.');return True
        if m['kind']=='fixture' and m['stage']!='league' and first[0]==first[1]:
            hold(d,m,'Knockout tie-break winner needs independent review.');return True
        reason=('Both independent captures agree' if len(readings)==2 else 'One validated capture; opponent did not respond within 15 minutes')+' under '+POLICY+'. Evidence is not publisher-authenticated.'
        if m['kind']=='open':__import__('gamebox_core').verify(d,m,*first,'system:local-ocr',reason)
        else:__import__('gaming').finalize_review(d,m,*first,'system:local-ocr',reason)
        finalized(d,m['kind'],m['id'],*first,'system:local-ocr',reason)
        audit(d,m,'system:local-ocr','private_evidence_decided',{'score':first,'policy':POLICY})
    return True

def hold(d,m,reason):
    job=row(d,'SELECT * FROM result_review_jobs WHERE kind=? AND match_id=?',(m['kind'],m['id']))
    if job['stage']=='photo':
        d.execute("UPDATE result_review_jobs SET stage='video',state='waiting_other',reason=?,deadline=NULL,ready_at=NULL,lease=NULL,lease_until=NULL,attempts=0 WHERE kind=? AND match_id=?",(reason,m['kind'],m['id']))
        audit(d,m,'system','private_video_evidence_requested',{'reason':reason,'policy':POLICY})
        notify(d,m,'Photo evidence could not settle the result. Use the phone camera to record navigation on the PC/TV, match details, final scores and both gaming IDs. Keep the result screen open. Each video response is due within 15 minutes of the first video submission.')
        return
    d.execute("UPDATE result_review_jobs SET state='needs_human',reason=?,lease=NULL,lease_until=NULL WHERE kind=? AND match_id=?",(reason,m['kind'],m['id']))
    audit(d,m,'system','private_evidence_needs_human',{'reason':reason,'policy':POLICY})
    notify(d,m,'Private result evidence needs an independent reviewer. No score, ranking or league points have changed.')

def dispatch(server):
    with server.db() as d:d.execute('UPDATE result_review_videos SET video=NULL WHERE expires<? AND video IS NOT NULL',(int(time.time()),))
    lock=server._result_review_lock
    if not lock.acquire(blocking=False):return
    def run():
        try:process_one(server)
        except Exception as error:print('Private result review deferred: '+type(error).__name__,flush=True)
        finally:lock.release()
    threading.Thread(target=run,daemon=True).start()
