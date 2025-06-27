import gi
import os
import random
import math
import re
from collections import deque
from datetime import datetime, timedelta, UTC

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
gi.require_version("GstPbutils", "1.0")
gi.require_version("GstController", "1.0")
from gi.repository import Gst, GLib, GObject, GstPbutils, GstController

# the initial pipeline looks like this
# videotestsrc -> videoconvert -> capsfilter -> compositor c -> x264enc -> queue -> mpegtsmux m -> hlssink
# audiomixer am -> avenc_aac -> queue -> m

# The filebin element internally contains the following: 
# filesrc -> decodebin -> [decodebin-video-src] -> video_identity -> videoconvert -> videoscale -> capsfilter -> c
#  [decodebin-audio-src] -> audioconvert -> audioresample -> audio_identity -> am

Gst.init(None)

class Settings:
    pass
settings = Settings()
settings.max_clip_duration_ms = math.floor(float(os.getenv("MAX_CLIP_DURATION_S", "60")) * 1000)
if float(os.getenv("MAX_CLIP_DURATION_M", "0")) > 0:
    settings.max_clip_duration_ms = math.floor(float(os.getenv("MAX_CLIP_DURATION_M", "0")) * 60 * 1000)
settings.inter_transition_ms = math.floor(float(os.getenv("INTER_TRANSITION_S", "2")) * 1000)
settings.intra_transition_ms = math.floor(float(os.getenv("INTRA_TRANSITION_S", "0")) * 1000)
settings.max_clips_per_file = math.floor(float(os.getenv("MAX_CLIPS_PER_FILE", "1")))
settings.intra_file_min_gap_ms = math.floor(float(os.getenv("INTRA_FILE_MIN_GAP_S", "3")) * 1000)
settings.intra_file_max_percent = float(os.getenv("INTRA_FILE_MAX_PERCENT", "80")) / 100
settings.preroll_ms = math.floor(float(os.getenv("PREROLL_S", "0.5")) * 1000)
settings.postroll_ms = math.floor(float(os.getenv("POSTROLL_S", "0.5")) * 1000)
settings.width = int(os.getenv("WIDTH", "1280"))
settings.height = int(os.getenv("WIDTH", "720"))

settings.whitelist_path_contains_csv = os.getenv("WHITELIST_PATH_CONTAINS_CSV", "").strip()
settings.whitelist_path_startswith_csv = os.getenv("WHITELIST_PATH_STARTSWITH_CSV", "").strip()
settings.blacklist_path_contains_csv = os.getenv("BLACKLIST_PATH_CONTAINS_CSV", "").strip()
settings.blacklist_path_startswith_csv = os.getenv("BLACKLIST_PATH_STARTSWITH_CSV", "").strip()

settings.input_base_dir = "/media"
settings.output_dir = "./serve"
settings.bin_creation_ms = 1000
settings.audio_controller_fix = True
settings.auto_pause_s = 60
settings.last_activity_file = "last-activity.txt"
settings.last_activity_on_startup_s = 30

