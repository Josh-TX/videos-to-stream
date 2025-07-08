# videos-to-stream

Videos-to-stream is a server that creates a continuous livestream from video files. Created with Python and heavily uses the GStreamer library. Deployable as a docker container via the following command

```
docker run -p 3000:3000 -v "/path/to/files:/media" joshtxdev/videos-to-stream
```

This will serve an HLS stream at `/playlist.m3u8`. It also serves a simple webpage at `/` that plays the stream. The stream will recursively scan the container's /media folder for all video files, randomly select a file, and play a random 1-minute video clip from the file. It then crossfades into the next randomly-selected file, and so on.

# Configuration

There are many adjustable settings that affect the streams behavior. At the moment these settings can be controlled via environmental variables. Some useful settings include
* Changing the duration of each clip. You can have each clip be hours long or under a second. 
* Play consecutive clips from the same file before moving on to the next file
* Change the transition speed. Instead of crossfades you can do instant cuts
* Filter what files can be played
* Bias certain files to be randomly selected more often

For example, this command will make it play each clip for 1.5 seconds, have no crossfades, play 3 clips per file, and will play videos from the "favorites" folder twice as often
```
docker run -p 3000:3000 -e MAX_CLIP_DURATION_S="1.5" -e INTER_TRANSITION_S="0" -e MAX_CLIPS_PER_FILE="3" -e BOOSTED_STARTSWITH_CSV="favorites/" -v "/path/to/files:/media" joshtxdev/videos-to-stream
```

Here's a complete list of all settings

| environmental var | default | data type | description |
| --- | ----- | -----| ----- |
CLIP_DURATION_S | 60 | decimal | The duration (in seconds) of each clip, not including crossfade time. If a file's total duration is less than CLIP_DURATION_S, then the clip's duration will just be the file's duration
CLIP_DURATION_M | | decimal | The duration (in minutes) of each clip. When specified, will override CLIP_DURATION_S
INTER_TRANSITION_S | 2 | decimal | The duration (in seconds) of the crossfade when transitioning from one file to another file
INTRA_TRANSITION_S | 0 | decimal | The duration (in seconds) of the crossfade when transitioning from one clip to the next clip within the same file
CLIPS_PER_FILE | 1 | int | When a file is selected, determines how many clips to play from that file. Clips will be played in chronological order without any overlap. If CLIPS_PER_FILE is too high, then it'll play as many clips as it can given all the constraints (such as clip duration). 
INTRA_FILE_MIN_GAP_S | 5 | decimal | When there's multiple clips per file, determines the minimum seconds between the end of one clip and the start of the next clip. A high value can reduce the number of clips per file. Be careful with a low value, since seeking is keyframe-based, so the next clip could contain footage you just saw. 
INTRA_FILE_MAX_PERCENT | 80 | percent | Another way to limit the max clips per file. If a file is 10 minutes long, a value of 80 means that you it can't play more than 8 minutes worth of clips.
FONT_SIZE | 6 | int | The size of the text in the bottom-left corner that shows the currently-playing file and position. Set it to 0 to hide this text
WIDTH | 1280 | int | The width (in pixels) of the output stream
HEIGHT | 720 | int | The height (in pixels) of the output stream
X_CROP_PERCENT | 0 | percent | If the input video's aspect ratio is wider than the output stream's aspect ratio, a postive X_CROP_PERCENT will crop the left and right edges of such videos. 
Y_CROP_PERCENT | 0 | percent | If the input video's aspect ratio is taller than the output stream's aspect ratio, a postive Y_CROP_PERCENT will crop the top and bottom edges of such videos. 
PREROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the beginning of a clip prior to changing the clip's volume and alpha. 
POSTROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the end after changing the clip's volume and alpha
EXCLUDE_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be excluded from being played. Sorta like a whitelist 
EXCLUDE_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be excluded from being played. Sorta like a whitelist
BOOSTED_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_FACTOR | 2 | int | A factor for how often boosted videos are selected over non-boosted. A boosted factor of 2 means that an individual video that's boosted is twice as likely to be selected compared to an individual video that's neutral, and 4 times more likely to be selected compared to a video that's suppressed (with suppressed factor of 2).
SUPPRESSED_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_FACTOR | 2 | int | A factor for how often not-suppressed videos are selected over suppressed. A suppressed factor of 2 means that an individual video that's suppressed is half as likely to be selected compared to an individual video that's neutral, and 4 times less likely to be selected compared to a video that's boosted (with boosted factor of 2).


