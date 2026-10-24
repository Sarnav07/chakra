export default function Button({
  variant = "primary",
  size = "md",
  disabled,
  onClick,
  type,
  children,
}) {
  return (
    <button
      className={`ck-btn ck-btn--${variant} ck-btn--${size}`}
      disabled={disabled}
      onClick={onClick}
      type={type}
    >
      {children}
    </button>
  );
}
