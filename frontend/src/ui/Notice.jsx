export default function Notice({ kind, children }) {
  return <div className={`ck-notice ck-notice--${kind}`}>{children}</div>;
}
