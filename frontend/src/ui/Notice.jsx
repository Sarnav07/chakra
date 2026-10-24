export default function Notice({ kind, children }) {
  return <div role={kind === "error" ? "alert" : "status"}
    className={`ck-notice ck-notice--${kind}`}>{children}</div>;
}
