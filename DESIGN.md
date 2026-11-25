# Design

The design was decided three times. A first version was drafted before anything was generated, from a few sentences. Twelve test pictures were made under it. Then I told the story in full and nearly every shot changed: that is in "The story" below. Then three people heard it, and it got an audience, a message and a new ending: that is in "User test 1". On 26 November a review of the cut found faults in the pictures and the subtitles, and seven shots were drawn again. The same night I wrote the narration myself, and it replaced the lines the coding agent had drafted: both are in the last two sections of this file. The storyboard carries the short version of the first two sections in its `audience` and `intent` fields.

## Who it is for

People who left a small town for a big city, and those who are about to. My friends who made the same journey watch it first, on their phones.

Until the first test this said "myself, and the friend who was waiting for me that night". That is two people, and a film for two people has nobody to test it on. The first listeners' answers are what widened it: see user test 1.

## What they should feel at the end

They should recognise their own first night, and feel that being lost at the start is normal and worth living through.

## The story

Told by me, by voice, on 25 November 2026, scene by scene. This replaced a first draft that had guessed at fear and at a bag full of books: neither was true. The pictures are still drawn from this telling. The words of the film are not these: they are the narration I wrote on 26 November, which is given further down.

Around midday in 2019 I left Ankober with one backpack, in the plastic sandals that everybody wears there. A friend came to see me off. Nobody travelled with me. I sat by the window of the bus. The road was gravel as far as Debre Birhan and asphalt after that, and outside there was forest and mountains: the view was amazing. It was night when I reached Lamberet, on the edge of Addis Ababa. My friend, who is about my age, was waiting for me. It was crowded, the buildings were lit, and there were so many cars. At Autobus Tera the brokers came at us from every side asking if we wanted a bed. There were a lot of them, we were confused, and we picked one. The room had one bed. It was not very good and not bad, and it was clean. In the morning we stood in a long queue for the ticket. What I would tell that boy today: experience it.

Five beats, as the narration now tells them:

1. **Leaving.** I have finished twelfth grade and am assigned to Bahir Dar University. The journey starts in Ankober, with one backpack and a mind full of questions.
2. **The road.** Debre Birhan, then Addis Ababa, then Bahir Dar. From the window the land keeps changing.
3. **The city at dusk.** Autobus Tera: my friend meets me, people move every way, cars pass, brokers ask if we want a bed.
4. **Too much at once.** A moment of confusion, and then a room with one bed, clean enough to rest.
5. **The morning, and now.** The queue for a ticket to go on, and what I say today to everyone who leaves the world they know.

What the film says to them: the first night is always confusing. Do not run. Savour it. The first cut ended on one word to my younger self, and a listener's comment asked whom the story was for.

## Choices and why

Rewritten with the storyboard on 25 November, after the story was told in full. To revise after the user tests.

