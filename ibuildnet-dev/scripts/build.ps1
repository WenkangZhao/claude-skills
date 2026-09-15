<#
.SYNOPSIS
    Build iBuildNet the way a developer needs it built.

.DESCRIPTION
    Wraps the solution build so the four traps in CLAUDE.md cannot be hit by accident:
    MSBuild is discovered through vswhere (edition- and version-agnostic), the platform is
    "Any CPU" with the space, restore is cache-only, and the log is filtered down to errors.

    This is NOT buildTools\build.bat. That one is the 2016 release/packaging script, pinned
    to MSBuild 14.0, x86 and Release; running it when you wanted a debug build gives you
    something quite different.

.PARAMETER Project
    Build one project instead of the solution. SolutionDir is supplied explicitly, because
    without it every project writes to a bogus path and the real bin\Debug is left stale
    with no error at all.

.PARAMETER Configuration
    Debug (default) or Release.

.PARAMETER Restore
    Run a cache-only restore first. Safe: RestoreSources is emptied, so NuGet either
    resolves from ~\.nuget\packages or fails cleanly - it can never resolve a wrong version
    and corrupt obj\project.assets.json.

.PARAMETER Rebuild
    Clean before building.

.PARAMETER Full
    Show MSBuild's own console output instead of just the errors.

.EXAMPLE
    .\build.ps1
    .\build.ps1 -Project iBuilding.BLL
    .\build.ps1 -Restore -Rebuild
#>
[CmdletBinding()]
param(
    [string] $Project,
    [ValidateSet('Debug', 'Release')]
    [string] $Configuration = 'Debug',
    [switch] $Restore,
    [switch] $Rebuild,
    [switch] $Full
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_common.ps1"

$msbuild = Get-MSBuildPath
$solution = Join-Path $RepoRoot 'iBuilding\iBuilding_2010.sln'
$logDir = Join-Path $env:TEMP 'ibuildnet-build'
if (-not (Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}
$log = Join-Path $logDir ("build-{0}.log" -f (Get-Date -Format 'yyyyMMdd-HHmmss'))

if ($Project) {
    $target = Get-ProjectPath $Project
    if (-not $target) {
        Write-Host "No project named '$Project' in the solution. Try: .\affected.ps1 -List" -ForegroundColor Red
        exit 2
    }
    # The trailing slash is required, and forward slashes keep MSYS from rewriting the path.
    $solutionDir = (Join-Path $RepoRoot 'iBuilding').Replace('\', '/') + '/'
    $buildArgs = @($target, "-p:SolutionDir=$solutionDir")
    Write-Host "Building project $Project ($Configuration)" -ForegroundColor Cyan
}
else {
    $buildArgs = @($solution)
    Write-Host "Building the solution ($Configuration)" -ForegroundColor Cyan
}

$common = @('-nologo', '-v:m', '-m', "-p:Configuration=$Configuration", '-p:Platform=Any CPU')

# MSBuild writes warnings and errors to stderr; under Stop, PowerShell would turn a normal
# failed build into a terminating error and swallow the diagnostics. Exit codes decide here.
$ErrorActionPreference = 'Continue'

if ($Restore) {
    Write-Host 'Restoring (cache only)...' -ForegroundColor DarkGray
    & $msbuild @buildArgs @common '-t:Restore' '-p:RestoreSources=' | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Restore failed. Every package except DevExpress can be fetched; DevExpress must already be in ~\.nuget\packages.' -ForegroundColor Red
        exit $LASTEXITCODE
    }
}

if ($Rebuild) {
    $common += '-t:Rebuild'
}

$stopwatch = [Diagnostics.Stopwatch]::StartNew()

if ($Full) {
    & $msbuild @buildArgs @common '-fl' "-flp:logfile=$log;verbosity=normal"
}
else {
    # Piping a native command keeps $LASTEXITCODE as MSBuild's own, not the filter's.
    & $msbuild @buildArgs @common '-fl' "-flp:logfile=$log;verbosity=normal" |
        Select-String -Pattern ': error|: warning MSB3644|Build succeeded|Build FAILED|Time Elapsed'
}
$code = $LASTEXITCODE

$stopwatch.Stop()
Write-Host ("Finished in {0:mm\:ss} - full log: {1}" -f $stopwatch.Elapsed, $log) -ForegroundColor DarkGray

if ($code -ne 0) {
    Write-Host 'BUILD FAILED' -ForegroundColor Red
    Write-Host 'Distinct errors:' -ForegroundColor Red
    Select-String -Path $log -Pattern ': error' |
        ForEach-Object { $_.Line.Trim() } |
        Sort-Object -Unique |
        Select-Object -First 25
}
else {
    # Exit code 0 alone is not proof: Gotcha 1 makes a bare-project build "succeed" while
    # leaving the real output untouched. Show what the deployed folder actually holds now.
    $exe = Join-Path $RepoRoot 'iBuilding\iBuilding.UI\bin\Debug\iBuildNet.exe'
    if (Test-Path $exe) {
        $age = (Get-Date) - (Get-Item $exe).LastWriteTime
        Write-Host ("BUILD SUCCEEDED - iBuildNet.exe written {0:n0} minute(s) ago" -f $age.TotalMinutes) -ForegroundColor Green
    }
    else {
        Write-Host 'BUILD SUCCEEDED, but iBuildNet.exe is not in bin\Debug - check what you actually built.' -ForegroundColor Yellow
    }
}

exit $code
