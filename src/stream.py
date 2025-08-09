import gi
import os
import random
import math
import re
import signal
import glob
from pathlib import Path
from fractions import Fraction
from collections import deque
from datetime import datetime, timedelta, UTC

from preset_manager import PresetManager

gi.require_version("Gst", "1.0")
gi.require_version("GLib", "2.0")
gi.require_version("GstPbutils", "1.0")
gi.require_version("GstController", "1.0")
from gi.repository import Gst, GLib, GObject, GstPbutils, GstController

# the initial pipeline looks like this
# videotestsrc -> videoconvert -> capsfilter -> compositor c -> textoverlay -> x264enc -> queue -> mpegtsmux m -> hlssink
# audiomixer am -> avenc_aac -> queue -> m

# The filebin element internally contains the following: 
# filesrc -> decodebin -> [decodebin-video-src] -> video_identity -> videoconvert -> videoscale -> capsfilter -> c
#  [decodebin-audio-src] -> audioconvert -> audioresample -> audio_identity -> am
Gst.init(None)

class Settings:
    pass
settings = Settings()

def decimal_to_fraction_string(decimal_value: float, max_denominator: int = 1001) -> str:
    fraction = Fraction(decimal_value).limit_denominator(max_denominator)
    return f"{fraction.numerator}/{fraction.denominator}"

