"""Offline tests of the author's desk. No API keys and no model: the server listens on 127.0.0.1 and the providers are the mock ones.

    HERITAGE_FAST_TESTS=1 python -m unittest discover -s tests
"""
import http.client
import json
import os
import re
import tempfile
import threading
import unittest
from pathlib import Path

from pipeline import core, desk, keyframes, narration, script
from test_pipeline import make_project, read_sb

REPO = Path(__file__).resolve().parent.parent

# A storyboard in miniature, written the way the real one is: small objects on one line, the rest a member per line.
HAND = """{
  "title": "A test",
  "language": {"narration": "am", "subtitles": "en"},
  "music": {
    "seeds": [11, 22],
    "chosen": null,
    "cues": [
      {"at_shot": "s01", "note": "A brace } and a quote \\" inside a sentence."}
    ]
  },
  "shots": [
    {
      "id": "s01",
      "keyframe": {
        "prompt": "A bag on a bed.",
        "seed": 101
      },
      "narration": {
        "am": "ሰላም።",
        "en": "Hello, \\"friend\\"."
      },
      "review": {"confirmed": false, "note": "A draft: say it in your own words."}
    },
    {
      "id": "s02",
      "keyframe": {"prompt": "A road.", "seed": 102},
      "narration": null
    }
  ]
}"""


def changed(old: str, new: str) -> tuple[str, str]:
    """What differs between two texts, once everything they share at the start and at the end is set aside."""
    shortest = min(len(old), len(new))
    head = next((i for i in range(shortest) if old[i] != new[i]), shortest)
    tail = next((i for i in range(shortest - head) if old[-1 - i] != new[-1 - i]), shortest - head)
    return old[head:len(old) - tail], new[head:len(new) - tail]


class ScannerTests(unittest.TestCase):
    """An edit changes the text of one value. A `json.dumps` rewrite would reformat every line of a file written by hand."""

    def test_one_value_changes_and_every_other_byte_stays(self):
        cases = [
            ("shots.s01.review.confirmed", True, '{"confirmed": false, "note"', '{"confirmed": true, "note"'),
            ("shots.s01.narration.am", "አዲስ መስመር።", '"am": "ሰላም።"', '"am": "አዲስ መስመር።"'),
            ("shots.s01.narration.en", 'He said "go".', '"en": "Hello, \\"friend\\"."', '"en": "He said \\"go\\"."'),
            ("music.chosen", 2, '"chosen": null', '"chosen": 2'),
            ("music.cues.0.note", "Krar alone.", '"note": "A brace } and a quote \\" inside a sentence."', '"note": "Krar alone."'),   # a list item by its index
            ("shots.s02.narration", {"am": "ሰላም።"}, '"narration": null', '"narration": {"am": "ሰላም።"}'),
        ]
        for path, value, before, after in cases:
            with self.subTest(path):
                self.assertEqual(HAND.count(before), 1)
                self.assertEqual(desk.edit_text(HAND, path.split("."), value), HAND.replace(before, after))

    def test_the_hand_written_storyboard_keeps_its_formatting(self):
        text = (REPO / "storyboard.json").read_bytes().decode("utf-8")
        sb = json.loads(text)
        sentence = "Nobody yet: this sentence is a test."
        was, now = changed(text, desk.edit_text(text, ["audience"], sentence))
        self.assertIn(was, json.dumps(sb["audience"], ensure_ascii=False))       # nothing outside the old sentence was touched
        self.assertIn(now, json.dumps(sentence))
        for shot in sb["shots"]:
            if not shot.get("review"):
                continue
            flipped = not shot["review"]["confirmed"]
            new = desk.edit_text(text, ["shots", shot["id"], "review", "confirmed"], flipped)
            was, now = changed(text, new)
            self.assertIn(was, json.dumps(not flipped), shot["id"])              # a few letters of "false" became a few letters of "true"
            self.assertIn(now, json.dumps(flipped), shot["id"])
            self.assertEqual(new.count("\n"), text.count("\n"))

    def test_a_missing_key_is_added_the_way_its_object_is_written(self):
        cases = [
            # a member per line
            ("shots.s01.keyframe.pick", 2, '"seed": 101\n      }', '"seed": 101,\n        "pick": 2\n      }'),
            # on one line
            ("shots.s02.keyframe.pick", 1, '{"prompt": "A road.", "seed": 102}', '{"prompt": "A road.", "seed": 102, "pick": 1}'),
            ("language.dubbing", "ti", '{"narration": "am", "subtitles": "en"}', '{"narration": "am", "subtitles": "en", "dubbing": "ti"}'),
            # after a member that ends in a list
            ("music.chosen_reason", "It leaves room for the voice.", '    ]\n  },', '    ],\n    "chosen_reason": "It leaves room for the voice."\n  },'),
            # the object the key belongs in is missing too
            ("shots.s02.review.confirmed", True, '"narration": null\n    }', '"narration": null,\n      "review": {"confirmed": true}\n    }'),
        ]
        for path, value, before, after in cases:
            with self.subTest(path):
                self.assertEqual(HAND.count(before), 1)
                new = desk.edit_text(HAND, path.split("."), value)
                self.assertEqual(new, HAND.replace(before, after))
                wanted = json.loads(HAND)
                desk.set_in(wanted, path.split("."), value)
                self.assertEqual(json.loads(new), wanted)

    def test_a_path_that_leads_nowhere_is_refused(self):
        for path in ("shots.s02.narration.am", "shots.s09.review.confirmed", "title.words"):   # a shot without words, no such shot, a sentence is not an object
            with self.subTest(path):
                with self.assertRaises(desk.Refused):
                    desk.edit_text(HAND, path.split("."), "x")
                with self.assertRaises(desk.Refused):
                    desk.set_in(json.loads(HAND), path.split("."), "x")


