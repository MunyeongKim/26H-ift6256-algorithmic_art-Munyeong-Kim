> "or we could use it like this: two people play together, have a talk, and then it turns into blocks? that sounds interesting too."

# Assignment 2 - "When my presentation is boring"

Digital code, interactive format

*Summary* People talk; their speech becomes UTF-8 bytes, and those bytes become falling Tetris blocks they play together in real time.

## Theme / question
There is not really a fixed theme, and I just kind of wanted to make a work through transcription. At first I made it because I thought it would be fun if speech generated blocks that fall, but the falling feeling started to feel like actually playing Tetris. So while I was at it, I thought: would it be funny if the audience (like, the students in this class) played Tetris while I was presenting? So I made it that way. Originally it was for one player, but I thought it would be more fun if two people cooperated.

## How it works
If you turn on recording and speak, the program transcribes it, then converts it back into UTF-8 bytes, and then turns those bytes into 2*4 blocks. For example, if a byte is `10110111`, it becomes:

```text
1011
0111
```

Then from here, if something like a meaningful "tetris piece" appears,

for example,

```text
0000
1111

0100
1110

1001
1110
```

if blocks come out in shapes like these, it turns them into Tetris blocks and drop them on the left side so two people can play the game.

- `grid.png` was the initial idea. The first intention was basically, if we are doing this anyway, why not just make it fall from the sky? And the second was, if we are doing this anyway, why not just bring two people up front and make them play Tetris? That is more fun.

## Role of the audience
Originally I imagined a museum-like setup where two kids come out and play, and adults stand behind and speak/watch. Even outside that setup, if two people just talk to each other, that gets turned into blocks and falls, and I wanted to mix that game element and conversation element in a balanced way. So even if there are only two audience members, that is okay. (But then I realized: if users intentionally manipulate the conversation, they might be able to get the block they want! wow.)

And the reason the title is *When my presentation is boring* is in a similar context: if it is boring, just play Tetris. Then they still have to predict the next block, so they cannot help but listen to my presentation, and it becomes a virtuous cycle. (Funny enough, during my actual presentation, students focused on my talk (!) so they barely played the game with zero score. I choose to believe that means the work was fun.)

## Point of the experience
Similar to above. (1) In a shared space, especially during presentation time, the idea that students openly play a game is interesting, and the concept that the game blocks are formed through actual participation from both sides, students and presenter, is the fun part. Also even outside a presentation setting, like when there are only two people or a small group, I think the concept that people's conversation can directly continue into gameplay is interesting.

## Why this format
I thought Tetris was the most intuitive game, because everyone knows the rules. And it was also the closest match to the block shapes. And when participants interact, I thought the game format itself should be intuitive enough that anyone can immediately understand it (and it actually worked).

## Installation / technical info
In practice, I implemented it so everything can run on one MacBook. If there is a microphone and a keyboard, it runs on the web. But during the presentation, to keep the feeling of a game, I brought two controllers from home and gave mapped controls.

## Direction for improvement?
I still have a lot to think about in how the blocks and transcript are represented. In the early version (the presentation version), transcript was front-and-center and the block size was very small, so the structure had a problem: people could not really get curious about how blocks were falling (because the converted blocks were too small). But this time, when I made blocks bigger and removed text, there was no intuitive understanding of how the conversion works. I want to keep thinking about this issue. I want the transformed block element and the curiosity about how that transformation works to be delivered together on one screen, but right now I still feel there is a lot of room to improve.

## Additional note on technical implementation

While building the game, I spent a lot of time tuning whisper processing performance so it would run best on a MacBook M1. I adjusted the delay so it still feels immediate when people speak, while keeping transcription quality high, and also keeping processing time faster than the delay itself so the pipeline does not fall behind. I wanted people to feel that something was truly happening in real time. I hope this shows how much attention I gave to those technical details too.
