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
docker run -p 3000:3000 -e MAX_CLIP_DURATION_S="1.5" -e INTER_TRANSITION_S="0" -e MAX_CLIPS_PER_FILE="3" -e BIAS_STARTSWITH_CSV="favorites/" -v "/path/to/files:/media" joshtxdev/videos-to-stream
```

Here's a complete list of all settings

| environmental var | default | data type | description |
| --- | ----- | -----| ----- |
MAX_CLIP_DURATION_S | 60 | decimal | The duration (in seconds) of each clip, not including crossfade time. If a file's total duration is less than MAX_CLIP_DURATION_S, then the clip's duration will just be the file's duration
MAX_CLIP_DURATION_M | | decimal | The duration (in minutes) of each clip. When specified, will override MAX_CLIP_DURATION_S
INTER_TRANSITION_S | 2 | decimal | The duration (in seconds) of the crossfade when transitioning from one file to another file
INTRA_TRANSITION_S | 0 | decimal | The duration (in seconds) of the crossfade when transitioning from one clip to the next clip within the same file
MAX_CLIPS_PER_FILE | 1 | int | When a file is selected, determines how many clips to play from that file. Clips will be played in chronological order
INTRA_FILE_MIN_GAP_S | 3 | decimal | when there's multiple clips per file, determines the minimum amount of time between the end of one clip and the start of the next clip. A high value can reduce the number of clips per file
INTRA_FILE_MAX_PERCENT | 80 | percent | Another way to limit the max clips per file. If a file is 10 minutes long, a value of 80 means that you it can't play more than 8 minutes worth of clips.
WIDTH | 1280 | int | the width (in pixels) of the output stream
HEIGHT | 720 | int | the height (in pixels) of the output stream
PREROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the beginning of a clip prior to changing the clip's volume and alpha. 
POSTROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the end after changing the clip's volume and alpha
EXCLUDE_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be excluded from being played. Sorta like a whitelist 
EXCLUDE_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be excluded from being played. Sorta like a whitelist
BIAS_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected more often (depending on the bias factor)
BIAS_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected more often (depending on the bias factor)
BIAS_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected more often (depending on the bias factor)
BIAS_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected more often (depending on the bias factor)
BIAS_FACTOR | 2 | int | A factor for how often biased videos are selected. A bias factor of 2 means that an individual video that's biased is twice as likely to be selected compared to an individual video that's not biased.

Note that a video is either biased or not biased. Having both contains and startswith matching a video doesn't make it doubly-biased or something. 

Even though each file path is something like `/media/favorites/vid.mp4`, the path is trimmed to just `favorites/vid.mp4` when evaluating each startswith term. This means you should NOT prefix your startswith with a `/`. 

# Notes on randomization

Although I call it "random", the logic is very complex to ensure every file eventually gets played, and recently-played files don't come up again too soon, all while not being a predictable pattern, and also being adaptable to changes to the /media directory contents. 