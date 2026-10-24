import { Link } from "react-router-dom";

export default function LeafLogo({ size = 22 }) {
  return (
    <Link to="/" className="ck-leaf-logo" style={{ textDecoration: "none" }}>
      <svg
        className="ck-leaf-logo__icon"
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="var(--color-accent)"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c1.5-3 2-6.5 2-10S13.5 5 12 2z" />
        <path d="M12 2c3 2.5 5 6 5 10s-2 7.5-5 10" />
        <path d="M2 12h20" />
      </svg>
      <span className="ck-leaf-logo__text">CHAKRA</span>
    </Link>
  );
}
