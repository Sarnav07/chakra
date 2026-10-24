export default function Backdrop() {
  const prefersReducedMotion =
    typeof window !== "undefined" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  return (
    <div className="ck-backdrop" aria-hidden="true">
      {prefersReducedMotion ? (
        <img
          className="ck-backdrop__media"
          src="/media/chakra-bg-poster.jpg"
          alt=""
        />
      ) : (
        <video
          className="ck-backdrop__media"
          src="/media/chakra-bg.mp4"
          poster="/media/chakra-bg-poster.jpg"
          muted
          autoPlay
          loop
          playsInline
        />
      )}
      <div className="ck-backdrop__veil" />
    </div>
  );
}
