# Design

The design was decided twice. A first version was drafted before anything was generated, from a few sentences. Twelve test pictures were made under it. Then I told the story in full and nearly every shot changed: that is in "The story" below. The storyboard carries the short version of the first two sections in its `audience` and `intent` fields, and the pipeline warns while they are still marked DRAFT.

## Who it is for

**DRAFT, to confirm or rewrite in my own words.** Myself, and the friend who was waiting for me that night. We watch it on a phone.

## What they should feel at the end

**DRAFT, to confirm or rewrite.** We should remember that night the way it was, confusing and new, and be glad we lived it. Experience it.

## The story

Told by me, by voice, on 25 November 2026, scene by scene. This replaced a first draft that had guessed at fear and at a bag full of books: neither was true.

Around midday in 2019 I left Ankober with one backpack, in the plastic sandals that everybody wears there. A friend came to see me off. Nobody travelled with me. I sat by the window of the bus. The road was gravel as far as Debre Birhan and asphalt after that, and outside there was forest and mountains: the view was amazing. It was night when I reached Lamberet, on the edge of Addis Ababa. My friend, who is about my age, was waiting for me. It was crowded, the buildings were lit, and there were so many cars. At Autobus Tera the brokers came at us from every side asking if we wanted a bed. There were a lot of them, we were confused, and we picked one. The room had one bed. It was not very good and not bad, and it was clean. In the morning we stood in a long queue for the ticket. What I would tell that boy today: experience it.

Five beats:

1. **The goodbye.** Midday in Ankober, one backpack, a friend who came to see me off.
2. **The road.** Gravel, forest and mountains from a bus window, alone.
3. **The city at night.** Lamberet: my friend waiting, crowds, lights, cars.
4. **The confusion.** The brokers at Autobus Tera, and a clean plain room at the end of it.
5. **Now.** The queue the next morning, and the two words I would say to that boy.

## Choices and why

Rewritten with the storyboard on 25 November, after the story was told in full. To revise after the user tests.

| Choice | Why |
|---|---|
| Confusion, not fear | That is how I tell it. The first draft made the night frightening because a frightened boy is an easy story. What happened was brokers on every side and two friends who had to pick a bed. |
| One object runs through the film: the backpack | It is on my shoulders at the start, on the floor of the room, and at my feet at the end. An object stays the same across shots more easily than a face. |
| The plastic sandals | I arrived in the moulded plastic sandals that are everywhere at home. They are drawn in every picture of me in 2019, next to the backpack. The first pictures had me in leather boots. |
| Every person is seen from behind | I am drawn from behind in every shot I am in, and so is my friend, as he agreed. Faces are where image models drift, and nobody's likeness is generated. |
| My friend is drawn in one shot only, with the brokers | He agreed to one scene. After I told the story in full, the storyboard had him in three: at Lamberet, with the brokers, and in the queue. Two things brought it back to one. It was more than he had said yes to. And the image model could not draw two people from behind in a crowd: of eight pictures for Lamberet and eight for the queue, over four runs, none was usable (F05 in `FAILURES.md`). So at Lamberet and in the queue I am alone in the frame, and the voice says he was there. |
| The friend who said goodbye in Ankober is heard about, not shown | Showing him would put a third real person in the film. The voice says he came. |
| The brokers have no faces | They are strangers, and the shot is about how many they were. Their faces are in shadow or turned away. |
| One shot moves, the road | Two shots were made as real video on a free GPU: the bus on the gravel road, and the city lights. The bus works: something in the picture can move, and it does. The lights did not: the model painted things into the blur that were not there (E08 in `EXPERIMENTS.md`). The shots with a person in them stay as slow pans. They were not tried as video: there was GPU time for two clips that evening, and I did not want to spend it on a figure that might change shape from frame to frame. |
| Day, then night, then morning | Midday and mountains for the road, night and electric light for the city, gold morning light for the queue. The light tells the time, so the voice does not have to. |
| Painted, grainy look instead of photographic | It suits a memory, it hides the softness of enlarged crops, and it does not pretend to be footage of real events. |
| Amharic narration, English subtitles | The story happened in Amharic. Subtitles let colleagues and the diaspora follow. |
| A prebuilt voice, not my own | No voice is cloned. |
| A krar and washint score in the tizita mood | Tizita is the music of memory and longing, which is what the film is. |

## A reason for every shot

The source of truth is the `reason` field of each shot in `storyboard.json`. The schema refuses a shot without one.

| Shot | Size | Reason |
|---|---|---|
| s01 Midday, Ankober | medium | Where it starts: a small highland town at midday and one backpack. The goodbye is said in the voice, because the friend who came to say it is not shown. |
| s02 The gravel road | extreme wide | The journey itself, and the scale of it: one small bus on a gravel road under forested mountains. He said the view was amazing, so the shot is wide and takes its time. |
| s03 The window seat | pov | The same journey from where he sat. Nobody travelled with him, so the shot is his alone: a window, and what was outside it. |
| s04 Lamberet at night | wide | The arrival, and the turn of the film: daylight and mountains give way to night, crowds, lit buildings and cars. He is alone in the frame, facing all of it. His friend is somewhere in that crowd, and the voice says so. |
| s05 Across the city | pov | A breath between two crowded places, with no words: only the lights of a city he did not know yet, passing a window. |
| s06 Do you want a bed? | medium | The heart of the story as he tells it: not fear but confusion. Brokers on every side offering a bed, and two friends who have to pick one. |
| s07 The room | wide | Quiet after the noise, and exactly as he described it: one bed, not very good, not bad, clean. The backpack is the only thing of his in it. |
| s08 The queue | wide | The morning after: the city is ordinary again, a long line of people waiting for a ticket. He is the last one in it, seen from behind. |
| s09 Now | medium | The answer to the whole night, in two words of his. The same city, seen calmly by the man that boy became, with the same kind of backpack at his feet. |

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