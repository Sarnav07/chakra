export default function EmptyState({ title, children }) {
  return (
    <div className="ck-empty">
      <h3>{title}</h3>
      {children}
    </div>
  );
}
