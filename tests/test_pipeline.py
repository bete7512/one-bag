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

from pipeline import assemble, cli, core, keyframes, music, pricing, providers
from pipeline.blindtest import sign_test
from pipeline.narration import similarity

REPO = Path(__file__).resolve().parent.parent

ETHICS_DRAFT = """# Ethics (test copy: no consent is recorded)

| ID | Person | What appears in the film | How consent was given | Date (YYYY-MM-DD) |
|---|---|---|---|---|
| consent-author | The author | A drawn character | | |
| consent-friend | The friend | A drawn character | | |
"""


def make_project(folder: Path, small: bool = True) -> Path:
    """A throwaway copy of the project, set back to a first draft.

    The tests describe how the pipeline behaves, so they must give the same answer whether the real
    film is a draft or ready for release. The copy keeps the real shots, and goes back to: nobody's
    consent recorded, the audience still marked DRAFT, no score chosen, the voice spoken in one take
    with its pauses as they come, and no picture picked by hand or drawn without its reference.
    """
    for name in ("schema", "kaggle"):
        shutil.copytree(REPO / name, folder / name)
    for name in ("storyboard.json", "pricing.json"):
        shutil.copy2(REPO / name, folder / name)
    (folder / "ETHICS.md").write_text(ETHICS_DRAFT, encoding="utf-8")
    sb = read_sb(folder)
    sb["audience"] = "DRAFT, a test audience."
    sb["music"]["chosen"] = None
    sb["music"].pop("chosen_reason", None)
    sb["voice"] = {"name": sb["voice"]["name"], "style": sb["voice"]["style"]}
    for shot in sb["shots"]:
        for choice in ("pick", "reference"):
            shot["keyframe"].pop(choice, None)
    for character in sb["characters"]:
        if character["real_person"]:
            character["consent"]["status"] = "pending"
    if small:  # tiny frames keep the full run fast; the logic is the same
        sb["format"]["master"] = {"width": 256, "height": 256}
        sb["format"]["exports"] = [{"name": "vertical", "width": 180, "height": 320, "subtitle_margin_v": 40},
                                   {"name": "horizontal", "width": 320, "height": 180, "subtitle_margin_v": 10}]
    write_sb(folder, sb)
    return folder


@contextlib.contextmanager
def mock_now(stamp: str):
    """Freeze the time stamp that job folders are given."""
    from unittest import mock
    with mock.patch("pipeline.kagglejob.now", lambda: stamp):
        yield


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
        self.assertTrue(8 <= len(sb["shots"]) <= 12, len(sb["shots"]))   # what the brief asks for
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

    def test_a_crop_anchor_is_a_number_or_one_number_per_export(self):
        valid = read_sb(self.root)

        def load(axis: str, value) -> None:
            sb = json.loads(json.dumps(valid))                                       # every try starts from the valid storyboard
            sb["shots"][0]["keyframe"][axis] = value
            write_sb(self.root, sb)
            core.load_storyboard(self.root)

        for axis in ("focus_x", "focus_y"):
            for value in (0.3, 0, 1, {"vertical": 0.3}, {"vertical": 0.3, "horizontal": 0.5}):
                load(axis, value)                                                    # one number, or one per export: accepted
            for value in ("left", 1.2, -0.1, None, {"vertical": 1.2}, {"vertical": "left"}, {}):
                with self.assertRaisesRegex(core.StoryboardError, f"keyframe/{axis}", msg=value):   # a word, or a place outside the picture
                    load(axis, value)

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
        others = set()
        for c in sb["characters"]:
            if c["consent"].get("record") == "consent-author":
                c["consent"]["status"] = "recorded"
            elif c["real_person"]:
                others.add(c["id"])
        write_sb(self.root, sb)
        with open(self.root / "ETHICS.md", "a", encoding="utf-8") as fh:
            fh.write("\n| consent-author | me | a drawn character | my own statement | 2026-11-25 |\n")
        ctx = self.ctx(mock=False)
        with mock.patch.object(providers, "image", fake_image), mock.patch.object(providers, "text", fake_text):
            index = keyframes.run(ctx, {})
        still_held = {s["id"] for s in sb["shots"] if others & set(s["characters"])}     # only shots with someone else in them
        self.assertEqual({sid for sid, k in index.items() if k["blocked"]}, still_held)
        sheets = {f"ref_{c['id']}" for c in sb["characters"] if c.get("reference_prompt") and c["consent"]["status"] == "recorded"}
        self.assertTrue(sheets and sheets <= set(drawn), sheets)                         # the author's reference sheet is drawn now


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
        for key in ("ts", "run_id", "stage", "unit", "provider", "model", "params", "seed", "latency_s", "cost_usd"):
            self.assertIn(key, runs[-1])                                        # what the brief asks of every line

    def test_a_rejected_request_is_not_retried(self):
        ctx, attempts = self.ctx(), []

        def rejected():
            attempts.append(1)
            raise core.ProviderError("HTTP 400", 400, retryable=False)

        with self.assertRaises(core.PipelineError):
            core.model_call(ctx, stage="keyframes", unit="s01_c1", provider="mock", model="m", params={}, seed=1, fn=rejected)
        self.assertEqual(len(attempts), 1)

    def test_waits_between_attempts_are_long_enough_for_a_busy_model(self):
        ctx, waits = self.ctx(), []
        ctx.sleep = waits.append

        def busy():
            raise core.ProviderError("HTTP 503", 503, retryable=True)

        with self.assertRaises(core.PipelineError):
            core.model_call(ctx, stage="keyframes", unit="s05_c1_judge", provider="mock", model="m", params={}, seed=None, fn=busy)
        self.assertEqual(waits, [10.0, 30.0, 90.0])
        self.assertEqual(len(core.read_jsonl(ctx.runlog)), 4)

    def test_mock_runs_never_touch_the_real_run_log(self):
        ctx = self.ctx()
        providers.tts(ctx, "narration", "s01", "ሰላም", voice="Charon", style="calm")
        self.assertTrue((ctx.root / "outputs_mock" / "runs.mock.jsonl").exists())
        self.assertFalse((ctx.root / "runs.jsonl").exists())


