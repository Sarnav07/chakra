import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import Backdrop from "./Backdrop";
import LeafLogo from "./LeafLogo";

const NAV_LINKS = [
  { to: "/", label: "Home" },
  { to: "/map", label: "Risk map" },
  { to: "/plan", label: "Plan tomorrow" },
  { to: "/worker", label: "Worker" },
  { to: "/reports", label: "Reports" },
  { to: "/check", label: "Check an item" },
  { to: "/mess", label: "Mess log" },
  { to: "/twin", label: "Twin lab" },
  { to: "/dashboard", label: "Dashboard" },
  { to: "/scale", label: "Scale lab" },
];

export default function Layout({ children }) {
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => {
    function closeOnEscape(event) { if (event.key === "Escape") setMenuOpen(false); }
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, []);

  return (
    <>
      <Backdrop />
      <div className="ck-shell">
        <a className="ck-skip" href="#main">Skip to content</a>
        <header className="ck-topbar">
          <LeafLogo />
          <button type="button" className="ck-menu-toggle"
            aria-expanded={menuOpen} aria-controls="chakra-nav"
            onClick={() => setMenuOpen((value) => !value)}>Menu</button>
          <nav id="chakra-nav" className={`ck-topbar__nav ${menuOpen ? "ck-topbar__nav--open" : ""}`}>
            {NAV_LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} onClick={() => setMenuOpen(false)}
                className={({ isActive }) =>
                  `ck-topbar__link${isActive ? " ck-topbar__link--active" : ""}`}
                end={link.to === "/"}>
                {link.label}
              </NavLink>
            ))}
          </nav>
        </header>
        <main id="main" className="page fade-up">{children}</main>
      </div>
    </>
  );
}
