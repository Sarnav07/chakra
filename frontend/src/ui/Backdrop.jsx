import { useEffect, useRef, useState } from "react";

export default function Backdrop() {
  const video = useRef(null);
  const [posterOnly, setPosterOnly] = useState(
    () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches || false
  );
  useEffect(() => {
    if (!video.current || posterOnly) return;
    video.current.muted = true;
    video.current.play().catch(() => {});
  }, [posterOnly]);
  return (
    <>
      {posterOnly ? (
        <img className="ck-backdrop" src="/media/chakra-bg-poster.jpg"
          alt="" aria-hidden="true" />
      ) : (
        <video ref={video} className="ck-backdrop" src="/media/chakra-bg.mp4"
          poster="/media/chakra-bg-poster.jpg" muted autoPlay loop playsInline
          preload="auto" aria-hidden="true" onError={() => setPosterOnly(true)} />
      )}
      <div className="ck-backdrop-veil" aria-hidden="true" />
    </>
  );
}