class TimingTests(unittest.TestCase):
    def test_a_subtitle_changes_where_the_voice_pauses(self):
        text = "It was night when I reached Lamberet. My friend was waiting for me. So many people, lights on the buildings, so many cars."
        by_length = core.subtitle_cues(text, 10.0, 9.0)
        self.assertEqual(len(by_length), 2)
        self.assertAlmostEqual(by_length[0][1], 15.02, places=1)                     # shared out by length alone
        # the voice stops for a breath at 2.0 s, for a full second after the second sentence at 4.2 s, and for a breath at 7.0 s
        timed = core.subtitle_cues(text, 10.0, 9.0, pauses=[[2.0, 2.3], [4.2, 5.2], [7.0, 7.3]])
        self.assertEqual([lines for _, _, lines in timed], [lines for _, _, lines in by_length])
        self.assertAlmostEqual(timed[0][1], 15.12, places=2)                         # the cue changes as the long pause ends
        self.assertEqual((timed[0][0], timed[-1][1], timed[1][0]), (10.0, 19.0, timed[0][1]))

    def test_the_last_words_of_a_line_stay_up_after_the_voice_stops(self):
        from pipeline import assemble
        cues = [(0.4, 5.6, ["If I met that boy today, I would tell", "him just one thing:"]), (5.6, 6.4, ["experience it."])]
        self.assertEqual(assemble.hold_last(list(cues), 9.7)[-1], (5.6, 8.9, ["experience it."]))   # 2.5 s more, the shot lasts that long
        self.assertEqual(assemble.hold_last(list(cues), 7.0)[-1], (5.6, 7.0, ["experience it."]))   # never past the end of its shot
        self.assertEqual(assemble.hold_last(list(cues), 6.0)[-1], (5.6, 6.4, ["experience it."]))   # and never shorter than the voice
        self.assertEqual(assemble.hold_last([], 5.0), [])

    def test_the_wide_film_keeps_the_part_of_the_picture_the_shot_points_at(self):
        from pipeline import assemble
        middle, mode = assemble.fit_graph(1024, 1024, 1920, 1080)
        head, _ = assemble.fit_graph(1024, 1024, 1920, 1080, focus_y=0.15)
        self.assertEqual(mode, "crop")
        self.assertIn("crop=1920:1080:(iw-1920)*0.500:(ih-1080)*0.500", middle)      # the middle band, as before
        self.assertIn("crop=1920:1080:(iw-1920)*0.500:(ih-1080)*0.150", head)        # higher up, where a standing figure has its head
        tall, _ = assemble.fit_graph(1024, 1024, 1080, 1920, focus_y=0.15)
        self.assertIn("crop=1080:1920:(iw-1080)*0.500:", tall)                       # the tall film loses width only, so nothing moves

    def test_the_tall_film_keeps_the_side_of_the_picture_the_shot_points_at(self):
        middle, mode = assemble.fit_graph(1024, 1024, 1080, 1920)
        left, _ = assemble.fit_graph(1024, 1024, 1080, 1920, focus_x=0.3)
        self.assertEqual(mode, "crop")
        self.assertIn("crop=1080:1920:(iw-1080)*0.500:(ih-1920)*0.500", middle)      # the middle band of the width, as before
        self.assertIn("crop=1080:1920:(iw-1080)*0.300:(ih-1920)*0.500", left)        # further left, where the brokers stand
        edge, _ = assemble.fit_graph(1024, 1024, 1080, 1920, focus_x=1.4, focus_y=-2)
        self.assertIn("crop=1080:1920:(iw-1080)*1.000:(ih-1920)*0.000", edge)        # an anchor never pushes the crop off the picture
        bars, mode = assemble.fit_graph(1920, 1080, 1080, 1920, focus_x=0.3)         # a wide clip in the tall film would lose 68% of itself
        self.assertEqual(mode, "blur_fill")                                          # so it still sits whole over a blurred copy
        self.assertIn("overlay=(W-w)/2:(H-h)/2", bars)

    def kept(self, width: int, height: int, **focus: float) -> tuple[float, float]:
        """Fit a square picture to an export. Return where the middle of what is left sat in the picture, as (x, y) from 0 to 1.

        The picture gets redder from left to right and greener from top to bottom, so the mean colour of a crop says where it was cut.
        """
        graph, mode = assemble.fit_graph(256, 256, width, height, **focus)
        self.assertEqual(mode, "crop")
        with tempfile.TemporaryDirectory() as folder:
            picture, cut = Path(folder) / "picture.rgb", Path(folder) / "cut.rgb"
            picture.write_bytes(bytes(value for y in range(256) for x in range(256) for value in (x, y, 0)))
            core.ff(["-f", "rawvideo", "-pix_fmt", "rgb24", "-s", "256x256", "-i", str(picture), "-vf", graph,
                     "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", str(cut)])
            px = cut.read_bytes()
        self.assertEqual(len(px), 3 * width * height)                                # exactly the size of the export
        return sum(px[0::3]) / (255 * width * height), sum(px[1::3]) / (255 * width * height)

    def test_each_export_follows_the_anchor_for_the_side_it_cuts(self):
        tall, wide = (180, 320), (320, 180)                                          # the two exports, small. Each keeps 56% of the square

        def keeps(size: tuple, x: float, y: float, **focus: float) -> None:
            got = self.kept(*size, **focus)
            self.assertTrue(abs(got[0] - x) < 0.01 and abs(got[1] - y) < 0.01, (size, focus, got))

        keeps(tall, 0.5, 0.5)                                                        # nothing said: the middle, in both directions
        keeps(wide, 0.5, 0.5)
        keeps(tall, 0.28, 0.5, focus_x=0.0)                                          # the tall film moves sideways with focus_x: its left 56%
        keeps(tall, 0.72, 0.5, focus_x=1.0)                                          # and its right 56%
        keeps(wide, 0.5, 0.5, focus_x=0.0)                                           # the wide film keeps the whole width, so focus_x moves nothing
        keeps(wide, 0.5, 0.28, focus_y=0.0)                                          # it moves up and down with focus_y
        keeps(tall, 0.5, 0.5, focus_y=0.0)                                           # which in turn moves nothing in the tall film
        keeps(tall, 0.41, 0.5, focus_x=0.3, focus_y=0.9)                             # both given: each export takes the one that concerns it
        keeps(wide, 0.5, 0.68, focus_x=0.3, focus_y=0.9)

    def test_a_shot_can_point_each_export_at_another_part_of_the_picture(self):
        both = ("vertical", "horizontal")
        self.assertEqual([assemble.focus_of({}, name) for name in both], [(0.5, 0.5), (0.5, 0.5)])          # nothing said: the middle
        number = {"prompt": "A room.", "seed": 1, "focus_x": 0.3, "focus_y": 0.15}
        self.assertEqual([assemble.focus_of(number, name) for name in both], [(0.3, 0.15), (0.3, 0.15)])    # a number is for every export
        each = {"focus_x": {"vertical": 0.3}, "focus_y": {"vertical": 0.4, "horizontal": 0.15}}
        self.assertEqual(assemble.focus_of(each, "vertical"), (0.3, 0.4))                                   # an object says it per export
        self.assertEqual(assemble.focus_of(each, "horizontal"), (0.5, 0.15))                                # one it does not name keeps the middle
        mixed = {"focus_x": {"vertical": 0.0, "horizontal": 1}, "focus_y": 0.15}                            # one of each kind, and 0 is an anchor, not a gap
        self.assertEqual([assemble.focus_of(mixed, name) for name in both], [(0.0, 0.15), (1, 0.15)])

    def test_what_follows_a_colon_waits_for_its_own_cue(self):
        cues = core.subtitle_cues("If I met that boy today, I would tell him just one thing: experience it.", 0.0, 6.0, pauses=[[1.9, 2.4], [4.3, 5.3]])
        self.assertEqual(cues[-1][2], ["experience it."])                            # the last word is not shown before it is said
        self.assertAlmostEqual(cues[-1][0], 5.22, places=2)

    def test_subtitles_fit_two_lines_of_forty_characters(self):
        sb = read_sb(REPO)
        for shot in sb["shots"]:
            subtitle = (shot["narration"] or {}).get(sb["language"]["subtitles"])
            if not subtitle:
                continue
            cues = core.subtitle_cues(subtitle, 2.0, 6.0)
            self.assertAlmostEqual(cues[0][0], 2.0)
            self.assertAlmostEqual(cues[-1][1], 8.0, places=2)
            for start, end, lines in cues:
                self.assertLess(start, end)
                self.assertLessEqual(len(lines), 2)
                self.assertTrue(all(len(line) <= 40 for line in lines), lines)

    def test_picture_follows_the_voice(self):
        sb = read_sb(REPO)
        fmt, spoken = sb["format"], sb["shots"][0]["min_duration_s"] + 2.0        # a line longer than the shot's minimum
        timeline = core.plan_timeline(sb, {sb["shots"][0]["id"]: spoken})
        first, second = timeline["shots"][0], timeline["shots"][1]
        self.assertAlmostEqual(first["duration"], fmt["lead_in_s"] + spoken + fmt["tail_s"], places=1)   # the voice sets the length
        self.assertEqual(second["duration"], sb["shots"][1]["min_duration_s"])    # nothing spoken yet: its minimum
        self.assertAlmostEqual(second["start"], first["duration"], places=3)
        self.assertEqual(first["frames"], round(first["duration"] * fmt["fps"]))


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
        speech_model = read_sb(self.root)["models"]["tts"]
        with post, env:
            raw, _ = providers.tts(self.ctx(mock=False), "narration", "s01", "ሰላም", voice="Charon", style="calm")
        self.assertEqual(raw, wav)
        req = sent[0]
        self.assertEqual(req["url"], "https://generativelanguage.googleapis.com/v1beta/interactions")
        self.assertEqual(req["headers"], {"x-goog-api-key": "test-gemini"})
        self.assertEqual(req["json"], {
            "model": speech_model,
            "input": [{"type": "user_input", "content": [{"type": "text", "text": "ሰላም", "annotations": [{"type": "speech_metadata", "style": "calm"}]}]}],
            "response_format": {"type": "audio"},
            "generation_config": {"speech_config": [{"voice": "Charon"}]}})
        logged = core.read_jsonl(self.root / "runs.jsonl")[-1]
        self.assertEqual((logged["provider"], logged["model"], logged["status"]), ("gemini", speech_model, "ok"))
        self.assertEqual(logged["audio_seconds"], 0.01)                         # speech is priced by the second
        self.assertGreater(logged["cost_usd"], 0)
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
        self.assertTrue(req["url"].endswith(f"/v1beta/models/{read_sb(self.root)['models']['text']}:generateContent"))
        parts = req["json"]["contents"][0]["parts"]
        self.assertEqual([list(p)[0] for p in parts], ["inlineData", "text"])
        self.assertEqual(req["json"]["generationConfig"], {"temperature": 0.0, "responseMimeType": "application/json"})
        self.assertEqual((out, meta["usage"]), ('{"artifacts": 4}', {"input_tokens": 9, "output_tokens": 3, "thoughts_tokens": None}))


