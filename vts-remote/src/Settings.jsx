
import { useRef, useState, useEffect } from "react";
import usePresetStore from "./PresetStore.jsx"
import { useBlocker } from 'react-router-dom';
import Logo from "./Logo.jsx";

const ContextMenu = () => {
    const [isOpen, setIsOpen] = useState(false);
    const { renameActivePreset, deleteActivePreset, duplicateActivePreset, isDirty, revert } = usePresetStore();
    const buttonRef = useRef(null);
    const menuRef = useRef(null);

    useEffect(() => {
        const handleClickOutside = (e) => {
            if (
                menuRef.current &&
                !menuRef.current.contains(e.target) &&
                buttonRef.current &&
                !buttonRef.current.contains(e.target)
            ) {
                setIsOpen(false);
            }
        };

        document.addEventListener("mousedown", handleClickOutside);
        return () => document.removeEventListener("mousedown", handleClickOutside);
    }, []);

    return (
        <>
            <button className="h-28" ref={buttonRef} style={{ position: "relative" }} onClick={() => setIsOpen((prev) => !prev)}>
                Manage
                {isOpen && (
                    <div ref={menuRef} className="context-menu">
                        <div className="menu-item" onClick={duplicateActivePreset}>duplicate preset</div>
                        <div className="menu-item" onClick={renameActivePreset}>rename preset</div>
                        <div className="menu-item" onClick={deleteActivePreset}>delete preset</div>
                        {isDirty && <div className="menu-item" onClick={revert}>revert unsaved changes</div>}
                    </div>
                )}
            </button>


        </>
    );
};