os.makedirs(settings.input_base_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

class HLSPipelineManager:
    def __init__(self):
        self.update_last_activity_file()
        self.pipeline = Gst.Pipeline.new("hls-pipeline")
        self.clock = self.pipeline.get_clock()
        self.clipinfo_manager = ClipInfoManager()
        self.clips = []
        self._setup_pipeline()

    def _setup_pipeline(self):
        # video elements
        videotestsrc = Gst.ElementFactory.make("videotestsrc", None)
        videoconvert = Gst.ElementFactory.make("videoconvert", None)
        videocapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.compositor = Gst.ElementFactory.make("compositor", None)
        x264enc = Gst.ElementFactory.make("x264enc", None)
        videoqueue = Gst.ElementFactory.make("queue", None)
        # audio elements
        audiotestsrc = Gst.ElementFactory.make("audiotestsrc", None)
        audioconvert = Gst.ElementFactory.make("audioconvert", None)
        audioresample = Gst.ElementFactory.make("audioresample", None)
        audiocapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.audiomixer = Gst.ElementFactory.make("audiomixer", None)
        faac = Gst.ElementFactory.make("avenc_aac", None)
        audioqueue = Gst.ElementFactory.make("queue", None)
        # shared ending elements
        mpegtsmux = Gst.ElementFactory.make("mpegtsmux", None)
        hlssink = Gst.ElementFactory.make("hlssink", None)

        elements = [
            videotestsrc, videoconvert, videocapsfilter, self.compositor, x264enc, videoqueue,
            audiotestsrc, audioconvert, audioresample, audiocapsfilter, self.audiomixer, faac, audioqueue, 
            mpegtsmux, hlssink
        ]
        for i, e in enumerate(elements):
            if not e:
                raise Exception(f"[ERROR] Failed to create element {i}")
            self.pipeline.add(e)

        # Properties
        videotestsrc.set_property("is-live", True)
        videotestsrc.set_property("pattern", "ball")
        videocapsfilter.set_property("caps", Gst.Caps.from_string(f"video/x-raw, format=NV12, width={settings.width}, height={settings.height}, pixel-aspect-ratio=1/1"))

        hlssink.set_property("location", os.path.join(settings.output_dir, "segment%05d.ts"))
        hlssink.set_property("playlist-location", os.path.join(settings.output_dir, "playlist.m3u8"))
        hlssink.set_property("target-duration", 4)
        hlssink.set_property("playlist-length", 12)
        hlssink.set_property("max-files", 18)

        x264enc.set_property("speed-preset", "fast")
        audiotestsrc.set_property("is-live", True)
        audiotestsrc.set_property("wave", "silence")
        audiocapsfilter.set_property("caps", Gst.Caps.from_string("audio/x-raw, format=F32LE,rate=44100,channels=2"))

        # Link video path
        videotestsrc.link(videoconvert)
        videoconvert.link(videocapsfilter)
        compositor_pad = self.compositor.request_pad_simple("sink_%u")
        compositor_pad.set_property("alpha", 1)
        compositor_pad.set_property("zorder", 0)
        videocapsfilter.get_static_pad("src").link(compositor_pad)
        self.compositor.link(x264enc)
        x264enc.link(videoqueue)
        videoqueue.link(mpegtsmux)

        # Link audio path
        audiotestsrc.link(audioconvert)
        audioconvert.link(audioresample)
        audioresample.link(audiocapsfilter)
        audiocapsfilter.link(self.audiomixer)
        self.audiomixer.link(faac)
        faac.link(audioqueue)
        audioqueue.link(mpegtsmux)

        mpegtsmux.link(hlssink)

        self.zorder = 1
        self.is_paused = False
        self.ready_to_create = True
        GLib.timeout_add(2000, self.timeout_callback)

    def timeout_callback(self):
        try:
            s = self.get_seconds_since_activity()
            if s > settings.auto_pause_s:
                if not self.is_paused:
                    print(f"pausing stream due to {s} seconds of inactivity")
                    self.pipeline.set_state(Gst.State.PAUSED)
                    self.is_paused = True
                GLib.timeout_add(1000, self.timeout_callback)
                return False
            if self.is_paused:
                print(f"resuming stream")
                self.pipeline.set_state(Gst.State.PLAYING)
                self.is_paused = False
            ns_till_next_prepare = self.prepare_next()
            timeout_ms = min(2000, max(5, ns_till_next_prepare / Gst.MSECOND)) + 5
            GLib.timeout_add(timeout_ms, self.timeout_callback)
            return False
        except Exception as e:
            print("===================================")
            print(f"Error occurred: {e}")
            print("===================================")
        
        GLib.timeout_add(2000, self.timeout_callback)
        return False # repeat timeout

    def prepare_next(self):
        prep_time_needed_ns = (settings.bin_creation_ms + settings.preroll_ms) * Gst.MSECOND
        if not self.clips:
            fadeout_t = self.create_clip(self.get_time() + prep_time_needed_ns)
            return fadeout_t - self.get_time() - prep_time_needed_ns
        now = self.get_time()
        existing_clip = max(self.clips, key=lambda clip: clip.fadeout_t)
        remaining_time_ns = existing_clip.fadeout_t - now
        if (remaining_time_ns > prep_time_needed_ns):
            return remaining_time_ns - prep_time_needed_ns
        fadeout_t = self.create_clip(existing_clip.fadeout_t)
        return fadeout_t - self.get_time() - prep_time_needed_ns

    def create_clip(self, fadein_t):
        def on_ready(filebin):
            ms_till_fadein = (fadein_t - self.get_time()) / Gst.MSECOND
            timeout_ms = max(5, ms_till_fadein - settings.preroll_ms)
            GLib.timeout_add(timeout_ms, lambda: self.add_clip(clip))
        clip = self.clipinfo_manager.next_clipinfo()
        clip.fadein_t = fadein_t
        ms_between_fades = clip.duration_ms - clip.fadeout_ms
        clip.fadeout_t = fadein_t + ms_between_fades * Gst.MSECOND
        clip.filebin = FileBin(clip.location, clip.seek_ms)
        clip.filebin.connect("ready", on_ready)
        self.clips.append(clip)
        return clip.fadeout_t

    def add_clip(self, clip):
        self.pipeline.add(clip.filebin)
        before_started = self.get_time()
        filebin_video_pad = clip.filebin.get_static_pad("video_src")
        compositor_pad = self.compositor.request_pad_simple("sink_%u")
        compositor_pad.set_property("zorder", self.zorder)
        compositor_pad.set_property("alpha", 0)
        self.zorder += 1
        filebin_video_pad.link(compositor_pad)

        filebin_audio_pad = clip.filebin.get_static_pad("audio_src")
        if filebin_audio_pad:
            audiomixer_pad = self.audiomixer.request_pad_simple("sink_%u")
            audiomixer_pad.set_property("volume", 0)
            filebin_audio_pad.link(audiomixer_pad)

        clip.filebin.sync_state_with_parent()
        clip.filebin.unblock_pads()
        def on_started(filebin):
            GLib.timeout_add(5, lambda: self.swap_clip(clip))
        clip.filebin.connect("started", on_started)
        return False
    
    def swap_clip(self, new_clip):
        old_clip = None if len(self.clips) == 1 else next((clip for clip in self.clips if clip.fadeout_t == new_clip.fadein_t), None)
        
        transition_ns = max(1, new_clip.fadein_ms * Gst.MSECOND)
        interp_mode = GstController.InterpolationMode.LINEAR if transition_ns > 1 else GstController.InterpolationMode.NONE
        now = self.get_time()
        ns_till_swap = new_clip.fadein_t - now

        new_filebin_video_pad = new_clip.filebin.get_static_pad("video_src") 
        new_compositor_pad = new_filebin_video_pad.get_peer()
        video_control_source = GstController.InterpolationControlSource()
        video_control_source.set_property("mode", GstController.InterpolationMode.LINEAR)
        video_control_source.set(now + ns_till_swap, 0.0)
        video_control_source.set(now + ns_till_swap + transition_ns, 1)
        video_binding = GstController.DirectControlBinding.new(new_compositor_pad, "alpha", video_control_source)
        new_compositor_pad.add_control_binding(video_binding)

        audio_start_t = now + ns_till_swap
        if settings.audio_controller_fix:
            new_filebin_elapsed = now - new_clip.filebin.time_started
            audio_start_t = new_clip.filebin.segment_start_ns + new_filebin_elapsed + ns_till_swap

        new_filebin_audio_pad = new_clip.filebin.get_static_pad("audio_src")
        if new_filebin_audio_pad:
            new_audiomixer_pad = new_filebin_audio_pad.get_peer()
            new_clip.audio_control_source = GstController.InterpolationControlSource()
            new_clip.audio_control_source.set_property("mode", GstController.InterpolationMode.LINEAR)
            new_clip.audio_control_source.set(audio_start_t, 0.0)
            new_clip.audio_control_source.set(audio_start_t + transition_ns, 0.1)
            audio_binding = GstController.DirectControlBinding.new(new_audiomixer_pad, "volume", new_clip.audio_control_source)
            new_audiomixer_pad.add_control_binding(audio_binding)
            
        if old_clip:
            # no need to fade out old video, the new one will just be on top

            old_filebin_elapsed = now - old_clip.filebin.time_started
            last_pts = old_clip.filebin.segment_start_ns + old_filebin_elapsed + ns_till_swap + transition_ns
            def try_cleanup():
                if old_clip.video_finished and old_clip.audio_finished:
                    old_clip.cleanup_scheduled = True
                    GLib.timeout_add(settings.postroll_ms, lambda: self.cleanup_clip(old_clip))
    
            def detect_end_video(pad, info):
                buffer = info.get_buffer()
                if buffer and buffer.pts > last_pts:
                    old_clip.video_finished = True
                    try_cleanup()
                    pad.remove_probe(info.id)
                return Gst.PadProbeReturn.OK
            old_filebin_video_pad = old_clip.filebin.get_static_pad("video_src")
            old_compositor_pad = old_filebin_video_pad.get_peer()
            video_probe_id = old_compositor_pad.add_probe(Gst.PadProbeType.BUFFER, detect_end_video)

            old_filebin_audio_pad = old_clip.filebin.get_static_pad("audio_src")
            audio_probe_id = None
            if old_filebin_audio_pad and old_clip.audio_control_source:
                if settings.audio_controller_fix:
                    audio_start_t = old_clip.filebin.segment_start_ns + old_filebin_elapsed + ns_till_swap
                old_clip.audio_control_source.set(audio_start_t, 0.1)
                old_clip.audio_control_source.set(audio_start_t + transition_ns, 0)

                def detect_end_audio(pad, info):
                    buffer = info.get_buffer()
                    if buffer and buffer.pts > last_pts:
                        old_clip.audio_finished = True
                        try_cleanup()
                        pad.remove_probe(info.id)
                    return Gst.PadProbeReturn.OK
                old_audiomixer_pad = old_filebin_audio_pad.get_peer()
                audio_probe_id = old_audiomixer_pad.add_probe(Gst.PadProbeType.BUFFER, detect_end_audio)
            else:
                old_clip.audio_finished = True

            def force_cleanup():
                if not old_clip.cleanup_scheduled:
                    print("RESORTING TO FORCE CLEANUP")
                    #Are the buffers behind? Or maybe we scheduled beyond the file's end?
                    old_clip.cleanup_scheduled = True
                    if not old_clip.audio_finished and audio_probe_id:
                        old_audiomixer_pad.remove_probe(audio_probe_id)
                    if not old_clip.video_finished:
                        old_compositor_pad.remove_probe(video_probe_id)
                    self.cleanup_clip(old_clip)
            # allow postroll + 2 seconds until we force cleanup
            GLib.timeout_add((ns_till_swap + transition_ns) / Gst.MSECOND + settings.postroll_ms + 2000, force_cleanup)
        return False # Don't repeat timeout

    def cleanup_clip(self, clip):
        video_src_pad = clip.filebin.get_static_pad("video_src") 
        if video_src_pad:
            peer_pad = video_src_pad.get_peer()
            if peer_pad:
                video_src_pad.unlink(peer_pad)
                self.compositor.release_request_pad(peer_pad)
        audio_src_pad = clip.filebin.get_static_pad("audio_src")
        if audio_src_pad:
            peer_pad = audio_src_pad.get_peer()
            if peer_pad:
                audio_src_pad.unlink(peer_pad)
                self.audiomixer.release_request_pad(peer_pad)
        self.pipeline.remove(clip.filebin)
        clip.filebin.set_state(Gst.State.NULL)
        clip.filebin = None
        clip.audio_control_source = None
        self.clips.remove(clip)
        return False # Don't repeat timeout

    def get_time(self):
        return self.pipeline.get_clock().get_time() - self.pipeline.get_base_time()


    
    def get_seconds_since_activity(self):
        try:
            with open(settings.last_activity_file, "r") as f:
                timestamp_str = f.read().strip()
            last_activity = datetime.fromisoformat(timestamp_str)
            now = datetime.now(UTC)
            return math.floor((now - last_activity).total_seconds())
        except Exception as e:
            print(f"Error reading last activity: {e}")
            
    def update_last_activity_file(self): #used when starting up to ensure we don't immediately pause
        future_time = datetime.now(UTC) + timedelta(seconds=settings.last_activity_on_startup_s)
        with open(settings.last_activity_file, "w") as f:
            f.write(future_time.isoformat())

    def is_playing(self):
        success, state, pending = self.pipeline.get_state(0)
        return state == Gst.State.PLAYING

    def pause(self):
        print("pause")
        self.pipeline.set_state(Gst.State.PAUSED)
        return False

    def resume(self):
        print("resume")
        self.pipeline.set_state(Gst.State.PLAYING)
        return False

    def run(self):
        self.pipeline.set_state(Gst.State.PLAYING)
        print(f"[INFO] HLS pipeline is running. Serving segments in {settings.output_dir}")

        loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()

        def on_message(bus, msg):
            t = msg.type
            if t == Gst.MessageType.EOS:
                print("[INFO] End of stream.")
                loop.quit()
            elif t == Gst.MessageType.ERROR:
                err, debug = msg.parse_error()
                print(f"[ERROR] {err}: {debug}")
                loop.quit()

        bus.connect("message", on_message)

        loop.run()
        self.pipeline.set_state(Gst.State.NULL)
        print("[INFO] Pipeline stopped.")

class ClipInfo:
    def __init__(self, location, seek_ms, duration_ms, fadein_ms, fadeout_ms):
        self.location = location
        self.seek_ms = seek_ms
        self.duration_ms = duration_ms
        self.fadein_ms = fadein_ms
        self.fadeout_ms = fadeout_ms
        self.fadein_t = None
        self.fadeout_t = None
        self.audio_control_source = None
        self.video_finished = None
        self.audio_finished = None
        self.cleanup_scheduled = False

class ClipInfoManager:
    def __init__(self):
        self.recent_files_queue = deque(maxlen=10)
        self.clipinfo_queue = deque()
        self.ever_selected = set()
        self.discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
        self.video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm'}

    def next_clipinfo(self):
        if not self.clipinfo_queue:
            more_clipinfos = self._get_more_clipinfos()
            self.clipinfo_queue.extend(more_clipinfos)
        if not self.clipinfo_queue:
            raise Exception(f"[ERROR] No clips to queue")
        return self.clipinfo_queue.popleft()

    def _get_more_clipinfos(self):
        location = self._next_file()
        if not location:
            raise FileNotFoundError(f"[ERROR] no video files in {settings.input_base_dir}")
        file_duration_ms = math.floor(self._get_duration_ms(location))
        duration_w_inter_transitions = settings.max_clip_duration_ms + (settings.inter_transition_ms * 2)

        def simple_case():
            clip_duration_ms = min(duration_w_inter_transitions, file_duration_ms)
            startrange_ms = file_duration_ms - clip_duration_ms
            seek_ms = random.randint(0, startrange_ms)
            return [ClipInfo(location, seek_ms, clip_duration_ms, settings.inter_transition_ms, settings.inter_transition_ms)]

        # first check if we're in the simple case where it's obvious there's just 1 clip for this file
        if settings.max_clips_per_file <= 1 or file_duration_ms < (duration_w_inter_transitions + settings.max_clip_duration_ms):
            return simple_case()

        # step 1: compute clip count
        ms_after_first_clip = file_duration_ms - duration_w_inter_transitions # must result in a positive number because of the earlier check
        duration_w_intra_transitions = settings.max_clip_duration_ms + (settings.intra_transition_ms * 2)
        max_clips_due_to_gaps = 1 + (ms_after_first_clip // (duration_w_intra_transitions + settings.intra_file_min_gap_ms))
        max_clips_due_to_percent = file_duration_ms // settings.intra_file_max_percent
        clip_count = min(max_clips_due_to_gaps, max_clips_due_to_percent, settings.max_clips_per_file)
        if clip_count <= 1:
            return simple_case()

        # step 2: get spaces list
        space_count = clip_count + 1
        gap_count = space_count - 2
        total_space_ms = file_duration_ms - (duration_w_inter_transitions + ((clip_count - 1) * duration_w_intra_transitions))
        total_space_without_required_gaps = total_space_ms - (gap_count * settings.intra_file_min_gap_ms)
        if total_space_without_required_gaps < 0:
            raise ValueError("total_space_without_required_gaps < 0")
        raw_randoms = [random.random() for _ in range(space_count)]
        raw_sum = sum(raw_randoms)
        spaces = [r / raw_sum * total_space_without_required_gaps for r in raw_randoms]
        for i in range(1, space_count - 1):
            spaces[i] += settings.intra_file_min_gap_ms

        # step 3: create clipinfos
        clipinfos = []
        seek_ms = 0
        for i in range(space_count - 1):
            seek_ms += spaces[i]
            fadein_transition_ms = settings.inter_transition_ms if i == 0 else settings.intra_transition_ms
            fadeout_transition_ms = settings.inter_transition_ms if i == (space_count - 1) else settings.intra_transition_ms
            clip_duration_ms = duration_w_intra_transitions
            if i == 0 or i == space_count - 1:
                clip_duration_ms = settings.max_clip_duration_ms + settings.inter_transition_ms + settings.intra_transition_ms
            clipinfos.append(ClipInfo(location, seek_ms, clip_duration_ms, fadein_transition_ms, fadeout_transition_ms))
            seek_ms += clip_duration_ms
        return clipinfos

    def _next_file(self):
        start_time = datetime.now(UTC)
        all_files = self._get_files()
        mid_time = datetime.now(UTC)
        filecount = len(all_files)

        if filecount == 0:
            return None
        # Determine recent exclusion count
        recent_exclude_count = 10 if filecount >= 20 else math.floor(filecount / 2)
        # Build exclusion set from recent queue (up to recent_exclude_count)
        recent_set = set(list(self.recent_files_queue)[-recent_exclude_count:]) if recent_exclude_count > 0 else set()
        # Attempt to get eligible files (not in recent or ever_selected)
        eligible = [f for f in all_files if f not in self.ever_selected and f not in recent_set]
        # If none left, reset ever_selected and try again
        if not eligible:
            self.ever_selected.clear()
            eligible = [f for f in all_files if f not in recent_set]
            if not eligible:
                return None  # Still nothing eligible
        selected = random.choice(eligible)
        self.recent_files_queue.append(selected)
        self.ever_selected.add(selected)
        end_time = datetime.now(UTC)
        duration1_ms = (mid_time - start_time).total_seconds() * 1000
        duration2_ms = (end_time - mid_time).total_seconds() * 1000
        print(f"scanned files in: {duration1_ms:.2f} ms, selected file in: {duration2_ms:.2f} ms")
        return selected

    def _get_duration_ms(self, location):
        path = os.path.abspath(location)
        uri = f"file://{path}"
        info = self.discoverer.discover_uri(uri)
        duration_ns = info.get_duration()
        return duration_ns / Gst.MSECOND

    def _get_files(self):
        video_files = []

        white_contain_pattern = None
        white_startswith_list = None
        black_contain_pattern = None
        black_startswith_list = None
        any_filters = False
        if settings.whitelist_path_contains_csv:
            any_filters = True
            whitelist_terms_lower = [term.lower() for term in settings.whitelist_path_contains_csv.split(",") if term.strip()]
            white_contain_pattern = re.compile("|".join(re.escape(term) for term in whitelist_terms_lower))
        if settings.whitelist_path_startswith_csv:
            any_filters = True
            white_startswith_list = [term.lower() for term in settings.whitelist_path_startswith_csv.split(",") if term.strip()]
        if settings.blacklist_path_contains_csv:
            any_filters = True
            blacklist_terms_lower = [term.lower() for term in settings.blacklist_path_contains_csv.split(",") if term.strip()]
            black_contain_pattern = re.compile("|".join(re.escape(term) for term in blacklist_terms_lower))
        if settings.blacklist_path_startswith_csv:
            any_filters = True
            black_startswith_list = [term.lower() for term in settings.blacklist_path_startswith_csv.split(",") if term.strip()]

        stack = [settings.input_base_dir]
        while stack:
            current_dir = stack.pop()
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir():
                        stack.append(entry.path)
                    elif entry.is_file():
                        if not os.path.splitext(entry.name)[1].lower() in self.video_extensions:
                            continue
                        if not any_filters: # since this is a very common case, handle it now for best performance
                            video_files.append(entry.path)
                            continue
                        path = os.path.relpath(entry.path, start=settings.input_base_dir).lower()
                        if white_startswith_list and not any(path.startswith(p) for p in white_startswith_list):
                            continue
                        if white_contain_pattern and not bool(white_contain_pattern.search(path)): 
                            continue
                        if black_startswith_list and any(path.startswith(p) for p in black_startswith_list):
                            continue
                        if black_contain_pattern and bool(black_contain_pattern.search(path)): 
                            continue
                        video_files.append(entry.path)
        return video_files

class FileBin(Gst.Bin):
    __gsignals__ = {
        "ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "started": (GObject.SignalFlags.RUN_FIRST, None, ())
    }
    _instance_count = 0
    def __init__(self, location, seek_ms):
        super().__init__()
        FileBin._instance_count += 1
        print(f"Created Filebin for {location}. Active Filebin Count: {FileBin._instance_count}")
        self.location = location
        self.seek_ms = seek_ms
        self.pad_states = {"video": False, "audio": False}
        self.video_block_probe_id = None
        self.audio_block_probe_id = None
        
        self.segment_start_ns = None
        self.segment_base_ns = None
        self.time_started = None

        # Create elements
        self.filesrc = Gst.ElementFactory.make("filesrc", None)
        self.decodebin = Gst.ElementFactory.make("decodebin", None)
        self.video_identity = Gst.ElementFactory.make("identity", None)
        self.videoconvert = Gst.ElementFactory.make("videoconvert", None)
        self.videoscale = Gst.ElementFactory.make("videoscale", None)
        self.vcapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.audioconvert = Gst.ElementFactory.make("audioconvert", None)
        self.audioresample = Gst.ElementFactory.make("audioresample", None)
        self.audiocapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.audio_identity = Gst.ElementFactory.make("identity", None)
        
        self.filesrc.set_property("location", self.location)
        self.videoscale.set_property("add-borders", True)
        self.vcapsfilter.set_property("caps", Gst.Caps.from_string(f"video/x-raw, format=NV12, width={settings.width}, height={settings.height}, pixel-aspect-ratio=1/1"))
        self.audiocapsfilter.set_property("caps", Gst.Caps.from_string("audio/x-raw, format=F32LE,rate=44100,channels=2"))
        elements = [
            self.filesrc, self.decodebin,
            self.video_identity, self.videoconvert, self.videoscale, self.vcapsfilter,
            self.audioconvert, self.audioresample, self.audiocapsfilter, self.audio_identity
        ]
        for e in elements:
            self.add(e)

        self.filesrc.link(self.decodebin)
        self.videoconvert.link(self.videoscale)
        self.videoscale.link(self.vcapsfilter)
        self.audioconvert.link(self.audioresample)
        self.audioresample.link(self.audiocapsfilter)
        self.audiocapsfilter.link(self.audio_identity)
        self.pad_added_id = self.decodebin.connect("pad-added", self._on_pad_added)
        self.no_more_pads_id = self.decodebin.connect("no-more-pads",  self._on_no_more_pads)
        self.set_state(Gst.State.PAUSED)

    def __del__(self):
        FileBin._instance_count -= 1

    def _on_pad_added(self, decodebin, pad):
        caps = pad.query_caps(None).to_string()

        if caps.startswith("video/") and not self.pad_states["video"]:
            pad.link(self.video_identity.get_static_pad("sink"))
            self.video_identity.link(self.videoconvert)

            # Add ghost pad
            ghost = Gst.GhostPad.new("video_src", self.vcapsfilter.get_static_pad("src"))
            self.video_block_probe_id = ghost.add_probe(
                Gst.PadProbeType.BLOCK_DOWNSTREAM,
                lambda pad, info: Gst.PadProbeReturn.OK  # This blocks everything
            )
            self.add_pad(ghost)

            # Add probe to the identity sink
            self.video_identity.get_static_pad("sink").add_probe(
                Gst.PadProbeType.EVENT_DOWNSTREAM, self._segment_probe_callback
            )
            self.pad_states["video"] = True

        elif caps.startswith("audio/") and not self.pad_states["audio"]:
            pad.link(self.audioconvert.get_static_pad("sink"))

            # Add ghost pad
            ghost = Gst.GhostPad.new("audio_src", self.audio_identity.get_static_pad("src"))
            self.audio_block_probe_id = ghost.add_probe(
                Gst.PadProbeType.BLOCK_DOWNSTREAM,
                lambda pad, info: Gst.PadProbeReturn.OK  # This blocks everything
            )
            self.add_pad(ghost)

            # Add probe to the identity sink
            self.audio_identity.get_static_pad("sink").add_probe(
                Gst.PadProbeType.EVENT_DOWNSTREAM, self._segment_probe_callback
            )
            self.pad_states["audio"] = True

    def unblock_pads(self):
        video_pad = self.get_static_pad("video_src")
        audio_pad = self.get_static_pad("audio_src")
        
        if self.video_block_probe_id and video_pad:
            video_pad.remove_probe(self.video_block_probe_id)
            self.video_block_probe_id = None
            
        if self.audio_block_probe_id and audio_pad:
            audio_pad.remove_probe(self.audio_block_probe_id)
            self.audio_block_probe_id = None

    def _on_no_more_pads(self, decodebin):
        self.decodebin.disconnect(self.pad_added_id)
        self.decodebin.disconnect(self.no_more_pads_id)
        GLib.timeout_add(10, self._perform_seek)
    def _perform_seek(self):
        success = self.decodebin.seek_simple(
            Gst.Format.TIME,
            Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            self.seek_ms * Gst.MSECOND
        )
        if not success:
            print("Warning: seek failed")
            return False
        self.emit("ready")
        return False  # Don't repeat timeout

    def _segment_probe_callback(self, pad, info):

        if not (info.type & Gst.PadProbeType.EVENT_DOWNSTREAM):
            return Gst.PadProbeReturn.OK

        event = info.get_event()
        if not event or event.type != Gst.EventType.SEGMENT:
            return Gst.PadProbeReturn.OK

        old_segment = event.parse_segment()

        def clone_segment(segment):
            new_segment = Gst.Segment()
            for attr in dir(segment):
                if attr.startswith('_'):
                    continue
                value = getattr(segment, attr)
                if not callable(value):
                    try:
                        setattr(new_segment, attr, value)
                    except Exception:
                        pass
            return new_segment


        # this callback is used for both audio and video, but I want both to have the same base
        if self.segment_base_ns is None:
            self.segment_base_ns = self._get_time()

        new_segment = clone_segment(old_segment)
        new_segment.base = self.segment_base_ns
        
        caps = pad.get_current_caps() or pad.query_caps(None)
        isAudio = caps.get_structure(0).get_name().startswith("audio/")
        # I might later change this logic to use the min or max start
        if isAudio:
            self.segment_start_ns = new_segment.start
            self.time_started = self._get_time()
            self.emit("started")

        new_event = Gst.Event.new_segment(new_segment)
        pad.remove_probe(info.id)
        peer = pad.get_peer()
        if peer:
            peer.push_event(new_event)

        return Gst.PadProbeReturn.DROP

    def _get_time(self):
        pipeline = self.get_parent()
        return pipeline.get_clock().get_time() - pipeline.get_base_time()

if __name__ == "__main__":
    manager = HLSPipelineManager()
    manager.run()