class ChecksThatOnlyMeasureTests(Project):
    """The picture judge and the listening check measure. A model that cannot be reached must not cost the film."""

    def busy(self, units: set):
        """The text provider, except that it fails for the named units the way a busy model does."""
        from unittest import mock
        answer = providers.text

        def text(ctx, stage, unit, prompt, **kw):
            if unit in units:
                raise core.PipelineError(f"gemini call for {unit} failed: HTTP 503")
            return answer(ctx, stage, unit, prompt, **kw)

        return mock.patch.object(providers, "text", text)

    def test_an_optional_unit_that_fails_does_not_stop_the_run(self):
        def broken(tmp):
            raise core.PipelineError("the model is busy")

        ctx = self.ctx()
        units = [core.Unit("unit_test", "check", {"a": 1}, "json", broken, optional=True),
                 core.Unit("unit_test", "thing", {"a": 1}, "txt", lambda tmp: tmp.write_text("x", encoding="utf-8") and None)]
        results = core.run_units(ctx, units)
        self.assertEqual((results["check"].path, results["check"].failed), (None, "the model is busy"))
        self.assertTrue(results["thing"].path.exists())
        self.assertEqual(list((ctx.out / "unit_test").glob("check__*")), [])     # nothing cached: the next run tries again

    def test_keyframes_are_made_when_the_judge_cannot_be_reached(self):
        sb = read_sb(self.root)
        sb["qa"].update(keyframe_candidates=2, judge=True)
        first = sb["shots"][0]
        first["keyframe"] = {k: v for k, v in first["keyframe"].items() if k not in ("pick", "candidates")}
        write_sb(self.root, sb)
        sid = first["id"]
        with self.busy({f"{sid}_c2_judge"}):
            index = keyframes.run(self.ctx(), {})
        self.assertEqual((index[sid]["candidate"], index[sid]["picked_by"], index[sid]["unscored"]),
                         (1, "first full-frame candidate (judge incomplete)", [2]))
        self.assertTrue(index[sid]["file"])                                     # the picture is there all the same
        index = keyframes.run(self.ctx(), {})                                   # the model answers again
        self.assertEqual((index[sid]["picked_by"], index[sid]["unscored"]), ("judge", []))

    def test_lines_are_spoken_when_the_listening_check_cannot_be_reached(self):
        from pipeline import narration, script
        ctx, state = self.ctx(), {}
        script.run(ctx, state)
        sid = next(iter(state["script"]["lines"]))
        with self.busy({f"{sid}_listen"}):
            index = narration.run(ctx, state)
        self.assertTrue(index[sid]["file"])
        self.assertNotIn("roundtrip", index[sid])
        self.assertTrue(all("roundtrip" in line for other, line in index.items() if other != sid))


class SubtitleCheckTests(Project):
    """The film is graded on accurate subtitles, and the people who read them cannot hear whether they are."""

    def test_a_subtitle_that_differs_from_its_line_is_reported_and_stops_nothing(self):
        from unittest import mock
        from pipeline import script
        answer = providers.text
        sid = next(s["id"] for s in read_sb(self.root)["shots"] if s["narration"])

        def strict(ctx, stage, unit, prompt, **kw):
            if unit == f"{sid}_subtitle_check":
                return json.dumps({"literal": "He knows the city.", "faithful": False, "differences": ["tense: knows, not knew"]}), {}
            return answer(ctx, stage, unit, prompt, **kw)

        with mock.patch.object(providers, "text", strict):
            index = script.run(self.ctx(), {})
        self.assertEqual(index["lines"][sid]["subtitle_check"], {"faithful": False, "literal": "He knows the city.", "differences": ["tense: knows, not knew"]})
        others = [line["subtitle_check"]["faithful"] for other, line in index["lines"].items() if other != sid]
        self.assertTrue(others and all(others))

    def test_the_check_can_be_switched_off_and_cannot_stop_the_stage(self):
        from unittest import mock
        from pipeline import script

        def unreachable(ctx, stage, unit, prompt, **kw):
            raise core.PipelineError("the model is busy")

        with mock.patch.object(providers, "text", unreachable):
            index = script.run(self.ctx(), {})                       # every check fails: the lines are still settled
        self.assertTrue(all("subtitle_check" not in line and line["subtitle"] for line in index["lines"].values()))
        sb = read_sb(self.root)
        sb["qa"]["subtitle_check"] = False
        write_sb(self.root, sb)
        ctx = self.ctx()
        script.run(ctx, {})
        self.assertEqual([r for r in core.read_jsonl(ctx.runlog) if r["unit"].endswith("_subtitle_check")], [])


