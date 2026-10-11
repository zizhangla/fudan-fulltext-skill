---
name: fudan-fulltext
description: 科研查新遇到非开放获取论文、Methods或补充材料缺口时，优先经出版社机构登录／CARSI获取复旦授权全文，WebVPN作为后备。Windows账号凭据和会话使用本机DPAPI加密。
---

# 复旦论文全文访问

## 第一优选：出版社机构登录／CARSI

先核对目标论文题名、DOI和版本。非OA文献首先从目标论文页面点击 Access through your institution / Institutional access，在机构搜索框输入 Fudan，选择 Fudan University，点击机构访问按钮后进入复旦统一身份认证。已有有效出版社机构会话或学校单点登录会话时直接复用，不重复提交密码。

只向经核验的HTTPS复旦域名 `id.fudan.edu.cn`、`uis.fudan.edu.cn`、`idpfudan.fudan.edu.cn` 提交校园凭据。学校认证后回到论文页面，检查订阅预览是否消失以及是否出现全文和真实Download PDF链接；在同一会话内下载，避免关闭浏览器丢失会话Cookie。验证码/MFA由用户实际完成，不绕过、不重复尝试失败密码。

优先使用当前可操作浏览器的实际界面与下载工具。`scripts/institution_browser.py --url <论文URL> --doi <DOI> --out <输出目录> --login` 是Windows本地辅助程序，已适配Springer Nature机构搜索；其他出版社字段不唯一或未适配时停止自动选择，交由用户或浏览器工具完成。`--manual`允许用户在本地浏览器完成机构选择、认证或验证码；不把认证信息传回模型。

## 后备路径

机构登录／CARSI不可用或订阅不覆盖时，再尝试WebVPN门户提供的实际资源链接或网址访问入口，随后考虑官方图书馆代理或文献传递。仅登录WebVPN后打开出版社原始网址，不自动获得机构权限。不要猜造WebVPN加密地址。

官方入口：https://webvpn.fudan.edu.cn/；数据库导航：https://libdbnav.fudan.edu.cn/。
首次使用或页面结构变化时复核[复旦校外访问指南](https://library.fudan.edu.cn/118/list.htm)及[CARSI数据库列表](https://library.fudan.edu.cn/_s928/e8/b6/c42806a518326/page.psp)。

`scripts/fulltext_browser.py inspect --follow-cas`检查WebVPN匿名界面，`login`为WebVPN后备认证；`download --url <实际观察到的PDF链接> --out <目录> --doi <DOI>`使用其本地会话。不要把WebVPN登录成功当成出版社订阅授权。

## 安装依赖与凭据

技能路径为安装后的技能目录，不能硬编码维护者个人路径。使用Python 3.10+，先执行 `python -m pip install -r <技能目录>/requirements.txt`。机构浏览器辅助程序默认Edge，`--channel chrome`可切换Chrome；两者都没有时执行 `python -m playwright install chromium`并指定`--channel chromium`。WebVPN旧版辅助程序使用Edge。

Windows首次运行 `python <技能目录>/scripts/credential_store.py setup`，由用户在本地表单录入自己的复旦账号密码。不得要求用户把密码发到聊天。凭据使用Windows DPAPI CurrentUser加密至本用户LOCALAPPDATA下的CodexResearchCredentials；`status`只返回是否可用，`self-test`只使用随机数据。非Windows用户使用浏览器内手动认证，不运行DPAPI凭据辅助程序。

凭据、Cookie、学校与出版社会话、浏览器资料目录、认证截图、HAR、trace均不得进入Git或公开包。没有打印或导出真实凭据的命令。不要把含token/session/ticket/signature的签名URL传给模型可见参数，改用本地浏览器保存。DPAPI绑定本机Windows用户，不代表能抵抗该用户会话被攻破。

## 下载与读取核验

`scripts/fulltext_fetch.py --url <实际观察到的PDF链接> --doi <DOI> --out <目录> --session carsi`优先复用CARSI加密缓存；`--session webvpn`使用WebVPN缓存，`--session legacy`用于旧版本缓存。缓存存在或此前验证过不等于当前授权有效。首次认证、缓存过期或MFA时回到相应浏览器认证入口。

核验HTTP 200、PDF签名、可解析页数、题名、DOI和正文／补充材料身份，记录来源、时间与SHA256。全文提取不等于阅读全文；只有实际读过正文、Methods和所需SI后才能作科学判断。挑战页、登录HTML或付费页标记未取得全文，订阅缺口标记ENTITLEMENT_NOT_AVAILABLE。合法作者版本可用于阅读，但不算机构非OA下载成功。

2026-10-11实测：Nature Nanotechnology订阅论文DOI `10.1038/nnano.2015.2`及`10.1038/s41565-017-0034-6`经机构搜索Fudan／CARSI取得PDF并核验身份；这不保证所有出版社、账号或订阅都可用。公开包不包含这些论文。
