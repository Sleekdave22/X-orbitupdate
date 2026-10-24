"""Offline, bounded screenshot reading; no image or text leaves the local server."""
import io,re,threading
from PIL import Image,ImageOps
import numpy as np
from rapidocr_onnxruntime import RapidOCR
_lock=threading.Lock();_engine=None

def read(raw):
 global _engine
 with Image.open(io.BytesIO(raw)) as img:
  if img.width*img.height>24000000:raise ValueError('Screenshot resolution is too large')
  img=ImageOps.exif_transpose(img).convert('RGB');img.thumbnail((1920,1920));pixels=np.array(img)[:,:,::-1].copy()
 if not _lock.acquire(timeout=2):return {'available':False,'text':'','scores':[],'note':'Screenshot reader busy; enter the score manually.'}
 try:
  if _engine is None:_engine=RapidOCR(intra_op_num_threads=2,inter_op_num_threads=2)
  result,_=_engine(pixels);text='\n'.join(r[1] for r in result or [])[:6000]
  scores=list(dict.fromkeys(pair for r in result or [] if float(r[2])>=.8 for pair in re.findall(r'\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b',r[1])))
  lines=[{'box':np.asarray(r[0]).tolist(),'text':str(r[1])[:300],'confidence':float(r[2])} for r in (result or [])[:200]]
  return {'available':True,'text':text,'scores':scores,'lines':lines,'note':'Suggested readings only. Confirm player identities and score; authenticity is not established.'}
 finally:_lock.release()
