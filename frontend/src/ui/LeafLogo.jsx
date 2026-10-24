// Leaf icon: Lucide (ISC License, (c) Lucide Icons and Contributors)
// via AnimateIcons (MIT License, (c) 2025 Avijit Dey)
import { Link } from "react-router-dom";

export default function LeafLogo({ size = 22 }) {
  return (
    <Link to="/" className="chakra-logo" aria-label="CHAKRA home">
      <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24"
        fill="none" stroke="var(--color-accent)" strokeWidth="2"
        strokeLinecap="round" strokeLinejoin="round">
        <path className="chakra-leaf"
          d="M11 20A7 7 0 0 1 9.8 6.1C15.5 5 17 4.48 19 2c1 2 2 4.18 2 8 0 5.5-4.78 10-10 10Z" />
        <path d="M2 21c0-3 1.85-5.36 5.08-6C9.5 14.52 12 13 13 12" />
      </svg>
      CHAKRA
    </Link>
  );
}
