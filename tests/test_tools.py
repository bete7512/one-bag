"""Offline tests of what the README calls "a tool for others": `python -m pipeline init` and the MCP server.

No network and no API keys. Every project here is made by `init` in a temporary folder, so the film this
repository makes, its outputs and its run log are never touched. The `mcp` package is not needed: the server
module is imported against a stand-in that keeps each tool as the plain function it is.

    python -m unittest tests.test_tools -v                         everything, including a mock film made through the tools
    HERITAGE_FAST_TESTS=1 python -m unittest tests.test_tools -v   without that film (the radio cut is still built)
"""
import contextlib
import importlib
import importlib.util
import inspect
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

import pipeline
from pipeline import cli, core, pricing, providers, scaffold

REPO = Path(__file__).resolve().parent.parent
TOOLS = ["costs", "final_check", "make_film", "plan", "radio_cut", "read_storyboard", "run_stage", "validate"]
SPOTS = {"mcpserver": "MCPServer", "fastmcp": "FastMCP"}   # where the server class lives in mcp 2.x and in mcp 1.x
KEY_SHAPES = r"sk-ant-[A-Za-z0-9_-]{20,}|KGAT_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_-]{30,}|AQ\.[A-Za-z0-9_-]{30,}"   # as in NoSecretsTests


def read_sb(folder: Path) -> dict:
    return json.loads((folder / "storyboard.json").read_text(encoding="utf-8"))


def write_sb(folder: Path, sb: dict) -> None:
    (folder / "storyboard.json").write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")


def new_project(folder: Path, lang: str = "en") -> Path:
    """What `python -m pipeline init <folder> --lang <lang>` leaves behind, made in this process."""
    said = io.StringIO()
    with contextlib.redirect_stdout(said):
        code = cli.main(["init", str(folder), "--lang", lang])
    if code:
        raise AssertionError(f"init failed: {said.getvalue()}")
    return folder


def shrink(folder: Path) -> None:
    """Tiny frames keep a run fast. The logic is the same."""
    sb = read_sb(folder)
    sb["format"]["master"] = {"width": 256, "height": 256}
    sb["format"]["exports"] = [{"name": "vertical", "width": 180, "height": 320, "subtitle_margin_v": 40},
                               {"name": "horizontal", "width": 320, "height": 180, "subtitle_margin_v": 10}]
    write_sb(folder, sb)


def write_the_film(folder: Path) -> None:
    """What a new author does next: a line and a picture of their own for every shot, long enough to make a film."""
    sb = read_sb(folder)
    for n, shot in enumerate(sb["shots"], 1):
        shot["narration"] = {"en": f"Line {n} of a film that tests the tools."}
        shot["keyframe"]["prompt"] = f"Picture {n}: one plain object in the centre."
        shot["min_duration_s"] = 8
    write_sb(folder, sb)


def strings(node) -> set:
    """Every piece of text inside a storyboard, or inside a part of one."""
    if isinstance(node, str):
        return {node}
    children = node.values() if isinstance(node, dict) else node if isinstance(node, list) else []
    return set().union(*(strings(child) for child in children))


def files_of(folder: Path) -> dict:
    """Every file under a folder, as text, by its path."""
    return {p.relative_to(folder).as_posix(): p.read_text(encoding="utf-8", errors="ignore") for p in sorted(folder.rglob("*")) if p.is_file()}


