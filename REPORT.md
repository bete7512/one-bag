# One Bag: report

Bete Goshme, 10 Academy, B2W0, 26 November 2026

## 1. What I set out to make, and for whom

"One Bag" is a short film about the first night I spent far from home: the night I arrived in Addis Ababa from Ankober in late 2019, on my way to Bahir Dar University. It is narrated in Amharic, with English subtitles and an original score: ten shots, 85.2 s, a tall and a wide format (`DESIGN.md`). It is released at https://bete7512.github.io/one-bag/ (`README.md`, "Watch it"), and the repository is https://github.com/bete7512/one-bag.

It is for people who left a small town for a big city, and those who are about to. They should recognise their own first night, and feel that being lost at the start is normal and worth living through (`DESIGN.md`).

An AI coding agent (Claude) wrote the code, the first storyboard and the first wording of the lines, and drafted this report from the repository's record. I told the story, corrected it, proposed the Amharic voice, wrote the final narration myself and confirmed its English subtitles (`README.md`, "How this was built").

## 2. What my audience told me

**User test 1, the radio cut, 25 November.** Three people heard it. None answered the four questions. One wrote: "the voice repeats word ነበር a lot of time ... the pause between the sentence is little bit longer". The other two wrote that they liked it. Two more comments arrived minutes later: change the last word, and "the story it tells would be nicer if improved to send message for audience" (`DESIGN.md`, "User test 1").

Who the three are to me was not recorded, and the two later comments cannot be assigned to a listener or to me. That weakens the test.

What changed (commit `9935183`). I told the coding agent to decide, so the changes are its work. ነበር went from nine uses to five. The last word became አጣጥመው, "savour it". The audience had been "myself, and the friend who was waiting for me that night": it was widened, and the last line now speaks to everyone who leaves home. My own narration later brought ነበር back, six times (`DESIGN.md`).

**User test 2 was not done.** What stood in its place does not count as one: a second coding session reviewed the cut against the brief in five passes, and its findings changed pictures, subtitles and the takes of three lines (`DESIGN.md`).

My own corrections are not a user test either: one voice across the lines (commit `4ed0344`), and the narration, which I wrote myself, twice.

## 3. The hardest problem: one voice, in Amharic

On 25 November at about 23:35 I heard the cut and wrote: "audio continuity ... that audio isnt continued from previous it is alsmot different" (`FAILURES.md`, F10). The eight lines came from three sittings of the Gemini speech model, and their pitch moved by up to 4.5 semitones from line to line (`EXPERIMENTS.md`, E25).

1. **Record again.** Not possible: the day's ten free speech requests were used. I put in a second free-tier key. Google's terms say a user will not attempt to circumvent such limits, and a second key for that purpose is what they mean (F09). No audio made with either Gemini key is in the film.
2. **One take with a seed.** It could not be cut into lines (F10).
3. **Every line alone, with one seed.** The largest step came down to 1.8 semitones (E25).
4. **Another provider.** I proposed Addis AI, which is built for Ethiopian languages. Its voice has a largest step of 1.7 semitones (E26).

By pitch, steps 3 and 4 are level. Addis AI changed the limit: one request per line, no ten a day, nothing to cut. Its speech-to-text matched the script at 0.96 on average, where the text model reached 0.84 (E27).

The new voice brought a fault of its own: it left out the first word of my last line, and the listening check passed the line at 0.96 (F12). Now the first and the last word of every line are checked, and the last line is in its twelfth take (E30). The ten lines match at 0.945 to 1.00 (`DESIGN.md`). These are models' numbers. F10 calls its own "a number, not an ear".

## 4. A suggested practice that beat my instinct: narration line by line

The tip: "Generating narration line by line, one file per shot, makes re-takes cheap and timing easy to adjust" (brief, Appendix B).

It was set aside for a quota reason: ten speech requests a day, eight lines. The coding agent built the stage to speak all lines in one request and cut them apart at the pauses (E20).

What happened (F04):

- One request gave 70.19 s of audio that could not be cut: a margin of 1.24 between the pauses, where the stage accepts 1.5.
- Two ways of cutting agreed on four of the eight lines. The other four were spoken alone, each answered at the first attempt (`runs.jsonl`, run `20261125T171237Z-6f6e51`).

