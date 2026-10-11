# Fudan Fulltext — 复旦全文下载 Codex Skill

优先通过**出版社机构登录 → 搜索 Fudan → Fudan University → CARSI**获取合法订阅全文，WebVPN作为后备。适合复旦师生在Codex中查找论文正文、Methods与补充材料。

## 在 Codex 中安装

把下面这句话复制到Codex：

```text
使用 $skill-installer 从 https://github.com/zizhangla/fudan-fulltext-skill 安装 skills/fudan-fulltext。安装后根据技能目录中的 requirements.txt 配置 Python 依赖，核验凭据模块 self-test，不读取或上传我的账号密码。我的复旦账号由我在本地 setup 表单录入。
```

技能在安装后的下一轮对话可用。然后发送：

```text
使用 $fudan-fulltext 下载这篇论文的合法全文：<论文网址或 DOI>。优先使用机构登录，搜索 Fudan；成功后核验 PDF 的题名、DOI 和页数。
```

## Windows 手动安装

需要Python 3.10+及Codex。在PowerShell执行：

```powershell
git clone https://github.com/zizhangla/fudan-fulltext-skill.git
$skillRoot = Join-Path $env:USERPROFILE '.codex\skills\fudan-fulltext'
if (Test-Path -LiteralPath $skillRoot) { throw '技能目录已存在，请先核对，避免覆盖' }
New-Item -ItemType Directory -Path (Split-Path $skillRoot) -Force | Out-Null
Copy-Item -LiteralPath '.\fudan-fulltext-skill\skills\fudan-fulltext' -Destination $skillRoot -Recurse
python -m pip install -r "$skillRoot\requirements.txt"
python "$skillRoot\scripts\credential_store.py" self-test
python "$skillRoot\scripts\credential_store.py" setup
```

若配置了自定义CODEX_HOME，将技能放到该目录的skills子目录。机构浏览器辅助程序默认Edge，可加 `--channel chrome` 切换Chrome；两者都未安装时执行 `python -m playwright install chromium`，再加 `--channel chromium`。WebVPN旧版辅助程序使用Edge。非Windows用户可以安装技能指引并使用浏览器手动认证；DPAPI辅助脚本仅支持Windows。

## 本地脚本示例

安装依赖、录入自己的凭据后，在技能目录中执行：

```powershell
python scripts/institution_browser.py --url 'https://www.nature.com/articles/s41565-017-0034-6' --doi '10.1038/s41565-017-0034-6' --out './downloads' --login
```

自动机构搜索适配Springer Nature；其他出版社需实际检查机构入口。验证码、MFA、未显示密码表单或未适配页面使用 `--manual` 在本地浏览器完成。脚本返回 `FULLTEXT_PENDING_INSTITUTION_ACCESS` 表示没有取得全文，需要继续正规认证，不会自动重复提交密码。一次仅获取所需单篇文献，不批量抓取。

## 隐私与访问范围

- 每位使用者录入自己的复旦账号；本仓库不提供账号或订阅权限。
- 凭据和浏览器会话只在本机Windows用户下DPAPI加密保存，不进入聊天、日志或Git。
- 登录成功、PDF下载成功、阅读全文是分别核验的三个状态。
- 订阅范围取决于学校与出版社；不绕过验证码或付费限制。
- 公开仓库不包含论文PDF、浏览器资料、下载测试原始记录或维护者个人路径。

2026-10-11：机构搜索Fudan／CARSI工作流已在两篇Nature Nanotechnology订阅论文上实测成功。公开版通过技能格式、脚本语法与DPAPI随机数据自检；自动辅助程序复测能进入学校认证入口，但遇到未显示密码表单的状态时返回未取得全文，需要手动认证。这是特定目标的工作流验证，不是所有数据库或自动辅助程序每次都成功的保证。

[复旦官方CARSI说明](https://library.fudan.edu.cn/_s928/e8/b6/c42806a518326/page.psp) · [Codex技能入口](skills/fudan-fulltext/SKILL.md)
