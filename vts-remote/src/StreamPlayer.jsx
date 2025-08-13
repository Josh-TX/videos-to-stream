import { useEffect, useRef } from "react";
import Logo from "./Logo";

const StreamPlayer = () => {
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    const src = '/playlist.m3u8'
    if (Hls.isSupported()) {
      const hls = new Hls();
      hls.loadSource(src);
      hls.attachMedia(video);
      return () => {
        hls.destroy();
      };
    } else if (video.canPlayType("application/vnd.apple.mpegurl")) {
      // Native HLS support (Safari, some iOS browsers)
      video.src = src;
    }
  }, []);

  return (
    <>    
      <div style={{position: "fixed", zIndex: 200, opacity: 0.55}}><Logo></Logo></div>
      <video ref={videoRef} controls/>
    </>
  );
}

export default StreamPlayer;
