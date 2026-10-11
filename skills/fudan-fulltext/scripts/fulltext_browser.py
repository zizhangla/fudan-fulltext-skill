"""Local institution browser; secrets never returned to the orchestrator."""
import argparse,hashlib,json,os,sys
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse,parse_qsl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'vendor'))
from credential_store import load_credentials,BASE,transform
STAGE="INITIALIZING"
def safe_domain(url):
 u=urlparse(url);return u.scheme=='https' and u.hostname in {'webvpn.fudan.edu.cn','id.fudan.edu.cn','uis.fudan.edu.cn'} and not u.username and not u.password
def save_session(context,verified=False):
 payload={'storage_state':context.storage_state(),'authentication_verified':verified,'captured_at_utc':datetime.now(timezone.utc).isoformat()}
 destination=BASE/'fudan-webvpn-session.dpapi';temp=BASE/'fudan-webvpn-session.dpapi.tmp';temp.write_bytes(transform(json.dumps(payload).encode()));temp.replace(destination)

def main():
 global STAGE
 from playwright.sync_api import sync_playwright
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['inspect','login','check','capture-session','access-check','download']);ap.add_argument('--url');ap.add_argument('--out');ap.add_argument('--doi');ap.add_argument('--receipt');ap.add_argument('--follow-cas',action='store_true');a=ap.parse_args()
 def report(data):
  if a.receipt:
   dest=Path(a.receipt);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
  print(json.dumps(data,ensure_ascii=False),flush=True)
 with sync_playwright() as pw:
  if a.action=='login':report({'status':'BROWSER_STARTING_AUTH_UNVERIFIED','authentication_verified':False,'fulltext_obtained':False})
  STAGE="BROWSER_LAUNCH"
  proxy={}
  pu=urlparse(os.environ.get('HTTPS_PROXY',''))
  if pu.scheme=='http' and pu.hostname in {'127.0.0.1','localhost'} and pu.port and not pu.username and not pu.password:proxy={'proxy':{'server':f'http://{pu.hostname}:{pu.port}'}}
  browser=None
  if a.action=='inspect':
   browser=pw.chromium.launch(channel='msedge',headless=True,timeout=20000,**proxy);context=browser.new_context()
  else:context=pw.chromium.launch_persistent_context(str(BASE/'edge-profile'),channel='msedge',headless=False,accept_downloads=True,timeout=20000,**proxy)
  if a.action=='capture-session':
   save_session(context,False);report({'status':'SESSION_ENCRYPTED_FOR_HTTP_FETCH','authentication_verified':False,'credential_values_exposed':False});context.close();return
  if a.action=='access-check':
   from html.parser import HTMLParser
   import re
   class Links(HTMLParser):
    def __init__(self):super().__init__();self.links=[];self.current=None
    def handle_starttag(self,tag,attrs):
     if tag=='a':self.current={'href':dict(attrs).get('href',''),'text':''}
    def handle_data(self,data):
     if self.current is not None:self.current['text']+=data
    def handle_endtag(self,tag):
     if tag=='a' and self.current is not None:self.links.append(self.current);self.current=None
   response=context.request.get(a.url or 'https://webvpn.fudan.edu.cn/',timeout=20000)
   body=response.text();parser=Links();parser.feed(body)
   chosen=[]
   for link in parser.links:
    if re.search(r'IEEE|数据库|图书馆|Springer|Nature|ScienceDirect|Wiley|Optica|退出|注销',link['text'],re.I):
     href=link['href'];u=urlparse(href)
     if not u.query and not u.username:chosen.append({'href':href,'text':link['text'].strip()[:80]})
   report({'status':'INSTITUTION_HTTP_ACCESS_CHECK','http_status':response.status,'host':urlparse(response.url).hostname,'path':urlparse(response.url).path,'login_page':bool(re.search(r'cas-login|cas_login|type=[\"\']password',body)),'database_markers':bool(re.search(r'IEEE|数据库|图书馆',body)),'links':chosen[:25],'fulltext_obtained':False});context.close();return
  page=context.pages[0] if context.pages else context.new_page()
  STAGE='WEBVPN_NAVIGATION'
  try:
   page.goto('https://webvpn.fudan.edu.cn/',wait_until='commit',timeout=30000)
  except Exception:
   print(json.dumps({'status':'NAVIGATION_DIAGNOSTIC','host':urlparse(page.url).hostname,'page_is_closed':page.is_closed()},ensure_ascii=False),flush=True)
   raise
  if a.action!='check':page.locator('#cas-login:visible,#cas_login:visible,input[type=password]:visible,a[href*=logout]:visible').first.wait_for(state='visible',timeout=20000)
  if a.action in {'inspect','check'} and a.follow_cas:
   for selector in ['#cas-login:visible','#cas_login:visible']:
    link=page.locator(selector)
    if link.count()==1:link.click();page.wait_for_load_state('domcontentloaded',timeout=30000);break
  if a.action=='inspect':
   print(json.dumps({'status':'EPHEMERAL_PUBLIC_PAGE_INSPECTED','credential_session_reused':False,'authentication_verified':False,'host':urlparse(page.url).hostname,'inputs':page.locator('input').evaluate_all('(xs)=>xs.map(x=>({id:x.id,name:x.name,type:x.type,visible:!!(x.offsetWidth||x.offsetHeight||x.getClientRects().length)}))'),'login_controls':page.locator('[id],button,a,input[type=submit]').evaluate_all('(xs)=>xs.filter(x=>x.textContent.trim()==="登录"||(/login/i.test(x.id)&&x.tagName!=="INPUT")).map(x=>({tag:x.tagName,id:x.id,cls:x.className,text:x.textContent.trim().slice(0,40)})).slice(0,15)')},ensure_ascii=False));context.close();browser.close();return
  if a.action=='check':
   page.locator('body').wait_for(timeout=20000);page.wait_for_timeout(4000)
   body=page.locator('body').inner_text()
   import re
   logout=page.locator('a[href*=logout]:visible,a[href*=signout]:visible').count()>0 or any(x.is_visible() for x in page.get_by_text(re.compile(r'^(退出登录|退出|注销)$')).all())
   fields=page.locator('input[type=password]:visible').count()>0
   result={'status':'LOCAL_SESSION_CHECK','host':urlparse(page.url).hostname,'logout_control':logout,'password_field':fields,'captcha_or_mfa':bool(re.search(r'验证码|二次认证|双重认证|动态口令',body)),'credential_error':bool(re.search(r'密码错误|用户名或密码|认证失败|登录失败|账号.*锁定',body)),'cas_entry':page.locator('#cas-login:visible,#cas_login:visible').count()>0,'authentication_verified':safe_domain(page.url) and logout and not fields,'fulltext_obtained':False}
   del body
   report(result);context.close();return
  if a.action=='login':
   if not safe_domain(page.url):raise RuntimeError('UNTRUSTED_AUTH_DOMAIN')
   if page.locator('#user_name:visible,input[name=password]:visible').count()==0 and page.locator('a[href*=logout]:visible,a[href*=signout]:visible').count()>0:
    save_session(context,True);report({'status':'INSTITUTION_SESSION_VERIFIED','authentication_verified':True,'existing_session_reused':True,'host':urlparse(page.url).hostname,'fulltext_obtained':False});context.close();return
   passwords=page.locator('input[type=password]:visible')
   if passwords.count()==0:
    STAGE='CAS_NAVIGATION'
    for selector in ['#cas-login:visible','#cas_login:visible']:
     link=page.locator(selector)
     if link.count()==1:link.click();page.wait_for_load_state('domcontentloaded',timeout=30000);break
   if not safe_domain(page.url):raise RuntimeError('UNTRUSTED_AUTH_DOMAIN')
   import re
   if re.search(r'验证码|二次认证|双重认证|动态口令|captcha',page.locator('body').inner_text(),re.I):
    report({'status':'MANUAL_VERIFICATION_REQUIRED','authentication_verified':False});context.close();return
   passwords=page.locator('input[name=password]:visible,input#password:visible');user=page.locator('input[name=username]:visible,input#username:visible,#user_name:visible')
   if passwords.count()!=1 or user.count()!=1:
    report({'status':'MANUAL_LOGIN_REQUIRED','reason':'FIELDS_NOT_UNIQUE','authentication_verified':False});page.wait_for_timeout(120000);context.close();return
   STAGE='LOCAL_CREDENTIAL_FILL'
   username,password=load_credentials();user.fill(username);passwords.fill(password);del username,password
   # Only a unique displayed login button is eligible, preserving MFA/captcha.
   button=page.get_by_role('button',name='登录',exact=True)
   STAGE='LOGIN_SUBMIT'
   if button.count()==1:button.click(no_wait_after=True)
   report({'status':'CREDENTIALS_FILLED_LOCALLY','authentication_verified':False,'next':'Complete MFA/captcha if shown; session remains in local Edge profile.'})
   STAGE='AUTHENTICATION_CHECK'
   import time
   until=time.monotonic()+120
   while time.monotonic()<until:
    page.wait_for_timeout(2000)
    portal=urlparse(page.url).hostname=='webvpn.fudan.edu.cn' and urlparse(page.url).path not in ['/login','/login/'] and page.locator('input[type=password]:visible,#cas-login:visible,#cas_login:visible').count()==0
    if portal or (safe_domain(page.url) and page.locator('#user_name:visible,input[name=password]:visible').count()==0 and page.locator('a[href*=logout]:visible,a[href*=signout]:visible').count()>0):
     save_session(context,True);report({'status':'INSTITUTION_SESSION_VERIFIED','authentication_verified':True,'host':urlparse(page.url).hostname,'verified_at_utc':datetime.now(timezone.utc).isoformat(),'fulltext_obtained':False});context.close();return
   body=page.locator('body').inner_text();import re
   flags={'captcha_or_mfa':bool(re.search(r'验证码|二次认证|双重认证|动态口令',body)),'credential_error':bool(re.search(r'密码错误|用户名或密码|认证失败|登录失败|账号.*锁定',body)),'host':urlparse(page.url).hostname};del body
   save_session(context,False)
   report({'flags':flags,'status':'AUTHENTICATION_NOT_VERIFIED_WITHIN_WINDOW','authentication_verified':False,'fulltext_obtained':False,'next':'Inspect local MFA/captcha or credential error; no automatic retry.'});context.close();return
  if not a.url or not a.out or not a.doi:raise RuntimeError('URL_OUTPUT_DOI_REQUIRED')
  if urlparse(a.url).scheme!='https' or urlparse(a.url).username or urlparse(a.url).password:raise RuntimeError('HTTPS_WITHOUT_EMBEDDED_CREDENTIALS_REQUIRED')
  if any(any(secret in key.lower() for secret in ['token','session','ticket','signature','apikey','authorization','credential']) for key,value in parse_qsl(urlparse(a.url).query)):
   raise RuntimeError('SIGNED_URL_REQUIRES_LOCAL_BROWSER_CAPTURE_NOT_MODEL_ARGUMENTS')
  response=context.request.get(a.url,timeout=45000);b=response.body()
  if response.status!=200 or b[:5]!=b'%PDF-':
   print(json.dumps({'status':'FULLTEXT_NOT_OBTAINED','http_status':response.status,'pdf_signature':False}));context.close();return
  out=Path(a.out);out.mkdir(parents=True,exist_ok=True);name=hashlib.sha256(a.doi.encode()).hexdigest()[:16];pdf=out/(name+'.pdf')
  if pdf.exists():raise RuntimeError('OUTPUT_EXISTS_NO_OVERWRITE')
  pdf.write_bytes(b)
  receipt={'status':'PDF_SIGNATURE_VERIFIED_CONTENT_IDENTITY_PENDING','doi_requested':a.doi,'sha256':hashlib.sha256(b).hexdigest(),'bytes':len(b),'pdf':str(pdf.resolve()),'source_origin':urlparse(a.url).hostname,'source_url_without_query':urlparse(a.url)._replace(query='',fragment='').geturl(),'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'fulltext_read':False}
  (out/(name+'.receipt.json')).write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(receipt,ensure_ascii=False));context.close()
if __name__=='__main__':
 try:main()
 except Exception as e:
  error={'status':'FAILED','stage':STAGE,'error_type':type(e).__name__,'details':'Redacted; inspect local UI or nonsecret configuration.','authentication_verified':False}
  if '--receipt' in sys.argv:
   try:Path(sys.argv[sys.argv.index('--receipt')+1]).write_text(json.dumps(error),encoding='utf-8')
   except Exception:pass
  print(json.dumps(error));sys.exit(1)
