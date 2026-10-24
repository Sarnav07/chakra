export function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#5E6A6B";
}

export function riskColor(item) {
  if (!item) return "var(--color-muted)";
  const rc = item.reason_code;
  if (rc === "overflowing_now") return "var(--color-overflow)";
  if (rc === "reported") return "var(--color-reported)";
  if (rc === "needs_review") return "var(--color-review)";
  const p = item.p_overflow;
  if (p == null) return "var(--color-muted)";
  if (p < 0.3) return "var(--color-risk-low)";
  if (p < 0.6) return "var(--color-risk-mid)";
  return "var(--color-risk-high)";
}
