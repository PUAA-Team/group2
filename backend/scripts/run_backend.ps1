param(
    [ValidateSet('serve', 'migrate', 'test')]
    [string]$BackendAction = 'serve',
    [string]$RuntimeDir = 'D:\model-training-demo\backend-runtime',
    [int]$Port = 8000,
    [switch]$EnableBrowserSetup,
    [switch]$EnableLocalWorker
)
$ErrorActionPreference = 'Stop'
$backendRoot = Split-Path $PSScriptRoot -Parent
$pythonPath = Join-Path $RuntimeDir '.venv/Scripts/python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw "隔离 Python 不存在：$pythonPath" }
if (-not [System.IO.Path]::IsPathRooted($RuntimeDir)) { throw '运行目录必须为绝对路径' }
$saved = @{}
$values = @{
    MT_RUNTIME_DIR = $RuntimeDir
    MT_ALLOW_BROWSER_SETUP = $(if ($EnableBrowserSetup) { '1' } else { '0' })
    MT_ENABLE_LOCAL_WORKER = $(if ($EnableLocalWorker) { '1' } else { '0' })
    MT_LOCAL_CONTROLLER_URL = "http://127.0.0.1:$Port"
    PYTHONPATH = (Join-Path $backendRoot 'src')
    PYTHONDONTWRITEBYTECODE = '1'
    PYTHONIOENCODING = 'utf-8'
    TEMP = (Join-Path $RuntimeDir 'temp')
    TMP = (Join-Path $RuntimeDir 'temp')
}
try {
    foreach ($key in $values.Keys) {
        $saved[$key] = [Environment]::GetEnvironmentVariable($key, 'Process')
        [Environment]::SetEnvironmentVariable($key, $values[$key], 'Process')
    }
    New-Item -ItemType Directory -Path $values.TEMP -Force | Out-Null
    switch ($BackendAction) {
        'serve' { & $pythonPath -B -m uvicorn model_platform.main:create_app --factory --host 127.0.0.1 --port $Port --no-access-log }
        'migrate' { & $pythonPath -B -m model_platform.cli migrate }
        'test' {
            $testDir = Join-Path $RuntimeDir ('test-' + [guid]::NewGuid().ToString('N'))
            Write-Output "测试证据目录：$testDir"
            & $pythonPath -B -m pytest (Join-Path $backendRoot 'tests') -q -x `
                -o ("cache_dir=" + (Join-Path $RuntimeDir 'pytest-cache')) --basetemp $testDir `
                --junitxml (Join-Path $testDir 'report.xml')
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "后端命令失败，退出码：$LASTEXITCODE" }
}
finally {
    foreach ($key in $saved.Keys) { [Environment]::SetEnvironmentVariable($key, $saved[$key], 'Process') }
}
