#!/usr/bin/env python
"""Report which Sidekick verification layers this machine can actually run.

Layers 3 and 4 SKIP rather than FAIL when a prerequisite is missing, so a run that
proved nothing looks exactly like a run that proved everything. This script answers the
question those layers cannot: is the C# gate able to compile, and is there a live app
behind driver.json - or just a file left over from last week?

    python verify_env.py                 # the report
    python verify_env.py --collect       # also count the tests in each service (slower)
    python verify_env.py --repos D:\\src  # when the checkouts are not beside this one

Exit code 0 always: this is a report, not a gate.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

SERVICES = ["pleiades-ms-ai-orchestrator",
            "pleiades-ms-ai-tool-engine",
            "pleiades-ms-ai-code-engine"]

APP_REL = Path("iBuilding") / "iBuilding.UI" / "bin" / "Debug"
SDK_TOOLS_REL = Path("StandaloneUtilities") / "Ranplan.SDK.Tools"

OK, NO, WARN = "[ok]", "[--]", "[!!]"


def out(mark: str, label: str, detail: str = "") -> None:
    print(f"  {mark} {label}" + (f"  {detail}" if detail else ""))


def age(path: Path) -> str:
    """How long ago a file was written, in the units a reader actually needs."""
    seconds = time.time() - path.stat().st_mtime
    if seconds < 3600:
        return f"{seconds / 60:.0f} min ago"
    if seconds < 86400:
        return f"{seconds / 3600:.1f} h ago"
    return f"{seconds / 86400:.0f} days ago"


def find_repos_root(explicit: str) -> Path:
    """The directory the checkouts sit in, side by side."""
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("SIDEKICK_REPOS")
    if env:
        return Path(env).expanduser().resolve()
    # scripts/ -> sidekick-verify/ -> claude-skills/ -> the repos root. resolve() follows the
    # junction when this skill is reached through %USERPROFILE%\.claude\skills.
    candidate = Path(__file__).resolve().parents[3]
    if any((candidate / name).is_dir() for name in SERVICES):
        return candidate
    return Path.cwd().resolve()


def find_ibuildnet(root: Path) -> Path | None:
    """The iBuildNet checkout, by the same rules the gates use: explicit, then layout."""
    env = os.environ.get("IBUILDNET_ROOT")
    if env and (Path(env) / APP_REL).is_dir():
        return Path(env).resolve()
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        if child.is_dir() and (child / APP_REL).is_dir():
            return child
    return None


def venv_python(repo: Path) -> Path | None:
    for rel in (Path(".venv") / "Scripts" / "python.exe", Path(".venv") / "bin" / "python"):
        if (repo / rel).exists():
            return repo / rel
    return None


def check_services(root: Path, collect: bool) -> bool:
    print("\nLayer 1-2  unit tests + the contract linter (no app, no key)")
    ready = True
    for name in SERVICES:
        repo = root / name
        if not repo.is_dir():
            out(NO, name, "checkout not found")
            ready = False
            continue
        python = venv_python(repo)
        if not python:
            out(NO, name, "no .venv - create one, the system Python has no pytest")
            ready = False
            continue
        detail = ""
        if collect:
            try:
                proc = subprocess.run([str(python), "-m", "pytest", "tests", "-q", "--collect-only"],
                                      cwd=repo, capture_output=True, text=True, timeout=180)
                line = [x for x in proc.stdout.splitlines() if "collected" in x]
                detail = line[-1].strip() if line else "collected ?"
            except Exception as exc:                      # a broken venv is the finding
                out(NO, name, f"pytest failed to run: {exc}")
                ready = False
                continue
        out(OK, name, detail or str(python.relative_to(repo)))
    return ready


def check_compile_gates(root: Path, ibuildnet: Path | None) -> bool:
    print("\nLayer 3  the C# compile gates (needs an iBuildNet Debug build, no running app)")
    dll = os.environ.get("RANPLAN_COMMAND_API_DLL")
    dll_path = Path(dll) if dll else (ibuildnet / APP_REL / "RanplanWireless.Professional.SDK.Api.dll"
                                      if ibuildnet else None)
    have_dll = bool(dll_path and dll_path.exists())
    if have_dll:
        out(OK, "SDK.Api.dll", f"built {age(dll_path)}  {dll_path}")
    else:
        out(NO, "SDK.Api.dll", "not found - build iBuilding_2010.sln, or set RANPLAN_COMMAND_API_DLL")

    engine = root / "pleiades-ms-ai-tool-engine"
    gate = engine / "tools" / "ScriptGate" / "bin" / "Debug" / "net472" / "ScriptGate.exe"
    if gate.exists():
        out(OK, "ScriptGate.exe", f"built {age(gate)} - the host's own compiler, prefer it")
    else:
        out(NO, "ScriptGate.exe", "not built - run: dotnet build tools/ScriptGate")

    mirror = engine / "tools" / "csbody-compile-check" / "bin" / "Debug" / "net472" / "CompileCheck.exe"
    if mirror.exists():
        out(OK, "CompileCheck.exe", f"built {age(mirror)} - mirrors the host gate, can drift")
    else:
        out(NO, "CompileCheck.exe", "not built - run: dotnet build tools/csbody-compile-check")

    return have_dll and (gate.exists() or mirror.exists())


def read_driver(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def check_live_app(root: Path, ibuildnet: Path | None) -> bool:
    print("\nLayer 4  the live app (iBuildNet running with --devlicense=auto)")
    if not ibuildnet:
        out(NO, "iBuildNet checkout", "not found beside these repos - pass --repos or set IBUILDNET_ROOT")
        return False

    exe = ibuildnet / APP_REL / "iBuildNet.exe"
    out(OK if exe.exists() else NO, "iBuildNet.exe",
        f"built {age(exe)}" if exe.exists() else "not built - build iBuilding_2010.sln")

    driver = ibuildnet / APP_REL / "driver.json"
    live = False
    if not driver.exists():
        out(NO, "driver.json", "absent - the app writes it AT STARTUP; start the app once")
    else:
        info = read_driver(driver)
        host, port = info.get("host") or "127.0.0.1", info.get("port")
        where = f"{host}:{port}  pid {info.get('process_id', '?')}  started {info.get('started_at', '?')}"
        try:
            with socket.create_connection((host, int(port)), timeout=1.5):
                live = True
        except Exception:
            live = False
        if live:
            out(OK, "driver.json", f"LIVE - {where}")
        else:
            out(WARN, "driver.json", f"STALE ({age(driver)}) - nothing answers. {where}")

    runner = os.environ.get("SDK_TEST_EXE") or str(
        ibuildnet / SDK_TOOLS_REL / "Ranplan.SDK.TestRunner" / "bin" / "Debug" / "net8.0"
        / "Ranplan.SDK.TestRunner.exe")
    if Path(runner).exists():
        out(OK, "sdk-test", f"built {age(Path(runner))}")
    else:
        out(NO, "sdk-test", "not built - dotnet build StandaloneUtilities/Ranplan.SDK.Tools/"
                            "Ranplan.SDK.Tools.slnx -c Debug")

    baseline = (ibuildnet / SDK_TOOLS_REL / "TestSuite" / "BaselineProjects" / "Project12"
                / "Project12.ibpx")
    out(OK if baseline.exists() else NO, "baseline project",
        str(baseline) if baseline.exists() else "missing - gate against the committed one, not a copy")

    keys = ["LOCAL_CODE_ENGINE_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY",
            "CORPUS_QUALITY_GEMINI_API_KEY", "LITELLM_MASTER_KEY"]
    named = next((k for k in keys if os.environ.get(k)), "")
    local_env = ibuildnet / SDK_TOOLS_REL / "local_code_engine" / "local.env"
    if named:
        out(OK, "Gemini key", f"in ${named} - local_code_engine and eval/loop.py can run")
    elif local_env.exists():
        out(OK, "Gemini key", f"in {local_env.name}")
    else:
        out(WARN, "Gemini key", "none - ask.py and eval/loop.py cannot run (preflight_only still can)")

    return live and Path(runner).exists()


def check_replay(root: Path) -> None:
    print("\nReplay  recorded sessions re-run through the real loop (no LLM, no engines)")
    traj = root / "pleiades-ms-ai-orchestrator" / "tests" / "data" / "trajectories"
    files = sorted(traj.glob("*.jsonl")) if traj.is_dir() else []
    if files:
        out(OK, "trajectories", f"{len(files)} recorded: " + ", ".join(f.stem for f in files[:5]))
    else:
        out(WARN, "trajectories", "none recorded yet - record one with scripts/replay_session.py "
                                  "--session <id> --url $SIDEKICK_BASE_URL --save ...")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repos", default="", help="directory holding the checkouts side by side")
    parser.add_argument("--collect", action="store_true", help="also count each service's tests")
    args = parser.parse_args()

    root = find_repos_root(args.repos)
    ibuildnet = find_ibuildnet(root)
    print(f"repos root : {root}")
    print(f"iBuildNet  : {ibuildnet or 'not found'}")

    layer12 = check_services(root, args.collect)
    layer3 = check_compile_gates(root, ibuildnet)
    layer4 = check_live_app(root, ibuildnet)
    check_replay(root)

    highest = 4 if layer4 else 3 if layer3 else 2 if layer12 else 0
    print(f"\nHighest layer this machine can run right now: {highest}")
    if highest < 4:
        print("Anything above that SKIPS rather than fails - a green run there proves nothing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
