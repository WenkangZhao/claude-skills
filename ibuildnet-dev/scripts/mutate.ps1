<#
.SYNOPSIS
    Prove a test actually pins the behaviour it claims to pin.

.DESCRIPTION
    A coverage claim has two states: mutation-verified, or not yet fit to go in a PR
    description. This applies one deliberate defect, builds, runs the test, and reports
    whether the test noticed - then puts the file back byte for byte.

    The restore is the part worth trusting. The original bytes are held in memory and
    written back in a finally block, the MD5 is compared before and after, and the working
    tree is checked with git. Hand-rolled apply/revert around this has already gone wrong
    once; that is why this script exists rather than another set of one-off edits.

    KILLED  - the test went red when the behaviour changed. The claim holds.
    SURVIVED - the test stayed green. The test is weaker than the claim: strengthen the
               test, never soften the claim.

.PARAMETER File
    The source file to mutate.

.PARAMETER Find
    Exact text to replace. Must occur exactly once - anything else and nothing is written.

.PARAMETER Replace
    What to put there. May be empty to delete the text.

.PARAMETER Test
    Test project(s) to run, as in test.ps1.

.PARAMETER Project
    Project to rebuild before running. Defaults to the solution, which is slow but always
    correct; name the project when you know it.

.PARAMETER Filter
    Optional /TestCaseFilter, to run only the test whose claim is being checked.

.EXAMPLE
    .\mutate.ps1 -File iBuilding\iBuilding.BLL\PowerCalculator.cs `
                 -Find "if (count == 0)" -Replace "if (count < 0)" `
                 -Project iBuilding.BLL -Test iBuilding.BLLTest -Filter "FullyQualifiedName~Power"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)] [string] $File,
    # AllowEmptyString so the check below reports *why* an empty Find is refused, rather
    # than PowerShell rejecting it with a binding error that explains nothing.
    [Parameter(Mandatory = $true)] [AllowEmptyString()] [string] $Find,
    [Parameter(Mandatory = $true)] [AllowEmptyString()] [string] $Replace,
    [Parameter(Mandatory = $true)] [string[]] $Test,
    [string] $Project,
    [string] $Filter
)

$ErrorActionPreference = 'Stop'

. "$PSScriptRoot\_common.ps1"

if ([string]::IsNullOrEmpty($Find)) {
    # An empty Find matches at position 0 and silently inserts there - a mutation nobody
    # asked for, in a place nobody looks.
    Write-Host 'Find must not be empty.' -ForegroundColor Red
    exit 2
}

$path = (Resolve-Path $File).Path
$original = [IO.File]::ReadAllBytes($path)
$md5 = [Security.Cryptography.MD5]::Create()
$hashBefore = [BitConverter]::ToString($md5.ComputeHash($original))

# Preserve the BOM exactly: this codebase requires UTF-8 with BOM on .cs files, and a
# round trip that drops it turns a mutation run into an unrelated diff.
$hasBom = $original.Length -ge 3 -and $original[0] -eq 0xEF -and $original[1] -eq 0xBB -and $original[2] -eq 0xBF
$offset = if ($hasBom) { 3 } else { 0 }
$encoding = New-Object Text.UTF8Encoding($false)
$text = $encoding.GetString($original, $offset, $original.Length - $offset)

$occurrences = ([regex]::Matches($text, [regex]::Escape($Find))).Count
if ($occurrences -ne 1) {
    Write-Host "'$Find' occurs $occurrences time(s) in $(Split-Path $path -Leaf). It must occur exactly once; nothing was written." -ForegroundColor Red
    exit 2
}

$result = 'ERROR'
$code = 1

try {
    $mutated = $text.Replace($Find, $Replace)
    $bytes = New-Object byte[] 0
    if ($hasBom) {
        $bytes = [byte[]](0xEF, 0xBB, 0xBF)
    }
    [IO.File]::WriteAllBytes($path, $bytes + $encoding.GetBytes($mutated))
    Write-Host "Mutation applied to $(Split-Path $path -Leaf)" -ForegroundColor Cyan
    Write-Host "  -  $Find" -ForegroundColor DarkGray
    Write-Host "  +  $Replace" -ForegroundColor DarkGray

    $buildArgs = @()
    if ($Project) {
        $buildArgs = @('-Project', $Project)
    }
    & "$PSScriptRoot\build.ps1" @buildArgs | Out-Null
    if ($LASTEXITCODE -ne 0) {
        # A mutation that does not compile proves nothing about the test.
        Write-Host 'The mutated source does not build - pick a mutation that compiles.' -ForegroundColor Yellow
        $result = 'DID NOT COMPILE'
    }
    else {
        $testArgs = @{ Assembly = $Test }
        if ($Filter) {
            $testArgs['Filter'] = $Filter
        }
        & "$PSScriptRoot\test.ps1" @testArgs
        if ($LASTEXITCODE -ne 0) {
            $result = 'KILLED'
            $code = 0
        }
        else {
            $result = 'SURVIVED'
        }
    }
}
finally {
    [IO.File]::WriteAllBytes($path, $original)
    $hashAfter = [BitConverter]::ToString($md5.ComputeHash([IO.File]::ReadAllBytes($path)))

    if ($hashBefore -ne $hashAfter) {
        Write-Host "RESTORE FAILED - $path does not match its original bytes. Fix this before anything else." -ForegroundColor Red
        Write-Host "  before $hashBefore" -ForegroundColor Red
        Write-Host "  after  $hashAfter" -ForegroundColor Red
        exit 3
    }

    Push-Location $RepoRoot
    $previousPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $dirty = & git diff --name-only 2>$null
    $ErrorActionPreference = $previousPreference
    Pop-Location
    if ($dirty) {
        Write-Host 'Working tree is not clean after the run. Check these before continuing:' -ForegroundColor Yellow
        $dirty | ForEach-Object { Write-Host "  $_" -ForegroundColor Yellow }
    }
    else {
        Write-Host 'Restored byte for byte; working tree clean.' -ForegroundColor DarkGray
    }
}

switch ($result) {
    'KILLED' {
        Write-Host 'KILLED - the test noticed. The coverage claim holds.' -ForegroundColor Green
    }
    'SURVIVED' {
        Write-Host 'SURVIVED - the test stayed green while the behaviour changed.' -ForegroundColor Red
        Write-Host 'Strengthen the test. Do not soften the claim in the PR description.' -ForegroundColor Red
    }
    default {
        Write-Host $result -ForegroundColor Yellow
    }
}

exit $code
