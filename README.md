# Videos to Stream

Videos-to-stream (VTS) is a server that creates a continuous livestream from video files. Created with Python and heavily uses the GStreamer library. Deployable as a docker container via the following command

```
docker run -p 3000:3000 -v "/path/to/files:/media" joshtxdev/videos-to-stream
```

This will serve an HLS stream at `/playlist.m3u8`. The stream will recursively scan the container's /media folder for all video files, randomly select a file, and play a random 1-minute video clip from the file. It then crossfades into the next randomly-selected file, and repeats this forever. To reduce hardware strain, the stream will auto-pause after 60 seconds of no network activity, and it auto-resumes once there is. 

There's also source code for a basic Roku TV App. [See more info below](#playing-on-roku-tv)

## VTS Remote 

In addition to serving a stream at `/playlist.m3u8`, The server also serves a website at `/` called VTS Remote. This site has several features

* View the stream directly
* Manage settings
* Browse Files
* Restart the Stream

The settings page allows you to create named presets and toggle between them. Keep in mind that the stream usually has a ~25 second delay, so changes to the settings won't immediately appear. 

The presets are internally stored in the container's `/metadata` folder. You can mount a volume there to preserve the presets beyond the lifetime of the container

## Settings

There are many adjustable settings that affect the streams behavior. Some useful settings include
* Change the duration of each clip. Clips can be hours long or under a second. 
* Play consecutive clips from the same file before moving on to the next file
* Change the crossfade speed
* Filter what files can be played
* Bias certain files to be randomly selected more often

These settings can be initially configured via the container's environmental variables, but a more user-friendly management page is available at VTS Remote

Here's a complete list of all settings

| setting name | default | data type | description |
| --- | ----- | -----| ----- |
CLIP_DURATION_S | 60 | decimal | The duration (in seconds) of each clip, not including crossfade time. If a file's total duration is less than CLIP_DURATION_S, then the clip's duration will just be the file's duration
INTER_TRANSITION_S | 2 | decimal | The duration (in seconds) of the crossfade when transitioning from one file to another file
CLIPS_PER_FILE | 1 | int | When a file is selected, determines how many clips to play from that file. Clips will be played in chronological order without any overlap. If CLIPS_PER_FILE is too high, then it'll play as many clips as it can given all the constraints (such as clip duration). 
INTRA_TRANSITION_S | 0 | decimal | The duration (in seconds) of the crossfade when transitioning from one clip to the next clip within the same file
INTRA_FILE_MIN_GAP_S | 8 | decimal | When there's multiple clips per file, determines the minimum seconds between the end of one clip and the start of the next clip. A high value can reduce the number of clips per file. A value below 8 can risk seeing the same footage twice, since seeking is keyframe-based. 
INTRA_FILE_MAX_PERCENT | 80 | percent | Another way to limit the max clips per file. If a file is 10 minutes long, a value of 80 means that you it can't play more than 8 minutes worth of clips.
BASE_DIRECTORY | | string | If specified, will use /media/{BASE_DIRECTORY} as the base directory instead of just /media. This is similar to EXCLUDE_NOTSTARTSWITH_CSV, but is case-sensitive, affects other settings that use STARTSWITH, and affects the bottom-left info text
EXCLUDE_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be excluded from being played. Sorta like a blacklist 
EXCLUDE_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be excluded from being played. Sorta like a whitelist 
EXCLUDE_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be excluded from being played. Sorta like a whitelist
BOOSTED_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected more often (depending on the boosted factor)
BOOSTED_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected more often (depending on the boosted factor)
SUPPRESSED_STARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_CONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_NOTSTARTSWITH_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected less often (depending on the suppressed factor)
SUPPRESSED_NOTCONTAINS_CSV | | string | a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected less often (depending on the suppressed factor)
BOOSTED_FACTOR | 2 | int | A factor for how often boosted videos are selected over non-boosted. A boosted factor of 2 means that an individual video that's boosted is twice as likely to be selected compared to an individual video that's neutral, and 4 times more likely to be selected compared to a video that's suppressed (with suppressed factor of 2).
SUPPRESSED_FACTOR | 2 | int | A factor for how often not-suppressed videos are selected over suppressed. A suppressed factor of 2 means that an individual video that's suppressed is half as likely to be selected compared to an individual video that's neutral, and 4 times less likely to be selected compared to a video that's boosted (with boosted factor of 2).
FONT_SIZE | 8 | int | The size of the text in the bottom-left corner that shows the currently-playing file and position. Set it to 0 to hide this text
WIDTH | 1280 | int | The width (in pixels) of the output stream
HEIGHT | 720 | int | The height (in pixels) of the output stream
X_CROP_PERCENT | 0 | percent | If the input video's aspect ratio is wider than the output stream's aspect ratio, a postive X_CROP_PERCENT will crop the left and right edges of such videos. 
Y_CROP_PERCENT | 0 | percent | If the input video's aspect ratio is taller than the output stream's aspect ratio, a postive Y_CROP_PERCENT will crop the top and bottom edges of such videos. 
PREROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the beginning of a clip prior to changing the clip's volume and alpha. 
POSTROLL_S | 0.5 | decimal | The amount of time (in seconds) to play the video in the background at the end after changing the clip's volume and alpha

