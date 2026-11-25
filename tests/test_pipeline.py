"""Offline tests. No network and no API keys: every model call is answered by the mock providers.

    python -m unittest discover -s tests -v          everything, including a full mock film (about a minute)
    HERITAGE_FAST_TESTS=1 python -m unittest ...     unit tests only
"""
import contextlib
import io
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from pipeline import cli, core, keyframes, music, providers
from pipeline.blindtest import sign_test
from pipeline.narration import similarity

REPO = Path(__file__).resolve().parent.parent


def make_project(folder: Path, small: bool = True) -> Path:
    """A throwaway copy of the project: the contract and the docs, not the outputs."""
    for name in ("schema", "kaggle"):
        shutil.copytree(REPO / name, folder / name)
    for name in ("storyboard.json", "ETHICS.md"):
        shutil.copy2(REPO / name, folder / name)
    if small:  # tiny frames keep the full run fast; the logic is the same
        sb = read_sb(folder)
        sb["format"]["master"] = {"width": 256, "height": 256}
        sb["format"]["exports"] = [{"name": "vertical", "width": 180, "height": 320, "subtitle_margin_v": 40},
                                   {"name": "horizontal", "width": 320, "height": 180, "subtitle_margin_v": 10}]
        write_sb(folder, sb)
    return folder


def read_sb(folder: Path) -> dict:
    return json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))


