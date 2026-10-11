"""CARSI-first single-paper helper. Credentials and session data stay local."""
import argparse
import hashlib
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin, urlparse, parse_qsl
from credential_store import BASE, load_credentials, transform

SCHOOL = {'id.fudan.edu.cn', 'uis.fudan.edu.cn', 'idpfudan.fudan.edu.cn'}

def validate_url(value):
    u = urlparse(value)
    if u.scheme != 'https' or not u.hostname or u.username or u.password:
        raise ValueError('HTTPS_WITHOUT_CREDENTIALS_REQUIRED')
    if any(re.search(r'token|session|ticket|signature|authorization|credential|apikey', k, re.I)
           for k, _ in parse_qsl(u.query)):
        raise ValueError('SIGNED_URL_REQUIRES_LOCAL_BROWSER_DOWNLOAD')
    return u

def report(data):
    print(json.dumps(data, ensure_ascii=False), flush=True)

def optional_cookies(page):
    reject = page.get_by_role('button', name='Reject optional cookies', exact=True)
    if reject.count() == 1 and reject.is_visible():
        reject.click()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--url', required=True)
    ap.add_argument('--doi', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--title')
    ap.add_argument('--login', action='store_true', help='Fill the verified Fudan login from local DPAPI')
    ap.add_argument('--manual', action='store_true', help='Allow local user institution selection/MFA')
    ap.add_argument('--channel', choices=['msedge','chrome','chromium'], default='msedge')
    ap.add_argument('--headless', action='store_true', help='For unattended verification without MFA')
    a = ap.parse_args()
    validate_url(a.url)
    if os.name != 'nt':
        raise RuntimeError('WINDOWS_REQUIRED_USE_BROWSER_MANUAL_LOGIN')
    from playwright.sync_api import sync_playwright
    BASE.mkdir(parents=True, exist_ok=True)
    session_file = BASE/'fudan-carsi-session.dpapi'
    with sync_playwright() as pw:
        if a.manual and a.headless:
            raise ValueError('MANUAL_REQUIRES_VISIBLE_BROWSER')
        options = {'headless':a.headless, 'accept_downloads':True, 'timeout':20000}
        if a.channel != 'chromium':
            options['channel'] = a.channel
        proxy = urlparse(os.environ.get('HTTPS_PROXY',''))
        if proxy.scheme == 'http' and proxy.hostname in {'localhost','127.0.0.1'} and proxy.port and not proxy.username:
            options['proxy'] = {'server':f'http://{proxy.hostname}:{proxy.port}'}
        context = pw.chromium.launch_persistent_context(str(BASE/'carsi-profile'), **options)
        try:
            if session_file.exists():
                state = json.loads(transform(session_file.read_bytes(), True))
                context.add_cookies(state['storage_state'].get('cookies', []))
                del state
            page = context.new_page()
            for previous in context.pages:
                if previous != page:
                    previous.close()
            page.set_default_timeout(10000)
            page.goto(a.url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(2000)
            optional_cookies(page)
            pdf = page.get_by_role('link', name='Download PDF', exact=True)
            if pdf.count() != 1 and not a.manual:
                institution = page.get_by_role('link', name='Access through your institution', exact=True)
                if institution.count():
                    institution.first.click()
                    page.wait_for_timeout(2000)
                    optional_cookies(page)
                    search = page.locator('#autocomplete-input:visible')
                    if search.count() == 1:
                        search.fill('fudan')
                        choice = page.get_by_text('Fudan University', exact=True)
                        choice.wait_for(state='visible', timeout=15000)
                        if choice.count() != 1:
                            raise RuntimeError('INSTITUTION_RESULT_NOT_UNIQUE')
                        choice.click()
                        page.wait_for_timeout(2500)
                        optional_cookies(page)
                        access = page.get_by_role('button', name='Access through your institution', exact=True)
                        if access.count() != 1:
                            raise RuntimeError('INSTITUTION_BUTTON_NOT_UNIQUE')
                        # School redirects may leave a slow navigation pending even
                        # when the login form is already usable. Wait for the form.
                        access.click(no_wait_after=True, timeout=15000)
                        deadline = time.monotonic()+45
                        while time.monotonic() < deadline:
                            if len(context.pages)>1:
                                page = context.pages[-1]
                            page.wait_for_timeout(500)
                            if (urlparse(page.url).hostname in SCHOOL and page.locator('input[type=password]:visible').count()) or page.get_by_role('link',name='Download PDF',exact=True).count() == 1:
                                break
            u = urlparse(page.url)
            if page.locator('input[type=password]:visible').count() and a.login:
                if u.scheme != 'https' or u.hostname not in SCHOOL:
                    raise RuntimeError('UNVERIFIED_SCHOOL_HOST_NO_CREDENTIAL_FILL')
                body = page.locator('body').inner_text()
                if not re.search(r'验证码|动态口令|二次认证|captcha|multi.factor', body, re.I):
                    username = page.locator('#login-username:visible,input[name=username]:visible,input[name=j_username]:visible')
                    password = page.locator('input[type=password]:visible')
                    submit = page.get_by_role('button', name='登录', exact=True)
                    if username.count() == password.count() == submit.count() == 1:
                        name, secret = load_credentials()
                        username.fill(name); password.fill(secret)
                        del name, secret
                        submit.click(no_wait_after=True, timeout=15000)
                        page.wait_for_timeout(5000)
                    elif not a.manual:
                        raise RuntimeError('LOGIN_FIELDS_NOT_UNIQUE')
                elif not a.manual:
                    raise RuntimeError('USER_VERIFICATION_REQUIRED')
            pdf = page.get_by_role('link', name='Download PDF', exact=True)
            if pdf.count() != 1 and a.manual:
                report({'status':'COMPLETE_INSTITUTION_LOGIN_IN_LOCAL_BROWSER','credential_values_exposed':False})
                deadline = time.monotonic()+180
                while time.monotonic() < deadline:
                    if len(context.pages)>1:
                        page=context.pages[-1]
                        pdf=page.get_by_role('link',name='Download PDF',exact=True)
                    page.wait_for_timeout(1000)
                    if pdf.count() == 1:
                        break
            if pdf.count() != 1:
                report({'status':'FULLTEXT_PENDING_INSTITUTION_ACCESS','pdf_obtained':False,'current_host':urlparse(page.url).hostname,'password_field_visible':page.locator('input[type=password]:visible').count()>0,'next':'Use --manual to complete local institution login/verification; no password retry.'})
                return
            href = urljoin(page.url, pdf.get_attribute('href'))
            validate_url(href)
            response = context.request.get(href, timeout=45000)
            blob = response.body()
            result = {'doi_requested':a.doi, 'http_status':response.status,
                      'pdf_obtained':False, 'fulltext_read':False,
                      'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
                      'source_host':urlparse(href).hostname, 'source_path':urlparse(href).path}
            if response.status != 200 or not blob.startswith(b'%PDF-'):
                result['status'] = 'CHALLENGE_OR_NO_PDF'
                report(result)
                return
            import pymupdf
            with pymupdf.open(stream=blob, filetype='pdf') as doc:
                text = '\n'.join(p.get_text() for p in doc)
                result.update(pages=len(doc),doi_text_match=a.doi.lower() in text.lower())
                if a.title:
                    result['title_text_match'] = a.title.lower() in re.sub(r'\s+',' ',text).lower()
            out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
            stem = hashlib.sha256(a.doi.encode()).hexdigest()[:16]
            dest = out/(stem+'.pdf')
            digest = hashlib.sha256(blob).hexdigest()
            if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() != digest:
                raise RuntimeError('DIFFERENT_EXISTING_PDF_NO_OVERWRITE')
            if not dest.exists():
                dest.write_bytes(blob)
            result.update(status='PDF_OBTAINED_CONTENT_REVIEW_PENDING',pdf_obtained=True,
                          pdf=str(dest.resolve()),bytes=len(blob),sha256=digest)
            (out/(stem+'.receipt.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            # A public/OA PDF alone is not evidence of institutional authentication.
            state = {'storage_state':context.storage_state(), 'authentication_verified':False,
                     'route':'carsi','captured_at_utc':datetime.now(timezone.utc).isoformat()}
            session_file.write_bytes(transform(json.dumps(state).encode()))
            report(result)
        except Exception:
            # Only the public institution picker is eligible for a diagnostic image.
            if 'page' in locals() and urlparse(page.url).hostname == 'wayf.springernature.com' and not page.locator('input[type=password]').count():
                diagnostic = Path(a.out); diagnostic.mkdir(parents=True,exist_ok=True)
                page.screenshot(path=str(diagnostic/'institution_picker_failure.png'))
            raise
        finally:
            context.close()

if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        import traceback
        frames = [f.lineno for f in traceback.extract_tb(e.__traceback__) if Path(f.filename).name == 'institution_browser.py']
        report({'status':'FAILED','error_type':type(e).__name__,'script_line':frames[-1] if frames else None,'details':'redacted','pdf_obtained':False})
        sys.exit(1)