Note that a video is either biased or not biased. Having both contains and startswith matching a video doesn't make it doubly-biased or something. 

# Fitting and Cropping

By default, the stream output has a width of 1280px and a height of 720px, which is a 16/9 aspect ratio. This can be changed via the WIDTH and HEIGHT settings, but they're still a static value. Input videos don't have to match this exact resolution, as the GStreamer pipeline can scale the videos to match the output. If the input video has a width of 854px and a height of 480px, then this can be scaled without any issue. But if the input video has a width of 640px and a height of 480px, this would be a slight problem since the aspect ratio of 4/3, which doesn't match the output's 16/9. The 4/3 aspect ratio is almost a square shape, whereas 16/9 is wider. There are generally 3 ways to solve this kind of problem:

1. stretching
2. black bars
3. cropping

Stretching is usually not wanted since circles become ovals and so on. By default, this problem is solved with black bars. So a more square shaped video will have vertical bars on the left and right sides. However, there's also an option to use the `X_CROP_PERCENT` and `Y_CROP_PERCENT` variables to solve this problem by cropping. Back to the 4/3 to 16/9 example, the top and bottom would need to each have 12.5% (60px) cut off, leaving the middle 75%. This means that a `Y_CROP_PERCENT` of 25 or higher would allow fully cropping a 4/3 video into a a 16/9 ratio. If the `Y_CROP_PERCENT` was something like 10, then it would crop off 5% of the top, 5% of the bottom, but there still be black bars, just thinner than without cropping. You can set `X_CROP_PERCENT` and `Y_CROP_PERCENT` to both be 100, which just means that you can crop however much is need to create the output aspect ratio. 

# Randomization and Bias

The randomization logic seeks to accomplish the following:
1. Eventually play all files
2. Don't play a recently-played file
3. Don't follow a predictable pattern
4. Adapt to changes to the /media directory.
5. Allow specifying some files to play more often than others

To accomplish this, each selected file gets added to a set. Only files not in the set can be selected. If all the files are in the set, a "reset" happens wherein the set is cleared. This mostly works, but after a reset a recently-selected file could be selected again. So a queue is also used to prevent recent files from being selected, even after a reset. 

If there are any settings to make files boosted and/or suppressed, then three sets are used instead of one. A set for suppressed files, a set for neutral files, and a set for boosted files. The goal then is to select neutral files more often than suppressed files such that the neutral set gets reset twice for each time the suppressed set gets reset once. Likewise, the boosted set should get reset twice for each time the suppressed set gets reset once. To give an example, suppose there are 2 files in each of the 3 bias categories; the 2 suppressed files would each have a weight of 1, the 2 neutral files would each have a weight of 2, and the 2 neutral files would eahc have a weight of 4. This means the sum weight is 1*2 + 2*2 + 4*2 = 14. When selecting the first file, there's a 2/14 chance of selecting a suppressed file, a 4/14 chance of selecting a neutral file, and a 8/14 chance of selecting a boosted file. These probabilities adjust as files are selected, until all 3 sets have done the correct number of resets. These explanations assume the SUPPRESSED_FACTOR and BOOSTED_FACTOR are both 2 (default). Making a factor greater than 2 will make the bias more extreme.

If a file is matched by both boosted settings and suppressed settings, then the file becomes neutral. 