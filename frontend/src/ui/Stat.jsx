export default function Stat({ label, value, unit, hint }) {
  return (
    <div className="ck-stat">
      <div className="ck-stat__value">
        {value}
        {unit && <span className="ck-stat__unit"> {unit}</span>}
      </div>
      <div className="ck-stat__label">{label}</div>
      {hint && <div className="ck-stat__hint">{hint}</div>}
    </div>
  );
}