class TakeTests(Project):
    """The free speech tier counts requests, not lines: the lines missing from the cache are spoken in one request."""

    def narrate(self, ctx=None) -> tuple[dict, list]:
        from pipeline import narration, script
        ctx, state = ctx or self.ctx(), {}
        before = len(core.read_jsonl(ctx.runlog))
        script.run(ctx, state)
        index = narration.run(ctx, state)
        speech = [r for r in core.read_jsonl(ctx.runlog)[before:] if r["model"] == ctx.sb["models"]["tts"]]
        return index, speech

    def test_all_lines_cost_one_request_and_one_changed_line_costs_one(self):
        index, speech = self.narrate()
        self.assertEqual([(r["unit"], r["params"]["lines"]) for r in speech], [("take", len(index))])
        self.assertTrue(all(line["file"] and line["seconds"] > 0.5 and line["roundtrip"] == 1.0 for line in index.values()), index)
        takes = sorted((self.root / "outputs_mock" / "narration" / "takes").glob("*"))
        self.assertEqual([p.suffix for p in takes], [".json", ".wav"])               # the model's answer is kept as it came

        _, speech = self.narrate()
        self.assertEqual(speech, [])                                                 # nothing changed: nothing is spoken

        sb = read_sb(self.root)
        changed = next(s for s in sb["shots"] if s["narration"])
        changed["narration"][sb["language"]["narration"]] += " በጣም።"
        write_sb(self.root, sb)
        _, speech = self.narrate()
        self.assertEqual([r["unit"] for r in speech], [changed["id"]])               # that line alone, in a request of its own

    def test_a_take_is_cut_at_its_longest_pauses(self):
        from pipeline import narration
        take = self.root / "take.wav"   # three lines of 1.0, 2.0 and 1.5 s. The second has a short breath inside it.
        parts = ["sine=f=300:d=1.0", "anullsrc=d=1.2", "sine=f=300:d=0.8", "anullsrc=d=0.4", "sine=f=300:d=0.8", "anullsrc=d=1.2", "sine=f=300:d=1.5"]
        inputs = [arg for part in parts for arg in ("-f", "lavfi", "-i", part + (":r=24000" if part.startswith("sine") else ":r=24000:cl=mono"))]
        core.ff([*inputs, "-filter_complex", "".join(f"[{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1", "-ar", "24000", str(take)])
        spans, margin = narration.speech_spans(take, 3)
        self.assertEqual([round(b - a, 1) for a, b in spans], [1.2, 2.3, 1.6])       # each line with its small pads, the breath left inside
        self.assertEqual(margin, 3.0)                                                # the cuts are three times longer than that breath
        with self.assertRaisesRegex(core.PipelineError, "cannot be cut"):
            narration.speech_spans(take, 5)

    def test_a_cut_that_would_be_a_guess_is_not_made(self):
        from unittest import mock
        from pipeline import narration

        def no_long_pauses(ctx, stage, unit, texts, **kw):  # the pause after a line is no longer than the pauses inside it
            gap = b"\x00\x00" * int(0.4 * 24000)
            tone = providers._mock_speech("ሰላም ለሁላችሁ ይሁን።")
            return [providers.pcm_to_wav(gap.join([tone] * (2 * len(texts))))], {"audio_blocks": 1}

        ctx = self.ctx()
        with mock.patch.object(providers, "tts_take", no_long_pauses):
            pieces = narration.take(ctx, {"s01": "ሰላም ለሁላችሁ ይሁን። ሰላም ለሁላችሁ ይሁን።", "s03": "ደህና ሁኑ ወዳጆቼ። ደህና ሁኑ ወዳጆቼ።"}, ctx.sb["voice"], "mock-tts")
        self.assertEqual(pieces, {})                                                          # neither the pauses nor the words say where a line is
        self.assertEqual(len(list((ctx.out / "narration" / "takes").glob("*.wav"))), 1)       # the take is kept for a second look
        self.assertEqual(list((ctx.out / "narration").glob("s0*.wav")), [])                   # and no line entered the cache
        with mock.patch.object(providers, "tts_take", no_long_pauses):
            index, speech = self.narrate(ctx)
        self.assertEqual([r["unit"] for r in speech], list(index))                            # each line is then spoken alone, nothing is guessed
        self.assertTrue(all(line["roundtrip"] == 1.0 for line in index.values()), index)

    def test_a_line_is_kept_from_a_take_only_where_pauses_and_words_agree(self):
        from unittest import mock
        from pipeline import narration
        calls = []

        def uneven_pauses(ctx, stage, unit, texts, **kw):
            # five phrases. The words say: line 1 is phrases 1 and 2, line 2 is phrase 3, line 3 is phrases 4 and 5.
            # The pause inside line 3 (0.8 s) is longer than the pause before it (0.6 s), so the pauses alone would cut line 3 in two.
            tone = providers._mock_speech("ሰላም ለሁላችሁ ይሁን።")
            gaps = [b"\x00\x00" * int(seconds * 24000) for seconds in (0.4, 1.0, 0.6, 0.8)]
            return [providers.pcm_to_wav(b"".join(part for pair in zip([tone] * 4, gaps) for part in pair) + tone)], {"audio_blocks": 1}

        def listener(ctx, wav, found, stage, unit, lang=None):
            calls.append(len(found))
            return ["ሰላም ለሁላችሁ", "ይሁን ዛሬ", "እንኳን ደህና መጣችሁ", "ደህና ሁኑ", "ወዳጆቼ ሁሉ"]

        ctx = self.ctx()
        lines = {"s01": "ሰላም ለሁላችሁ ይሁን ዛሬ።", "s03": "እንኳን ደህና መጣችሁ።", "s04": "ደህና ሁኑ ወዳጆቼ ሁሉ።"}
        with mock.patch.object(providers, "tts_take", uneven_pauses), mock.patch.object(narration, "hear_phrases", listener):
            pieces = narration.take(ctx, lines, ctx.sb["voice"], "mock-tts")
            narration.take(ctx, lines, ctx.sb["voice"], "mock-tts")
        self.assertEqual(calls, [5])                                                  # what was heard is kept: the second cut asks nobody
        self.assertEqual(list(pieces), ["s01"])                                       # the one line both methods place the same
        record = json.loads(next((ctx.out / "narration" / "takes").glob("*.json")).read_text(encoding="utf-8"))
        self.assertEqual((record["cut_from_take"], record["word_match"]), (["s01"], {"s01": 1.0, "s03": 1.0, "s04": 1.0}))
        self.assertLess(record["cut_margin"], narration.MIN_CUT_MARGIN)

    def test_long_silences_inside_a_line_are_shortened_and_the_words_are_kept(self):
        from pipeline import narration
        line = self.root / "line.wav"   # three phrases of 1 s: a long silence of 1.2 s after the first, a breath of 0.3 s after the second
        parts = ["sine=f=300:d=1.0", "anullsrc=d=1.2", "sine=f=300:d=1.0", "anullsrc=d=0.3", "sine=f=300:d=1.0"]
        inputs = [arg for part in parts for arg in ("-f", "lavfi", "-i", part + (":r=24000" if part.startswith("sine") else ":r=24000:cl=mono"))]
        core.ff([*inputs, "-filter_complex", "".join(f"[{i}:a]" for i in range(len(parts))) + f"concat=n={len(parts)}:v=0:a=1", "-ar", "24000", str(line)])
        out = self.root / "tight.wav"
        done = narration.tighten(line, out, 0.6)
        self.assertEqual((done["shortened"], round(done["removed_s"], 1)), (1, 0.6))        # only the long silence, cut down to the limit
        self.assertAlmostEqual(core.wav_seconds(out), 3.9, places=1)
        self.assertEqual([round(b - a, 1) for a, b in narration.pauses(out)[0]], [0.6, 0.3])  # the breath is left as it was
        same = self.root / "same.wav"
        self.assertEqual(narration.tighten(out, same, 0.6)["shortened"], 0)                 # nothing left to shorten: the file is copied
        self.assertEqual(same.read_bytes(), out.read_bytes())

    def test_the_film_uses_the_shortened_line_when_the_storyboard_sets_a_limit(self):
        sb = read_sb(self.root)
        sb["voice"]["max_pause_s"] = 0.6
        write_sb(self.root, sb)
        index, speech = self.narrate()
        self.assertTrue(all("_tight__" in line["file"] and line["as_spoken"] and line["roundtrip"] == 1.0 for line in index.values()), index)
        self.assertEqual(len(speech), 1)                                                     # one take, as before: shortening asks no model
        sb["voice"]["max_pause_s"] = 0.4
        write_sb(self.root, sb)
        _, speech = self.narrate()
        self.assertEqual(speech, [])                                                         # another limit is cut from the kept audio

    def test_each_line_is_spoken_alone_when_the_storyboard_says_so(self):
        sb = read_sb(self.root)
        sb["voice"]["one_take"] = False
        write_sb(self.root, sb)
        index, speech = self.narrate()
        self.assertEqual([r["unit"] for r in speech], list(index))                         # one request a line, and no take to cut
        self.assertFalse((self.root / "outputs_mock" / "narration" / "takes").exists())
        self.assertTrue(all(line["roundtrip"] == 1.0 for line in index.values()), index)

    def test_phrases_go_to_the_line_they_sound_like(self):
        from pipeline import narration
        lines = ["ክፍሉ ባለ አንድ አልጋ ነበር። ንጹሕ ነበር።", "ጠዋት ትኬት ቆረጥን።", "ኑረው።"]
        heard = ["ክፍሉ ባለ አንድ", "አልጋ ነበረ", "ንጹህ ነበር", "ጠዋት", "ትኬት ቆረጥን", "ኑረው"]              # heard with small mistakes, as a listener does
        self.assertEqual(narration.assign(heard, lines), [3, 2, 1])
        self.assertEqual(narration.assign(["ሀ", "ለ", "ሐ"], ["ሀ", "ለ", "ሐ"]), [1, 1, 1])
        with self.assertRaisesRegex(core.PipelineError, "cannot be matched"):
            narration.assign(["ሀ"], ["ሀ", "ለ"])

    def test_the_listening_check_follows_the_sound_not_the_line(self):
        index, _ = self.narrate()
        sid = next(iter(index))
        ctx = self.ctx()
        wav = ctx.out / "narration" / index[sid]["file"]
        wav.write_bytes(providers.pcm_to_wav(providers._mock_speech("ሌላ ድምፅ"), note="ሌላ ድምፅ"))   # the same line, cut differently
        before = len(core.read_jsonl(ctx.runlog))
        index, _ = self.narrate()
        self.assertEqual([r["unit"] for r in core.read_jsonl(ctx.runlog)[before:]], [f"{sid}_listen"])   # heard again, and only that one
        self.assertLess(index[sid]["roundtrip"], 1.0)

    def test_one_audio_per_line_needs_no_cutting(self):
        from unittest import mock
        from pipeline import narration

        def one_per_line(ctx, stage, unit, texts, **kw):
            return [providers.pcm_to_wav(providers._mock_speech(text) + b"\x00\x00" * 24000) for text in texts], {"audio_blocks": len(texts)}

        ctx = self.ctx()
        with mock.patch.object(providers, "tts_take", one_per_line):
            pieces = narration.take(ctx, {"s01": "ሰላም ለሁላችሁ ይሁን።", "s03": "እንደምን አደራችሁ።"}, ctx.sb["voice"], "speech-model")
        self.assertEqual(sorted(pieces), ["s01", "s03"])
        self.assertTrue(all(1.0 <= core.wav_seconds(path) < 3.6 for path in pieces.values()))   # the second of silence at the end is trimmed


class LanguageTestTests(Project):
    def test_each_language_costs_one_speech_request(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(cli.main(["langtest", "--mock", "--root", str(self.root), "--langs", "am,ti"]), 0)
        sb = read_sb(self.root)
        log = core.read_jsonl(self.root / "outputs_mock" / "runs.mock.jsonl")
        speech = [(r["unit"], r["params"]["lines"]) for r in log if r["model"] == sb["models"]["tts"]]
        self.assertEqual(speech, [("am_take", 4), ("ti_take", 4)])                # eight lines, two requests
        rows = json.loads((self.root / "outputs_mock" / "langtest" / "results.json").read_text(encoding="utf-8"))
        self.assertEqual((len(rows), sum(r["score"] is not None for r in rows), [r for r in rows if r["error"]]), (8, 8, []))
        self.assertEqual({r["origin"] for r in rows if r["lang"] == "am"}, {"written by a person"})
        takes = json.loads((self.root / "outputs_mock" / "langtest" / "takes.json").read_text(encoding="utf-8"))
        self.assertEqual({lang: (t["lines_cut"], t["seconds"] > 4, t["score"] is not None) for lang, t in takes.items()},
                         {"am": (4, True, True), "ti": (4, True, True)})            # each language is also heard as one take
        self.assertIn("## Each language as one take", (self.root / "outputs_mock" / "langtest" / "report.md").read_text(encoding="utf-8"))


class FreeTierTests(Project):
    """Ten speech requests a day are easy to spend by accident. The run log is the counter."""

    LIMITS = {"speech-model": {"unit": "per_audio_second", "usd_out": 0.0, "free_tier": {"requests_per_minute": 3, "requests_per_day": 2, "reset": "pacific"}}}

    def call(self, ctx):
        return core.model_call(ctx, stage="narration", unit="take", provider="gemini", model="speech-model", params={}, seed=None,
                               fn=lambda: (b"", {"audio_seconds": 1.0}))

    def test_a_request_over_the_daily_limit_is_not_sent(self):
        ctx, waits = self.ctx(mock=False), []
        ctx._prices, ctx.sleep = self.LIMITS, waits.append
        self.call(ctx)
        self.call(ctx)
        self.assertEqual(core.free_tier_use(ctx, "speech-model")["requests"], 2)
        with self.assertRaisesRegex(core.PipelineError, "allows 2 requests a day.*Nothing was sent"):
            self.call(ctx)
        self.assertEqual(len(core.read_jsonl(ctx.runlog)), 2)                        # the refused request never reached the log or the provider
        self.assertEqual(len(waits), 1)                                              # and the second call waited for the per-minute limit
        self.assertTrue(19.0 < waits[0] <= 20.0, waits)

    def test_an_account_that_pays_for_the_rest_is_not_stopped_at_the_free_allowance(self):
        ctx = self.ctx(mock=False)
        price = {"unit": "per_512_tile", "usd_out": 0.03, "free_tier": {"usd_per_day": 0.1, "reset": "utc"}}
        ctx._prices = {"picture-model": price}
        call = lambda: core.model_call(ctx, stage="keyframes", unit="s01_c1", provider="cloudflare", model="picture-model",  # noqa: E731
                                       params={"width": 512, "height": 512, "refs": 0}, seed=1, fn=lambda: (b"", {}))
        for _ in range(4):
            call()                                                                   # 0.12 USD at list price: over the allowance of 0.10
        with self.assertRaisesRegex(core.PipelineError, "free daily allowance.*Nothing was sent"):
            call()
        price["free_tier"]["then_paid_from"] = "2020-01-01T00:00:00Z"                # the account now pays for what goes over
        call()
        self.assertEqual(len(core.read_jsonl(ctx.runlog)), 5)
        from pipeline import costs
        self.assertAlmostEqual(costs.over_allowance(ctx, core.read_jsonl(ctx.runlog)), 0.05, places=4)   # five calls, 0.15, less the free 0.10

    def test_a_model_without_a_known_limit_is_not_held_back(self):
        ctx = self.ctx(mock=False)
        ctx._prices = {}
        self.assertIsNone(core.free_tier_use(ctx, "speech-model"))
        self.call(ctx)


class BorderTests(Project):
    """A painted look can come back as a framed picture on a page. The margin would show in the film."""

    def picture(self, graph: str) -> Path:
        out = self.root / "picture.png"
        core.ff(["-f", "lavfi", "-i", graph, "-frames:v", "1", str(out)])
        return out

    def test_bare_paper_is_counted_side_by_side(self):
        ctx = self.ctx()
        painted = "color=c=0x336699:s=224x224"
        self.assertEqual(keyframes.paper_edges(ctx, self.picture(f"{painted},scale=256:256")), 0)                           # fills the frame
        self.assertEqual(keyframes.paper_edges(ctx, self.picture(f"{painted},pad=256:256:16:16:color=0xF4F1EA")), 4)        # a framed page
        self.assertEqual(keyframes.paper_edges(ctx, self.picture(f"{painted},pad=224:256:0:32:color=white,scale=256:256")), 1)  # a white sky
        self.assertEqual(keyframes.paper_edges(ctx, self.picture("color=c=0xC8DCF0:s=256x256")), 0)                         # pale blue is not paper

    def test_a_full_frame_candidate_is_preferred_to_a_bordered_one(self):
        from unittest import mock
        sb = read_sb(self.root)
        sb["qa"].update(keyframe_candidates=2, judge=True)
        first = sb["shots"][0]
        first["keyframe"] = {k: v for k, v in first["keyframe"].items() if k not in ("pick", "candidates")}
        write_sb(self.root, sb)
        sid = first["id"]
        def edges(ctx, image):  # candidate 1 of the first shot has a border, everything else fills its frame
            return 4 if image.name.startswith(f"{sid}_c1__") else 0

        def generous(ctx, stage, unit, prompt, **kw):  # the judge likes the bordered one more
            total = 5 if unit == f"{sid}_c1_judge" else 4
            return json.dumps({"character_match": total, "prompt_adherence": total, "artifacts": total, "text_in_image": False}), {}

        with mock.patch.object(keyframes, "paper_edges", edges), mock.patch.object(providers, "text", generous):
            index = keyframes.run(self.ctx(), {})
        self.assertEqual((index[sid]["candidate"], index[sid]["border"], index[sid]["paper_sides"]), (2, False, {"1": 4, "2": 0}))


class SceneTests(Project):
    """A generated clip lasts a few seconds. A shot lasts as long as its narration."""

    def scene(self, clip_s: float, frames: int) -> tuple[dict, Path]:
        clip, scene = self.root / "clip.mp4", self.root / "scene.mp4"
        core.ff(["-f", "lavfi", "-i", f"testsrc2=size=128x128:rate=24:duration={clip_s}", "-pix_fmt", "yuv420p", str(clip)])
        meta = assemble.render_scene(self.ctx(), clip, scene, width=180, height=320, frames=frames, fps=24, cues=[], margin_v=40)
        return meta, scene

    def difference(self, scene: Path, first: int, second: int) -> float:
        """Mean difference between two frames of a video, counted from frame 0, on a scale of 0 to 255."""
        grabbed = []
        for n in (first, second):
            raw = self.root / "frame.raw"
            core.ff(["-i", str(scene), "-vf", f"select=eq(n\\,{n})", "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", str(raw)])
            grabbed.append(raw.read_bytes())
        return sum(abs(a - b) for a, b in zip(*grabbed)) / len(grabbed[0])

    def test_a_clip_shorter_than_its_shot_keeps_moving(self):
        meta, scene = self.scene(clip_s=1, frames=96)                 # one second of clip for a four second shot
        self.assertEqual((meta["slowdown"], meta["tail"]), (1.25, "push"))
        self.assertAlmostEqual(meta["tail_s"], 4.0 - 1.25, places=2)
        self.assertAlmostEqual(core.media_info(scene)["duration"], 4.0, places=2)
        self.assertGreater(self.difference(scene, 27, 28), 2.0)       # the clip itself moves (slowed to 30 frames)
        self.assertLess(self.difference(scene, 29, 30), 0.5)          # no jump where it hands over to its last frame
        self.assertGreater(self.difference(scene, 40, 90), 2.0)       # and the picture is still moving long after

    def test_a_clip_as_long_as_its_shot_is_left_alone(self):
        meta, scene = self.scene(clip_s=2, frames=48)
        self.assertEqual((meta["slowdown"], meta["tail"], meta["tail_s"]), (1.0, "none", 0.0))
        self.assertAlmostEqual(core.media_info(scene)["duration"], 2.0, places=2)

    def test_a_scene_is_cut_around_the_point_its_shot_names(self):
        clip = self.root / "clip.mp4"
        core.ff(["-f", "lavfi", "-i", "testsrc2=size=128x128:rate=24:duration=1", "-pix_fmt", "yuv420p", str(clip)])

        def first_frame(width: int, height: int, **focus: float) -> bytes:
            scene, raw = self.root / "scene.mp4", self.root / "frame.raw"
            meta = assemble.render_scene(self.ctx(), clip, scene, width=width, height=height, frames=24, fps=24, cues=[], margin_v=10, **focus)
            self.assertEqual(meta["fit"], "crop")
            core.ff(["-i", str(scene), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "gray", str(raw)])
            return raw.read_bytes()

        left, right = first_frame(180, 320, focus_x=0.0), first_frame(180, 320, focus_x=1.0)
        self.assertNotEqual(left, right)                                             # the tall scene shows another side of the clip
        self.assertEqual(first_frame(180, 320, focus_x=1.0, focus_y=0.0), right)     # and has no height to give up
        top, bottom = first_frame(320, 180, focus_y=0.0), first_frame(320, 180, focus_y=1.0)
        self.assertNotEqual(top, bottom)                                             # the wide scene: the other way round
        self.assertEqual(first_frame(320, 180, focus_x=0.0, focus_y=1.0), bottom)

    def test_a_clip_of_another_shape_still_sits_whole_over_a_blurred_copy(self):
        clip, scene = self.root / "wide.mp4", self.root / "scene.mp4"
        core.ff(["-f", "lavfi", "-i", "testsrc2=size=256x144:rate=24:duration=1", "-pix_fmt", "yuv420p", str(clip)])
        meta = assemble.render_scene(self.ctx(), clip, scene, width=180, height=320, frames=24, fps=24, cues=[], margin_v=40, focus_x=0.3)
        info = core.media_info(scene)
        self.assertEqual((meta["fit"], info["width"], info["height"]), ("blur_fill", 180, 320))   # a crop would lose 68% of it, anchor or not


class ListPriceTests(unittest.TestCase):
    """cost_usd in the run log: the list price of a call, or None. Never a guess."""

    PRICES = {"text-model": {"unit": "per_1m_tokens", "usd_in": 0.30, "usd_out": 2.50},
              "thinking-model": {"unit": "per_1m_tokens", "usd_in": 0.75, "usd_out": 3.75, "thinks": True},
              "speech-model": {"unit": "per_audio_second", "usd_in": 0.50, "usd_out": 0.000225},
              "image-model": {"unit": "per_512_tile", "usd_out": 0.000287, "usd_in": 0.000059},
              "step-model": {"unit": "per_512_tile", "usd_out": 0.0000528, "usd_step": 0.0001056, "default_steps": 4},
              "kaggle_gpu": {"unit": "per_gpu_minute", "usd": None}}

    def cost(self, **run):
        return pricing.cost_usd({"status": "ok", **run}, self.PRICES)

    def test_tokens_seconds_and_tiles(self):
        self.assertEqual(self.cost(model="text-model", usage={"input_tokens": 1331, "output_tokens": 69}), 0.000572)
        self.assertEqual(self.cost(model="thinking-model", usage={"input_tokens": 1000, "output_tokens": 10, "thoughts_tokens": 90}), 0.001125)
        self.assertEqual(self.cost(model="speech-model", audio_seconds=8.0), 0.0018)
        self.assertEqual(self.cost(model="image-model", params={"width": 1024, "height": 1024, "refs": 1}), 0.001207)   # 4 tiles out, 1 in
        self.assertEqual(self.cost(model="step-model", params={"width": 1024, "height": 1024}), 0.000634)               # 4 tiles, 4 steps

    def test_what_is_not_known_is_not_priced(self):
        self.assertIsNone(self.cost(model="a model with no entry", usage={"input_tokens": 1, "output_tokens": 1}))
        self.assertIsNone(self.cost(model="thinking-model", usage={"input_tokens": 8, "output_tokens": 1}))   # thinking tokens not logged
        self.assertIsNone(self.cost(model="speech-model"))                                                    # length not logged
        self.assertIsNone(self.cost(provider="kaggle", model="any", gpu_minutes=12.5, gpu_count=2))           # no price read yet

    def test_a_failed_api_call_costs_nothing(self):
        self.assertEqual(pricing.cost_usd({"status": "error", "model": "text-model"}, self.PRICES), 0.0)

    def test_every_price_in_the_repository_names_its_source_and_date(self):
        for model, price in pricing.load(REPO).items():
            numbers = [v for k, v in price.items() if k.startswith("usd")]
            if any(v is not None for v in numbers):
                self.assertTrue(price.get("source", "").startswith("https://"), model)
                self.assertRegex(price.get("checked") or "", r"^\d{4}-\d{2}-\d{2}$", model)


FAKE_KAGGLE = '''#!/usr/bin/env python3
"""A stand-in for the kaggle command line tool: it keeps its state in a folder and records every call."""
import json, os, shutil, sys
from pathlib import Path
state, args = Path(os.environ["FAKE_KAGGLE_STATE"]), sys.argv[1:]
with open(state / "calls.jsonl", "a") as fh:
    fh.write(json.dumps(args) + "\\n")
def folder():
    return Path(args[args.index("-p") + 1])
if args[:2] == ["config", "view"]:
    print("- username: tester")
elif args[:2] == ["datasets", "status"]:
    if not (state / "dataset.json").exists():
        sys.exit("404 not found")
    print((state / "dataset.json").read_text())
elif args[:2] in (["datasets", "create"], ["datasets", "version"]):
    old = json.loads((state / "dataset.json").read_text())["current_version_number"] if (state / "dataset.json").exists() else 0
    (state / "dataset.json").write_text(json.dumps({"status": "ready", "current_version_number": old + 1}))
    (state / "uploaded.json").write_text(json.dumps(sorted(p.name for p in folder().iterdir())))
elif args[:2] == ["kernels", "push"] and (state / "refuse_push").exists():
    print("Kernel push error: Maximum batch GPU session count of 2 reached.")   # the real tool says this and exits with 0
elif args[:2] == ["kernels", "push"]:
    shutil.copytree(folder(), state / "kernel", dirs_exist_ok=True)
    (state / "status.json").write_text(json.dumps(["QUEUED", "RUNNING", "COMPLETE"]))
    print("Kernel version 1 successfully pushed.")
elif args[:2] == ["kernels", "status"]:
    left = json.loads((state / "status.json").read_text())
    (state / "status.json").write_text(json.dumps(left[1:] or left))
    print(f'tester/heritage-music has status "KernelWorkerStatus.{left[0]}"')
elif args[:2] == ["kernels", "output"]:
    shutil.copytree(state / "results", folder(), dirs_exist_ok=True)
elif args[:2] == ["kernels", "logs"]:
    print("a log")
'''


class KaggleRunTests(Project):
    """Upload, push, wait, fetch, ingest: tested against a stand-in for the kaggle command line tool."""

    def setUp(self):
        super().setUp()
        from unittest import mock
        self.state = self.root / "fake_kaggle"
        (self.state / "bin").mkdir(parents=True)
        tool = self.state / "bin" / "kaggle"
        tool.write_text(FAKE_KAGGLE, encoding="utf-8")
        tool.chmod(0o755)
        env = {"PATH": f"{tool.parent}{os.pathsep}{os.environ['PATH']}", "KAGGLE_API_TOKEN": "KGAT_test", "FAKE_KAGGLE_STATE": str(self.state)}
        for patch in (mock.patch.dict(os.environ, env), mock.patch("pipeline.kagglerun.time.sleep", lambda seconds: None)):
            patch.start()
            self.addCleanup(patch.stop)

    def results(self, ctx, created):
        """What the GPU job would leave behind for the first candidate of the waiting music job."""
        job = json.loads((ctx.out / "music" / "kaggle_job" / "manifest.json").read_text(encoding="utf-8"))["jobs"][0]
        folder = self.state / "results"
        folder.mkdir(exist_ok=True)
        name = f"{job['unit']}__{job['key']}.wav"
        (folder / name).write_bytes(providers.pcm_to_wav(b"\x10\x00" * 48000))
        (folder / "results.json").write_text(json.dumps({
            "stage": "music", "job_id": "job1", "job_created": created, "model": "acestep-v15-turbo", "gpu": "Tesla T4, Tesla T4",
            "results": [{"unit": job["unit"], "key": job["key"], "fingerprint": job["fingerprint"], "seed": job["seed"], "params": {},
                         "status": "ok", "file": name, "latency_s": 90.0, "peak_mem_gb": 3.1}]}), encoding="utf-8")

    def test_the_job_that_is_sent_is_the_job_of_the_storyboard_as_it_is_now(self):
        from pipeline import kagglerun
        music.run(self.ctx(mock=False), {})                  # a job is written, and then the storyboard changes
        sb = read_sb(self.root)
        sb["music"]["caption"] = "Solo krar, plucked slowly. One instrument only, in a quiet room. No drums, no vocals."
        write_sb(self.root, sb)
        ctx = self.ctx(mock=False)
        self.assertEqual(kagglerun.run(ctx, "run", "music", wait_for_it=False), 0)
        sent = json.loads((ctx.out / "music" / "kaggle_job" / "manifest.json").read_text(encoding="utf-8"))
        self.assertIn("Solo krar", json.dumps(sent))                                   # the new caption went out, not the old job
        self.assertIn(repr(sent["created"]), (self.state / "kernel" / "launch.py").read_text())

    def test_nothing_is_sent_when_nothing_waits_for_a_gpu(self):
        from pipeline import kagglerun
        sb = read_sb(self.root)
        sb["music"]["seeds"] = sb["music"]["seeds"][:1]      # one candidate, so one result fills the cache
        write_sb(self.root, sb)
        ctx = self.ctx(mock=False)
        music.run(ctx, {})
        self.results(ctx, kagglerun.job_manifest(ctx, "music")["created"])
        self.assertEqual(kagglerun.run(ctx, "run", "music"), 0)
        pushes = len([c for c in core.read_jsonl(self.state / "calls.jsonl") if c[:2] == ["kernels", "push"]])
        with self.assertRaisesRegex(core.PipelineError, "waiting for a GPU.*Nothing was sent"):
            kagglerun.run(ctx, "run", "music")
        self.assertEqual(len([c for c in core.read_jsonl(self.state / "calls.jsonl") if c[:2] == ["kernels", "push"]]), pushes)

    def test_a_push_that_kaggle_refuses_is_not_reported_as_running(self):
        from pipeline import kagglerun
        ctx = self.ctx(mock=False)
        music.run(ctx, {})
        (self.state / "refuse_push").write_text("")
        with self.assertRaisesRegex(core.PipelineError, "did not start the music run: Kernel push error: Maximum batch GPU session count"):
            kagglerun.run(ctx, "run", "music")

    def test_a_job_goes_to_kaggle_and_its_result_comes_back_into_the_cache(self):
        from pipeline import kagglerun
        ctx = self.ctx(mock=False)
        music.run(ctx, {})                                   # nothing is cached, so the stage writes the job
        created = kagglerun.job_manifest(ctx, "music")["created"]
        self.results(ctx, created)
        self.assertEqual(kagglerun.run(ctx, "run", "music"), 0)

        calls = [" ".join(c[:2]) for c in core.read_jsonl(self.state / "calls.jsonl")]
        self.assertEqual([c for c in calls if c not in ("config view", "datasets status", "kernels status")],
                         ["datasets create", "kernels push", "kernels output"])
        self.assertEqual(json.loads((self.state / "uploaded.json").read_text()), ["acestep_music.py", "dataset-metadata.json", "manifest.json"])
        meta = json.loads((self.state / "kernel" / "kernel-metadata.json").read_text())
        self.assertEqual((meta["enable_gpu"], meta["enable_internet"], meta["machine_shape"], meta["is_private"], meta["dataset_sources"]),
                         ("true", "true", "NvidiaTeslaT4", "true", ["tester/heritage-music-job"]))
        self.assertIn(repr(created), (self.state / "kernel" / "launch.py").read_text())   # the launcher only runs this job's data
        self.assertIsNotNone(music.run(ctx, {})["candidates"]["candidate_1"])              # the candidate is in the cache now
        gpu = [r for r in core.read_jsonl(ctx.runlog) if r["provider"] == "kaggle"]
        self.assertEqual([(r["unit"], r["gpu_minutes"], r["gpu_count"]) for r in gpu], [("candidate_1", 1.5, 2)])
        self.assertEqual(core.read_jsonl(ctx.out / "logs" / "kaggle_sessions.jsonl")[-1]["status"], "COMPLETE")

    def test_a_job_written_again_unchanged_keeps_its_stamp(self):
        from pipeline import kagglerun
        ctx = self.ctx(mock=False)
        music.run(ctx, {})
        first = kagglerun.job_manifest(ctx, "music")["created"]
        with mock_now("2030-01-01T00:00:00Z"):
            music.run(ctx, {})                                # the stage runs again while the GPU job is still out
            self.assertEqual(kagglerun.job_manifest(ctx, "music")["created"], first)
            sb = read_sb(self.root)
            sb["music"]["bpm"] = 70                           # a different job gets a new stamp
            write_sb(self.root, sb)
            music.run(self.ctx(mock=False), {})
            self.assertEqual(kagglerun.job_manifest(ctx, "music")["created"], "2030-01-01T00:00:00Z")

    def test_a_failed_status_poll_is_not_an_ended_run(self):
        from unittest import mock
        from pipeline import kagglerun
        failed = mock.Mock(returncode=1, stdout="", stderr="503 Server Error: ERROR for url")
        with mock.patch.object(kagglerun, "kaggle", return_value=failed):
            self.assertEqual(kagglerun.status("tester/heritage-music"), "UNKNOWN")

    def test_a_file_missing_from_an_interrupted_download_is_taken_next_time(self):
        ctx = self.ctx(mock=False)
        music.run(ctx, {})
        from pipeline import kagglerun
        self.results(ctx, kagglerun.job_manifest(ctx, "music")["created"])
        wav = next((self.state / "results").glob("*.wav"))
        held = wav.read_bytes()
        wav.unlink()
        self.assertEqual(music.ingest(ctx, self.state / "results"), 0)      # the download stopped before the audio arrived
        wav.write_bytes(held)
        self.assertEqual(music.ingest(ctx, self.state / "results"), 1)      # complete now: it enters the cache
        self.assertEqual(len([r for r in core.read_jsonl(ctx.runlog) if r["provider"] == "kaggle"]), 1)   # and is logged once

    def test_output_of_an_older_job_is_refused(self):
        from pipeline import kagglerun
        ctx = self.ctx(mock=False)
        music.run(ctx, {})
        self.results(ctx, "2020-01-01T00:00:00Z")
        with self.assertRaisesRegex(core.PipelineError, "older job"):
            kagglerun.run(ctx, "fetch", "music")

    def test_without_a_token_nothing_is_called(self):
        from unittest import mock
        from pipeline import kagglerun
        with mock.patch.dict(os.environ, {"KAGGLE_API_TOKEN": "", "HOME": str(self.root)}):
            with self.assertRaisesRegex(core.PipelineError, "no Kaggle token"):
                kagglerun.kaggle(["quota"])
        self.assertFalse((self.state / "calls.jsonl").exists())


class SiteTests(Project):
    """The public page is built from the repository alone, and says how far the film has come."""

    def test_the_page_shows_every_shot_and_admits_what_is_not_done(self):
        from pipeline import site
        ctx = self.ctx()
        keyframes.run(ctx, {})
        out = site.run(ctx)
        page = (out / "index.html").read_text(encoding="utf-8")
        sb = ctx.sb
        for shot in sb["shots"]:
            self.assertIn(f"{shot['id']} &middot;", page)
            self.assertTrue((out / "media" / f"{shot['id']}.jpg").exists(), shot["id"])   # cut from the kept original
        self.assertIn("The film is not made yet", page)             # no film has been assembled in this copy
        self.assertIn("work in progress", page)
        self.assertIn("made with AI", page)
        self.assertNotIn("DRAFT", page)                             # a draft sentence is shown as a draft, without the marker
        self.assertIn("a draft, not yet confirmed by the author", page)
        self.assertNotIn("http://", page)                           # nothing is loaded from elsewhere


class JudgeTests(Project):
    """The judge looks for what is wrong. It can run on a Claude model when the storyboard names one."""

    def test_what_a_film_frame_cannot_have_costs_points(self):
        clean = {"character_match": 3, "prompt_adherence": 5, "artifacts": 5, "border": False, "text_in_image": False, "wrong_setting": "", "anatomy": ""}
        self.assertEqual(keyframes.judge_total(clean, False), 5.0)
        self.assertEqual(keyframes.judge_total({**clean, "border": True}, False), 3.5)
        self.assertEqual(keyframes.judge_total({**clean, "text_in_image": True, "wrong_setting": "a European street"}, False), 2.5)
        self.assertEqual(keyframes.judge_total({**clean, "anatomy": "six fingers"}, False), 4.0)

    def test_a_claude_model_is_called_through_the_sdk_with_pictures_first_and_a_schema(self):
        import sys
        import types
        from unittest import mock
        sent = []

        class Messages:
            def create(self, **request):
                sent.append(request)
                return types.SimpleNamespace(stop_reason="end_turn", model="claude-opus-5-5",
                                             content=[types.SimpleNamespace(type="thinking"), types.SimpleNamespace(type="text", text='{"border": true}')],
                                             usage=types.SimpleNamespace(input_tokens=1200, output_tokens=300))

        fake = types.ModuleType("anthropic")
        made = []
        fake.Anthropic = lambda **kw: made.append(kw) or types.SimpleNamespace(beta=types.SimpleNamespace(messages=Messages()))
        for name in ("RateLimitError", "BadRequestError", "AuthenticationError", "PermissionDeniedError", "NotFoundError", "APIStatusError", "APIConnectionError"):
            setattr(fake, name, type(name, (Exception,), {}))
        keys = {"ANTHROPIC_API_KEY": "test-claude", "ANTHROPIC_WORKSPACE_ID": "wrkspc_test"}
        with mock.patch.dict(sys.modules, {"anthropic": fake}), mock.patch.dict(os.environ, keys):
            out, meta = providers.text(self.ctx(mock=False), "keyframes", "s01_c1_judge", "Find what is wrong.", kind="judge",
                                       parts=[("image/jpeg", b"img")], schema=keyframes.JUDGE_SCHEMA, model="claude-opus-5-5")
        request = sent[0]
        self.assertEqual(made[0], {"max_retries": 0, "default_headers": {"anthropic-workspace-id": "wrkspc_test"}})   # our retries, and the workspace
        self.assertEqual((request["model"], request["fallbacks"], request["betas"]), ("claude-opus-5-5", "default", ["server-side-fallback-2026-07-01"]))
        self.assertEqual([block["type"] for block in request["messages"][0]["content"]], ["image", "text"])
        self.assertEqual(request["output_config"], {"format": {"type": "json_schema", "schema": keyframes.JUDGE_SCHEMA}})
        self.assertEqual((out, meta["served_by"]), ('{"border": true}', "claude-opus-5-5"))
        logged = core.read_jsonl(self.root / "runs.jsonl")[-1]
        self.assertEqual((logged["provider"], logged["usage"]["input_tokens"], logged["cost_usd"]), ("anthropic", 1200, 0.0108))   # 1200 in at 4, 300 out at 20, per million
        self.assertNotIn("test-claude", json.dumps(logged))

    def test_a_claude_model_is_not_given_audio(self):
        import sys
        import types
        from unittest import mock
        with mock.patch.dict(sys.modules, {"anthropic": types.ModuleType("anthropic")}), mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "k"}):
            with self.assertRaisesRegex(core.PipelineError, "not audio"):
                providers.text(self.ctx(mock=False), "narration", "s01_listen", "Transcribe.", kind="transcribe",
                               parts=[("audio/wav", b"RIFF")], model="claude-opus-5-5")


