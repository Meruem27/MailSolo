# MailSolo

MailSolo 是一个基于 Python 标准库的 Windows 桌面邮件发送程序。它会把收件人列表中的地址逐个处理：**每封邮件都新建一封消息，且 `To` 中仅出现当前这一个收件人**，不会使用群发、抄送或密送。

> 仅向已明确同意接收邮件、或与您存在正当业务/个人联系的收件人发送。请遵守适用的反垃圾邮件、隐私和退订规则，以及邮箱服务商条款。

## 免安装使用

`dist\MailSolo.exe` 是**单文件绿色版**：直接双击即可运行，无需安装 Python、无需安装任何运行库，也无需管理员权限。把 EXE 单独发给别人（微信、邮件、U 盘）对方也能直接打开。

- 程序启动后所有输入框均为空，不预置任何邮箱、密码、SMTP 地址或收件人，全部由使用者自行填写。
- 程序目录没有写入权限时（例如放在只读目录），发送日志会自动改存到 `%LOCALAPPDATA%\MailSolo\logs`。
- 首次运行 Windows 可能弹出 SmartScreen 提示，这是因为 EXE 未做代码签名，选择“更多信息 → 仍要运行”即可。

## 已实现功能

- 发件人邮箱、密码/授权码、SMTP 主机、端口、SSL/STARTTLS 配置，全部由用户自行填写，不预置任何默认值。
- 点击“按常见邮箱自动填写”后，可按 QQ、Gmail、Outlook/Hotmail/Live、163、126 等域名补齐 SMTP 参数；其他企业邮箱手动填写。
- 邮件标题、纯文本正文，以及多个本地附件（可一键清空）。
- 每行粘贴一个收件人；自动忽略空行，跳过格式错误邮箱，按大小写去重，并实时显示有效地址数量。
- 后台逐封发送；每封均使用独立 `EmailMessage`，收件人之间不可见。
- 可设置每两封邮件的间隔（默认 3 秒），并可暂停、继续或停止。暂停/停止会在当前 SMTP 网络操作结束后、下一封发送前生效。
- 表格日志记录“发送中 / 成功 / 失败”和错误详情，按状态着色；任务结束时自动保存 CSV 到 `logs` 文件夹，也可手动导出。
- 密码或授权码只放在程序运行时内存中：不会写入 CSV、配置文件或代码。
- 窗口与任务栏图标使用 `logo\MailSolo.png`，并适配 Windows 高分屏缩放。

## 目录结构

```text
mailsolo/
├─ main.py                # 启动入口
├─ app.py                 # Tkinter 图形界面
├─ mailer.py              # SMTP、逐封发送和校验逻辑
├─ test_mailer.py         # 单元测试
├─ MailSolo.spec          # PyInstaller 打包配置（图标、资源、本地运行时目录）
├─ version_info.txt       # EXE 版本与产品信息
├─ build_exe.ps1          # 一键打包脚本
├─ requirements.txt       # 仅构建期依赖（PyInstaller、Pillow）
├─ logo/
│  └─ MailSolo.png        # 应用图标源文件（打包时生成 MailSolo.ico）
└─ tools/
   └─ make_icon.py        # PNG → 多尺寸 ICO 转换
```

构建产物位于 `dist\MailSolo.exe`；`.venv`、`.pip-cache`、`.tmp`、`build` 均为项目本地目录，可随时删除后重新生成。

## 运行环境

- Windows 10/11（也可在安装了 Tk 的 macOS/Linux Python 环境使用）
- Python 3.10 或更高版本；本项目已在 Python 3.12 验证
- 网络可访问所使用邮箱的 SMTP 服务

程序本身不依赖第三方 Python 包；PyInstaller 与 Pillow 仅在打包时使用，且安装到项目本地的 `.venv` 中。

## 部署与启动

### 1. 安装 Python

从 Python 官网安装 Python 3.10+。安装界面请勾选 **Add Python to PATH**。安装后，在 PowerShell 运行：

```powershell
python --version
```

### 2. 进入项目目录

```powershell
cd D:\project\mailsolo
```

### 3. 可选：执行测试

```powershell
python -m unittest -v
```

预期会看到 3 个测试全部通过。测试不会连接真实邮箱，也不会发送邮件。

### 4. 启动程序

```powershell
python main.py
```

首次发送前，请先使用一个自己可收信的测试邮箱验证配置与附件。

## 使用步骤

1. 输入发件人完整邮箱地址。
2. 输入 **SMTP 授权码或应用专用密码**；除服务商明确允许外，不要输入网页登录主密码。
3. 点击“按常见邮箱自动填写”；若不能识别域名，请根据服务商官方帮助页填入 SMTP 主机、端口和加密方式。
4. 填写标题、正文；需要时点击“添加附件”。附件在发送期间请保持原位置不变。
5. 在“收件人列表”中一行粘贴一个地址。
6. 设定间隔（建议先保留默认 3 秒），点击“开始发送”。
7. 在下方检查逐条发送日志。完成、停止后，日志会自动写入 `logs\send_log_时间.csv`。其中“成功”表示 SMTP 服务器已接受提交，不等同于收件方最终送达；后续退信或被判为垃圾邮件仍可能发生。

## 常用 SMTP 参数

这些只是程序的自动预填值；企业邮箱和服务商策略可能不同，请以对应服务商当前官方文档为准。

| 邮箱域名 | SMTP 主机 | 端口 | 加密方式 |
| --- | --- | ---: | --- |
| `qq.com` | `smtp.qq.com` | 465 | SSL |
| `gmail.com` | `smtp.gmail.com` | 465 | SSL |
| `outlook.com` / `hotmail.com` / `live.com` | `smtp.office365.com` | 587 | STARTTLS |
| `163.com` | `smtp.163.com` | 465 | SSL |
| `126.com` | `smtp.126.com` | 465 | SSL |

