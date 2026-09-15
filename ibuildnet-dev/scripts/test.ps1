<#
.SYNOPSIS
    Run iBuildNet unit tests the way they have to be run here.

.DESCRIPTION
    Every test project in this solution writes to one shared output folder,
    iBuilding\iBuilding.UITest\bin\Debug, so a run selects assemblies out of there. This
    wrapper finds vstest.console.exe through vswhere and - the part that matters - never
    passes /Platform. The GdalBin natives are x64-only, and /Platform:x86 kills the run with
    a load failure that reads like a test bug.

.PARAMETER Assembly
    One or more test project names, with or without .dll.

.PARAMETER Changed
    Run whatever affected.ps1 says your changes touched.

.PARAMETER Filter
    A vstest /TestCaseFilter expression, e.g. "FullyQualifiedName~SelectMaterial".

.PARAMETER Against
    Passed through to affected.ps1 when -Changed is used.

.EXAMPLE
    .\test.ps1 -Changed
    .\test.ps1 iBuilding.ModelTest
    .\test.ps1 iBuilding.BLLTest -Filter "FullyQualifiedName~Antenna"
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)]
    [string[]] $Assembly,
    [switch] $Changed,
    [string] $Filter,
    [string] $Against
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_common.ps1"

if ($Changed) {
    $affectedArgs = @{}
    if ($Against) {
        $affectedArgs['Against'] = $Against
    }
    $found = & "$PSScriptRoot\affected.ps1" @affectedArgs | Where-Object { $_ -match '^[A-Za-z0-9_.]+$' }
    if (-not $found) {
        Write-Host 'Nothing to run.' -ForegroundColor DarkGray
        exit 0
    }
    $Assembly = @($found)
}

if (-not $Assembly) {
    Write-Host 'Name a test project, or use -Changed. Available:' -ForegroundColor Yellow
    Get-TestProjects
    exit 2
}

if (-not (Test-Path $TestOutputDir)) {
    Write-Host "No test output at $TestOutputDir - build the solution first (.\build.ps1)." -ForegroundColor Red
    exit 2
}

$dlls = @()
$missing = @()
foreach ($name in $Assembly) {
    $leaf = $name
    if ($leaf -notlike '*.dll') {
        $leaf = "$leaf.dll"
    }
    $path = Join-Path $TestOutputDir $leaf
    if (Test-Path $path) {
        $dlls += $path
    }
    else {
        $missing += $leaf
    }
}

if ($missing) {
    # A missing assembly nearly always means that project was never built, not that the name
    # is wrong - say which, because the two need different fixes.
    Write-Host "Not in the shared output folder: $($missing -join ', ')" -ForegroundColor Red
    Write-Host "Build it first:  .\build.ps1 -Project $($missing[0] -replace '\.dll$','')" -ForegroundColor Yellow
    if (-not $dlls) {
        exit 2
    }
}

$vstest = Get-VsTestPath
$vstestArgs = @($dlls) + @('/Logger:console;verbosity=minimal')
if ($Filter) {
    $vstestArgs += "/TestCaseFilter:$Filter"
}

Write-Host "Running $($dlls.Count) assembly(ies) from the shared output folder" -ForegroundColor Cyan
$dlls | ForEach-Object { Write-Host "  $(Split-Path $_ -Leaf)" -ForegroundColor DarkGray }

$stopwatch = [Diagnostics.Stopwatch]::StartNew()
# A failing test writes to stderr, which PowerShell would turn into a terminating error
# under Stop - hiding the very output the run exists to show. The exit code is the verdict.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
& $vstest @vstestArgs
$code = $LASTEXITCODE
$ErrorActionPreference = $previousPreference
$stopwatch.Stop()

Write-Host ("Finished in {0:mm\:ss}" -f $stopwatch.Elapsed) -ForegroundColor DarkGray

if ($code -ne 0) {
    Write-Host 'TESTS FAILED' -ForegroundColor Red
    Write-Host 'If the failures are duplicate-type compile errors, delete the nested iBuilding.UITest directories under other projects'' output and rebuild.' -ForegroundColor Yellow
}

exit $code
