import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { getDashboard, getScenario } from "../api";
import "./Home.css";

export default function Home() {
  const [dashboard, setDashboard] = useState(null);
  const [scenario, setScenario] = useState(null);
  useEffect(() => {
    getDashboard().then(setDashboard).catch(() => {});
    getScenario().then(setScenario).catch(() => {});
  }, []);
  const plan = dashboard?.plan;
  const lastTrend = dashboard?.fill_trend?.at(-1);

  return (
    <div className="home-root">
      <div className="home-badge"><span className="home-dot" />
        SOCIOTHON 2026 · Prototype on simulated data</div>
      <h1 className="home-title">Waste collection that sees <em>tomorrow</em></h1>
      <p className="home-subtitle">CHAKRA forecasts which campus bins will overflow by the end of tomorrow, plans capacity-safe routes for only those bins, and proves the trade-off on a 30-day digital twin.</p>
      <div className="home-actions">
        <Link className="home-primary" to="/map">Open the risk map</Link>
        <Link className="home-play" to="/twin" aria-label="See the 30-day twin">
          <svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24">
            <path d="M8 5.5v13l10.5-6.5z" fill="currentColor" />
          </svg>
        </Link>
      </div>
      <figure className="home-preview" aria-label="Preview of the CHAKRA dispatcher screen with simulated data">
        <div className="home-preview-inner">
          <div className="home-preview-top">
            <strong><span className="home-mark">C</span> CHAKRA</strong>
            <span>Dispatcher overview</span>
            <span>{scenario?.plan_date ? `Plan for ${scenario.plan_date}` : "Simulated scenario"}</span>
          </div>
          <div className="home-preview-body">
            <aside className="home-preview-nav">
              <strong>Risk map</strong><span>Plan tomorrow</span><span>Worker</span>
              <span>Reports</span><span>Twin lab</span><span>Dashboard</span>
            </aside>
            <div className="home-preview-main">
              <div className="home-preview-greeting">
                <strong>Good evening, Dispatcher</strong>
                <span>Live view of the simulated scenario</span>
              </div>
              <div className="home-preview-pills">
                <span>Plan routes</span><span>Tap a level</span><span>Report overflow</span>
                <span>Check an item</span>
              </div>
              <div className="home-preview-cards">
                <section>
                  <small>Bins to visit tomorrow</small>
                  <strong>{plan?.selected ?? "—"} <small>of {scenario?.bins_count ?? "—"}</small></strong>
                  <p>{plan ? `${plan.skipped} bins skipped by the committed plan` : "Commit a plan to see the route summary"}</p>
                  <svg className="home-spark" viewBox="0 0 300 80" preserveAspectRatio="none" aria-hidden="true">
                    <defs><linearGradient id="homeAreaFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="var(--color-accent)" stopOpacity=".22" />
                      <stop offset="100%" stopColor="var(--color-accent)" stopOpacity="0" />
                    </linearGradient></defs>
                    <path d="M0 62 C35 57 42 42 72 49 S112 65 146 42 S191 57 221 30 S268 47 300 18 L300 80 L0 80Z" fill="url(#homeAreaFill)" />
                    <path d="M0 62 C35 57 42 42 72 49 S112 65 146 42 S191 57 221 30 S268 47 300 18" fill="none" stroke="var(--color-accent)" strokeWidth="2" />
                  </svg>
                </section>
                <section>
                  <small>Collection at a glance</small>
                  <strong>{lastTrend?.avg_fill_pct == null ? "—" : `${lastTrend.avg_fill_pct.toFixed(0)}%`}</strong>
                  <p>Average observed fill on the latest day</p>
                  <div className="home-fleet"><span>Reports open</span><b>{dashboard?.reports.open ?? "—"}</b></div>
                  <div className="home-fleet"><span>Pickups completed</span><b>{dashboard?.pickups.live_total ?? "—"}</b></div>
                </section>
              </div>
              <div className="home-preview-footer">
                <strong>Collection handoff</strong>
                <span>Plan → worker pickup → batch → compost stop</span>
              </div>
            </div>
          </div>
        </div>
      </figure>
    </div>
  );
}