def update_settings():
    preset_manager = PresetManager()
    active_preset = preset_manager.get_active_preset()
    settings.clip_duration_ms = math.floor(float(active_preset["CLIP_DURATION_S"]) * 1000)
    settings.inter_transition_ms = math.floor(float(active_preset["INTER_TRANSITION_S"]) * 1000)
    settings.intra_transition_ms = math.floor(float(active_preset["INTRA_TRANSITION_S"]) * 1000)
    settings.clips_per_file = math.floor(float(active_preset["CLIPS_PER_FILE"]))
    settings.intra_file_min_gap_ms = math.floor(float(active_preset["INTRA_FILE_MIN_GAP_S"]) * 1000)
    settings.intra_file_max_percent = float(active_preset["INTRA_FILE_MAX_PERCENT"]) / 100

    settings.width = int(active_preset["WIDTH"])
    settings.height = int(active_preset["HEIGHT"])
    settings.frame_rate_str = decimal_to_fraction_string(float(active_preset["FRAME_RATE"]))
    settings.x_crop_percent = float(active_preset["X_CROP_PERCENT"]) / 100
    settings.y_crop_percent = float(active_preset["Y_CROP_PERCENT"]) / 100
    settings.font_size = int(active_preset["FONT_SIZE"])
    settings.preroll_ms = math.floor(float(active_preset["PREROLL_S"]) * 1000)
    settings.postroll_ms = math.floor(float(active_preset["POSTROLL_S"]) * 1000)

    settings.base_directory = active_preset["BASE_DIRECTORY"].strip(" \t\n\r/\\")
    settings.exclude_startswith_csv = active_preset["EXCLUDE_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.exclude_contains_csv = active_preset["EXCLUDE_CONTAINS_CSV"].strip(" \t\n\r")
    settings.exclude_notstartswith_csv = active_preset["EXCLUDE_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.exclude_notcontains_csv = active_preset["EXCLUDE_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_startswith_csv = active_preset["BOOSTED_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.boosted_contains_csv = active_preset["BOOSTED_CONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_notstartswith_csv = active_preset["BOOSTED_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.boosted_notcontains_csv = active_preset["BOOSTED_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.boosted_factor = int(active_preset["BOOSTED_FACTOR"])
    settings.suppressed_startswith_csv = active_preset["SUPPRESSED_STARTSWITH_CSV"].strip(" \t\n\r")
    settings.suppressed_contains_csv = active_preset["SUPPRESSED_CONTAINS_CSV"].strip(" \t\n\r")
    settings.suppressed_notstartswith_csv = active_preset["SUPPRESSED_NOTSTARTSWITH_CSV"].strip(" \t\n\r")
    settings.suppressed_notcontains_csv = active_preset["SUPPRESSED_NOTCONTAINS_CSV"].strip(" \t\n\r")
    settings.suppressed_factor = int(active_preset["SUPPRESSED_FACTOR"])
    
update_settings()

settings.input_root_dir = "/media"
settings.output_dir = "./serve"
settings.bin_creation_ms = 1000
settings.audio_controller_fix = True
settings.auto_pause_s = 60
settings.last_activity_file = "last-activity.txt"
settings.last_activity_on_startup_s = 30
settings.recent_file_queue_length = 30
settings.settings_change_msg = False


def handle_presets_changed(signum, frame):
    print("presets changed")
    old_width = settings.width
    old_height = settings.height
    old_font_size = settings.font_size
    old_frame_rate_str = settings.frame_rate_str
    update_settings()
    if settings.width != old_width or settings.height != old_height or settings.font_size != old_font_size or settings.frame_rate_str != old_frame_rate_str:
        manager.technical_changes()
    settings.settings_change_msg = True
    def msg_done():
        settings.settings_change_msg = False
    GLib.timeout_add(2000, msg_done)
signal.signal(signal.SIGUSR1, handle_presets_changed)

os.makedirs(settings.input_root_dir, exist_ok=True)
os.makedirs(settings.output_dir, exist_ok=True)

class HLSPipelineManager:
    def __init__(self):
        self.update_last_activity_file()
        self.pipeline = Gst.Pipeline.new("hls-pipeline")
        self.clock = self.pipeline.get_clock()
        self.clipinfo_manager = ClipInfoManager()
        self.displayed_text = " stream is starting..." if settings.font_size > 0 else ""
        self.clips = []
        self._setup_pipeline()

    def technical_changes(self):
        print("technical changes to preset")
        self.videocapsfilter.set_property("caps", Gst.Caps.from_string(f"video/x-raw, format=NV12, width={settings.width}, height={settings.height}, framerate={settings.frame_rate_str}, pixel-aspect-ratio=1/1"))
        self.textoverlay.set_property("font-desc", f"Sans, {settings.font_size}")

    def _setup_pipeline(self):
        # video elements
        videotestsrc = Gst.ElementFactory.make("videotestsrc", None)
        videoconvert = Gst.ElementFactory.make("videoconvert", None)
        self.videocapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.compositor = Gst.ElementFactory.make("compositor", None)
        self.textoverlay = Gst.ElementFactory.make("textoverlay", None)
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
            videotestsrc, videoconvert, self.videocapsfilter, self.compositor, self.textoverlay, x264enc, videoqueue,
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
        self.videocapsfilter.set_property("caps", Gst.Caps.from_string(f"video/x-raw, format=NV12, width={settings.width}, height={settings.height}, framerate={settings.frame_rate_str}, pixel-aspect-ratio=1/1"))
        
        self.textoverlay.set_property("text", self.displayed_text)
        self.textoverlay.set_property("halignment", "left")
        self.textoverlay.set_property("wrap-mode", "none")
        self.textoverlay.set_property("valignment", "bottom")
        self.textoverlay.set_property("font-desc", f"Sans, {settings.font_size}")
        self.textoverlay.set_property("xpad", 0)
        self.textoverlay.set_property("ypad", 0)
        self.textoverlay.set_property("draw-outline", False)
        self.textoverlay.get_static_pad("src").add_probe(Gst.PadProbeType.BUFFER, self.text_overlay_probe_callback)


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
        videoconvert.link(self.videocapsfilter)
        compositor_pad = self.compositor.request_pad_simple("sink_%u")
        compositor_pad.set_property("alpha", 1)
        compositor_pad.set_property("zorder", 0)
        self.videocapsfilter.get_static_pad("src").link(compositor_pad)
        self.compositor.link(self.textoverlay)
        self.textoverlay.link(x264enc)
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
        clip.filebin = FileBin(clip.filepath, clip.seek_ms, clip.width, clip.height)
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
                    print(f"RESORTING TO FORCE CLEANUP (not good). Filepath = {old_clip.filepath}")
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

    def text_overlay_probe_callback(self, pad, info):
        if settings.font_size == 0:
            if not self.displayed_text == "":
                self.displayed_text = ""
                self.textoverlay.set_property("text", self.displayed_text)
            return Gst.PadProbeReturn.OK
        buf = info.get_buffer()
        if not buf:
            return Gst.PadProbeReturn.OK
        if settings.settings_change_msg:
            self.textoverlay.set_property("text", " settings changed!")
            return Gst.PadProbeReturn.OK
        active_clip = max(
            (c for c in self.clips if buf.pts >= c.fadein_t + int(0.5 * c.fadein_ms * Gst.MSECOND)),
            key=lambda c: c.fadein_t,
            default=None)
        if not active_clip:
            return Gst.PadProbeReturn.OK
        time_ns = buf.pts - active_clip.fadein_t + active_clip.filebin.segment_start_ns + settings.preroll_ms * Gst.MSECOND
        seconds = time_ns // Gst.SECOND
        minutes = seconds // 60
        hours = minutes // 60
        if hours >= 1:
            time_str = f"{hours:02}:{minutes % 60:02}:{seconds % 60:02}"
        else:
            time_str = f"{minutes:02}:{seconds % 60:02}"
        filepath = active_clip.filepath
        # filepath does not include the input_root_dir, it should usually start with the base_directory (unless base_directory was just changed)
        if settings.base_directory and filepath.startswith(settings.base_directory + os.sep):
            filepath = filepath[len(settings.base_directory) + 1:]
        new_display_text = f" {time_str}   {os.path.splitext(filepath)[0]}"
        if self.displayed_text != new_display_text:
            self.displayed_text = new_display_text
            self.textoverlay.set_property("text", self.displayed_text)
        return Gst.PadProbeReturn.OK
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
    def __init__(self, filepath, seek_ms, duration_ms, fadein_ms, fadeout_ms, width, height):
        self.filepath = filepath
        self.seek_ms = seek_ms
        self.duration_ms = duration_ms
        self.fadein_ms = fadein_ms
        self.fadeout_ms = fadeout_ms
        self.width = width
        self.height = height

        self.fadein_t = None
        self.fadeout_t = None
        self.audio_control_source = None
        self.video_finished = None
        self.audio_finished = None
        self.cleanup_scheduled = False

class ClipInfoManager:
    def __init__(self):
        self.clipinfo_queue = deque()
        self.discoverer = GstPbutils.Discoverer.new(5 * Gst.SECOND)
        self.video_extensions = {'.mp4', '.mkv', '.avi', '.mov', '.flv', '.wmv', '.webm', 'mpeg'}
        self.suppressed_group = FileGroup()
        self.neutral_group = FileGroup()
        self.boosted_group = FileGroup()

    def next_clipinfo(self):
        if not self.clipinfo_queue:
            more_clipinfos = self._get_more_clipinfos()
            self.clipinfo_queue.extend(more_clipinfos)
        if not self.clipinfo_queue:
            raise Exception(f"[ERROR] No clips to queue")
        return self.clipinfo_queue.popleft()

    def _get_more_clipinfos(self):
        filepath = self._next_file()
        self.suppressed_group.cleanup()
        self.neutral_group.cleanup()
        self.boosted_group.cleanup()

        if not filepath:
            raise FileNotFoundError(self._get_error_message())
        file_duration_ms, width, height = self._get_media_info(filepath)
        duration_w_inter_transitions = settings.clip_duration_ms + (settings.inter_transition_ms * 2)

        def simple_case():
            clip_duration_ms = min(duration_w_inter_transitions, file_duration_ms)
            startrange_ms = file_duration_ms - clip_duration_ms
            seek_ms = random.randint(0, startrange_ms)
            return [ClipInfo(filepath, seek_ms, clip_duration_ms, settings.inter_transition_ms, settings.inter_transition_ms, width, height)]

        # first check if we're in the simple case where it's obvious there's just 1 clip for this file
        if settings.clips_per_file <= 1 or file_duration_ms < (duration_w_inter_transitions + settings.clip_duration_ms):
            return simple_case()

        # step 1: compute clip count
        ms_after_first_clip = file_duration_ms - duration_w_inter_transitions # must result in a positive number because of the earlier check
        duration_w_intra_transitions = settings.clip_duration_ms + (settings.intra_transition_ms * 2)
        max_clips_due_to_gaps = 1 + (ms_after_first_clip // (duration_w_intra_transitions + settings.intra_file_min_gap_ms))
        max_clips_due_to_percent = file_duration_ms // settings.intra_file_max_percent
        clip_count = min(max_clips_due_to_gaps, max_clips_due_to_percent, settings.clips_per_file)
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
                clip_duration_ms = settings.clip_duration_ms + settings.inter_transition_ms + settings.intra_transition_ms
            clipinfos.append(ClipInfo(filepath, seek_ms, clip_duration_ms, fadein_transition_ms, fadeout_transition_ms, width, height))
            seek_ms += clip_duration_ms
        return clipinfos

    def _get_error_message(self):
        if not os.listdir(settings.input_root_dir):
            return "[ERROR] no video file to play. The /media directory is empty"
        suppressed_files, neutral_files, boosted_files = self._get_files(False) # get files but with no exclusion filters
        if suppressed_files or neutral_files or boosted_files:
            return "[ERROR] no video file to play. The EXCLUDE settings filtered out all video files"
        return "[ERROR] no video file to play. The /media directory contains no video files"

    def _next_file(self):
        suppressed_files, neutral_files, boosted_files = self._get_files(True)
        #print(f"suppressed_files={len(suppressed_files)}, neutral_files={len(neutral_files)}, boosted_files={len(boosted_files)}")
        if len(suppressed_files) == 0 and len(boosted_files) == 0:
            # simple case where there's only neutral files
            if len(neutral_files) == 0:
                return None
            self.neutral_group.setup(neutral_files, 1)
            if not self.neutral_group.eligible_files:
                self.neutral_group.next_iteration()
            return self.neutral_group.select_file()
        if len(suppressed_files) == 0:
            # slightly-complex case where there's neutral and boosted files
            self.neutral_group.setup(neutral_files, 1)
            self.boosted_group.setup(boosted_files, settings.boosted_factor)
            if self.neutral_group.remaining_total_file_count == 0 and self.boosted_group.remaining_total_file_count == 0:
                self.neutral_group.next_iteration()
                self.boosted_group.next_iteration()
            boosted_chance = self.boosted_group.remaining_total_file_count / (self.boosted_group.remaining_total_file_count + self.neutral_group.remaining_total_file_count)
            is_boosted = random.random() < boosted_chance
            print(f"neutral={self.neutral_group.remaining_total_file_count}, boosted={self.boosted_group.remaining_total_file_count}, is_boosted={is_boosted}")
            if is_boosted:
                if not self.boosted_group.eligible_files:
                    self.boosted_group.next_iteration()
                return self.boosted_group.select_file()
            else:
                return self.neutral_group.select_file()
        # complex case where there could be all 3
        self.suppressed_group.setup(suppressed_files, 1)
        self.neutral_group.setup(neutral_files, settings.suppressed_factor)
        self.boosted_group.setup(boosted_files, settings.suppressed_factor * settings.boosted_factor)
        #print(f"suppressed_group_c={self.suppressed_group.remaining_total_file_count}, neutral_group_c={self.neutral_group.remaining_total_file_count}, boosted_group_c={self.boosted_group.remaining_total_file_count}")

        not_suppressed_count = self.neutral_group.remaining_total_file_count + self.boosted_group.remaining_total_file_count
        if self.suppressed_group.remaining_total_file_count == 0 and not_suppressed_count == 0:
            self.suppressed_group.next_iteration()
            self.neutral_group.next_iteration()
            self.boosted_group.next_iteration()
            not_suppressed_count = self.neutral_group.remaining_total_file_count + self.boosted_group.remaining_total_file_count
        suppressed_chance =  self.suppressed_group.remaining_total_file_count / ( self.suppressed_group.remaining_total_file_count + not_suppressed_count)
        is_suppressed = random.random() < suppressed_chance
        if is_suppressed:
            print(f"suppressed={self.suppressed_group.remaining_total_file_count}, neutral={self.neutral_group.remaining_total_file_count}, boosted={self.boosted_group.remaining_total_file_count}, selected=suppressed")
            return self.suppressed_group.select_file()
        # at this point, it's either boosted or neutral. However, we multiplied by settings.suppressed_factor, and we want to reverse that affect
        neutral_adjusted_file_count = self.neutral_group.get_adjusted_remaining_total_file_count(settings.suppressed_factor)
        boosted_adjusted_file_count = self.boosted_group.get_adjusted_remaining_total_file_count(settings.suppressed_factor)
        # now we can do basically the same thing as the slightly-complex case
        if neutral_adjusted_file_count == 0 and boosted_adjusted_file_count == 0:
            self.neutral_group.next_iteration()
            self.boosted_group.next_iteration()
            neutral_adjusted_file_count = self.neutral_group.get_adjusted_remaining_total_file_count(settings.suppressed_factor)
            boosted_adjusted_file_count = self.boosted_group.get_adjusted_remaining_total_file_count(settings.suppressed_factor)
        boosted_chance = boosted_adjusted_file_count / (boosted_adjusted_file_count + neutral_adjusted_file_count)
        is_boosted = random.random() < boosted_chance
        if is_boosted:
            print(f"suppressed={self.suppressed_group.remaining_total_file_count}, neutral={self.neutral_group.remaining_total_file_count}, boosted={self.boosted_group.remaining_total_file_count}, selected=boosted")
            if not self.boosted_group.eligible_files:
                self.boosted_group.next_iteration()
            return self.boosted_group.select_file()
        else:
            print(f"suppressed={self.suppressed_group.remaining_total_file_count}, neutral={self.neutral_group.remaining_total_file_count}, boosted={self.boosted_group.remaining_total_file_count}, selected=neutral")
            return self.neutral_group.select_file()



    def _get_media_info(self, filepath):
        path = os.path.join(settings.input_root_dir, filepath) 
        uri = Path(path).as_uri()
        info = self.discoverer.discover_uri(uri)
        duration_ns = info.get_duration()

        width = height = None
        for stream in info.get_stream_list():
            if isinstance(stream, GstPbutils.DiscovererVideoInfo):
                caps = stream.get_caps()
                if caps:
                    structure = caps.get_structure(0)
                    width = structure.get_value("width")
                    height = structure.get_value("height")
                break  # Only look at first video stream
        return (math.floor(duration_ns / Gst.MSECOND), width, height)

    def _get_files(self, enable_filters):
        suppressed_files = []
        neutral_files = []
        boosted_files = []
        def get_contain_pattern(csv):
            if not csv:
                return None
            lower_terms = [term.strip().lower() for term in csv.split(",") if term.strip()]
            return re.compile("|".join(re.escape(term) for term in lower_terms))
        def get_startswith_list(csv):
            if not csv:
                return None
            return [term.strip().lstrip("/").lower() for term in csv.split(",") if term.strip()]
        exclude_startswith_list = get_startswith_list(settings.exclude_startswith_csv)
        exclude_contains_pattern = get_contain_pattern(settings.exclude_contains_csv)
        exclude_notstartswith_list = get_startswith_list(settings.exclude_notstartswith_csv)
        exclude_notcontains_pattern = get_contain_pattern(settings.exclude_notcontains_csv)

        boosted_startswith_list = get_startswith_list(settings.boosted_startswith_csv)
        boosted_contains_pattern = get_contain_pattern(settings.boosted_contains_csv)
        boosted_notstartswith_list = get_startswith_list(settings.boosted_notstartswith_csv)
        boosted_notcontains_pattern = get_contain_pattern(settings.boosted_notcontains_csv)

        suppressed_startswith_list = get_startswith_list(settings.suppressed_startswith_csv)
        suppressed_contains_pattern = get_contain_pattern(settings.suppressed_contains_csv)
        suppressed_notstartswith_list = get_startswith_list(settings.suppressed_notstartswith_csv)
        suppressed_notcontains_pattern = get_contain_pattern(settings.suppressed_notcontains_csv)

        stack = [os.path.join(settings.input_root_dir, settings.base_directory)]
        while stack:
            current_dir = stack.pop()
            with os.scandir(current_dir) as it:
                for entry in it:
                    if entry.is_dir():
                        stack.append(entry.path)
                    elif not entry.is_file():
                        continue 
                    if not os.path.splitext(entry.name)[1].lower() in self.video_extensions:
                        continue
                    path = os.path.relpath(entry.path, start=settings.input_root_dir)
                    if settings.base_directory:
                        lower_path = path[len(settings.base_directory) + 1:].lower()
                    else:
                        lower_path = path.lower()
                    
                    if enable_filters and (
                        (exclude_startswith_list and any(lower_path.startswith(p) for p in exclude_startswith_list))
                        or (exclude_contains_pattern and bool(exclude_contains_pattern.search(lower_path)))
                        or (exclude_notstartswith_list and not any(lower_path.startswith(p) for p in exclude_notstartswith_list))
                        or (exclude_notcontains_pattern and not bool(exclude_notcontains_pattern.search(lower_path)))
                    ):
                        continue
                    bias=0
                    if (
                        (boosted_startswith_list and any(lower_path.startswith(p) for p in boosted_startswith_list))
                        or (boosted_contains_pattern and bool(boosted_contains_pattern.search(lower_path)))
                        or (boosted_notstartswith_list and not any(lower_path.startswith(p) for p in boosted_notstartswith_list))
                        or (boosted_notcontains_pattern and not bool(boosted_notcontains_pattern.search(lower_path)))
                    ):
                        bias+=1
                    if (
                        (suppressed_startswith_list and any(lower_path.startswith(p) for p in suppressed_startswith_list))
                        or (suppressed_contains_pattern and bool(suppressed_contains_pattern.search(lower_path)))
                        or (suppressed_notstartswith_list and not any(lower_path.startswith(p) for p in suppressed_notstartswith_list))
                        or (suppressed_notcontains_pattern and not bool(suppressed_notcontains_pattern.search(lower_path)))
                    ):
                        bias-=1
                    if bias == -1:
                        suppressed_files.append(path)
                    elif bias == 0:
                        neutral_files.append(path)
                    else:
                        boosted_files.append(path)
        return (suppressed_files, neutral_files, boosted_files)

class FileGroup():
    def __init__(self):
        self.files_set = set()
        self.recent_files_queue = deque()
        self.iteration_index = 0
        self.cleanup()


    def setup(self, files, iteration_count):
        self.files = files
        self.iteration_count = iteration_count
        self.iteration_index %= iteration_count
        recent_exclude_count = min(settings.recent_file_queue_length, math.floor(len(self.files) / 2))
        recent_set = set(list(self.recent_files_queue)[-recent_exclude_count:]) if recent_exclude_count > 0 else set()
        self.eligible_files = [f for f in self.files if f not in self.files_set and f not in recent_set]
        self.remaining_iteration_file_count = sum(1 for f in self.files if f not in self.files_set)
        if len(self.eligible_files) == 0 and self.remaining_iteration_file_count > 0:
            print("[WARN] unexpected situation in random filepicker logic") # I don't think this is possible, but hard to definitively prove
            self.remaining_iteration_file_count = 0
        self.remaining_iterations = self.iteration_count - 1 - self.iteration_index
        self.remaining_total_file_count = self.remaining_iteration_file_count + (self.remaining_iterations * len(self.files))

    def cleanup(self):
        self.files = None
        self.eligible_files = None
        self.iteration_count = None
        self.remaining_iterations = None
        self.remaining_iteration_file_count = None
        self.remaining_total_file_count = None


    def get_adjusted_remaining_total_file_count(self, factor):
        adjusted_iteration_count = self.iteration_count / factor
        if self.iteration_index >= adjusted_iteration_count:
            return self.remaining_total_file_count
        adjusted_remaining_iterations = adjusted_iteration_count - 1 - self.iteration_index
        return self.remaining_iteration_file_count + (adjusted_remaining_iterations * len(self.files))

    def next_iteration(self):
        self.files_set.clear()
        self.iteration_index += 1
        self.iteration_index %= self.iteration_count
        self.setup(self.files, self.iteration_count)

    def select_file(self):
        selected_file = random.choice(self.eligible_files)
        self.recent_files_queue.append(selected_file)
        self.files_set.add(selected_file)
        return selected_file


class FileBin(Gst.Bin):
    __gsignals__ = {
        "ready": (GObject.SignalFlags.RUN_FIRST, None, ()),
        "started": (GObject.SignalFlags.RUN_FIRST, None, ())
    }
    _instance_count = 0
    def __init__(self, filepath, seek_ms, width, height):
        super().__init__()
        FileBin._instance_count += 1
        #print(f"Created Filebin for {filepath}. Active Filebin Count: {FileBin._instance_count}")
        location = os.path.join(settings.input_root_dir, filepath)
        self.seek_ms = seek_ms
        self.pad_states = {"video": False, "audio": False}
        self.video_block_probe_id = None
        self.audio_block_probe_id = None
        
        self.segment_start_ns = None
        self.segment_base_ns = None
        self.time_started = None

        # Create elements
        filesrc = Gst.ElementFactory.make("filesrc", None)
        self.decodebin = Gst.ElementFactory.make("decodebin", None)
        self.video_identity = Gst.ElementFactory.make("identity", None)
        self.videoconvert = Gst.ElementFactory.make("videoconvert", None)
        videocrop = Gst.ElementFactory.make("videocrop", None)
        videoscale = Gst.ElementFactory.make("videoscale", None)
        self.vcapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.audioconvert = Gst.ElementFactory.make("audioconvert", None)
        audioresample = Gst.ElementFactory.make("audioresample", None)
        audiocapsfilter = Gst.ElementFactory.make("capsfilter", None)
        self.audio_identity = Gst.ElementFactory.make("identity", None)
        
        filesrc.set_property("location", location)
        self._crop(videocrop, width, height)
        videoscale.set_property("add-borders", True)
        self.vcapsfilter.set_property("caps", Gst.Caps.from_string(f"video/x-raw, format=NV12, width={settings.width}, height={settings.height}, pixel-aspect-ratio=1/1"))
        audiocapsfilter.set_property("caps", Gst.Caps.from_string("audio/x-raw, format=F32LE,rate=44100,channels=2"))
        elements = [
            filesrc, self.decodebin,
            self.video_identity, self.videoconvert, videocrop, videoscale, self.vcapsfilter,
            self.audioconvert, audioresample, audiocapsfilter, self.audio_identity
        ]
        for e in elements:
            self.add(e)

        filesrc.link(self.decodebin)
        self.videoconvert.link(videocrop)
        videocrop.link(videoscale)
        videoscale.link(self.vcapsfilter)
        self.audioconvert.link(audioresample)
        audioresample.link(audiocapsfilter)
        audiocapsfilter.link(self.audio_identity)
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

    def _crop(self, videocrop, width, height):
        if not settings.x_crop_percent and not settings.y_crop_percent:
            return
        if not width or not height:
            print("error getting width and height")
            return
        input_ratio = width / height
        output_ratio = settings.width / settings.height
        if abs(input_ratio - output_ratio) < 0.01:
            return
        if input_ratio > output_ratio: #input is wider than output
            if not settings.x_crop_percent:
                return
            max_crop_px = width * settings.x_crop_percent
            crop_px = min(width - height * output_ratio, max_crop_px)
            videocrop.set_property('left', math.ceil(crop_px / 2))
            videocrop.set_property('right', math.floor(crop_px / 2))
        else: #input is taller than output
            if not settings.y_crop_percent:
                return
            max_crop_px = height * settings.y_crop_percent
            crop_px = min(height - width / output_ratio, max_crop_px)
            videocrop.set_property('top', math.floor(crop_px / 2))
            videocrop.set_property('bottom', math.ceil(crop_px / 2))

    def _get_time(self):
        pipeline = self.get_parent()
        return pipeline.get_clock().get_time() - pipeline.get_base_time()


def delete_stream_files():
    file_patterns = [os.path.join(settings.output_dir, "*.ts"), os.path.join(settings.output_dir, "*.m3u8")]
    for pattern in file_patterns:
        for file_path in glob.glob(pattern):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting {file_path}: {e}")
delete_stream_files()

manager = HLSPipelineManager()
manager.run()