## 打包为独立 EXE

在项目目录执行：

```powershell
powershell -ExecutionPolicy Bypass -File .\build_exe.ps1
```

脚本会完成以下步骤，全部使用项目本地路径：

1. 若不存在则创建本地虚拟环境 `.venv`；
2. 将 `requirements.txt` 中的依赖安装到 `.venv`，pip 缓存写入 `.pip-cache`、临时文件写入 `.tmp`；
3. 用 `tools\make_icon.py` 从 `logo\MailSolo.png` 生成多尺寸 `logo\MailSolo.ico`；
4. 按 `MailSolo.spec` 打包，图标、版本信息与 logo 资源一并写入；
5. 输出 `dist\MailSolo.exe`（单文件，dist 目录不夹带任何配置文件）。

打包参数说明：

- `--onefile`：单文件 EXE；
- `--windowed`：不弹出控制台窗口；
- 图标：`logo\MailSolo.ico`（由 `logo\MailSolo.png` 转换而来）；
- 运行时解压目录：使用系统临时目录，随用随清，不依赖项目路径，因此 EXE 可以复制到任意电脑运行。

建议在干净的测试环境中，用测试邮箱验证打包版本；部分安全软件会对新生成的网络发送类 EXE 提示风险，这是常见的信誉检查场景，应从可信来源获取代码并自行打包。

## 授权码、身份验证与限制提醒

### Gmail / Google Workspace

- 对使用 SMTP 的本工具，通常需先为 Google 账号启用两步验证，再创建“应用专用密码”（App Password），将该专用密码填入程序；Google 明确说明该密码是给不支持“使用 Google 登录”的应用/设备使用的 16 位密码。
- 个人 Gmail 的公开帮助页提示：单日发送超过 500 封或合计收件人超过 500 个可能触发限制，恢复可能需要 1–24 小时。Google Workspace 的额度会随版本和组织策略而不同。
- 向 Gmail 地址每天发送 5,000 封及以上的发件域名，需要满足更严格的发件人要求，如邮件认证、避免未经请求邮件、可见且易用的退订方式；不合规邮件可能被临时或永久拒收。

### Outlook.com / Microsoft 365 / Exchange Online

- Microsoft 365 租户的 SMTP AUTH 可能被组织安全默认设置、全局策略或单个邮箱设置禁用；需由管理员仅为需要的邮箱启用，且有些组织可能要求 OAuth，而不是本程序使用的用户名/密码方式。
- Microsoft 当前文档列出的 Exchange Online SMTP AUTH 限制包括：每分钟 30 封、每 24 小时 10,000 个收件人；组织还可能设置更低的外部收件人限额。达到限制会被节流或拒绝。
- Microsoft 建议需要合法大批量商业邮件时使用专门的第三方批量邮件服务，而不是普通客户端 SMTP。

### QQ、163、126 与其他国内邮箱

- 先在网页版邮箱的“设置 / 账户 / POP3/IMAP/SMTP 或客户端服务”中开启 SMTP，并按页面提示生成“授权码 / 客户端授权密码”。不要把网页版登录密码直接交给本程序，除非服务商明确允许。
- 国内邮箱的每日额度、附件大小、异地登录验证和异常发送风控可能因账号等级、实名认证、历史信誉、内容和收件人质量而动态变化。应从小批量、较长间隔的测试开始；若出现验证码、登录保护或频控，停止重试并按服务商提示处理。

### 所有服务商的共通风险

- 逐封发送不是规避限制的方式；频繁、重复、无同意基础、退信率高或内容可疑的邮件仍可能触发反滥用机制，导致拒信、限流、账号验证甚至停用。
- 请先清理无效地址并使用真实、相关的标题与正文。营销或订阅类邮件应保留同意记录、提供清晰退订路径，并正确配置自己的域名认证（SPF、DKIM、DMARC）。
- 附件总大小、单封大小和可执行文件类型受服务商限制；发送失败时查看日志中的 SMTP 错误，并优先查服务商的错误码文档。
- 程序为保护隐私不保存密码；关闭程序后必须重新输入授权码。

## 常见问题

### `Username and Password not accepted` / 登录失败

优先确认：邮箱地址完整无误、SMTP 功能已开启、填写的是授权码/应用密码而非网页登录密码、端口和加密方式相匹配。Gmail 还需检查两步验证及应用专用密码是否仍有效。

### `SMTP AUTH` 被禁用（常见于 Microsoft 365）

联系 Microsoft 365 管理员，检查该邮箱及组织是否允许 Authenticated SMTP；如果组织要求 OAuth，本示例的账号密码登录模式不适用，需要改造成 OAuth 2.0 客户端。

### 发送过程中点击暂停或停止，为什么当前封仍完成了？

SMTP 连接、上传附件或提交邮件本身是正在进行的网络操作。程序会保证在该操作返回后不再开始下一位收件人，不能安全地中断已经被服务器接收的当前邮件。

### 打包时提示找不到图标？

确认 `logo\MailSolo.png` 存在；`build_exe.ps1` 会自动调用 `tools\make_icon.py` 生成 `logo\MailSolo.ico`。若手动执行 PyInstaller，请先运行一次该脚本。

## 参考的官方服务商说明

- Google：应用专用密码、Gmail 发信上限、Gmail 发件人要求。
- Microsoft Learn：Exchange Online SMTP AUTH 开关及其发信/节流上限。

这些服务政策会更新；在正式或高频使用前，请再次查看您所用邮箱服务商的最新官方文档。
