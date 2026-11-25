"""E27: who hears Amharic better, and where does a sentence end?

    python experiments/e27_subtitle_timing.py

Two questions about the eight narration lines of the film, answered from files that are already in
the repository. No model is called.

1. The listening check. On 26 Nov the same eight audio files were written down twice: by the text
   model, which is given the audio and asked for a transcription (kept in the index of commit
   531e84a), and by a speech model built for Amharic (the index as it is now). Both are scored here
   in the same way, against the script, with Ethiopic letters that sound the same counted as one.

2. The subtitles. A subtitle sentence should come up when its sentence is spoken. Where a spoken
   sentence ends is worked out in two ways: from the number of letters and the measured pauses
   (what the pipeline did until 26 Nov), and from the words the speech model heard with the time of
   each. The difference between the two, per sentence end, says how far off the first way was.

Results go to outputs/experiments/E27/results.json.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pipeline import core  # noqa: E402
from pipeline.narration import similarity  # noqa: E402

BEFORE = "531e84a"  # the commit whose index holds what the text model heard in the same audio files


def letters(text: str) -> int:
    return max(1, sum(ch.isalnum() for ch in text))


def main() -> None:
    sb = json.loads((ROOT / "storyboard.json").read_text(encoding="utf-8"))
    lang = sb["language"]["narration"]
    now = json.loads((ROOT / "outputs" / "narration" / f"index.{lang}.json").read_text(encoding="utf-8"))
    old = json.loads(subprocess.run(["git", "show", f"{BEFORE}:outputs/narration/index.{lang}.json"], cwd=ROOT, capture_output=True,
                                    text=True, encoding="utf-8", check=True).stdout)
    lines = {s["id"]: s["narration"][lang] for s in sb["shots"] if s["narration"]}
    rows, gaps = {}, []
    for sid, text in lines.items():
        a, b = old.get(sid, {}), now[sid]
        row = {"same_audio": a.get("file") == b["file"], "seconds": b["seconds"],
               "text_model": {"heard": a.get("heard"), "match": similarity(text, a["heard"]) if a.get("heard") else None},
               "speech_model": {"heard": b.get("heard"), "match": similarity(text, b["heard"]) if b.get("heard") else None, "model": b.get("heard_by")}}
        said = core.sentences(text)
        by_letters = core.sentence_ends([letters(s) for s in said], b["seconds"], b.get("pauses"))
        by_words = core.sentence_ends_heard(text, b.get("words") or [], b["seconds"])
        row["sentences"] = len(said)
        row["ends_by_letters_and_pauses"] = [round(stop, 2) for stop, _ in by_letters[:-1]]
        row["ends_by_heard_words"] = [round(stop, 2) for stop, _ in by_words[:-1]] if by_words else None
        if by_words:
            row["difference_s"] = [round(x - y, 2) for (x, _), (y, _) in zip(by_letters[:-1], by_words[:-1])]
            gaps += [abs(d) for d in row["difference_s"]]
        rows[sid] = row
        print(f"{sid}  text model {row['text_model']['match']}  speech model {row['speech_model']['match']}  "
              f"sentence ends: letters {row['ends_by_letters_and_pauses']}  words {row['ends_by_heard_words']}")
    both = [r for r in rows.values() if r["same_audio"] and r["text_model"]["match"] is not None and r["speech_model"]["match"] is not None]
    summary = {
        "lines": len(rows), "lines_compared_on_the_same_audio": len(both),
        "text_model_mean_match": round(sum(r["text_model"]["match"] for r in both) / max(1, len(both)), 3),
        "speech_model_mean_match": round(sum(r["speech_model"]["match"] for r in both) / max(1, len(both)), 3),
        "text_model_lowest": min((r["text_model"]["match"] for r in both), default=None),
        "speech_model_lowest": min((r["speech_model"]["match"] for r in both), default=None),
        "sentence_ends_compared": len(gaps),
        "mean_difference_s": round(sum(gaps) / max(1, len(gaps)), 2),
        "largest_difference_s": max(gaps, default=None),
        "ends_more_than_half_a_second_apart": sum(g > 0.5 for g in gaps),
    }
    out = ROOT / "outputs" / "experiments" / "E27" / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "lines": rows}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("\nsummary")
    for key, value in summary.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
