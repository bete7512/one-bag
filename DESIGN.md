# Design

Decided before anything was generated. The storyboard carries the short version of the first two sections in its `audience` and `intent` fields, and the pipeline warns while they are still marked DRAFT.

## Who it is for

**DRAFT, to confirm or rewrite in my own words.** My family, and the friends who also left home to study. They watch on a phone, mostly in vertical, and they forward what moves them.

## What they should feel at the end

**DRAFT, to confirm or rewrite.** That fear at the start of something new is normal, and that it passes.

## The story

In 2019 I left Ankober by bus with one bag: some clothes and some books. I reached Addis Ababa as the evening was starting. At Lamberet my friend and I took a taxi across the city to Autobus Tera. He knew the city and I did not. It was almost night when we got there, and that is where the fear came: the crowd, the sound, a city full of light. I followed him through it to find a room near the station, to be close to the bus for Bahir Dar. What I would tell that boy today: do not be scared, there is a lot to learn in life.

Five beats:

1. **The bag.** One bag, clothes and books.
2. **The crossing.** A taxi through a city I could not read.
3. **The fear.** Autobus Tera: too many people, too much sound, too much light.
4. **The room.** Following my friend to a room near the station. Quiet.
5. **Now.** The same city, seen calmly, and the sentence I would say to that boy.

## Choices and why

First version, written with the storyboard draft. To revise after the user tests.

| Choice | Why |
|---|---|
| One object runs through the film: the bag with the books | It opens the film and comes back at the end, where "a lot to learn" gives the books their meaning. An object also stays the same across shots more easily than a face. |
| One close-up of a face, in the dark (s08) | Faces are where image models drift. One face shot, half lit, carries the fear without asking the model to keep an identity across ten shots. |
| The friend is only seen from behind | He is a real person. From behind he is "one back to follow", which is what he was that night, and less of his likeness is generated. No picture of him is made until his consent is recorded. |
| The crowd is shown as light and blur (s05) | Crowds are a known weak spot (hands, faces). Blur is also how it felt. |
| The light follows the real clock of that day | Daylight on the road, dusk in the taxi, nightfall at Autobus Tera, night in the room. That is how it happened: evening was starting when I reached Addis, and it was almost night at the station. The fear arrives with the dark, and the last shot answers it in warm light. |
| Painted, grainy look instead of photographic | It suits a memory, it hides the softness of enlarged crops, and it does not pretend to be footage of real events. |
| Amharic narration, English subtitles | The story happened in Amharic. Subtitles let colleagues and the diaspora follow. |
| A prebuilt voice, not my own | No voice is cloned. |
| A krar and washint score in the tizita mood | Tizita is the music of memory and longing, which is what the film is. |

## A reason for every shot

The source of truth is the `reason` field of each shot in `storyboard.json`. The schema refuses a shot without one.

| Shot | Size | Reason |
|---|---|---|
| s01 The bag | insert | Opens on the one object that carries the whole film. Sets up the last line about learning. |
| s02 The road out | extreme wide | Where he comes from, and how small he is against the journey. A breath before the city. |
| s03 Taxi across the city | point of view | He is carried through a city he cannot read. Lights through glass need no faces. |
| s04 Autobus Tera | wide | The fear needs a place. The wide shot makes him small and the station enormous. |
| s05 Too much | point of view | Inside his head: no faces, only noise and light. The one shot that should feel too fast. |
| s06 Follow him | over the shoulder | Trust replaces fear: one back to follow. The grip on the bag keeps the object in frame. |
| s07 The room | wide | Quiet after the noise. The pause between home and what comes next. |
| s08 Awake | close-up | The only close-up of his face: the fear made small and private. The book links to the ending. |
| s09 Morning bus | wide | He goes anyway. Shown, not said. |
| s10 Now | medium | The answer to the fear: the same city, seen calmly. The book returns for the last line. |

## User test 1: the radio cut

Not done yet. The radio cut is `outputs/radio_cut.mp4`: narration over placeholder music on a black screen, with subtitles.

**Who:** at least three people from the audience above. **How:** play it once without explaining anything, then ask.

1. In one sentence, what happened?
2. Where did you feel something? Where did you get lost or bored?
3. Was any word hard to understand, or said strangely?
4. What would you say if you forwarded this?

| # | Who (relation, not name) | Date | Language they follow | What they said, in their words | Where they reacted |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

**What I learned:**

**What I will change in the storyboard:**

## User test 2: the near-final cut

Not done yet. Same people if possible, plus at least one new viewer who has not heard the radio cut.

1. Did the pictures match what you imagined from the voice?
2. Is the young man the same person in every shot?
3. Could you read the subtitles in time? Was the music ever in the way of the voice?
4. What is the one thing you would cut or change?

| # | Who (relation, not name) | Date | Watched vertical or horizontal | What they said, in their words | Where they reacted |
|---|---|---|---|---|---|
| 1 | | | | | |
| 2 | | | | | |
| 3 | | | | | |

**What I learned:**

**What I changed:**

## Changes made because of the tests

One row per change, so the storyboard's history can be read against what people said.

| Date | What a viewer said | What changed in `storyboard.json` | Commit |
|---|---|---|---|
| | | | |