class Project(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = make_project(Path(self._tmp.name))
        self.file = self.root / "storyboard.json"
        # two marks only a hand leaves in a JSON file: a rewrite of the whole file would lose them, and a test would see it
        text = self.file.read_text(encoding="utf-8").replace('"version": ', '"version":   ', 1) + "\n"
        self.file.write_text(text, encoding="utf-8")
        self.before = self.file.read_bytes()

    def refused(self, path: str, value, why: str, **kw) -> None:
        with self.assertRaisesRegex(desk.Refused, why):
            desk.apply_edit(self.root, path, value, **kw)
        self.assertEqual(self.file.read_bytes(), self.before)
        self.assertEqual(sorted(p.name for p in self.root.glob("tmp-*")), [])


class EditTests(Project):
    """An edit is checked like any storyboard before it is written, and written in one step."""

    def test_an_edit_is_saved_and_nothing_else_in_the_file_moves(self):
        text = self.before.decode("utf-8")
        result = desk.apply_edit(self.root, "audience", "  My family, on their phones.\n", seen=desk.stamp(text))
        new = self.file.read_bytes().decode("utf-8")
        self.assertEqual(new, text.replace('"DRAFT, a test audience."', '"My family, on their phones."'))   # the stray spaces are not saved
        self.assertEqual(result, {"changed": True, "value": "My family, on their phones.", "seen": desk.stamp(new)})
        again = desk.apply_edit(self.root, "audience", "My family, on their phones.", seen=result["seen"])
        self.assertEqual((again["changed"], self.file.read_bytes().decode("utf-8")), (False, new))

    def test_a_key_the_file_does_not_have_yet_is_saved_too(self):
        sb = read_sb(self.root)
        sb["music"].pop("chosen_reason", None)                                  # whatever the real film says by now
        self.file.write_text(json.dumps(sb, ensure_ascii=False, indent=2), encoding="utf-8")
        text = self.file.read_bytes().decode("utf-8")
        desk.apply_edit(self.root, "music.chosen_reason", "It leaves room for the voice.")
        sb["music"]["chosen_reason"] = "It leaves room for the voice."
        self.assertEqual(read_sb(self.root), sb)
        self.assertEqual(changed(text, self.file.read_bytes().decode("utf-8")), ("", ',\n    "chosen_reason": "It leaves room for the voice."'))

    def test_an_invalid_edit_is_refused_and_the_file_is_unchanged(self):
        sb = read_sb(self.root)
        shot = next(s for s in sb["shots"] if s["narration"])
        sid, lang = shot["id"], sb["language"]["narration"]
        candidates = shot["keyframe"].get("candidates", sb["qa"]["keyframe_candidates"])
        self.refused("music.chosen", len(sb["music"]["seeds"]) + 1, "music.chosen is")                 # a candidate that does not exist
        self.refused(f"shots.{sid}.keyframe.pick", candidates + 1, "pick")
        self.refused(f"shots.{sid}.keyframe.pick", 1.0, "whole number")
        self.refused(f"shots.{sid}.review.confirmed", "yes", "would not be valid")                     # not a yes or no
        self.refused(f"shots.{sid}.narration.{lang}", "   ", "would not be valid")                     # a line with no words
        self.refused("audience", "My family.", "changed on disk", seen="0123456789abcdef")             # made against another state of the file

    def test_consent_is_never_changed_from_the_desk(self):
        ethics = (self.root / "ETHICS.md").read_bytes()
        person = read_sb(self.root)["characters"][0]["id"]
        for path, value in ((f"characters.{person}.consent.status", "recorded"), (f"characters.{person}.consent", {"status": "not_required"}),
                            (f"characters.{person}.real_person", False), ("characters.0.consent.record", "consent-author"), ("characters", [])):
            with self.subTest(path):
                self.refused(path, value, "Consent is not changed from this page")
        for path, value in (("models.image", "another-model"), ("shots.s01.keyframe.prompt", "Another picture, in another place."),
                            ("shots.s01.review.note", ""), ("title", "Another film")):
            with self.subTest(path):
                self.refused(path, value, "is not edited from this page")
        self.assertEqual((self.root / "ETHICS.md").read_bytes(), ethics)


class PageTests(Project):
    """One round trip through the server: read the page, save an edit, read the file."""

    def setUp(self):
        super().setUp()
        self.ctx = core.make_ctx(root=self.root, mock=True, quiet=True)
        self.ctx.sleep = lambda seconds: None
        state: dict = {}
        script.run(self.ctx, state)
        narration.run(self.ctx, state)
        keyframes.run(self.ctx, state)
        self.calls = len(core.read_jsonl(self.ctx.runlog))
        self.server = desk.Desk(self.ctx, 0)                                    # port 0: any free port
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)

    def ask(self, method: str, path: str, body: dict | None = None, **headers) -> tuple[int, str, bytes]:
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=60)
        try:
            data = None if body is None else json.dumps(body).encode("utf-8")
            conn.request(method, path, body=data, headers={**({"Content-Type": "application/json"} if data else {}), **headers})
            reply = conn.getresponse()
            return reply.status, reply.getheader("Content-Type"), reply.read()
        finally:
            conn.close()

    def edit(self, path: str, value, seen: str) -> tuple[int, dict]:
        status, _, body = self.ask("POST", "/edit", {"path": path, "value": value, "seen": seen})
        return status, json.loads(body)

    def test_the_page_an_edit_and_the_file(self):
        sb = read_sb(self.root)
        status, kind, body = self.ask("GET", "/")
        page = body.decode("utf-8")
        self.assertEqual((status, kind), (200, "text/html; charset=utf-8"))
        for shot in sb["shots"]:
            self.assertIn(f"{shot['id']} &middot;", page)
            self.assertIn(f"data-path='shots.{shot['id']}.review.confirmed'", page)
            self.assertIn(f"data-path='shots.{shot['id']}.keyframe.pick'", page)
        self.assertIn("it runs no stage and calls no model", page)
        self.assertNotIn("<button", page)                                       # nothing to press: a control saves what it shows
        self.assertNotIn("<form", page)
        self.assertNotRegex(page, r"data-path='[^']*(consent|real_person|characters)")
        self.assertNotRegex(page, r"https?://")                                 # nothing is loaded from elsewhere
        for person in sb["characters"]:
            self.assertIn(f"<td>{person['consent']['status']}</td>", page)      # consent is shown, as text

        seen = re.search(r'data-seen="([0-9a-f]{16})"', page)[1]
        self.assertEqual(seen, desk.stamp(self.before.decode("utf-8")))
        pictures = re.findall(r"/media/keyframes/s\d\d_c\d__[0-9a-f]{16}\.jpg", page)
        candidates = sum(s["keyframe"].get("candidates", sb["qa"]["keyframe_candidates"]) for s in sb["shots"])
        self.assertEqual(len(set(pictures)), candidates)                        # every candidate of every shot, cut from its kept original
        status, kind, body = self.ask("GET", pictures[0])
        self.assertEqual((status, kind, body[:3]), (200, "image/jpeg", b"\xff\xd8\xff"))
        status, kind, body = self.ask("GET", re.search(r"/media/narration/s\d\d__[0-9a-f]{16}\.wav", page)[0])
        self.assertEqual((status, kind, body[:4]), (200, "audio/wav", b"RIFF"))

        shot = sb["shots"][0]
        path, value = f"shots.{shot['id']}.review.confirmed", not (shot.get("review") or {}).get("confirmed", False)
        status, reply = self.edit(path, value, seen)
        self.assertEqual((status, reply["ok"], reply["changed"]), (200, True, True))
        text = self.file.read_bytes().decode("utf-8")
        self.assertEqual(read_sb(self.root)["shots"][0]["review"]["confirmed"], value)
        self.assertEqual(reply["seen"], desk.stamp(text))
        if shot.get("review"):
            was, now = changed(self.before.decode("utf-8"), text)
            self.assertIn(was, json.dumps(not value))
            self.assertIn(now, json.dumps(value))

        self.before = self.file.read_bytes()
        status, reply = self.edit("audience", "My family, on their phones.", seen)             # the page's stamp is out of date now
        self.assertEqual((status, reply["ok"]), (409, False))
        self.assertIn("changed on disk", reply["error"])
        status, reply = self.edit(f"characters.{sb['characters'][0]['id']}.consent.status", "recorded", desk.stamp(text))
        self.assertEqual((status, reply["ok"]), (409, False))
        self.assertIn("Consent is not changed", reply["error"])
        self.assertEqual(self.ask("POST", "/edit", {"path": "audience"})[0], 400)
        self.assertEqual(self.ask("GET", "/", Host="film.example")[0], 403)                    # reached under another name: not this machine's page
        self.assertEqual(self.file.read_bytes(), self.before)

        status, kind, body = self.ask("GET", "/plan")
        plan = body.decode("utf-8")
        self.assertEqual((status, kind), (200, "text/plain; charset=utf-8"))
        for stage in core.STAGES:
            self.assertIn(f"== {stage}  (plan only, no model is called)", plan)
        self.assertRegex(plan, r"\[keyframes\] s\d\d_c1 +HIT")
        self.assertEqual(len(core.read_jsonl(self.ctx.runlog)), self.calls)     # the desk made no model call, mock or real

        if os.name == "posix":                                                  # elsewhere two servers may share a port, and this would wait for ever
            with self.assertRaisesRegex(core.PipelineError, "Choose another port"):
                desk.run(self.ctx, self.server.server_address[1])               # a second desk on a port that is taken says so


if __name__ == "__main__":
    unittest.main()
