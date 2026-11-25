"""Command line for the pipeline. Run `python -m pipeline --help`.

    python -m pipeline film              the whole pipeline, then the final-cut check
    python -m pipeline radio             narration over placeholder music on a black screen
    python -m pipeline plan              what would be regenerated, and why. Calls no model.
    python -m pipeline stage keyframes   one stage
    python -m pipeline kaggle run music  run an exported GPU job on Kaggle: upload, push, wait, fetch, ingest
    python -m pipeline ingest shots results.zip    bring GPU work that was run by hand into the cache
    python -m pipeline review            one HTML page to look at and listen to everything
    python -m pipeline site              the film's public page, built from the repository
    python -m pipeline doctor            check this machine before the first run

Add --mock to any command to use the offline mock providers (outputs go to outputs_mock/).
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from . import assemble, costs, keyframes, music, narration, qc, script, shots
from .core import STAGES, Ctx, PipelineError, make_ctx

RUNNERS = {"script": script.run, "narration": narration.run, "keyframes": keyframes.run, "shots": shots.run, "music": music.run}
RADIO_STAGES = ["script", "narration", "music", "assemble"]
SAMPLE_WORDS = {"am": "ሰላም።", "ti": "ሰላም።", "om": "Akkam.", "so": "Salaan.", "en": "Hello."}


def run_stages(ctx: Ctx, names: list[str], mode: str = "film", plan_only: bool = False) -> dict:
    state: dict = {}
    for name in names:
        ctx.say(f"== {name}" + ("  (plan only, no model is called)" if plan_only else ""))
        if name == "assemble":
            assemble.run(ctx, state, mode=mode, plan_only=plan_only)
        else:
            RUNNERS[name](ctx, state, plan_only)
    return state


def smoke(ctx: Ctx) -> int:
    """Call each provider once with something tiny. The latencies land in the run log."""
    from . import providers

    voice = ctx.sb["voice"]
    calls = [
        ("text", lambda: providers.text(ctx, "smoke", "text", "Reply with the single word OK.", kind="smoke")),
        ("speech", lambda: providers.tts(ctx, "smoke", "speech", SAMPLE_WORDS.get(ctx.narration_lang, "Hello."), voice=voice["name"], style=voice["style"])),
        ("image", lambda: providers.image(ctx, "smoke", "image", "A small red circle on a plain white background.", width=512, height=512, seed=1)),
    ]
    failed = 0
    for name, call in calls:
        t0 = time.time()
        try:
            call()
            ctx.say(f"  {name:<7} ok     {time.time() - t0:6.1f}s")
        except PipelineError as e:
            failed += 1
            ctx.say(f"  {name:<7} FAILED {time.time() - t0:6.1f}s  {e}")
    if ctx.runlog.exists():
        ctx.say(f"  every attempt is logged in {ctx.runlog.relative_to(ctx.root).as_posix()}")
    return 1 if failed else 0


def doctor(root: Path | None) -> int:
    """Check this machine before the first run: tools, FFmpeg features, Python packages, keys. Prints no secret."""
    import importlib.util
    import os
    import shutil
    import subprocess

    from .core import ROOT, load_env

    load_env(Path(root or ROOT))
    problems = 0

    def report(ok: bool, name: str, fix: str = "", must: bool = True) -> None:
        nonlocal problems
        problems += 0 if ok or not must else 1
        print(f"  {'ok  ' if ok else ('FAIL' if must else 'note')} {name}" + ("" if ok or not fix else f"  ->  {fix}"))

    report(sys.version_info >= (3, 10), f"Python {sys.version.split()[0]} (3.10 or newer)", "install a newer Python")
    print(f"       running {sys.executable}")
    for tool in ("ffmpeg", "ffprobe"):
        report(shutil.which(tool) is not None, f"{tool} on PATH", "install FFmpeg, on Ubuntu or Debian: sudo apt install ffmpeg")
    if shutil.which("ffmpeg"):
        def listing(flag: str) -> str:
            return subprocess.run(["ffmpeg", "-hide_banner", flag], capture_output=True, text=True, errors="replace").stdout
        banner = (listing("-version").splitlines() or ["version unknown"])[0]
        print(f"       {banner.split(' Copyright')[0]}")
        filters, encoders = listing("-filters"), listing("-encoders")
        for name in ("ass", "zoompan", "sidechaincompress", "loudnorm", "tpad", "ebur128", "boxblur"):
            report(f" {name} " in filters, f"FFmpeg filter {name}", "use a full FFmpeg build (with libass)")
        for name in ("libx264", "aac"):
            report(f" {name} " in encoders, f"FFmpeg encoder {name}", "use a full FFmpeg build")
        # the sound mix uses two options that old builds lack: try them instead of trusting a version number
        mix = "[0:a]adelay=50:all=1[a];[a][1:a]amix=inputs=2:normalize=0"
        trial = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-f", "lavfi", "-i", "sine=d=0.2", "-f", "lavfi", "-i", "sine=f=660:d=0.2",
                                "-filter_complex", mix, "-f", "null", "-"], capture_output=True, text=True, errors="replace")
        report(trial.returncode == 0, "FFmpeg can run the sound mix (amix normalize, adelay all)", "FFmpeg 4.4 or newer is needed")
    for module in ("jsonschema", "requests"):
        report(importlib.util.find_spec(module) is not None, f"Python package {module}", "make setup")
    report(importlib.util.find_spec("mcp") is not None, "Python package mcp (only for the MCP server)", "pip install mcp", must=False)
    for key in ("GEMINI_API_KEY", "CLOUDFLARE_ACCOUNT_ID", "CLOUDFLARE_API_TOKEN"):
        present = bool(os.environ.get(key, "").strip())
        report(present, f"{key} is {'set' if present else 'not set'}", "put it in .env (see .env.example)", must=False)
    print("  ready" if not problems else f"  {problems} thing(s) to fix before the pipeline can run")
    return 1 if problems else 0


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", type=Path, default=None, help="project folder (default: this repository)")
    common.add_argument("--mock", action="store_true", help="offline mock providers, outputs in outputs_mock/")
    common.add_argument("--lang", default=None, help="narrate in another language that has lines in the storyboard")

    p = argparse.ArgumentParser(prog="python -m pipeline", description="Storyboard in, short film out.")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate", parents=[common], help="check storyboard.json").add_argument("--strict", action="store_true")
    sub.add_parser("plan", parents=[common], help="show what would be regenerated and why")
    sub.add_parser("stage", parents=[common], help="run one stage").add_argument("name", choices=STAGES)
    sub.add_parser("radio", parents=[common], help="radio cut: narration and placeholder music on black")
    sub.add_parser("film", parents=[common], help="the whole pipeline").add_argument("--strict", action="store_true", help="refuse drafts, pending consent and a failed final-cut check")
    sub.add_parser("qc", parents=[common], help="final-cut check on the exported films")
    sub.add_parser("costs", parents=[common], help="latency and cost per stage from the run log").add_argument("--write", action="store_true", help="also update COSTS.md")
    sub.add_parser("smoke", parents=[common], help="call each provider once")
    sub.add_parser("doctor", parents=[common], help="check tools, FFmpeg features, packages and keys on this machine")
    sub.add_parser("review", parents=[common], help="one HTML page with every shot, line, candidate and clip, for review by eye and ear")
    sub.add_parser("site", parents=[common], help="the film's public page, built from the repository into site/")
    ing = sub.add_parser("ingest", parents=[common], help="bring finished GPU work into the cache")
    ing.add_argument("stage", choices=["shots", "music"])
    ing.add_argument("path", type=Path)
    kg = sub.add_parser("kaggle", parents=[common], help="run an exported GPU job on Kaggle: upload, push, wait, fetch, ingest")
    kg.add_argument("action", choices=["run", "status", "fetch", "logs"])
    kg.add_argument("stage", choices=["shots", "music"])
    kg.add_argument("--no-wait", action="store_true", help="push the job and return. Fetch the results later with `kaggle fetch`")
    lt = sub.add_parser("langtest", parents=[common], help="speak test lines in several languages and score them by listening back")
    lt.add_argument("--langs", default="am,ti,so,om")
    bt = sub.add_parser("blindtest", parents=[common], help="blind A/B preference test")
    bt.add_argument("action", choices=["pack", "score"])
    bt.add_argument("name")
    bt.add_argument("--a", type=Path, action="append", default=[], help="file made the first way (repeat for more pairs)")
    bt.add_argument("--b", type=Path, action="append", default=[], help="file made the second way, same order as --a")
    bt.add_argument("--labels", default="A,B", help="what the two ways are called, e.g. kenburns,wan")
    bt.add_argument("--votes", type=Path, help="CSV with the columns rater,pair,choice (choice is X or Y)")
    bt.add_argument("--seed", type=int, default=2026)
    new = sub.add_parser("init", help="start a new film: a folder with a blank storyboard and the pipeline")
    new.add_argument("folder", type=Path)
    new.add_argument("--lang", default="en")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):  # narration lines are printed in their own script
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    args = build_parser().parse_args(argv)
    try:
        if args.cmd == "init":
            from . import scaffold
            return scaffold.init(args.folder, args.lang)
        if args.cmd == "doctor":
            return doctor(args.root)
        strict = bool(getattr(args, "strict", False))
        ctx = make_ctx(root=args.root, mock=True if args.mock else None, lang=args.lang, strict=strict)
        if ctx.mock:
            ctx.say("  mock providers: nothing here comes from a real model")
        if args.cmd == "validate":
            ctx.say(f"storyboard.json is valid: {len(ctx.sb['shots'])} shots, narration in '{ctx.narration_lang}'" + (" (strict)" if strict else ""))
        elif args.cmd == "plan":
            run_stages(ctx, STAGES, plan_only=True)
        elif args.cmd == "stage":
            run_stages(ctx, [args.name])
        elif args.cmd == "radio":
            run_stages(ctx, RADIO_STAGES, mode="radio")
        elif args.cmd == "film":
            state = run_stages(ctx, STAGES)
            ctx.say("== final-cut check")
            report = qc.run(ctx, state)
            return 1 if strict and not report["passed"] else 0
        elif args.cmd == "qc":
            return 0 if qc.run(ctx)["passed"] else 1
        elif args.cmd == "costs":
            costs.run(ctx, write=args.write)
        elif args.cmd == "smoke":
            return smoke(ctx)
        elif args.cmd == "review":
            from . import review
            review.run(ctx)
        elif args.cmd == "site":
            from . import site
            site.run(ctx)
        elif args.cmd == "ingest":
            count = (shots if args.stage == "shots" else music).ingest(ctx, args.path)
            ctx.say(f"  {count} file(s) ingested. Run `python -m pipeline film` to use them.")
        elif args.cmd == "kaggle":
            from . import kagglerun
            return kagglerun.run(ctx, args.action, args.stage, wait_for_it=not args.no_wait)
        elif args.cmd == "langtest":
            from . import langtest
            langtest.run(ctx, [code.strip() for code in args.langs.split(",") if code.strip()])
        elif args.cmd == "blindtest":
            from . import blindtest
            return blindtest.run(ctx, args)
        return 0
    except PipelineError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())