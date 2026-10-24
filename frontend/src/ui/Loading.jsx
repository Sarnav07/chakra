export default function Loading({ text }) {
  return (
    <div className="ck-loading" aria-live="polite">
      <div className="ck-loading__spinner" aria-hidden="true" />
      {text && <p>{text}</p>}
    </div>
  );
}