class MarkedPictureTests(Project):
    """The keyframes stage says "look at" once, when it picks a picture the judge marked. The final-cut check has to say it every time."""

    LOW, WRITING = "pictures: no picked keyframe scored under 3 by the judge", "pictures: no picked keyframe has writing in it"

    def picks(self, ctx: core.Ctx) -> dict:
        """What the check reads of a keyframes index: for each shot two scored candidates, the first one picked, nothing marked."""
        return {s["id"]: {"file": f"{s['id']}_c1__0000.png", "blocked": [], "candidate": 1, "picked_by": "judge", "unscored": [], "border": False,
                          "scores": {str(i): {"total": 4.1, "text_in_image": False, "notes": "clean"} for i in (1, 2)}} for s in ctx.sb["shots"]}

    def stand_in_film(self, ctx: core.Ctx) -> dict:
        """What the check measures of a film, without the film: both exports as one plain colour under a tone at the film's loudness."""
        sb, fmt = ctx.sb, ctx.sb["format"]
        total = (fmt["min_total_s"] + fmt["max_total_s"]) / 2                    # a length the brief accepts, whatever the shots add up to
        timeline = core.plan_timeline(sb, {s["id"]: 3.0 for s in sb["shots"] if s["narration"]})
        ctx.out.mkdir(parents=True, exist_ok=True)
        tone = ctx.out / "tone.m4a"                                              # encoded once for both exports: -14 LUFS, peaks far under -1 dB
        core.ff(["-f", "lavfi", "-i", f"sine=frequency=1000:sample_rate=48000:duration={total},pan=stereo|c0=1.6*c0|c1=1.6*c0", "-c:a", "aac", str(tone)])
        files = {exp["name"]: f"film_{exp['name']}.mp4" for exp in fmt["exports"]}
        for exp in fmt["exports"]:
            core.ff(["-f", "lavfi", "-i", f"color=c=0x30343c:s={exp['width']}x{exp['height']}:r={fmt['fps']}:d={total}", "-i", str(tone),
                     "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "copy", "-shortest", str(ctx.out / files[exp["name"]])])
        return {"mode": "film", "total_s": total, "files": files, "timeline": timeline, "cues": [], "end_card": sb["end_card"]["lines"], "tails": {}}

    def test_a_picked_picture_the_judge_marked_is_a_note_and_fails_nothing(self):
        from pipeline import qc
        ctx = self.ctx()
        film, index = self.stand_in_film(ctx), self.picks(ctx)

        def check(index: dict) -> tuple[dict, bool]:
            report = qc.run(ctx, {"assemble": film, "keyframes": index})
            return {c["check"]: (c["level"], c["ok"], c["detail"]) for c in report["checks"]}, report["passed"]

        notes, passed = check(index)                                             # no pick is marked: both lines are there and pass
        self.assertEqual((notes[self.LOW], notes[self.WRITING], passed), (("note", True, "none"), ("note", True, "none"), True))

        low, written, other, unscored = [s["id"] for s in ctx.sb["shots"]][:4]
        index[low].update(candidate=2, file=f"{low}_c2__0000.png")
        index[low]["scores"]["2"] = {"total": 2.3, "text_in_image": False}       # the pick is under 3. The candidate left behind was clean
        index[written]["scores"]["1"] = {"total": 3.5, "text_in_image": True}    # the pick has writing in it, and is not under 3 for it
        index[other]["scores"]["2"] = {"total": 0.2, "text_in_image": True}      # marked both ways, but this candidate was not picked
        index[unscored].update(scores={}, unscored=[1, 2])                       # the judge was not reached: another note says that
        notes, passed = check(index)
        self.assertEqual(notes[self.LOW], ("note", False, f"{low} (2.3)"))
        self.assertEqual(notes[self.WRITING], ("note", False, written))
        self.assertEqual(notes["pictures: the judge scored every candidate"], ("note", False, unscored))
        self.assertTrue(passed)                                                  # a note sends a person to look. It never fails the film

    def test_a_shot_without_a_pick_or_without_a_score_is_not_a_marked_picture(self):
        from pipeline import qc
        index = {"s01": {"file": "s01_card__0000.png", "key": "0000", "blocked": ["boy"], "candidate": None},   # waiting for consent: a card, no pick
                 "s02": {"candidate": 1, "scores": {}, "unscored": [1, 2]},                                     # picked, and never scored
                 "s03": {"candidate": 2, "scores": {"1": {"total": 1.0, "text_in_image": True}}, "unscored": [2]},   # scored, but not the pick
                 "s04": {"candidate": 1, "scores": {"1": {"total": 3.0, "text_in_image": False}}}}              # 3 is not under 3
        self.assertEqual(qc.marked_picks(index), ([], []))
        self.assertEqual(qc.marked_picks({}), ([], []))                          # no keyframes yet
        index["s04"]["scores"]["1"]["total"] = 2.999
        self.assertEqual(qc.marked_picks(index), (["s04 (2.999)"], []))


class NoSecretsTests(unittest.TestCase):
    """Keys live in .env, which git ignores. Nothing git tracks may hold one."""

    SHAPES = r"sk-ant-[A-Za-z0-9_-]{20,}|KGAT_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|AQ\.[A-Za-z0-9_-]{30,}"

    def test_no_tracked_file_holds_a_key_and_env_is_ignored(self):
        import re
        import subprocess
        listed = subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True)
        if listed.returncode != 0:
            self.skipTest("not a git checkout")
        files = listed.stdout.splitlines()
        self.assertNotIn(".env", files)
        holding = [name for name in files if (REPO / name).is_file() and (REPO / name).stat().st_size < 3_000_000
                   and re.search(self.SHAPES, (REPO / name).read_text(encoding="utf-8", errors="ignore"))]
        self.assertEqual(holding, [])


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
        index = music.run(ctx, {})
        self.assertEqual(index["source"], "acestep")
        self.assertTrue(index["file"].endswith(".flac"))                          # kept lossless, at half the size
        self.assertEqual(index["heard"]["candidate_1"]["vocals"], False)          # and a listener has said what is in it


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
        marked = [c["ok"] for c in report["checks"] if c["check"].startswith("pictures: no picked keyframe")]
        self.assertEqual(marked, [True, True])                       # under 3, and writing: the mock judge marks no picture
        for name in ("film_vertical.mp4", "film_horizontal.mp4", "subtitles.en.srt"):
            self.assertTrue((out / name).exists(), name)
        self.assertTrue(all(c["provider"] == "mock" for c in calls))
        self.assertFalse((self.root / "runs.jsonl").exists())

        built, calls = self.film()                                   # nothing changed
        self.assertEqual((built, calls), (set(), []))

        sb = read_sb(self.root)                                      # one narration line changed
        spoken = next(s for s in sb["shots"] if s["narration"])
        spoken["narration"][sb["language"]["narration"]] += " በጣም።"
        write_sb(self.root, sb)
        built, calls = self.film()
        sid = spoken["id"]
        films = {"film_vertical", "film_horizontal"}
        self.assertEqual(sorted(c["unit"] for c in calls), [sid, f"{sid}_listen", f"{sid}_subtitle_check"])   # check its subtitle, speak it, listen to it
        rebuilt = {sid, f"{sid}_listen", f"{sid}_subtitle_check", "mix", f"vertical_{sid}", f"horizontal_{sid}"} | films
        self.assertLessEqual(rebuilt, built)
        self.assertLessEqual(built, rebuilt | {f"{sid}_kenburns"})   # its clip too, when the longer line makes the shot longer

        drawn = sb["shots"][-1]                                      # one keyframe prompt changed, in another shot
        self.assertNotEqual(drawn["id"], sid)
        drawn["keyframe"]["prompt"] += " A wooden chair in the corner."
        write_sb(self.root, sb)
        built, calls = self.film()
        kid, n = drawn["id"], drawn["keyframe"].get("candidates", sb["qa"]["keyframe_candidates"])
        pictures = {f"{kid}_c{i}" for i in range(1, n + 1)}
        pictures |= {f"{unit}_judge" for unit in pictures} if sb["qa"]["judge"] else set()
        self.assertEqual({c["unit"] for c in calls}, pictures)
        self.assertEqual(built, pictures | {f"{kid}_kenburns", f"vertical_{kid}", f"horizontal_{kid}"} | films)

        aimed = sb["shots"][0]["keyframe"]                           # one shot points the tall film at another side of its picture
        tall, wide = (assemble.focus_of(aimed, name)[0] for name in ("vertical", "horizontal"))
        aimed["focus_x"] = {"vertical": 0.8 if tall == 0.2 else 0.2, "horizontal": wide}
        write_sb(self.root, sb)
        built, calls = self.film()
        self.assertEqual((built, calls), ({f"vertical_{sb['shots'][0]['id']}", "film_vertical"}, []))   # one scene of one export, and the film it is in

    def test_radio_cut(self):
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["radio", "--mock", "--root", str(self.root)])
        self.assertEqual(code, 0)
        info = core.media_info(self.root / "outputs_mock" / "radio_cut.mp4")
        self.assertEqual(info["acodec"], "aac")
        self.assertTrue(60 <= info["duration"] <= 90)


if __name__ == "__main__":
    unittest.main()
