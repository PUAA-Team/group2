param([Parameter(Mandatory)][string]$Source, [Parameter(Mandatory)][string]$Output)
$ErrorActionPreference = 'Stop'
$taskSource = (Resolve-Path -LiteralPath $Source).Path
$taskOutput = [IO.Path]::GetFullPath($Output)
if (Test-Path -LiteralPath $taskOutput) { throw "输出已存在，请指定新文件：$taskOutput" }
New-Item -ItemType Directory -Path (Split-Path -Parent $taskOutput) -Force | Out-Null
$taskWord = $null
$taskDocument = $null
$taskExistingDocuments = 0
try {
    $taskWord = New-Object -ComObject Word.Application
    $taskExistingDocuments = $taskWord.Documents.Count
    # 仅在新建的隔离实例中关闭提示，不改变已有 Office 会话。
    if ($taskExistingDocuments -eq 0) {
        $taskWord.Visible = $false
        $taskWord.DisplayAlerts = 0
    }
    $taskDocument = $taskWord.Documents.Open($taskSource, $false, $true, $false)
    $taskDocument.ExportAsFixedFormat($taskOutput, 17)
    Write-Output "原报告只读导出：$taskOutput"
} finally {
    if ($null -ne $taskDocument) {
        $taskDocument.Close(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDocument) | Out-Null
    }
    if ($null -ne $taskWord) {
        if ($taskExistingDocuments -eq 0) { $taskWord.Quit() }
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskWord) | Out-Null
    }
}
