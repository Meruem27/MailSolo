# 在项目目录内创建本地打包环境并生成可双击启动的 MailSolo.exe。
# 所有依赖、缓存与临时文件都落在项目目录内，不引用全局或其他外部路径。
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectRoot

$venvPython = Join-Path $projectRoot '.venv\Scripts\python.exe'

if (-not (Test-Path -LiteralPath $venvPython)) {
    Write-Host '创建项目本地虚拟环境 .venv ...'
    python -m venv (Join-Path $projectRoot '.venv')
}

$env:PIP_CACHE_DIR = Join-Path $projectRoot '.pip-cache'
$env:TEMP = Join-Path $projectRoot '.tmp'
$env:TMP = $env:TEMP
New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null

Write-Host '安装构建依赖到项目本地环境 ...'
# 国内网络直连官方源容易超时，默认走镜像；如企业内网有私有源可修改此处。
$indexUrl = 'https://pypi.tuna.tsinghua.edu.cn/simple'
& $venvPython -m pip install --disable-pip-version-check --timeout 60 -i $indexUrl --upgrade pip
& $venvPython -m pip install --disable-pip-version-check --timeout 60 -i $indexUrl -r (Join-Path $projectRoot 'requirements.txt')
# 依赖已存在时允许离线打包，只要模块可导入即可。
& $venvPython -c "import PyInstaller, PIL"
if ($LASTEXITCODE -ne 0) { throw '构建依赖不可用，请检查 .venv 与 requirements.txt。' }

Write-Host '生成应用图标 logo\MailSolo.ico ...'
& $venvPython (Join-Path $projectRoot 'tools\make_icon.py')
if ($LASTEXITCODE -ne 0) { throw '图标生成失败，请检查 logo\MailSolo.png 是否存在。' }

Write-Host '开始打包 MailSolo.exe ...'
& $venvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --distpath (Join-Path $projectRoot 'dist') `
    --workpath (Join-Path $projectRoot 'build') `
    (Join-Path $projectRoot 'MailSolo.spec')
if ($LASTEXITCODE -ne 0) { throw 'PyInstaller 打包失败。' }

$exePath = Join-Path $projectRoot 'dist\MailSolo.exe'
if (-not (Test-Path -LiteralPath $exePath)) { throw "未找到生成的 EXE：$exePath" }

# 绿色版校验：dist 目录只应包含可执行文件，不得夹带任何预置配置或账号信息。
$extra = Get-ChildItem -LiteralPath (Join-Path $projectRoot 'dist') -File |
    Where-Object { $_.Name -ne 'MailSolo.exe' }
if ($extra) {
    Write-Warning ("dist 目录存在额外文件，可能被误分发：" + (($extra | ForEach-Object { $_.Name }) -join ', '))
}

Write-Host "打包完成：$exePath"
Write-Host '该 EXE 为单文件绿色版，可直接复制到其他电脑双击运行，无需安装 Python 或任何依赖。'
