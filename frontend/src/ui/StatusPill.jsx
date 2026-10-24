export default function StatusPill({ status }) {
  return <span className={`ck-status-pill ck-status-pill--${status}`}>{status}</span>;
}