def write_sb(folder: Path, sb: dict) -> None:
    (folder / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = make_project(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def ctx(self, **kw) -> core.Ctx:
        ctx = core.make_ctx(root=self.root, mock=kw.pop("mock", True), quiet=True, **kw)
        ctx.sleep = lambda seconds: None
        return ctx


class StoryboardTests(Project):
    def test_repo_storyboard_is_valid(self):
        sb, problems = core.load_storyboard(REPO)
        self.assertEqual(len(sb["shots"]), 10)
        self.assertFalse([p for p in problems if p[0] == "error"])

    def test_every_shot_has_a_reason(self):
        for shot in read_sb(REPO)["shots"]:
            self.assertGreaterEqual(len(shot["reason"]), 15, shot["id"])

    def test_missing_reason_is_rejected(self):
        sb = read_sb(self.root)
        del sb["shots"][0]["reason"]
        write_sb(self.root, sb)
        with self.assertRaisesRegex(core.StoryboardError, "reason"):
            core.load_storyboard(self.root)

    def test_unknown_character_is_rejected(self):
        sb = read_sb(self.root)
        sb["shots"][1]["characters"] = ["nobody"]
        write_sb(self.root, sb)
        with self.assertRaisesRegex(core.StoryboardError, "nobody"):
            core.load_storyboard(self.root)

    def test_recorded_consent_needs_a_dated_row_in_ethics(self):
        sb = read_sb(self.root)
        sb["characters"][0]["consent"]["status"] = "recorded"
        write_sb(self.root, sb)
        (self.root / "ETHICS.md").write_text("# Ethics\n\n| ID | Person | Date |\n|---|---|---|\n", encoding="utf-8")
        with self.assertRaisesRegex(core.StoryboardError, "consent-author"):
            core.load_storyboard(self.root)
        with open(self.root / "ETHICS.md", "a", encoding="utf-8") as fh:
            fh.write("| consent-author | the author | 2026-11-25 |\n")
        core.load_storyboard(self.root)  # now accepted

    def test_strict_mode_refuses_drafts_and_pending_consent(self):
        with self.assertRaisesRegex(core.StoryboardError, "DRAFT|pending"):
            core.load_storyboard(self.root, strict=True)

    def test_consent_gate_binds_real_providers_only(self):
        boy = read_sb(self.root)["characters"][0]
        self.assertFalse(keyframes.cleared(self.ctx(mock=False), boy))
        self.assertTrue(keyframes.cleared(self.ctx(mock=True), boy))


class ConsentGateTests(Project):
    def test_real_providers_never_draw_a_person_without_recorded_consent(self):
        """Real mode, with the image and text providers replaced by local fakes, so no network is needed."""
        from unittest import mock

        drawn = []

        def fake_image(ctx, stage, unit, prompt, **kw):
            drawn.append(unit)
            return providers._mock_image(ctx, prompt, kw["width"], kw["height"], kw["seed"], unit), {"seed_applied": True}

        def fake_text(ctx, stage, unit, prompt, **kw):
            return '{"character_match": 4, "prompt_adherence": 4, "artifacts": 4, "text_in_image": false}', {}

        ctx = self.ctx(mock=False)
        with mock.patch.object(providers, "image", fake_image), mock.patch.object(providers, "text", fake_text):
            index = keyframes.run(ctx, {})
        people = {s["id"] for s in ctx.sb["shots"] if s["characters"]}
        self.assertEqual({sid for sid, k in index.items() if k["blocked"]}, people)      # every shot with a person is held back
        self.assertEqual({u.split("_")[0] for u in drawn}, {s["id"] for s in ctx.sb["shots"]} - people)
        self.assertFalse(any(u.startswith("ref_") for u in drawn))                       # no reference sheet of a person either

        sb = read_sb(self.root)                                                          # consent recorded for the author only
        for c in sb["characters"]:
            if c["consent"]["record"] == "consent-author":
                c["consent"]["status"] = "recorded"
        write_sb(self.root, sb)
        with open(self.root / "ETHICS.md", "a", encoding="utf-8") as fh:
            fh.write("\n| consent-author | me | a drawn character | my own statement | 2026-11-25 |\n")
        ctx = self.ctx(mock=False)
        with mock.patch.object(providers, "image", fake_image), mock.patch.object(providers, "text", fake_text):
            index = keyframes.run(ctx, {})
        self.assertEqual({sid for sid, k in index.items() if k["blocked"]}, {"s06"})     # only the shot with the friend is still held
        self.assertIn("ref_boy", drawn)


class CacheTests(Project):
    def unit(self, fingerprint, calls):
        def produce(tmp):
            calls.append(1)
            tmp.write_text("x", encoding="utf-8")
            return {"n": len(calls)}
        return core.Unit("unit_test", "thing", fingerprint, "txt", produce)

    def test_same_inputs_hit_and_changed_inputs_miss_with_a_reason(self):
        ctx, calls = self.ctx(), []
        first = core.run_units(ctx, [self.unit({"text": "a", "voice": "v"}, calls)])["thing"]
        again = core.run_units(ctx, [self.unit({"text": "a", "voice": "v"}, calls)])["thing"]
        changed = core.run_units(ctx, [self.unit({"text": "b", "voice": "v"}, calls)])["thing"]
        back = core.run_units(ctx, [self.unit({"text": "a", "voice": "v"}, calls)])["thing"]
        self.assertEqual((first.hit, again.hit, changed.hit, back.hit), (False, True, False, True))
        self.assertEqual(len(calls), 2)
        self.assertEqual(changed.reason, "changed: text")
        self.assertEqual(again.meta, {"n": 1})

    def test_plan_builds_nothing(self):
        ctx, calls = self.ctx(), []
        res = core.run_units(ctx, [self.unit({"text": "a"}, calls)], plan_only=True)["thing"]
        self.assertEqual((res.hit, res.path, calls), (False, None, []))

    def test_a_failed_build_leaves_no_file_behind(self):
        ctx = self.ctx()

        def produce(tmp):
            tmp.write_text("half", encoding="utf-8")
            raise core.PipelineError("boom")

        with self.assertRaises(core.PipelineError):
            core.run_units(ctx, [core.Unit("unit_test", "thing", {"a": 1}, "txt", produce)])
        self.assertEqual(list((ctx.out / "unit_test").glob("*.txt")), [])


class RunLogTests(Project):
    def test_retries_then_succeeds_and_logs_every_attempt(self):
        ctx, attempts = self.ctx(), []

        def flaky():
            attempts.append(1)
            if len(attempts) < 3:
                raise core.ProviderError("HTTP 429", 429, retryable=True, retry_after=1)
            return "ok", {"audio_bytes": 3}

        out, _ = core.model_call(ctx, stage="narration", unit="s01", provider="mock", model="m", params={"voice": "v"}, seed=None, fn=flaky)
        runs = core.read_jsonl(ctx.runlog)
        self.assertEqual(out, "ok")
        self.assertEqual([r["status"] for r in runs], ["error", "error", "ok"])
        self.assertEqual([r["attempt"] for r in runs], [1, 2, 3])
        for key in ("ts", "run_id", "stage", "unit", "provider", "model", "params", "seed", "latency_s"):
            self.assertIn(key, runs[-1])

    def test_a_rejected_request_is_not_retried(self):
        ctx, attempts = self.ctx(), []

        def rejected():
            attempts.append(1)
            raise core.ProviderError("HTTP 400", 400, retryable=False)

        with self.assertRaises(core.PipelineError):
            core.model_call(ctx, stage="keyframes", unit="s01_c1", provider="mock", model="m", params={}, seed=1, fn=rejected)
        self.assertEqual(len(attempts), 1)

    def test_mock_runs_never_touch_the_real_run_log(self):
        ctx = self.ctx()
        providers.tts(ctx, "narration", "s01", "ሰላም", voice="Charon", style="calm")
        self.assertTrue((ctx.root / "outputs_mock" / "runs.mock.jsonl").exists())
        self.assertFalse((ctx.root / "runs.jsonl").exists())


class TimingTests(unittest.TestCase):
    def test_subtitles_fit_two_lines_of_forty_characters(self):
        for shot in read_sb(REPO)["shots"]:
            if not shot["narration"]:
                continue
            cues = core.subtitle_cues(shot["narration"]["en"], 2.0, 6.0)
            self.assertAlmostEqual(cues[0][0], 2.0)
            self.assertAlmostEqual(cues[-1][1], 8.0, places=2)
            for start, end, lines in cues:
                self.assertLess(start, end)
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(len(line) <= 40 for line in lines), lines)

    def test_picture_follows_the_voice(self):
        sb = read_sb(REPO)
        timeline = core.plan_timeline(sb, {"s01": 9.0})
        first, second = timeline["shots"][0], timeline["shots"][1]
        self.assertAlmostEqual(first["duration"], 0.4 + 9.0 + 0.5, places=1)      # longer than its 7 s minimum
        self.assertEqual(second["duration"], sb["shots"][1]["min_duration_s"])    # no narration: its minimum
        self.assertAlmostEqual(second["start"], first["duration"], places=3)
        self.assertEqual(first["frames"], round(first["duration"] * 24))


class ProviderParsingTests(unittest.TestCase):
    def test_finds_audio_in_the_documented_interactions_response(self):
        response = {"steps": [{"type": "user_input"}, {"type": "model_output", "content": [{"type": "audio", "data": "UklGRg==", "mime_type": "audio/wav"}]}]}
        self.assertEqual(providers._find_audio(response), ("UklGRg==", "audio/wav"))

    def test_finds_audio_in_the_older_inline_data_response(self):
        response = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "audio/L16;rate=24000", "data": "AAAA"}}]}}]}
        self.assertEqual(providers._find_audio(response)[0], "AAAA")

    def test_wav_wrapper_and_private_note(self):
        wav = providers.pcm_to_wav(b"\x00\x00" * 2400, note="ሰላም")
        self.assertTrue(wav.startswith(b"RIFF"))
        self.assertEqual(providers.wav_note(wav), "ሰላም")

    def test_image_type_is_read_from_the_bytes(self):
        self.assertEqual(providers.image_ext(b"\x89PNG\r\n"), "png")
        self.assertEqual(providers.image_ext(b"\xff\xd8\xff"), "jpg")

    def test_listening_score_ignores_punctuation_and_case(self):
        self.assertEqual(similarity("አትፍራ። ብዙ ነገር አለ።", "አትፍራ ብዙ ነገር አለ"), 1.0)
        self.assertLess(similarity("Autobus Tera", "a different thing"), 0.6)


