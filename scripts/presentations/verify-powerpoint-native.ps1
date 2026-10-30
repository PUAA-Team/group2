param(
    [Parameter(Mandatory)][string]$Source,
    [Parameter(Mandatory)][string]$OutputDirectory,
    [int]$ExpectedSlides = 40,
    [int[]]$ExportSlides = @(30, 31, 32, 34, 35, 36),
    [switch]$RoundTrip
)
$ErrorActionPreference = 'Stop'
if ($PSVersionTable.PSEdition -ne 'Desktop') { throw '请通过 Windows PowerShell 5.1 运行本脚本。' }
$taskSource = (Resolve-Path -LiteralPath $Source).Path
$taskOutput = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $taskOutput) { throw "验收目录已存在：$taskOutput" }
New-Item -ItemType Directory -Path $taskOutput | Out-Null
$taskApp = $null
$taskDeck = $null
$taskExistingCount = -1
$taskReport = [ordered]@{ source = $taskSource; openAndRepair = $false; expectedSlides = $ExpectedSlides }
try {
    Write-Output 'NATIVE_COM_START'
    $taskApp = New-Object -ComObject PowerPoint.Application
    $taskExistingCount = $taskApp.Presentations.Count
    $taskReport.officeVersion = $taskApp.Version
    $taskReport.existingPresentations = $taskExistingCount
    # 不修改现有 Office 文稿或提示设置，只对本次文件执行只读检查。
    Write-Output 'NATIVE_OPEN_WITHOUT_REPAIR'
    $taskDeck = $taskApp.Presentations.Open2007($taskSource, -1, 0, 0, 0)
    if ($taskDeck.Slides.Count -ne $ExpectedSlides) { throw "页数异常：$($taskDeck.Slides.Count)" }
    $taskReport.slides = $taskDeck.Slides.Count
    $taskPages = @()
    for ($taskPage = 1; $taskPage -le $taskDeck.Slides.Count; $taskPage++) {
        $taskSlide = $taskDeck.Slides.Item($taskPage)
        $taskText = @()
        $taskTables = 0
        $taskCharts = 0
        $taskConnectors = 0
        foreach ($taskShape in $taskSlide.Shapes) {
            if ($taskShape.HasTextFrame -eq -1) { $taskText += $taskShape.TextFrame.TextRange.Text }
            if ($taskShape.HasTable -eq -1) { $taskTables++ }
            if ($taskShape.HasChart -eq -1) { $taskCharts++ }
            if ($taskShape.Connector -eq -1) { $taskConnectors++ }
        }
        $taskPages += [ordered]@{
            page = $taskPage; hidden = ($taskSlide.SlideShowTransition.Hidden -eq -1)
            shapes = $taskSlide.Shapes.Count; tables = $taskTables; charts = $taskCharts
            connectors = $taskConnectors; text = $taskText
        }
        if ($ExportSlides -contains $taskPage) {
            $taskSlide.Export((Join-Path $taskOutput ('{0:D2}.png' -f $taskPage)), 'PNG', 1280, 720)
        }
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskSlide) | Out-Null
    }
    $taskReport.pages = $taskPages
    if ($RoundTrip) {
        $taskCopy = Join-Path $taskOutput 'native-save-copy.pptx'
        $taskDeck.SaveCopyAs($taskCopy, 24)
        $taskDeck.Close()
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDeck) | Out-Null
        $taskDeck = $null
        Write-Output 'NATIVE_REOPEN_SAVED_COPY_WITHOUT_REPAIR'
        $taskDeck = $taskApp.Presentations.Open2007($taskCopy, -1, 0, 0, 0)
        if ($taskDeck.Slides.Count -ne $ExpectedSlides) { throw '原生保存后重新打开页数异常。' }
        $taskReport.roundTrip = [ordered]@{ file = $taskCopy; slides = $taskDeck.Slides.Count; openedWithoutRepair = $true }
    }
    $taskReport.passed = $true
    $taskReport | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $taskOutput 'native-validation.json') -Encoding UTF8
    Write-Output "NATIVE_PASS slides=$($taskReport.slides) version=$($taskReport.officeVersion)"
} finally {
    if ($null -ne $taskDeck) {
        $taskDeck.Close()
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskDeck) | Out-Null
    }
    if ($null -ne $taskApp) {
        # 只在没有用户演示文稿的实例中退出，保留所有已有会话。
        if ($taskExistingCount -eq 0 -and $taskApp.Presentations.Count -eq 0) { $taskApp.Quit() }
        [Runtime.InteropServices.Marshal]::FinalReleaseComObject($taskApp) | Out-Null
    }
}
