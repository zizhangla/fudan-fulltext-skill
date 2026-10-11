"""HTTP full-text retrieval from an encrypted local institution session; no UI."""
import argparse,hashlib,json,re,sys
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlparse,parse_qsl
import requests
from credential_store import BASE,transform

STATE=BASE/'fudan-session.dpapi'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--url',required=True);ap.add_argument('--doi',required=True);ap.add_argument('--out',required=True);ap.add_argument('--public-only',action='store_true');ap.add_argument('--probe',action='store_true');ap.add_argument('--session',choices=['carsi','webvpn','legacy'],default='carsi');a=ap.parse_args()
 state_file=BASE/({'carsi':'fudan-carsi-session.dpapi','webvpn':'fudan-webvpn-session.dpapi','legacy':'fudan-session.dpapi'}[a.session])
 u=urlparse(a.url)
 if u.scheme!='https' or u.username or u.password:raise ValueError('HTTPS_REQUIRED')
 if any(any(x in k.lower() for x in ['token','ticket','session','signature','authorization','credential']) for k,v in parse_qsl(u.query)):raise ValueError('SECRET_URL_MUST_STAY_LOCAL')
 session=requests.Session();authenticated_cache=False
 if not a.public_only:
  if not state_file.exists():print(json.dumps({'status':'FULLTEXT_PENDING_INSTITUTION_SESSION','browser_launched':False,'pdf_obtained':False}));return
  state=json.loads(transform(state_file.read_bytes(),True))
  for cookie in state['storage_state']['cookies']:
   session.cookies.set(cookie['name'],cookie['value'],domain=cookie['domain'],path=cookie.get('path','/'),secure=cookie.get('secure',False))
  authenticated_cache=state.get('authentication_verified') is True
  del state
 response=session.get(a.url,timeout=30)
 b=response.content
 if a.probe:
  from html.parser import HTMLParser
  class Links(HTMLParser):
   def __init__(self):super().__init__();self.links=[]
   def handle_starttag(self,tag,attrs):
    if tag=='a':
     href=dict(attrs).get('href','');u=urlparse(href)
     if href and not u.query and not u.username:self.links.append(href)
  parser=Links();parser.feed(response.text)
  print(json.dumps({'status':'HTTP_SESSION_PROBE','http_status':response.status_code,'final_host':urlparse(response.url).hostname,'final_path':urlparse(response.url).path,'browser_launched':False,'login_form':bool(re.search(r'cas-login|cas_login|type=[\"\']password',response.text)),'logout_marker':bool(re.search(r'退出登录|注销|logout',response.text,re.I)),'links':parser.links[:35],'institution_verified':False},ensure_ascii=False));return
 receipt={'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'doi_requested':a.doi,'source_origin':u.hostname,'source_path':u.path,'http_status':response.status_code,'browser_launched':False,'encrypted_session_used':not a.public_only,'session_authentication_previously_verified':authenticated_cache,'pdf_obtained':False,'fulltext_read':False}
 out=Path(a.out);out.mkdir(parents=True,exist_ok=True);stem=hashlib.sha256(a.doi.encode()).hexdigest()[:16]
 if response.status_code!=200 or not b.startswith(b'%PDF-'):
  receipt['status']='HTTP_CHALLENGE_OR_NO_PDF' if response.status_code in [202,403] else 'FULLTEXT_NOT_OBTAINED'
 else:
  import pymupdf as fitz
  with fitz.open(stream=b,filetype='pdf') as doc:
   text='\n\n'.join(page.get_text() for page in doc);receipt['pages']=len(doc)
  receipt.update({'status':'PDF_OBTAINED_IDENTITY_READING_PENDING','pdf_obtained':True,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'doi_text_match':a.doi.lower() in text.lower(),'methods_heading_present':bool(re.search(r'\bmethods\b|\bmethodology\b',text,re.I))})
  pdf=out/(stem+'.pdf');md=out/(stem+'.extracted.txt')
  if pdf.exists() and hashlib.sha256(pdf.read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('DIFFERENT_EXISTING_PDF_NO_OVERWRITE')
  if not pdf.exists():pdf.write_bytes(b)
  md.write_text(text,encoding='utf-8');receipt['pdf']=str(pdf.resolve());receipt['extracted_text']=str(md.resolve())
 (out/(stem+'.fetch_receipt.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'FAILED','error_type':type(e).__name__,'details':'redacted','browser_launched':False}));sys.exit(1)