## Playing on a Roku TV

On a Roku TV, there's not an official App designed to play an HLS stream. The best official way I've found is by manually constructing a m3u8 file that references the stream's URL, putting it on a USB stick, plugging it into the TV, and using the Roku Media Player App.

However, you can instead sideload a custom App using these steps:
1. Clone/Download this repository
2. Edit the file `<repo>/roku-tv-app/components/MainScene.brs` to have the correct `hlsUrl`
3. Make a zip file consisting of all the contents of the `<repo>/roku-tv-app` directory
4. On your Roku TV remote, enable developer mode by pressing home three times, up twice, and then right, left, right, left, right.
5. It should prompt for a passcode and then restart. Your TV will now host a webpage at it's current ipv4 address. Open this webpage in a browser, and login with username=rokudev, and the password is the passcode you entered
6. Upload the zip file and click "install with zip"


## Fitting and Cropping

If the input video doesn't match the output stream's dimensions, it'll the video to fit the output. But this isn't perfect when the aspect ratios differ. By default, black bars will be added on each side, which preserves the aspect ratio, but the result feels kinda zoomed out. There's no option for "stretch to fit", but there are the 
`X_CROP_PERCENT` and `Y_CROP_PERCENT` settings that allow cropping the input video to better match the output aspect ratio. 

For example, if you have a video file with a 1/1 aspect ratio, and the stream outputs a landscape aspect ratio like 16/9, normally black bars will be added on the left & right side. But if you had a `Y_CROP_PERCENT` of 25, this would allow the top 12.5% and bottom 12.5% of the input video to be cropped out so that it's closer to the output aspect ratio. In this example there would still be black bars, but thinner ones. It will never crop more than needed, so you can think of the CROP_PERCENT settings as merely upper bounds for how much cropping is allowed. So setting it to 100 allows as much cropping as needed. 

## Randomization and Bias

The randomization logic is more akin to a playlist shuffle rather than true randomness. Under normal circumstances (no boosted/suppressed files), it plays every file once in a random order, and repeats this (different order each time). 

There are many settings that can classify each file as being "boosted" or "suppressed". This can result in up to 3 groups of files: boosted, suppressed, and neutral. Each group basically has it's own playlist shuffling logic, and the stream will disproportionally choose files from the more boosted group. In fact, for each single playthrough of all suppressed files, it'll play all neutral files twice, and all boosted files 4 times. The `BOOSTED_FACTOR` or `SUPPRESSED_FACTOR` settings can make the relative ratios even more extreme.

In VTS Remote, there's a page to browse files, and it shows the boosted/suppressed status of each file. 

If a file is both boosted and suppressed, it becomes neutral. 