It cost 5 speech requests where 1 was planned, and it put three sittings into one film (section 3). Now every line is a request of its own: a line that comes back alone needs no cutting (E20).

## 5. A suggested practice that did not help as given: the character reference sheet

The tip: "Generate a character and style reference sheet first, then the keyframe for every shot, conditioned on it" (brief, Phase 2).

It was followed, and it failed in three ways.

1. **The sheet copied itself into the scenes (E19).** With a sheet of three poses the young man appeared more than once in 8 of 10 pictures. With one figure seen from behind: 3 of 10.
2. **The reference fixed the layout (E24).** With it he stood in the middle in 5 of 6 pictures, also where the words said he sits. From the words alone: 1 of 6.
3. **With two references the model drew neither scene (E28).** For the brokers' shot none of three candidates showed the scene. From the words alone all four did.

What held him together was thirty words of description with the colours named (E28):

| In the picked pictures | Before | After |
|---|---:|---:|
| Olive green backpack | 0 of 6 | 7 of 7 |
| Plastic sandals | 1 of 5 | 5 of 5 |
| Olive green trousers | 2 of 5 | 4 of 5 |
| Grey or charcoal grey jacket | 2 of 5 | 5 of 5 |

It is one model's reading, and the colours were not the only change. No shot is given the reference picture now. The brief's other tip is what worked: keep the character description attached to every prompt (Appendix B).

## 6. Beyond the floor

One experiment overturned a wrong diagnosis (E17). The first light judge gave 5.0 to fourteen answers of fifteen, and the model was blamed (E15). On the same 12 pictures, asked for scores from 1 to 5, it flagged none of the 7 pictures that the border check measures as bordered. Asked yes or no, it flagged 6. Claude Opus 5.5 with that question flagged all 7, for 0.195 USD against 0.012 USD at list price. Most of the weak judge was the question.

- **The mix, measured (E12):** three faults in a mix that the final-cut check had passed.
- **A clean clone (E23):** with no key and no model call it rebuilt the cut, the last time on the release commit `3fd45b4`, with the two films deleted first: each came back with the same SHA-256.
- **The tall film's subtitles, measured (E31):** they stood 332 to 411 px above the bottom, inside the area that YouTube, Meta and TikTok ask to keep clear, and are now at 682 to 752 px.
- **Tools:** a consent gate in code, `python -m pipeline init` and an MCP server for other people's films (`README.md`).

Built, not run: the language test (E14) and the blind A/B test (E10).

## 7. What it cost

By the run log with 901 calls, 70 of them failed, 4.44 USD was paid for model calls: almost all of it for Claude Opus 5.5 as picture judge and subtitle checker. Cloudflare's paid plan for the pictures is 5 USD a month. Addis AI ran on a sign-up credit of 3.17 USD, of which 0.53 USD is used. Gemini and the Kaggle GPU ran on free tiers. At list price all calls come to 5.86 USD (`COSTS.md`). A Wan 2.2 clip of 3.4 s took 766 to 890 s on a free T4 (E08).

## 8. Consent, labels and licences

Two real people stand behind drawn characters: I, and the friend who waited for me at Lamberet. Both consents are dated rows in `ETHICS.md`. My friend is in one shot, from behind, and his name is nowhere. No photo went to any model, and no voice was cloned. The film ends with a "Made with AI" card. The licence pages were opened and quoted by the coding agent (`ETHICS.md`).

## 9. What is not good yet, and what comes next

- The second user test is missing.
- The voice and the score were chosen by the coding agent from a listening model's numbers and descriptions, on my instruction to decide (E26, E22). No score candidate is heard as a krar.
- Three picked pictures score under 3 with the judge: s03 2.6, s05 1.6, s06 2.8 (E28).
- Four shots show invented faces. They stand for nobody (`ETHICS.md`).
- Three words are still not written by the listener as I wrote them, and both listeners are models (E30).

The next step is the second user test: the released film shown to at least three people who made such a journey, with the four prepared questions (`DESIGN.md`). After that, the voice and the score are chosen by ear from the kept candidates.

