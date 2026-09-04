@echo off
rem Junction every skill in this repository into %USERPROFILE%\.claude\skills so Claude
rem Code discovers them alongside the team repository's skills, and keep the team clone's
rem git status clean by listing the linked names in its local .git\info\exclude.
setlocal enabledelayedexpansion
set "TARGET=%USERPROFILE%\.claude\skills"
if not exist "%TARGET%" mkdir "%TARGET%"

for /d %%D in ("%~dp0*") do (
    set "NAME=%%~nxD"
    if not "!NAME:~0,1!"=="_" if not "!NAME!"==".git" if exist "%%D\SKILL.md" (
        if not exist "%TARGET%\!NAME!" (
            mklink /J "%TARGET%\!NAME!" "%%D"
        ) else (
            echo exists: !NAME!
        )
        if exist "%TARGET%\.git\info\exclude" (
            findstr /x /c:"!NAME!/" "%TARGET%\.git\info\exclude" >nul 2>&1 || echo !NAME!/>>"%TARGET%\.git\info\exclude"
        )
    )
)
echo done
