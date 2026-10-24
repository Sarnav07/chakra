import { useEffect, useState } from "react";
import { NavLink } from "react-router-dom";
import { resetDemo } from "../api";
import Button from "./Button";
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

  async function handleReset() {
    if (!window.confirm("Reset all demo data?")) return;
    try {
      await resetDemo();
      window.location.reload();
    } catch (err) {
      alert(err.message);
    }
  }

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
            <Button variant="secondary" size="sm" onClick={handleReset}>Reset demo</Button>
          </nav>
        </header>
        <div className="ck-simulated"><span />Data shown is SIMULATED for the prototype</div>
        <main id="main" className="page fade-up">{children}</main>
      </div>
    </>
  );
}