const Footer = () => {
    const { presets, getActivePreset, setActivePreset, isDirty, saveBtn, save, revert, errorSave } = usePresetStore();
    if (!presets) {
        return <div></div>
    }
    function handleChange(event) {
        setActivePreset(event.target.value)
    }
    var presetOptions = presets.map(preset => (
        <option key={preset.name} value={preset.name}>{preset.name}</option>
    ))

    //warn when navigating to an external site
    useEffect(() => {
        const handleBeforeUnload = (e) => {
            if (!isDirty) return;
            e.preventDefault();
            e.returnValue = '';
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [isDirty]);
    //warn when navigating internally
    const blocker = useBlocker(
        ({ currentLocation, nextLocation }) =>
            isDirty && currentLocation.pathname !== nextLocation.pathname
    );
    useEffect(() => {
        if (blocker.state === "blocked") {
            const shouldProceed = window.confirm(
                "You have unsaved changes. Are you sure you want to leave?"
            );

            if (shouldProceed) {
                revert();
                blocker.proceed();
            } else {
                blocker.reset();
            }
        }
    }, [blocker]);
    var errorToast = null;
    if (errorSave) {
        errorToast = (
            <div style={{ position: "fixed", bottom: "36px", left: 0, right: 0 }}>
                <div style={{ margin: "0 auto", maxWidth: "90vw", width: "400px", background: "#910808", color: "white", padding: "16px" }}>
                    {errorSave}
                </div>
            </div>)
    }

    return (
        <div className="footer-container">
            {errorToast}
            <div className="center-container">
                <div className="footer">
                    preset:&nbsp;
                    <select value={getActivePreset().name} onChange={handleChange} className="preset-selector h-28">
                        {presetOptions}
                    </select>
                    <ContextMenu></ContextMenu>
                    <div></div>
                    <button className="h-28" disabled={!isDirty || saveBtn != 'Save'} onClick={save}>{saveBtn}</button>
                </div>
            </div>
        </div>
    )
}

const SettingItem = ({ name, type = "number", description, preset, settingChanged }) => {
    const [isExpanded, setIsExpanded] = useState(false);
    const handleChange = (event) => {
        settingChanged(name, event.target.value);
    };
    const toggleExpand = () => {
        setIsExpanded(!isExpanded)
    }
    useEffect(() => {
        const handleCollapseAll = () => {
            console.log("SET IS EXPANDED")
            setIsExpanded(false);
        };

        window.addEventListener('collapse-all-settings', handleCollapseAll);
        
        return () => {
            window.removeEventListener('collapse-all-settings', handleCollapseAll);
        };
    }, []);
    if (!isExpanded) {
        if (type == "number") {
            return (
                <div onClick={toggleExpand} className="clickable-label expand-label">
                    <span>{name}</span>
                    <span>{preset[name]}</span>
                </div>
            );
        }
        const csv = preset[name] ? <div style={{ padding: "0 4px 4px 4px", overflow: "hidden", position: "relative", top: "-8px", whiteSpace: "nowrap", textAlign: "right" }}>{preset[name]}</div> : ""
        return (
            <div onClick={toggleExpand} className="clickable-label">
                <div className="expand-label">
                    <span>{name}</span>
                </div>
                {csv}
            </div>
        );
    }
    return (
        <div className={type == "number" ? "settings-num-item" : "settings-text-item"}>
            <div className="collapse-label" onClick={toggleExpand}>{name}</div>
            <input
                id={name}
                type={type}
                value={preset[name]}
                onChange={handleChange}
            />
            <p className="text-muted colspan-2 setting-desc">{description}</p>
        </div>
    );
};


const Settings = () => {
    const { isLoading, errorGet, settingChanged, getActivePreset, anyAlgoSettings, clearAlgorithmSettings } = usePresetStore();
    if (errorGet) {
        return <div>{errorGet}</div>
    }
    if (isLoading) {
        return <div>loading</div>
    }
    const preset = getActivePreset();

    return (
        <>
            <div className="flex-container center-container">
                <Logo></Logo>
                
                <div className="flex-grow" style={{ padding: "0 2px 50px 2px" }}>
                    <div className="panel" style={{ marginTop: "4px" }}>
                        <h2 style={{ margin: "0 0 8px 0" }}>General Settings</h2>
                        <SettingItem
                            name="CLIP_DURATION_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The max duration (in seconds) of each clip, not including crossfade time. If a file's total duration is less than CLIP_DURATION_S, then the clip's duration will just be the file's duration"
                        />
                        <SettingItem
                            name="CLIP_DURATION_MAX_PERCENT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="Another way to limit the max duration of each clip. An individual clip's duration cannot exceed the [file duration * CLIP_DURATION_MAX_PERCENT]. For example, a value of 50% would mean that a file with a duration of 40s couldn't have a clip longer than 20s. You can use CLIP_DURATION_MIN_S to mitigate the effect of this setting."
                        />
                        <SettingItem
                            name="CLIP_DURATION_MIN_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The min duration (in seconds) of each clip, not including crossfade time. This only has an effect in conjunction with CLIP_DURATION_MAX_PERCENT. This is basically a lower bound to how much the clip's max duration can be reduced by the CLIP_DURATION_MAX_PERCENT. This cannot cause a duration longer than CLIP_DURATION_S, nor can it make a clip's duration exceed the file's duration"
                        />
                        <SettingItem
                            name="INTER_TRANSITION_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The duration (in seconds) of the crossfade when transitioning from one file to another file"
                        />
                        <SettingItem
                            name="CLIPS_PER_FILE"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="When a file is selected, determines maximum number of clips to play from that file. Clips will be played in chronological order without any overlap."
                        />
                        <SettingItem
                            name="INTRA_TRANSITION_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The duration (in seconds) of the crossfade when transitioning from one clip to the next clip within the same file"
                        />
                        <SettingItem
                            name="INTRA_FILE_MIN_GAP_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description=" When there's multiple clips per file, determines the minimum seconds between the end of one clip and the start of the next clip. A high value can reduce the number of clips per file. Be careful with a low value, since seeking is keyframe-based, so the next clip could contain footage you just saw. "
                        />
                        <SettingItem
                            name="CLIPS_PER_FILE_MAX_PERCENT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="Another way to limit the max clips per file. For example, If a file is 10 minutes long, a value of 15% means that you it won't play more than 90s worth of clips from that file. If CLIP_DURATION_S was 60s, then this would limit it to only 1 clip from this 10min file. This setting will always allow at least 1 clip though"
                        />
                    </div>
                    <div className="panel" style={{ marginTop: "16px" }}>
                        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px"}}>
                            <h2 style={{ margin: "0" }}>Algorithm Settings</h2>
                            <div><button onClick={clearAlgorithmSettings} disabled={!anyAlgoSettings()}>clear</button></div>
                        </div>
                        <SettingItem
                            name="BASE_DIRECTORY"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="If specified, will use /media/{BASE_DIRECTORY} as the base directory instead of just /media. This is similar to EXCLUDE_NOTSTARTSWITH_CSV, but is case-sensitive, affects other settings that use STARTSWITH, and affects the bottom-left info text"
                        />
                        <SettingItem
                            name="EXCLUDE_STARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be excluded from being played. Sorta like a blacklist"
                        />
                        <SettingItem
                            name="EXCLUDE_CONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be excluded from being played. Sorta like a blacklist"
                        />
                        <SettingItem
                            name="EXCLUDE_NOTSTARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be excluded from being played. Sorta like a whitelist"
                        />
                        <SettingItem
                            name="EXCLUDE_NOTCONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be excluded from being played. Sorta like a whitelist"
                        />

                        <SettingItem
                            name="BOOSTED_STARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected more often (depending on the boosted factor)"
                        />
                        <SettingItem
                            name="BOOSTED_CONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected more often (depending on the boosted factor)"
                        />
                        <SettingItem
                            name="BOOSTED_NOTSTARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected more often (depending on the boosted factor)"
                        />
                        <SettingItem
                            name="BOOSTED_NOTCONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected more often (depending on the boosted factor)"
                        />

                        <SettingItem
                            name="SUPPRESSED_STARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path starts with any of the search terms, it'll be selected less often (depending on the suppressed factor)"
                        />
                        <SettingItem
                            name="SUPPRESSED_CONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path contains any of the search terms, it'll be selected less often (depending on the suppressed factor)"
                        />
                        <SettingItem
                            name="SUPPRESSED_NOTSTARTSWITH_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="a comma-separated list of search terms, and if a file's full path does NOT start with any of the search terms, it'll be selected less often (depending on the suppressed factor)"
                        />
                        <SettingItem
                            name="SUPPRESSED_NOTCONTAINS_CSV"
                            preset={preset}
                            type="text"
                            settingChanged={settingChanged}
                            description="	a comma-separated list of search terms, and if a file's full path does NOT contain any of the search terms, it'll be selected less often (depending on the suppressed factor)"
                        />

                        <SettingItem
                            name="BOOSTED_FACTOR"
                            preset={preset}
                            type="number"
                            settingChanged={settingChanged}
                            description="A factor for how often boosted videos are selected over non-boosted. A boosted factor of 2 means that an individual video that's boosted is twice as likely to be selected compared to an individual video that's neutral, and 4 times more likely to be selected compared to a video that's suppressed (with suppressed factor of 2)."
                        />
                        <SettingItem
                            name="SUPPRESSED_FACTOR"
                            preset={preset}
                            type="number"
                            settingChanged={settingChanged}
                            description="A factor for how often not-suppressed videos are selected over suppressed. A suppressed factor of 2 means that an individual video that's suppressed is half as likely to be selected compared to an individual video that's neutral, and 4 times less likely to be selected compared to a video that's boosted (with boosted factor of 2)."
                        />
                    </div>
                    <div className="panel" style={{ marginTop: "16px" }}>
                        <h2 style={{ margin: "0 0 8px 0" }}>Video Settings</h2>
                        <SettingItem
                            name="FONT_SIZE"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The size of the text in the bottom-left corner that shows the currently-playing file and position. Set it to 0 to hide this text"
                        />
                        <SettingItem
                            name="HEIGHT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The height (in pixels) of the output stream"
                        />
                        <SettingItem
                            name="WIDTH"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The width (in pixels) of the output stream"
                        />
                        <SettingItem
                            name="FRAME_RATE"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The frames-per-second of the output stream"
                        />
                        <SettingItem
                            name="X_CROP_PERCENT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="If the input video's aspect ratio is wider than the output stream's aspect ratio, a postive X_CROP_PERCENT will crop the left and right edges of such videos. See Fitting and Cropping section of README for more info"
                        />
                        <SettingItem
                            name="Y_CROP_PERCENT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="If the input video's aspect ratio is taller than the output stream's aspect ratio, a postive Y_CROP_PERCENT will crop the top and bottom edges of such videos. See Fitting and Cropping section of README for more info"
                        />
                    </div>
                    <div className="panel" style={{ marginTop: "16px" }}>
                        <h2 style={{ margin: "0 0 8px 0" }}>Technical Settings</h2>
                        <SettingItem
                            name="AUTO_PAUSE_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="To amount time (in seconds) until the stream auto-pauses if there's no network activity. The stream will auto-resume as soon as a player connects to the stream. This allows running the server 24/7 while only straining your CPU when needed"
                        />
                        <SettingItem
                            name="PREROLL_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The amount of time (in seconds) to play the video in the background at the beginning of a clip prior to changing the clip's volume and alpha."
                        />
                        <SettingItem
                            name="POSTROLL_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The amount of time (in seconds) to play the video in the background at the end after changing the clip's volume and alpha"
                        />
                        <SettingItem
                            name="FORCE_CLEANUP_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="If there's a internal issue with the stream's presentation timestamps (PTS), the clip might not be properly removed after POSTROLL_S. Because of this, there's also timestamp-agnostic method for removing clips just in case. By default this is 2 additional seconds after the normal cleanup should've run"
                        />
                        <SettingItem
                            name="HLS_SEG_DURATION_S"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The target duration (in seconds) of each segment file of the HLS stream."
                        />
                        <SettingItem
                            name="HLS_SEG_COUNT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The number of segment files (.ts) that should be referenced by the playlist file (.m3u8). A lower count like 5 will reduce the stream delay, but if the player buffers often consider raising this"
                        />
                        <SettingItem
                            name="HLS_SEG_EXTRACOUNT"
                            preset={preset}
                            settingChanged={settingChanged}
                            description="The number of segment files in addition to HLS_SEG_COUNT that should be kept on disk. For example, if count was 8 and extracount was 5, the server would only keep 13 segment files at a time. As additional segments are made, the oldest ones are auto-removed."
                        />
                    </div>
                </div>
                <Footer></Footer>
            </div>
        </>
    );
}

export default Settings;
