# Design

The design was decided three times. A first version was drafted before anything was generated, from a few sentences. Twelve test pictures were made under it. Then I told the story in full and nearly every shot changed: that is in "The story" below. Then three people heard it, and it got an audience, a message and a new ending: that is in "User test 1". The storyboard carries the short version of the first two sections in its `audience` and `intent` fields.

## Who it is for

People who left a small town for a big city, and those who are about to. My friends who made the same journey watch it first, on their phones.

Until the first test this said "myself, and the friend who was waiting for me that night". That is two people, and a film for two people has nobody to test it on. The first listeners' answers are what widened it: see user test 1.

## What they should feel at the end

They should recognise their own first night, and feel that being lost at the start is normal and worth living through.

## The story

Told by me, by voice, on 25 November 2026, scene by scene. This replaced a first draft that had guessed at fear and at a bag full of books: neither was true.

Around midday in 2019 I left Ankober with one backpack, in the plastic sandals that everybody wears there. A friend came to see me off. Nobody travelled with me. I sat by the window of the bus. The road was gravel as far as Debre Birhan and asphalt after that, and outside there was forest and mountains: the view was amazing. It was night when I reached Lamberet, on the edge of Addis Ababa. My friend, who is about my age, was waiting for me. It was crowded, the buildings were lit, and there were so many cars. At Autobus Tera the brokers came at us from every side asking if we wanted a bed. There were a lot of them, we were confused, and we picked one. The room had one bed. It was not very good and not bad, and it was clean. In the morning we stood in a long queue for the ticket. What I would tell that boy today: experience it.

Five beats:

1. **The goodbye.** Midday in Ankober, one backpack, a friend who came to see me off.
2. **The road.** Gravel, forest and mountains from a bus window, alone.
3. **The city at night.** Lamberet: my friend waiting, crowds, lights, cars.
4. **The confusion.** The brokers at Autobus Tera, and a clean plain room at the end of it.
5. **Now.** The queue the next morning, and what I say today to everyone who leaves home.

What the film says to them, since the first test: the first night is always confusing. Do not run from it. Savour it. The first cut ended on one word to my younger self, and a listener's comment asked whom the story was for.

## Choices and why

Rewritten with the storyboard on 25 November, after the story was told in full. To revise after the user tests.

| Choice | Why |
|---|---|
| Confusion, not fear | That is how I tell it. The first draft made the night frightening because a frightened boy is an easy story. What happened was brokers on every side and two friends who had to pick a bed. |
| One object runs through the film: the backpack | It is on my shoulders at the start, on the floor of the room, and at my feet at the end. An object stays the same across shots more easily than a face. |
| The plastic sandals | I arrived in the moulded plastic sandals that are everywhere at home. They are drawn in every picture of me in 2019, next to the backpack. The first pictures had me in leather boots. |
| Nobody's likeness is in the film | My friend is drawn from behind only, as he agreed. I am drawn from behind in every shot but one: on the bus seat I am seen from the side, looking out of the window. Drawn from the words alone, the model seated me as the voice says and turned me only half away (E24). That face is the model's invention. No photo of me, of him or of anyone was ever given to a model. |
| My friend is drawn in one shot only, with the brokers | He agreed to one scene. After I told the story in full, the storyboard had him in three: at Lamberet, with the brokers, and in the queue. Two things brought it back to one. It was more than he had said yes to. And the image model could not draw two people from behind in a crowd: of eight pictures for Lamberet and eight for the queue, over four runs, none was usable (F05 in `FAILURES.md`). So at Lamberet and in the queue I am alone in the frame, and the voice says he was there. |
| The friend who said goodbye in Ankober is heard about, not shown | Showing him would put a third real person in the film. The voice says he came. |
| The brokers are nobody | They are strangers, and the shot is about how many they were. I asked for their faces in shadow or turned away. In the picture that was kept the model lit them all the same. They are its invention and no real person's. |
| One shot moves, the road | Four shots were made as real video on a free GPU. The bus on the gravel road works: something in the picture can move, and it does. The other three do not: in the blurred city lights the model painted things that were not there, at Lamberet the minibuses melt from frame to frame, and on the balcony stains spread over my shirt. Those three stay as slow pans over their stills (E08 in `EXPERIMENTS.md`). |
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
| s05 Autobus Tera, from far | extreme wide | Where the night is going: the big bus station, seen whole and from far, before we are in the middle of it. No words, only the place. |
| s06 Do you want a bed? | medium | The heart of the story as he tells it: not fear but confusion. Brokers on every side offering a bed, and two friends who have to pick one. |
| s07 The room | wide | Quiet after the noise, and exactly as he described it: one bed, not very good, not bad, clean. The backpack is the only thing of his in it. |
| s08 The queue | wide | The morning after: the city is ordinary again, a long line of people waiting for a ticket. He is the last one in it, seen from behind. |
| s09 Now | medium | The answer to the whole night, in two words of his. The same city, seen calmly by the man that boy became, with the same kind of backpack at his feet. |

