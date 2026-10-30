param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$OutputPdf,
    [string]$OutputDocx,
    [switch]$UpdateContents,
    [switch]$UpdateContentsPageNumbers
)
$ErrorActionPreference = 'Stop'
$taskSource = (Resolve-Path -LiteralPath $Source).Path
$taskPdf = [IO.Path]::GetFullPath($OutputPdf)
if (Test-Path -LiteralPath $taskPdf) { throw "输出已存在：$taskPdf" }
if ($OutputDocx) {
    $taskDocx = [IO.Path]::GetFullPath($OutputDocx)
    if (Test-Path -LiteralPath $taskDocx) { throw "输出已存在：$taskDocx" }
}
$taskApp = $null
$taskDocument = $null
$taskExisting = -1
try {
    Write-Output 'WORD_COM_START'
    $taskApp = New-Object -ComObject Word.Application
    $taskExisting = $taskApp.Documents.Count
    if ($taskExisting -eq 0) {
        $taskApp.Visible = $false
        $taskApp.DisplayAlerts = 0
    }
    $taskMissing = [Type]::Missing
    # 隐藏、只读打开，禁用自动修复，不改已有用户文稿。
    $taskDocument = $taskApp.Documents.Open($taskSource, $false, $true, $false,
        $taskMissing, $taskMissing, $false, $taskMissing, $taskMissing,
        $taskMissing, $taskMissing, $false, $false)
    Write-Output 'WORD_OPENED'
    if ($UpdateContents) {
        foreach ($taskContents in $taskDocument.TablesOfContents) { $taskContents.Update() }
        $taskDocument.Fields.Update() | Out-Null
        $taskDocument.Repaginate()
        foreach ($taskContents in $taskDocument.TablesOfContents) { $taskContents.UpdatePageNumbers() }
    } elseif ($UpdateContentsPageNumbers) {
        # 仅调整分页时保留用户已有目录条目，不重新生成细分层级。
        $taskDocument.Repaginate()
        foreach ($taskContents in $taskDocument.TablesOfContents) { $taskContents.UpdatePageNumbers() }
    }
    if ($OutputDocx) {
        $taskDocument.SaveAs2($taskDocx, 16)
        Write-Output 'WORD_SAVED_NEW_COPY'
    }
    $taskDocument.ExportAsFixedFormat($taskPdf, 17)
    [pscustomobject]@{
        Source = $taskSource; Pdf = $taskPdf; Docx = $OutputDocx
        Pages = $taskDocument.ComputeStatistics(2); Tables = $taskDocument.Tables.Count
        OfficeVersion = $taskApp.Version; ExistingDocuments = $taskExisting
    } | ConvertTo-Json
} finally {
    if ($null -ne $taskDocument) {
        $taskDocument.Close(0)
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDocument) | Out-Null
    }
    if ($null -ne $taskApp) {
        if ($taskExisting -eq 0 -and $taskApp.Documents.Count -eq 0) { $taskApp.Quit() }
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskApp) | Out-Null
    }
}
