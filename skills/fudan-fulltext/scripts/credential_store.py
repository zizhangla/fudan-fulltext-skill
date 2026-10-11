"""CurrentUser DPAPI vault. No API/CLI that emits real credentials."""
import argparse,ctypes,json,os,secrets,subprocess,sys
from pathlib import Path
from ctypes import wintypes

BASE=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'CodexResearchCredentials'
FILE=BASE/'fudan.dpapi'
class Blob(ctypes.Structure):
 _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
def transform(data,decrypt=False):
 if os.name!='nt':raise RuntimeError('WINDOWS_REQUIRED')
 buf=ctypes.create_string_buffer(data); src=Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));dst=Blob()
 api=ctypes.WinDLL('crypt32',use_last_error=True);free=ctypes.WinDLL('kernel32',use_last_error=True).LocalFree
 free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
 if decrypt:
  fn=api.CryptUnprotectData;fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
  ok=fn(ctypes.byref(src),None,None,None,None,1,ctypes.byref(dst))
 else:
  fn=api.CryptProtectData;fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
  ok=fn(ctypes.byref(src),'Codex Fudan current-user credentials',None,None,None,1,ctypes.byref(dst))
 if not ok:raise RuntimeError('DPAPI_FAILED')
 try:return ctypes.string_at(dst.data,dst.size)
 finally:free(ctypes.cast(dst.data,ctypes.c_void_p))
def load_credentials():
 data=json.loads(transform(FILE.read_bytes(),True));assert data['school']=='fudan' and data['version']==1
 return data['username'],data['password']
def save_credentials(username,password):
 assert username and password
 BASE.mkdir(parents=True,exist_ok=True)
 sid=subprocess.check_output(['whoami','/user','/fo','csv','/nh'],text=True).strip().split(',')[-1].strip('"')
 # Limit the dedicated directory to this user and SYSTEM; no group-readable secret.
 r=subprocess.run(['icacls',str(BASE),'/inheritance:r','/grant:r',f'*{sid}:(OI)(CI)F','*S-1-5-18:(OI)(CI)F'],capture_output=True)
 if r.returncode:raise RuntimeError('VAULT_ACL_FAILED')
 payload=json.dumps({'version':1,'school':'fudan','username':username,'password':password}).encode()
 temp=BASE/'fudan.dpapi.tmp';temp.write_bytes(transform(payload));temp.replace(FILE)
 assert load_credentials()==(username,password)
def setup():
 import tkinter as tk
 from tkinter import messagebox
 app=tk.Tk();app.title('复旦全文访问：本地加密录入');app.geometry('480x255');app.resizable(False,False)
 tk.Label(app,text='账号密码仅在本机加密保存，不发送到聊天或Git。',wraplength=450).pack(pady=12)
 tk.Label(app,text='复旦统一身份认证账号').pack();u=tk.Entry(app,width=45);u.pack()
 tk.Label(app,text='密码').pack();p=tk.Entry(app,width=45,show='●');p.pack()
 def submit():
  try:
   save_credentials(u.get().strip(),p.get());u.delete(0,'end');p.delete(0,'end');messagebox.showinfo('已保存','账号密码已用Windows当前用户身份加密保存。');app.destroy()
  except Exception as e:messagebox.showerror('保存失败',type(e).__name__+'：请检查录入和本机权限。')
 tk.Button(app,text='加密保存',command=submit).pack(pady=14);u.focus_set();app.mainloop()
def main():
 ap=argparse.ArgumentParser();ap.add_argument('action',choices=['setup','status','self-test','delete']);a=ap.parse_args()
 if a.action=='setup':setup()
 elif a.action=='status':
  if not FILE.exists():print(json.dumps({'credential_ready':False,'reason':'NOT_ENROLLED'}))
  else:
   try:load_credentials();print(json.dumps({'credential_ready':True,'encryption':'DPAPI_CURRENT_USER'}))
   except Exception:print(json.dumps({'credential_ready':False,'reason':'UNREADABLE_FOR_CURRENT_USER'}))
 elif a.action=='self-test':
  raw=secrets.token_bytes(64);encrypted=transform(raw);assert encrypted!=raw and transform(encrypted,True)==raw
  corrupt=bytearray(encrypted);corrupt[len(corrupt)//2]^=1
  try:transform(bytes(corrupt),True)
  except RuntimeError:pass
  else:raise AssertionError('TAMPER_NOT_REJECTED')
  print(json.dumps({'dpapi_roundtrip':'PASS','ciphertext_differs':'PASS','tamper_rejected':'PASS','real_credential_accessed':False}))
 elif a.action=='delete':
  if FILE.exists():FILE.unlink()
  print(json.dumps({'credential_deleted':True}))
if __name__=='__main__':
 try:main()
 except Exception as e:print(json.dumps({'status':'FAILED','error_type':type(e).__name__}));sys.exit(1)