def run_cli(*argv: str, cwd: Path) -> subprocess.CompletedProcess:
    """`python -m pipeline ...` as someone types it in `cwd`, with nothing in the environment that points at another project."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(("HERITAGE_", "PYTHONPATH", "PYTHONSAFEPATH"))}
    return subprocess.run([sys.executable, "-m", "pipeline", *argv], cwd=cwd, env=env, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


class Recorder:
    """Stands in for the server class of the `mcp` package. It keeps each tool as the plain function it was given."""

    def __init__(self, name: str):
        self.name, self.tools = name, {}

    def tool(self):
        def register(fn):
            self.tools[fn.__name__] = fn
            return fn
        return register

    def run(self):
        raise AssertionError("the tests start no server")


def forget_server() -> None:
    """Leave no imported copy of the server module behind for another test to find."""
    sys.modules.pop("pipeline.mcp_server", None)
    vars(pipeline).pop("mcp_server", None)


def import_server(spot: str = "mcpserver"):
    """Import pipeline.mcp_server against a stand-in `mcp` package that has the server class in one of its two places."""
    package, server, holder = types.ModuleType("mcp"), types.ModuleType("mcp.server"), types.ModuleType(f"mcp.server.{spot}")
    package.__path__, server.__path__ = [], []
    setattr(holder, SPOTS[spot], Recorder)
    stand_ins = {"mcp": package, "mcp.server": server, **{f"mcp.server.{name}": None for name in SPOTS}, holder.__name__: holder}
    forget_server()
    try:
        with mock.patch.dict(sys.modules, stand_ins):
            return importlib.import_module("pipeline.mcp_server")
    finally:
        forget_server()


def no_network(*args, **kwargs):
    raise AssertionError("a test tried to open a network connection")


class NewProject(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = new_project(Path(self._tmp.name) / "my-film")

    def tearDown(self):
        self._tmp.cleanup()


class ScaffoldTests(NewProject):
    def test_a_new_project_validates_and_starts_as_a_draft_with_nothing_confirmed(self):
        for lang in ("en", "am"):                                                            # init takes the language the film is told in
            folder = new_project(Path(self._tmp.name) / f"film-{lang}", lang)
            sb, problems = core.load_storyboard(folder)                                      # raises on any error: schema, shot ids, consent, length
            self.assertEqual(sb["language"], {"narration": lang, "subtitles": "en"})
            self.assertTrue(8 <= len(sb["shots"]) <= 12, len(sb["shots"]))                   # what the brief asks for
            self.assertTrue(all({lang, "en"} <= set(s["narration"]) for s in sb["shots"]))   # a line and a subtitle to fill in, for every shot
            self.assertFalse(any(s["review"]["confirmed"] for s in sb["shots"]))             # that tick is the author's
            self.assertLessEqual({"draft", "unconfirmed"}, {code for _, code, _ in problems})
            with self.assertRaisesRegex(core.StoryboardError, "DRAFT"):                      # so a release is refused until it is written
                core.load_storyboard(folder, strict=True)

    def test_a_new_project_holds_nothing_of_the_film_it_was_copied_from(self):
        film, new, files = read_sb(REPO), read_sb(self.root), files_of(self.root)
        # format, models, video, qa and voice are copied on purpose. Everything else in the storyboard is this film's own.
        own = {key: film[key] for key in ("title", "audience", "intent", "style", "characters", "music", "end_card", "shots")}
        sentences = {s for s in strings(own) if len(s) >= 20}            # shorter ones are words any storyboard has: "medium", "s01", "Made with AI"
        self.assertEqual(sorted((name, s[:40]) for name, text in files.items() for s in sentences if s in text), [])
        lines = {line for shot in film["shots"] if shot["narration"] for line in shot["narration"].values()}
        self.assertEqual([line for line in lines if line in files["storyboard.json"]], [])   # no narration line, however short
        self.assertNotEqual(new["title"], film["title"])
        self.assertEqual(new["characters"], [])                           # nobody is in the new film yet
        self.assertFalse(any(shot["characters"] for shot in new["shots"]))
        self.assertEqual(core.consent_rows(self.root), {})                # and nobody's consent comes along with the code
        self.assertFalse({".env", "runs.jsonl"} & set(files))             # nor a key file, nor this film's run log
        self.assertFalse([name for name in files if name.startswith(("outputs/", "outputs_mock/"))])
        self.assertEqual([name for name, text in files.items() if re.search(KEY_SHAPES, text)], [])
        self.assertIn(".env", files[".gitignore"].split())                # and the new project keeps its own keys out of git

    def test_a_new_project_does_not_inherit_a_paid_model(self):
        prices = pricing.load(REPO)
        paid = [name for name, price in prices.items() if price.get("paid")]
        if not paid:
            self.skipTest("pricing.json lists no paid model")
        source = Path(self._tmp.name) / "source"                          # a film whose judge is paid for, whatever this repository's film uses today
        source.mkdir()
        film = read_sb(REPO)
        film["models"]["judge"] = paid[0]
        write_sb(source, film)
        with mock.patch.object(scaffold, "ROOT", source):
            models = scaffold.blank_storyboard("en")["models"]
        self.assertEqual([name for name in models.values() if name in paid], [])


class ScaffoldCommandTests(unittest.TestCase):
    def test_init_makes_a_project_that_runs_on_its_own_copy_of_the_pipeline(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "my-film"
            made = run_cli("init", str(folder), "--lang", "so", cwd=REPO)
            self.assertEqual(made.returncode, 0, made.stdout + made.stderr)
            self.assertIn("python -m pipeline validate", made.stdout)     # init names two commands to run next, inside the new folder:
            self.assertIn("python -m pipeline radio --mock", made.stdout)

            checked = run_cli("validate", cwd=folder)
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)
            self.assertIn("8 shots, narration in 'so'", checked.stdout)   # the copy read its own storyboard, not the one of the film it came from

            cut = run_cli("radio", "--mock", cwd=folder)                  # script, narration, music and assembly, end to end, offline
            self.assertEqual(cut.returncode, 0, cut.stdout[-600:] + cut.stderr[-600:])
            self.assertTrue((folder / "outputs_mock" / "radio_cut.mp4").exists())
            self.assertFalse((folder / "runs.jsonl").exists() or (folder / "outputs").exists())   # mock is never evidence

            kept = (folder / "storyboard.json").read_bytes()
            again = run_cli("init", str(folder), cwd=REPO)                # a folder that holds something is left alone
            self.assertEqual(again.returncode, 1)
            self.assertIn("not empty", again.stdout + again.stderr)
            self.assertEqual((folder / "storyboard.json").read_bytes(), kept)


class McpImportTests(unittest.TestCase):
    def test_the_server_module_imports_under_both_names_of_the_server_class_and_names_the_package_when_it_is_missing(self):
        for spot in SPOTS:
            module = import_server(spot)
            self.assertEqual(sorted(module.server.tools), TOOLS, spot)
            self.assertTrue(all(fn.__doc__ for fn in module.server.tools.values()))   # the docstring is what the agent is shown
        self.addCleanup(forget_server)
        if importlib.util.find_spec("mcp") is None:                       # no mcp package on this machine: the error has to name it
            with self.assertRaises(ImportError) as refused:
                importlib.import_module("pipeline.mcp_server")
            self.assertEqual(refused.exception.name, "mcp")
        else:
            module = importlib.import_module("pipeline.mcp_server")
            self.assertTrue(all(callable(getattr(module, name)) for name in TOOLS))


class McpToolTests(NewProject):
    """The tools as an agent gets them, called as plain functions on a new project.

    HERITAGE_ROOT names the project, as the server's docstring says. Two more guards keep a mistake in a test away
    from the real film and the real quotas: the pipeline's default folder is the temporary one too, and nothing can
    open a connection.
    """

    def setUp(self):
        super().setUp()
        shrink(self.root)
        self.module = import_server()
        self.tool = self.module.server.tools
        env = mock.patch.dict(os.environ, {"HERITAGE_ROOT": str(self.root)})
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("HERITAGE_PROVIDER", None)   # each test says mock or real itself. patch.dict puts the variable back
        for guard in (mock.patch.object(core, "ROOT", self.root), mock.patch.object(self.module, "ROOT", self.root),
                      mock.patch.object(socket.socket, "connect", no_network)):
            guard.start()
            self.addCleanup(guard.stop)

    def test_each_tool_answers_as_its_docstring_says_and_none_can_write_the_storyboard_or_the_consent_records(self):
        tool = self.tool
        kept = {name: (self.root / name).read_bytes() for name in ("storyboard.json", "ETHICS.md", "COSTS.md")}
        self.assertEqual(json.loads(tool["read_storyboard"]()), read_sb(self.root))          # the contract, as it is on disk
        self.assertRegex(tool["validate"](), r"storyboard\.json is valid: 8 shots[^\n]*\n\n\(exit code 0\)$")
        self.assertRegex(tool["validate"](strict=True), r"(?s)DRAFT.*\(exit code 1\)$")        # strict also refuses drafts

        plan = tool["plan"](mock=True)
        self.assertIn("MISS (new) would build", plan)                                        # what would be regenerated, and why
        self.assertTrue(plan.endswith("(exit code 0)"), plan[-300:])
        self.assertRegex(tool["final_check"](mock=True), r"(?s)no film has been assembled yet.*\(exit code 1\)$")
        self.assertRegex(tool["make_film"](mock=True, strict=True), r"(?s)DRAFT.*\(exit code 1\)$")
        self.assertFalse((self.root / "outputs_mock").exists())                              # a plan builds nothing, and a draft is refused before any stage runs

        self.assertTrue(tool["run_stage"]("script", mock=True).endswith("(exit code 0)"))
        self.assertTrue((self.root / "outputs_mock" / "script" / "index.en.json").exists())
        self.assertRegex(tool["run_stage"]("assemble", mock=True), r"(?s)the \w+ stage has not run yet.*\(exit code 1\)$")   # a stage out of order says which one comes first
        costs = tool["costs"](mock=True)
        self.assertTrue(all(column in costs for column in ("Total latency (s)", "GPU minutes", "List price (USD)")), costs)

        self.assertEqual({name: (self.root / name).read_bytes() for name in kept}, kept)
        self.assertFalse((self.root / "runs.jsonl").exists() or (self.root / "outputs").exists())   # mock runs never touch the real log
        # nothing a tool takes could carry a consent, a confirmation or a line of narration
        self.assertEqual({param for fn in tool.values() for param in inspect.signature(fn).parameters}, {"mock", "strict", "name"})

    def test_plan_with_real_providers_calls_no_model_and_leaves_no_file(self):
        called = []

        def model(*args, **kwargs):
            called.append(kwargs.get("unit") or args[1:3])
            raise AssertionError("a plan called a model")

        before = set(files_of(self.root))
        with mock.patch.object(providers, "text", model), mock.patch.object(providers, "image", model), \
                mock.patch.object(providers, "tts", model), mock.patch.object(providers, "tts_take", model), mock.patch.object(providers, "model_call", model):
            answer = self.tool["plan"]()                                  # mock is off: this is what an agent gets when it says nothing
        self.assertTrue(answer.endswith("(exit code 0)"), answer[-300:])
        self.assertIn("would build", answer)
        self.assertNotIn("mock providers", answer)
        self.assertEqual(called, [])
        self.assertEqual(set(files_of(self.root)), before)                # no outputs/, no runs.jsonl, no job folder

    def test_a_real_person_is_held_back_until_consent_is_a_dated_row_in_ethics(self):
        """Real mode, with the image and text providers replaced by local fakes, so no network is needed."""
        drawn = []

        def fake_image(ctx, stage, unit, prompt, **kw):
            drawn.append(unit)
            return providers._mock_image(ctx, prompt, kw["width"], kw["height"], kw["seed"], unit), {"seed_applied": True}

        def fake_text(ctx, stage, unit, prompt, **kw):
            return '{"character_match": 4, "prompt_adherence": 4, "artifacts": 4, "text_in_image": false}', {}

        sb = read_sb(self.root)                                           # the new author puts a relative into the first shot
        sb["characters"] = [{"id": "aunt", "label": "My aunt", "description": "An old woman in a white shawl, seen from behind.",
                             "reference_prompt": "One figure on a plain background, seen from behind.", "real_person": True,
                             "consent": {"status": "pending", "record": "consent-aunt"}}]
        sb["shots"][0]["characters"] = ["aunt"]
        write_sb(self.root, sb)
        hers, others = sb["shots"][0]["id"], {s["id"] for s in sb["shots"][1:]}
        candidates = range(1, sb["shots"][0]["keyframe"].get("candidates", sb["qa"]["keyframe_candidates"]) + 1)
        ethics = self.root / "ETHICS.md"
        blank = ethics.read_text(encoding="utf-8")
        row = "| consent-aunt | My aunt | A drawn figure, seen from behind | She said yes on the phone | {date} |\n"

        with mock.patch.object(providers, "image", fake_image), mock.patch.object(providers, "text", fake_text):
            answer = self.tool["run_stage"]("keyframes")                  # mock is off: the gate binds real providers
            self.assertIn("BLOCKED: consent not recorded for aunt", answer)
            self.assertEqual({unit.split("_")[0] for unit in drawn}, others)   # every other shot is drawn. Hers is not, and neither is her reference sheet
            index = json.loads((self.root / "outputs" / "keyframes" / "index.json").read_text(encoding="utf-8"))
            self.assertEqual({sid for sid, k in index.items() if k["blocked"]}, {hers})
            self.assertRegex(self.tool["validate"](strict=True), r"(?s)consent for aunt is pending.*\(exit code 1\)$")   # strict also refuses pending consent

            sb["characters"][0]["consent"]["status"] = "recorded"         # an agent can edit the storyboard. That alone records nothing
            write_sb(self.root, sb)
            del drawn[:]
            for text in (blank, blank + row.format(date="")):             # no row in ETHICS.md, then a row without a date
                ethics.write_text(text, encoding="utf-8")
                self.assertRegex(self.tool["validate"](), r"(?s)no dated row for consent-aunt.*\(exit code 1\)$")
                self.assertTrue(self.tool["run_stage"]("keyframes").endswith("(exit code 1)"))
            self.assertEqual(drawn, [])

            ethics.write_text(blank + row.format(date="2026-11-25"), encoding="utf-8")   # the person said yes, and the author wrote down when
            answer = self.tool["run_stage"]("keyframes")
            self.assertTrue(answer.endswith("(exit code 0)"), answer[-300:])
            self.assertEqual(set(drawn), {"ref_aunt"} | {f"{hers}_c{i}" for i in candidates})

    def test_a_stage_name_that_does_not_exist_is_answered_in_words(self):
        try:
            answer = self.tool["run_stage"]("qc", mock=True)              # a name an agent could try: the final-cut check is `qc` on the command line
        except SystemExit as stop:
            self.fail(f"run_stage left through SystemExit({stop.code}) and returned nothing")
        self.assertRegex(answer, r"\(exit code [1-9]\d*\)$")

    def test_a_stage_run_again_on_an_untouched_new_project_changes_nothing(self):
        for name in ("script", "narration"):
            answer = self.tool["run_stage"](name, mock=True)
            self.assertTrue(answer.endswith("(exit code 0)"), f"{name}: {answer[-400:]}")
        index = self.root / "outputs_mock" / "narration" / "index.en.json"
        first = json.loads(index.read_text(encoding="utf-8"))
        again = self.tool["run_stage"]("narration", mock=True)
        self.assertNotIn("built in", again)                               # every line is a cache hit
        self.assertEqual(json.loads(index.read_text(encoding="utf-8")), first)   # so what the next stage reads must be what it read before

    @unittest.skipIf(os.environ.get("HERITAGE_FAST_TESTS"), "full mock film skipped")
    def test_an_agent_can_take_a_new_project_to_a_film_through_the_tools(self):
        tool, out = self.tool, self.root / "outputs_mock"
        write_the_film(self.root)                                         # the agent edits storyboard.json as a normal file
        for name in core.STAGES:                                          # run_stage: each of the six stages, in order
            answer = tool["run_stage"](name, mock=True)
            self.assertTrue(answer.endswith("(exit code 0)"), f"{name}: {answer[-400:]}")
        self.assertTrue(all((out / name).exists() for name in ("film_vertical.mp4", "film_horizontal.mp4")))

        film = tool["make_film"](mock=True)                               # only changed units are regenerated, and nothing changed
        self.assertNotIn("built in", film)
        self.assertIn("== final-cut check", film)
        report = json.loads((out / "qc_report.json").read_text(encoding="utf-8"))
        self.assertTrue(report["passed"], [c for c in report["checks"] if not c["ok"]])

        check = tool["final_check"](mock=True)                            # length, both ratios, loudness, subtitles, end card
        for measured in ("vertical: length", "vertical: size", "horizontal: size", "loudness", "subtitles:", "end card:"):
            self.assertIn(measured, check)
        self.assertRegex(check, r"(?s)final-cut check: PASSED.*\(exit code 0\)$")
        costs = tool["costs"](mock=True)                                  # per stage, from the run log of this mode
        self.assertTrue(all(row in costs for row in ("| narration | mock |", "| keyframes | mock |", "outputs_mock/runs.mock.jsonl")), costs)

        radio = tool["radio_cut"](mock=True)
        self.assertTrue(radio.endswith("(exit code 0)"), radio[-400:])
        self.assertTrue((out / "radio_cut.mp4").exists())
        self.assertFalse((self.root / "runs.jsonl").exists() or (self.root / "outputs").exists())   # mock is never evidence


if __name__ == "__main__":
    unittest.main()
