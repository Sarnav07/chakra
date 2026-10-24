import { NavLink } from "react-router-dom";
import { resetDemo } from "../api";
import Button from "./Button";
import Notice from "./Notice";
import Backdrop from "./Backdrop";
import LeafLogo from "./LeafLogo";

const NAV_LINKS = [
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
      <header className="ck-topbar">
        <LeafLogo />
        <nav className="ck-topbar__nav">
          {NAV_LINKS.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              className={({ isActive }) =>
                `ck-topbar__link${isActive ? " ck-topbar__link--active" : ""}`
              }
>
              {link.label}
            </NavLink>
          ))}
        </nav>
        <Button variant="danger" size="sm" onClick={handleReset}>
          Reset demo
        </Button>
      </header>
      <Notice kind="info">Data shown is SIMULATED for the prototype</Notice>
      <main className="page">{children}</main>
    </>
  );
}