class RequestShapeTests(Project):
    """The real provider code has not met a real model yet. These pin its requests to the documented shapes."""

    KEYS = {"GEMINI_API_KEY": "test-gemini", "CLOUDFLARE_ACCOUNT_ID": "acct123", "CLOUDFLARE_API_TOKEN": "test-cf"}

    class Reply:
        def __init__(self, body=None, content=b"", ctype="application/json"):
            self._body, self.content, self.headers, self.text = body, content, {"content-type": ctype}, json.dumps(body)

        def json(self):
            return self._body

    def capture(self, reply):
        from unittest import mock
        sent = []

        def fake_post(url, headers, json_body=None, files=None, timeout=300):
            sent.append({"url": url, "headers": headers, "json": json_body, "files": files})
            return reply(len(sent)) if callable(reply) else reply

        return sent, mock.patch.object(providers, "_post", fake_post), mock.patch.dict(os.environ, self.KEYS)

    def test_speech_request_follows_the_interactions_api(self):
        import base64
        wav = providers.pcm_to_wav(b"\x01\x00" * 240)
        reply = self.Reply({"steps": [{"type": "model_output", "content": [{"type": "audio", "data": base64.b64encode(wav).decode()}]}]})
        sent, post, env = self.capture(reply)
        with post, env:
            raw, _ = providers.tts(self.ctx(mock=False), "narration", "s01", "ሰላም", voice="Charon", style="calm")
        self.assertEqual(raw, wav)
        req = sent[0]
        self.assertEqual(req["url"], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(req["headers"], {"x-goog-api-key": "test-gemini"})
        self.assertEqual(req["json"], {
            "model": "gemini-3.8-flash-tts",
            "input": [{"type": "user_input", "content": [{"type": "text", "text": "ሰላም", "annotations": [{"type": "speech_metadata", "style": "calm"}]}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": "Charon"}]}})
        logged = core.read_jsonl(self.root / "runs.jsonl")[-1]
        self.assertEqual((logged["provider"], logged["model"], logged["status"]), ("gemini", "gemini-3.8-flash-tts", "ok"))
        self.assertNotIn("test-gemini", json.dumps(logged))                     # the key never reaches the log

    def test_image_request_is_a_multipart_form_with_reference_images(self):
        import base64
        jpeg = b"\xff\xd8\xff\xe0fake"
        sent, post, env = self.capture(self.Reply({"result": {"image": base64.b64encode(jpeg).decode()}, "success": True}))
        with post, env:
            raw, meta = providers.image(self.ctx(mock=False), "keyframes", "s01_c1", "a bag", width=1024, height=1024, seed=7, refs=[b"ref"])
        req = sent[0]
        self.assertEqual(req["url"], "https://api.cloudflare.com/client/v4/accounts/acct123/ai/run/@cf/black-forest-labs/flux-2-klein-4b")
        self.assertEqual(req["headers"], {"Authorization": "Bearer test-cf"})
        self.assertIsNone(req["json"])
        self.assertEqual([name for name, _ in req["files"]], ["prompt", "width", "height", "seed", "input_image_0"])
        self.assertEqual((raw, meta["format"], meta["seed_applied"]), (jpeg, "jpg", True))

    def test_image_request_is_repeated_without_a_seed_when_the_seed_is_rejected(self):
        import base64

        def reply(n):
            if n == 1:
                raise core.ProviderError("HTTP 400. unknown field", 400, False)
            return self.Reply({"result": {"image": base64.b64encode(b"\x89PNG....").decode()}})

        sent, post, env = self.capture(reply)
        with post, env:
            _, meta = providers.image(self.ctx(mock=False), "keyframes", "s01_c1", "a bag", width=1024, height=1024, seed=7)
        self.assertEqual(len(sent), 2)
        self.assertNotIn("seed", [name for name, _ in sent[1]["files"]])
        self.assertEqual((meta["seed_applied"], meta["format"]), (False, "png"))

    def test_judge_request_sends_images_then_the_question_and_asks_for_json(self):
        reply = self.Reply({"candidates": [{"content": {"parts": [{"text": "{\"artifacts\": 4}"}]}}], "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 3}})
        sent, post, env = self.capture(reply)
        with post, env:
            out, meta = providers.text(self.ctx(mock=False), "keyframes", "s01_c1_judge", "Score it.", kind="judge",
                                       parts=[("image/jpeg", b"img")], json_mode=True, temperature=0.0)
        req = sent[0]
        self.assertTrue(req["url"].endswith("/v1beta/models/gemini-3.8-flash:generateContent"))
        parts = req["json"]["contents"][0]["parts"]
        self.assertEqual([list(p)[0] for p in parts], ["inlineData", "text"])
        self.assertEqual(req["json"]["generationConfig"], {"temperature": 0.0, "responseMimeType": "application/json"})
        self.assertEqual((out, meta["usage"]), ('{"artifacts": 4}', {"input_tokens": 9, "output_tokens": 3}))


class SmallToolTests(unittest.TestCase):
    def test_sign_test(self):
        self.assertAlmostEqual(sign_test(5, 5), 0.0625)
        self.assertAlmostEqual(sign_test(3, 6), 1.0)
        self.assertLess(sign_test(10, 10), 0.01)


class IngestTests(Project):
    def test_gpu_results_enter_the_cache_and_the_run_log_once(self):
        sb = read_sb(self.root)
        sb["music"]["chosen"] = 1
        write_sb(self.root, sb)
        ctx = self.ctx()
        before = music.run(ctx, {})
        self.assertEqual(before["source"], "placeholder")   # chosen, but not generated yet
        manifest = json.loads((ctx.out / "music" / "kaggle_job" / "manifest.json").read_text(encoding="utf-8"))
        job = manifest["jobs"][0]
        results = self.root / "results"
        results.mkdir()
        name = f"{job['unit']}__{job['key']}.wav"
        (results / name).write_bytes(providers.pcm_to_wav(b"\x10\x00" * 48000))
        (results / "results.json").write_text(json.dumps({
            "stage": "music", "job_id": "job1", "model": manifest["model"], "gpu": "Tesla T4",
            "results": [{"unit": job["unit"], "key": job["key"], "fingerprint": job["fingerprint"], "seed": job["seed"],
                         "params": {}, "status": "ok", "file": name, "latency_s": 42.0, "peak_mem_gb": 3.1},
                        {"unit": "candidate_2", "key": "x", "fingerprint": {}, "seed": 22, "params": {}, "status": "error",
                         "error": "CUDA out of memory", "latency_s": 5.0}]}), encoding="utf-8")
        self.assertEqual(music.ingest(ctx, results), 1)
        self.assertEqual(music.ingest(ctx, results), 0)     # a second ingest of the same results adds nothing
        runs = [r for r in core.read_jsonl(ctx.runlog) if r["provider"] == "kaggle"]
        self.assertEqual([(r["unit"], r["status"], r["latency_s"]) for r in runs], [("candidate_1", "ok", 42.0), ("candidate_2", "error", 5.0)])
        self.assertEqual(music.run(ctx, {})["source"], "acestep")


@unittest.skipIf(os.environ.get("HERITAGE_FAST_TESTS"), "full mock film skipped")
class EndToEndTests(Project):
    def film(self) -> tuple[set, list]:
        """Run the whole pipeline. Return the units that were rebuilt and the model calls that were made."""
        events_path = self.root / "outputs_mock" / "logs" / "events.jsonl"
        log_path = self.root / "outputs_mock" / "runs.mock.jsonl"
        seen_events, seen_runs = len(core.read_jsonl(events_path)), len(core.read_jsonl(log_path))
        with contextlib.redirect_stdout(io.StringIO()):   # the run prints a line per unit: keep the test output readable
            code = cli.main(["film", "--mock", "--root", str(self.root)])
        self.assertEqual(code, 0)
        built = {e["unit"] for e in core.read_jsonl(events_path)[seen_events:] if e["event"] == "built"}
        return built, core.read_jsonl(log_path)[seen_runs:]

    def test_one_command_makes_the_film_and_only_changed_shots_regenerate(self):
        built, calls = self.film()
        out = self.root / "outputs_mock"
        report = json.loads((out / "qc_report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"], [c for c in report["checks"] if not c["ok"]])
        self.assertTrue(60 <= report["total_s"] <= 90)
        for name in ("film_vertical.mp4", "film_horizontal.mp4", "subtitles.en.srt"):
            self.assertTrue((out / name).exists(), name)
        self.assertTrue(all(c["provider"] == "mock" for c in calls))
        self.assertFalse((self.root / "runs.jsonl").exists())

        built, calls = self.film()                                   # nothing changed
        self.assertEqual((built, calls), (set(), []))

        sb = read_sb(self.root)                                      # one narration line changed
        sb["shots"][3]["narration"]["am"] += " በጣም።"
        write_sb(self.root, sb)
        built, calls = self.film()
        self.assertEqual(sorted(c["unit"] for c in calls), ["s04", "s04_listen"])
        self.assertEqual(built, {"s04", "s04_listen", "mix", "vertical_s04", "horizontal_s04", "film_vertical", "film_horizontal"})

        sb["shots"][6]["keyframe"]["prompt"] += " A wooden chair in the corner."   # one keyframe prompt changed
        write_sb(self.root, sb)
        built, calls = self.film()
        self.assertEqual(sorted(c["unit"] for c in calls), ["s07_c1", "s07_c1_judge", "s07_c2", "s07_c2_judge"])
        self.assertEqual(built, {"s07_c1", "s07_c2", "s07_c1_judge", "s07_c2_judge", "s07_kenburns",
                                 "vertical_s07", "horizontal_s07", "film_vertical", "film_horizontal"})

    def test_radio_cut(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["radio", "--mock", "--root", str(self.root)])
        self.assertEqual(code, 0)
        info = core.media_info(self.root / "outputs_mock" / "radio_cut.mp4")
        self.assertEqual(info["acodec"], "aac")
        self.assertTrue(60 <= info["duration"] <= 90)


if __name__ == "__main__":
    unittest.main()
