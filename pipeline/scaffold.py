"""Start a new film: copy the pipeline into a folder with a blank storyboard.

This is the "tool for others" part. Someone with a story, or their coding agent, runs
`python -m pipeline init my-film`, fills in storyboard.json, and has the same stages, cache, run
log and final-cut check.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from .core import ROOT, check_storyboard

COPY = ["pipeline", "schema", "kaggle", "Makefile", "requirements.txt", ".gitignore", ".env.example", "pricing.json"]
DOCS = {
    "DESIGN.md": "# Design\n\n## Audience\n\n## Intent\n\n## A reason for every shot\n\nSee the `reason` field of each shot in storyboard.json.\n\n"
                 "## User test 1: radio cut\n\n## User test 2: near-final cut\n",
    "ETHICS.md": "# Ethics\n\n## Consent\n\n| ID | Person | What appears | How consent was given | Date |\n|---|---|---|---|---|\n\n"
                 "## Licences\n\n## Labelling\n",
    "EXPERIMENTS.md": "# Experiments\n\nOne entry per experiment: hypothesis, the one thing changed, result, decision.\n",
    "FAILURES.md": "# Failures\n\nOne entry per blocker: what broke, what was tried, what fixed it.\n",
    "COSTS.md": "# Costs\n\n<!-- costs:begin (written by `python -m pipeline costs --write`) -->\n<!-- costs:end -->\n",
}


def blank_storyboard(lang: str) -> dict:
    base = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
    sb = {k: base[k] for k in ("version", "format", "models", "video", "qa") if k in base}
    sb.update(
        title="Untitled",
        language={"narration": lang, "subtitles": "en"},
        audience="DRAFT: who will watch this, and where?",
        intent="DRAFT: what should they feel or understand when it ends?",
        style={"block": "DRAFT: describe the look in qualities (medium, palette, light). Do not name a living artist."},
        characters=[],
        voice=base["voice"],
        music={"caption": "DRAFT: style, mood, instruments and texture of the score.", "duration_s": 80, "seeds": [1, 2, 3], "chosen": None, "cues": []},
        end_card={"duration_s": 3, "lines": ["Made with AI"]},
        shots=[{
            "id": f"s{i:02d}", "title": f"Shot {i}", "reason": "DRAFT: why does this shot exist?", "size": "medium", "characters": [],
            "min_duration_s": 6,
            "keyframe": {"prompt": "DRAFT: what is in the picture, with the subject in the centre.", "seed": 100 + i},
            "motion": {"backend": "kenburns", "camera": "push_in", "prompt": "DRAFT: motion and camera only."},
            "narration": {lang: "DRAFT: the line spoken over this shot.", **({} if lang == "en" else {"en": "DRAFT: its subtitle."})},
            "review": {"confirmed": False, "note": "Not written yet."},
        } for i in range(1, 9)],
    )
    return sb


def init(folder: Path, lang: str) -> int:
    folder = Path(folder).resolve()
    if folder.exists() and any(folder.iterdir()):
        print(f"error: {folder} is not empty")
        return 1
    folder.mkdir(parents=True, exist_ok=True)
    for name in COPY:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, folder / name, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        elif src.exists():
            shutil.copy2(src, folder / name)
    for name, text in DOCS.items():
        (folder / name).write_text(text, encoding="utf-8")
    sb = blank_storyboard(lang)
    (folder / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    errors = [msg for level, _, msg in check_storyboard(sb, folder) if level == "error"]
    if errors:
        print("error: the blank storyboard does not validate:\n  " + "\n  ".join(errors))
        return 1
    print(f"New film in {folder}\nNext: edit storyboard.json, then run `python -m pipeline validate` and `python -m pipeline radio --mock` inside it.")
    return 0
