const DEFAULT_TEXT = {
  implemented: "IMPLEMENTED",
  simulated: "SIMULATED",
  proposed: "PROPOSED",
  new: "NEW",
};

export default function Badge({ kind, children }) {
  return (
    <span className={`ck-badge ck-badge--${kind}`}>
      {children || DEFAULT_TEXT[kind] || kind.toUpperCase()}
    </span>
  );
}
