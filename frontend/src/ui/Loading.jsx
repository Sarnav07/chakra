export default function Loading({ text }) {
  return (
    <div className="ck-loading">
      <div className="ck-loading__spinner" />
      {text && <p>{text}</p>}
    </div>
  );
}
