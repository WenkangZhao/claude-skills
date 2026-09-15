<#
    Shared helpers for the ibuildnet-dev scripts. Dot-source it:

        . "$PSScriptRoot\_common.ps1"

    Everything here is discovery rather than configuration, so the scripts work on any
    developer's machine regardless of Visual Studio edition, version, or checkout path.
#>

# These scripts live in the skills repository, not inside iBuildNet, so the repository is
# found from where they are run: $env:IBUILDNET_ROOT when set, otherwise the git top level
# of the current directory. Either has to hold iBuilding\iBuilding_2010.sln, which is also
# what makes a worktree resolve to itself rather than to the main checkout.
function Find-RepoRoot {
    $candidates = @()
    if ($env:IBUILDNET_ROOT) { $candidates += $env:IBUILDNET_ROOT }
    $top = & git rev-parse --show-toplevel 2>$null
    if ($top) { $candidates += $top }
    foreach ($candidate in $candidates) {
        $resolved = Resolve-Path $candidate -ErrorAction SilentlyContinue
        if ($resolved -and (Test-Path (Join-Path $resolved.Path 'iBuilding\iBuilding_2010.sln'))) {
            return $resolved.Path
        }
    }
    throw 'Not inside an iBuildNet checkout. Run from the repository (any subfolder) or set IBUILDNET_ROOT.'
}

$script:RepoRoot = Find-RepoRoot
$RepoRoot = $script:RepoRoot
$SolutionPath = Join-Path $RepoRoot 'iBuilding\iBuilding_2010.sln'

# Where every test project writes its output. They all share one folder, so a test run
# picks assemblies out of here rather than out of each project's own bin.
$TestOutputDir = Join-Path $RepoRoot 'iBuilding\iBuilding.UITest\bin\Debug'

function Get-VsWherePath {
    $p = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
    if (-not (Test-Path $p)) {
        throw "vswhere.exe not found at $p. It ships with Visual Studio 2017 and later at that fixed path."
    }
    return $p
}

function Get-MSBuildPath {
    <# MSBuild is not on PATH, and the version/edition differ per machine, so never
       hard-code it. dotnet build does not correctly build this legacy solution. #>
    $vswhere = Get-VsWherePath
    $found = & $vswhere -latest -products * -requires Microsoft.Component.MSBuild `
                        -find 'MSBuild\**\Bin\MSBuild.exe' | Select-Object -First 1
    if (-not $found) {
        throw 'No MSBuild found. Install the "MSBuild" component in the Visual Studio Installer.'
    }
    return $found
}

function Get-VsTestPath {
    $vswhere = Get-VsWherePath
    $found = & $vswhere -latest -products * `
                        -find 'Common7\IDE\CommonExtensions\Microsoft\TestWindow\vstest.console.exe' |
             Select-Object -First 1
    if (-not $found) {
        throw 'vstest.console.exe not found. Install the "Testing tools core features" component.'
    }
    return $found
}

function Get-SolutionProjects {
    <# name -> absolute .csproj path, read straight from the solution file so the list
       cannot drift from what actually builds. #>
    if ($script:ProjectCache) {
        return $script:ProjectCache
    }
    $map = @{}
    $slnDir = Split-Path $SolutionPath
    foreach ($line in Get-Content $SolutionPath) {
        if ($line -match '^Project\("\{[^}]+\}"\)\s*=\s*"([^"]+)",\s*"([^"]+)"') {
            $name = $Matches[1]
            $rel = $Matches[2]
            if ($rel -like '*.csproj') {
                $map[$name] = (Join-Path $slnDir $rel)
            }
        }
    }
    $script:ProjectCache = $map
    return $map
}

function Get-ProjectPath([string] $Name) {
    $projects = Get-SolutionProjects
    if ($projects.ContainsKey($Name)) {
        return $projects[$Name]
    }
    $hit = $projects.Keys | Where-Object { $_ -ieq $Name } | Select-Object -First 1
    if ($hit) {
        return $projects[$hit]
    }
    return $null
}

# Projects whose name ends in Test(s) but which are not runnable suites: a benchmark
# harness, an interactive capture harness, and the quarantine holding pen.
$NonSuiteProjects = @(
    'iBuilding.Benchmarks',
    'Ranplan.iBuildNet.CaptureControl.TestHarness'
)

function Get-TestProjects {
    $projects = Get-SolutionProjects
    return $projects.Keys |
        Where-Object { $_ -match '(Test|Tests)$' -and $NonSuiteProjects -notcontains $_ } |
        Sort-Object
}

function Get-TestedProjectName([string] $TestProjectName) {
    <# Strip the suffix a test project's name carries, so it can be matched back to the
       project it covers: iBuilding.BLLTest -> iBuilding.BLL, Optimisation.EngineTests ->
       Optimisation.Engine, iBuilding.License.UnitTests -> iBuilding.License. #>
    $stripped = $TestProjectName -replace '\.?(Unit)?Tests?$', ''
    return $stripped.TrimEnd('.')
}