| Choice | Why |
|---|---|
| Confusion, not fear | That is how I tell it. The first draft made the night frightening because a frightened boy is an easy story. What happened was brokers on every side and two friends who had to pick a bed. |
| One object runs through the film: the backpack | It is on my shoulders at the start, on the seat beside me on the bus, on the floor of the room, and at my feet at the end. An object stays the same across shots more easily than a face, but only once its colour is written down. Until 26 November the description said "one simple backpack", and it came out sage green, tan, charcoal and brown. Now it says "olive green canvas", and one model's reading of the seven pictures gives olive green seven times (E28 in `EXPERIMENTS.md`). |
| The plastic sandals | I arrived in the moulded plastic sandals that are everywhere at home. The first pictures had me in leather boots. In the cut of 26 November, 01:13, one picture of five had the sandals and the others had leather sandals or shoes. After the redraw the same reading finds plastic sandals in all five pictures of me in 2019 (E28). My friend has them too in the brokers' picture. That is the model's choice: I did not ask for it. |
| Nobody's likeness is in the film | My friend is drawn from behind only, as he agreed. I am drawn from behind in every shot. On the bus seat I am seen from behind and a little from the side, turned to the window, and part of a cheek shows. That cheek is the model's invention. No photo of me, of him or of anyone was ever given to a model. |
| My friend is drawn in one shot only, with the brokers | He agreed to one scene. After I told the story in full, the storyboard had him in three: at Lamberet, with the brokers, and in the queue. Two things brought it back to one. It was more than he had said yes to. And the image model could not draw two people from behind in a crowd: of eight pictures for Lamberet and eight for the queue, over four runs, none was usable (F05 in `FAILURES.md`). So in the city at dusk and in the queue I am alone in the frame, and the voice says he met me there. |
| The friend who said goodbye in Ankober is not in the film | He is in my telling of 25 November and not in the narration I wrote. Showing him would put a third real person in the film. |
| The brokers are nobody | They are strangers, and the shot is about how many they were. I asked for their faces in shadow or turned away. In the picture that was kept the model lit them all the same. They are its invention and no real person's. |
| One shot moves, the road | Four shots were made as real video on a free GPU. The bus on the gravel road works: something in the picture can move, and it does. The other three do not: in the blurred city lights the model painted things that were not there, at Lamberet the minibuses melt from frame to frame, and on the balcony stains spread over my shirt. Those three stay as slow pans over their stills (E08 in `EXPERIMENTS.md`). |
| Day, then night, then morning | Midday and mountains for the road, night and electric light for the city, gold morning light for the queue. The light tells the time, so the voice does not have to. |
| Painted, grainy look instead of photographic | It suits a memory, it hides the softness of enlarged crops, and it does not pretend to be footage of real events. |
| Amharic narration, English subtitles | The story happened in Amharic. Subtitles let colleagues and the diaspora follow. |
| A ready-made voice, not my own | No voice is cloned. Since 26 November the narrator is an Amharic voice of Addis AI (`am-nahom`). Until then it was a prebuilt voice of the Gemini speech model, whose lines did not sound like one voice (F10 in `FAILURES.md`). I proposed the provider built for Ethiopian languages. Three of its voices were recorded on the eight lines and compared by numbers (E26). The choice by ear between them and the Gemini recording is mine, and I have not made it yet. |
| A solo krar score in the tizita mood | Tizita is the music of memory and longing, which is what the film is. The description names one instrument, because a short description that names one gets it (E22). |

## A reason for every shot

The source of truth is the `reason` field of each shot in `storyboard.json`. The schema refuses a shot without one.

| Shot | Size | Reason |
|---|---|---|
| s00 Ankober, from far | extreme wide | Where he comes from, before he is in the picture: the town on its ridge, on the morning a new chapter begins. The voice says why he is leaving. |
| s01 Midday, Ankober | medium | Where the journey starts: a small highland town, a country bus with its door open, and one backpack. |
| s02 The gravel road | extreme wide | The journey itself, and the scale of it: one small bus on a gravel road under forested mountains, while the voice names the three places ahead. |
| s03 The window seat | medium | The same journey from where he sat. Nobody travelled with him, so the shot is his alone: he at the window, his backpack on the seat beside him, and the mountains outside. |
| s04 The city at dusk | wide | The arrival, and the turn of the film: daylight and mountains give way to dusk, crowds, lit buildings and cars. He is alone in the frame, facing all of it. His friend met him there, and the voice says so. |
| s05 Autobus Tera, from far | extreme wide | The big bus station, seen whole and from far: people moving every way between the buses, as the voice says, before we are in the middle of it. |
| s06 Too much at once | medium | The heart of the story as he tells it: not fear but confusion. Brokers on every side, and two friends in the middle of them. |
| s07 The room | wide | Quiet after the noise, and as he tells it: one bed, not the best, not bad, clean enough to rest. The backpack is the only thing of his in it. |
| s08 The queue | wide | The morning after: the city is ordinary again, a long line of people waiting for a ticket to go on. He is the last one in it, seen from behind. |
| s09 Now | medium | The answer to the whole night. The same city, seen calmly by the man that boy became, with the old backpack on the floor beside him. |

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

## Changes made after a review of the cut

On 26 November at 00:45 a second coding session reviewed the cut of that hour against the brief, frame by frame, and wrote down what was wrong. I read its list and passed it to the coding agent that builds the film. The fixes below are the agent's work, done the same night. It looked at every new picture before pinning it. I confirm them when I confirm the film.