## User test 1: the radio cut

Done on the evening of 25 November 2026. I sent three people the radio cut as it was at 20:14 that evening: the eight lines spoken, placeholder music, subtitles on a black screen, 80 seconds (the storyboard of commit `962e907`). With it went four questions:

1. In one sentence, what happened?
2. Where did you feel something? Where did you get lost or bored?
3. Was any word hard to understand, or said strangely?
4. What would you say if you forwarded this?

They did not answer question by question. They wrote what they thought, and this is all of it, as they wrote it:

| # | Who | Date | What they said, in their words |
|---|---|---|---|
| 1 | not noted | 25 Nov | "the video and the subtitle is nice. i liked it. one suggestion the voice repeats word ነበር a lot of time would be nicer adjusting that and also the pause between the sentence is little bit longer" |
| 2 | not noted | 25 Nov | "Very nice i liked it" |
| 3 | not noted | 25 Nov | "very nice i liked it looking to forward to see the video" |

Two more comments reached the working session a few minutes later, in these words: "also one last comment about last word ኑረው would be nice to change with other", and "in general the story it tells would be nicer if improved to send message for audience".

What is missing from this record: who the three are to me, and whether the two later comments are a listener's or mine. I passed the answers to the coding agent as they stand above and told it to decide the changes itself. The changes below are its work. I confirm them when I confirm the lines.

**What I learned:**

- Two of three said they liked it and nothing more. That is kind, and it is not information. Nobody answered "what happened?", so I still do not know what a listener takes the story to be.
- The one listener who gave a suggestion named two things that can be counted. The word for "was", ነበር, was in the eight lines nine times: the lines had been drafted from my English telling, and every English "was" had become one. And the voice, which had been asked to sound unhurried, stopped for up to 1.3 seconds between two sentences of one line.
- The comment about a message is the one that went deepest. The film told what happened in order and ended on one word of advice. It did not say whom it was speaking to.

**What changed in the storyboard:** the four rows dated 25 Nov in the table at the end of this file.

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
| 25 Nov | "the voice repeats word ነበር a lot of time" | The lines of s01 and s04 are rewritten without it, and s06 loses its ነበሩ: nine uses become five. s03 and s07 follow when the speech quota is fresh, which leaves one. | `9935183` |
| 25 Nov | "the pause between the sentence is little bit longer" | `voice.max_pause_s` is 0.6: sixteen silences inside the lines were shortened, and the speech of the eight old lines went from 58.2 to 53.6 s. The shortest length of four shots came down: s02 from 7 to 6 s, s03 from 8 to 7, s05 from 5 to 4, s08 from 7 to 5.5. | `9935183` |
| 25 Nov | "last word ኑረው would be nice to change with other" | The film ends on አጣጥመው, "savour it". | `9935183` |
| 25 Nov | "the story it tells would be nicer if improved to send message for audience" | `audience` and `intent` are rewritten. The last line (s09) now speaks to everyone who leaves home: "the first night is always confusing. Do not run from it. Savour it." The first line gives the year. The brokers' line says the offers came from every side. | `9935183` |
| 26 Nov | The author, after hearing the cut: "audio continuity ... that audio isnt continued from previous it is alsmot different" | Every line is recorded again in a request of its own, with one seed and a shorter style (`voice.seed`, `voice.style`, `voice.one_take`). The largest step in pitch between neighbouring lines went from 4.5 to 1.8 semitones (`outputs/experiments/E25/results.json`). | `4ed0344` |
| 26 Nov | The author: "it says we got ticket in morning then that night confused me the story order isntt corrrect" | The last line (s09) begins "Today, remembering that first night". The film runs night, morning, today. | `4ed0344` |
| 26 Nov | The author: "መስከረም 2012 is appropriate order" | The first line (s01) opens with መስከረም ሁለት ሺህ አሥራ ሁለት. | `4ed0344` |
| 26 Nov | The author: "still many ነበር are being used" | The lines of s02, s03 and s07 are rewritten as well. No line holds the word now. | `4ed0344` |
| 26 Nov | The author: "you bring some shit pic ... make sure bringing important picture for the video not just for trial" | No picture goes into the cut on the judge's score alone any more: each is looked at and pinned (`keyframe.pick`). The shot of blurred lights (s05) is replaced by the bus station at night. Three new candidates for Ankober were worse than the picture it had and were thrown out. | `4ed0344` |
