import { useId } from "react";

export default function Slider({ label, min, max, step, value, onChange, hint }) {
  const id = useId();
  return (
    <div className="ck-slider">
      <label className="ck-slider__label" htmlFor={id}>
        {label}: <strong>{value}</strong>
      </label>
      <input
        id={id}
        className="ck-slider__input"
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {hint && <div className="ck-slider__hint">{hint}</div>}
    </div>
  );
}
