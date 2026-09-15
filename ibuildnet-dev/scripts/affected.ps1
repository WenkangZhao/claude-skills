<#
.SYNOPSIS
    Work out which test projects cover the files you changed.

.DESCRIPTION
    "Run only the affected tests" is the rule here, but deciding what counts as affected is
    otherwise a judgement call made fresh every time - and a wrong guess means a regression
    ships. This makes it mechanical: it reads the solution for the project list, works out
    which project owns each changed file, and maps those projects to the test projects whose
    names say they cover them.

    It is a naming-based map, not a call-graph. It will not find a test that covers your
    change from two projects away, so treat the output as the floor, not the ceiling.

.PARAMETER Against
    What to diff against. Default is the merge base with origin/develop, which is what a PR
    will actually be reviewed against. Use HEAD to mean "just my uncommitted work".

.PARAMETER List
    Print every project in the solution instead, with its test project where one exists.

.EXAMPLE
    .\affected.ps1
    .\affected.ps1 -Against HEAD
    .\test.ps1 -Changed          # runs what this prints
#>
[CmdletBinding()]
param(
    [string] $Against,
    [switch] $List
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_common.ps1"

$projects = Get-SolutionProjects
$testProjects = @(Get-TestProjects)

# project name -> its directory, longest path first so the most specific project wins when
# one project's folder sits inside another's.
$projectDirs = @{}
foreach ($name in $projects.Keys) {
    $projectDirs[$name] = (Split-Path $projects[$name]).ToLowerInvariant()
}

function Get-CoveringTests([string] $ProjectName) {
    # Three passes in order of precision, returning as soon as one finds anything. Running
    # them together makes a broad project like iBuilding.Test (which strips to "iBuilding")
    # look like it covers every project in the solution.
    $exact = @()
    $suffix = @()
    $prefix = @()

    foreach ($t in $testProjects) {
        $covers = Get-TestedProjectName $t
        if ($covers -ieq $ProjectName) {
            $exact += $t
        }
        elseif ($ProjectName -ilike "*.$covers") {
            # SerializationTests -> iBuilding.Serialization
            $suffix += $t
        }
        elseif ($ProjectName -ilike "$covers.*" -and ($covers.Split('.').Count -ge 2)) {
            # iBuilding.License.UnitTests -> iBuilding.License.Module / .Contract.
            # The segment count is the guard: a single-segment stem is too broad to mean
            # anything, and that is exactly the case that swallowed the whole solution.
            $prefix += $t
        }
    }

    if ($exact) {
        return $exact | Sort-Object -Unique
    }
    if ($suffix) {
        return $suffix | Sort-Object -Unique
    }
    return $prefix | Sort-Object -Unique
}

if ($List) {
    foreach ($name in ($projects.Keys | Sort-Object)) {
        if ($testProjects -contains $name) {
            continue
        }
        $covering = Get-CoveringTests $name
        $shown = if ($covering) { $covering -join ', ' } else { '(no test project)' }
        '{0,-52} {1}' -f $name, $shown
    }
    exit 0
}

Push-Location $RepoRoot
# git writes ordinary progress and line-ending notices to stderr, which PowerShell turns
# into a terminating error while ErrorActionPreference is Stop. Only the exit codes matter
# here, so drop back to Continue for the git calls.
$previousPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
    if (-not $Against) {
        $base = (& git merge-base HEAD origin/develop 2>$null)
        if ($LASTEXITCODE -ne 0 -or -not $base) {
            Write-Host 'No merge base with origin/develop (fetch first?). Falling back to HEAD.' -ForegroundColor Yellow
            $Against = 'HEAD'
        }
        else {
            $Against = $base.Trim()
        }
    }

    $changed = @(& git diff --name-only $Against 2>$null) +
               @(& git diff --name-only --cached 2>$null) +
               @(& git ls-files --others --exclude-standard 2>$null)
    $changed = $changed | Where-Object { $_ } | Sort-Object -Unique
}
finally {
    $ErrorActionPreference = $previousPreference
    Pop-Location
}

if (-not $changed) {
    Write-Host "Nothing changed against $Against." -ForegroundColor DarkGray
    exit 0
}

$owning = @{}
foreach ($file in $changed) {
    if ($file -notmatch '\.(cs|xaml|resx|csproj|config)$') {
        continue
    }
    $full = (Join-Path $RepoRoot $file).ToLowerInvariant()
    $best = $null
    $bestLen = 0
    foreach ($name in $projectDirs.Keys) {
        $dir = $projectDirs[$name] + '\'
        if ($full.StartsWith($dir) -and $dir.Length -gt $bestLen) {
            $best = $name
            $bestLen = $dir.Length
        }
    }
    if ($best) {
        $owning[$best] = $true
    }
}

$result = @()
$noCover = @()
foreach ($name in ($owning.Keys | Sort-Object)) {
    if ($testProjects -contains $name) {
        $result += $name          # you edited a test project: run it
        continue
    }
    $covering = Get-CoveringTests $name
    if ($covering) {
        $result += $covering
    }
    else {
        $noCover += $name
    }
}

$result = $result | Sort-Object -Unique

Write-Host "Changed against $Against - $($changed.Count) file(s), $($owning.Count) project(s)" -ForegroundColor Cyan
if ($noCover) {
    Write-Host "No test project for: $($noCover -join ', ')" -ForegroundColor Yellow
}
if (-not $result) {
    Write-Host 'Nothing to run by this mapping. That is a reason to look, not a reason to relax.' -ForegroundColor Yellow
    exit 0
}

$result