| What the review found | What changed | Measured | Commit |
|---|---|---|---|
| His jacket, trousers, shoes and backpack change from shot to shot | The description of the young man names its colours, and every shot with him or his backpack is drawn again, from the words alone | E28: the backpack as described in 7 of 7 pictures (before: 0 of 6), plastic sandals in 5 of 5 (before: 1 of 5) | `ac3ac21` |
| The bus seat picture has him at the front beside a dashboard with no driver, and the judge gave it 0.4 of 5 | A new picture: a passenger row, he in the window seat seen from behind, his backpack on the seat beside him | Judge total 2.6. Still under 3, and listed by the final-cut check | `ac3ac21` |
| Garbled writing on the bus in the first shot | A new picture with the bus seen from its side. The judge finds no writing in it | Judge total 3.0 | `ac3ac21` |
| The wide film's last shot has no backpack: it is outside the crop | The last shot is a wider view: his whole figure small in the middle, the backpack at his leg. Both formats hold both. The camera now pulls out and ends on the whole view | I looked at the first and the last frame of the shot in both films | `ac3ac21` |
| "Meskerem 2012" reads as the year 2012 to an English reader | The first subtitle says "Meskerem 2012 (late 2019)." The voice is unchanged. The subtitle check was told that a correct gloss in brackets is not an addition, and passes it | Subtitle check: faithful | `ac3ac21` |
| The first subtitle holds four sentences for ten seconds, and two subtitles end on one left-over word | A subtitle is shown sentence by sentence, each while its sentence is spoken, and two lines are balanced. 23 cues where there were 13 | E27. The final-cut check finds no cue faster than about 20 characters a second | `ac3ac21` |
| Line s04 fails the pipeline's own listening check (0.16) | The listener is now a speech model built for Amharic. On the voice now in the film that line scores 0.98, and the lowest line 0.89 | E27 | `ac3ac21` |
| The road shot moves for 3.4 seconds and then stands on its last frame | The shot lasts as long as its voice needs, 4.8 seconds. The clip, slowed by a quarter, fills 4.2 of them | The final-cut check no longer lists it | `ac3ac21` |
| The last words of the film are on screen for 1.3 seconds | The last shot is 1.5 seconds longer, and "Do not run from it. Savour it." stays for 2.8 | Film length 70.9 s | `ac3ac21` |

Not changed: the bus station seen from far (s05) keeps its picture, which the judge scores 1.6 and I picked by eye.

The numbers in this table are those of commit `ac3ac21`. The review's last point, that the story did not say why I left Ankober or what the ticket was for, is answered in the next section.

## The narration I wrote myself

The review also asked whether the eight lines were what I would say. They were not mine: the coding agent had written them from my telling and from the listeners' comments. On 26 November I wrote the whole narration in Amharic and sent it to the agent at about 02:20 as the text to be spoken. It is in `storyboard.json` word for word: when the agent made the edit it checked that the ten lines, joined together, are the text I sent.

In English it says: When I finished twelfth grade, I was assigned to Bahir Dar University; right then a new chapter began. My journey began in Ankober; with only one backpack and a mind full of questions. First to Debre Birhan, then to Addis Ababa, and finally to Bahir Dar. As I looked out of the window, the road and the landscape kept changing; forest and mountains, valleys and roads stretching away. It was dusk when I reached Autobus Tera; my friend met me there. People move every way, cars pass, and brokers ask, "Do you want a bed?" For a moment everything seemed too much at once, and confusing. In the end we chose a room with one bed; it was not the best, and not bad, but clean enough to rest. Next morning, to continue the journey, we stood in a long queue and bought a ticket. When I remember that first night away from home, I say one thing to all who leave the familiar world and start a new journey: the first night is always confusing. Do not run. Savour it.

What the agent did with it, and what is still mine to check:

| What | How |
|---|---|
| Ten lines for ten shots | Each sentence stays whole and goes on the picture it fits. The first sentence had no picture, so a new first shot was added: the town seen from far in the morning (s00). The sentence about people, cars and brokers plays over the bus station seen from far (s05), which had no words before, and "too much at once" plays over the two friends among the brokers (s06). |
| The English subtitles | Written by the agent. A second model checks each against its line, and finds all ten faithful. I have not read them yet. |
| The voice | The same Addis AI voice, each line in a request of its own. The speech model that listens matches each line at 0.93 to 1.00. In the line about confusion it did not write the end of the last word, መሰለኝ. I have to hear whether the voice says it. |
| The road shot | Its line is longer than its generated clip, so the clip is played at about half speed with its frames blended (`motion.slow_max` in the storyboard). It now moves for the whole shot. |
| The score | The film is 85.9 s and the score is 80 s. Instead of starting again under the last words, the score is played 7% slower at the same pitch. |
| Lamberet | My narration does not name it. The picture of the avenue at dusk stays, under the sentence about reaching Autobus Tera. Whether that picture is right for that sentence is mine to say. |

