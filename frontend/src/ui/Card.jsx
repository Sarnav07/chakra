export default function Card({ title, actions, children }) {
  return (
    <div className="ck-card">
      {(title || actions) && (
        <div className="ck-card__header">
          {title && <h3 className="ck-card__title">{title}</h3>}
          {actions && <div className="ck-card__actions">{actions}</div>}
        </div>
      )}
      <div className="ck-card__body">{children}</div>
    </div>
  );
}
