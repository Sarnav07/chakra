// OWNER: P3
import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  PageHeader, Notice, Loading, EmptyState, Card, Button,
} from "../ui";
import { getWorkerRoutes, confirmPickup, arriveCompost } from "../api";
import ReportOverflowButton from "../components/ReportOverflowButton";

function localTime(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  } catch {
    return iso;
  }
}

export default function Worker() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [activeRoute, setActiveRoute] = useState(null);
  const [busy, setBusy] = useState(null);
  const [levels, setLevels] = useState({});
  const [notes, setNotes] = useState({});
  const [stopError, setStopError] = useState({});
  const [compostBusy, setCompostBusy] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await getWorkerRoutes();
      setData(d);
      if (!activeRoute && d.routes?.length) setActiveRoute(d.routes[0].route_id);
      setError(null);
    } catch (err) {
      if (err.message.includes("404") || err.message.toLowerCase().includes("no committed plan")) {
        setData(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }, [activeRoute]);

  useEffect(() => { load(); }, [load]);

  async function handleConfirm(routeId, binId) {
    const key = `${routeId}:${binId}`;
    setBusy(key);
    setStopError((prev) => ({ ...prev, [key]: null }));
    const body = { route_id: routeId, bin_id: binId };
    const lv = levels[key];
    if (lv) body.level = lv;
    const nt = notes[key];
    if (nt) body.staff_note = nt;
    try {
      await confirmPickup(body);
      await load();
    } catch (err) {
      setStopError((prev) => ({ ...prev, [key]: err.message }));
    } finally {
      setBusy(null);
    }
  }

  async function handleCompost(routeId) {
    setCompostBusy(true);
    try {
      await arriveCompost(routeId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setCompostBusy(false);
    }
  }

  if (loading) return <Loading text="Loading routes..." />;

  if (!data) {
    return (
      <>
        <PageHeader title="Worker" badges={["implemented", "simulated"]} />
        <Notice kind="info">
          No plan committed yet — <Link to="/plan">commit a plan on Plan tomorrow</Link>.
        </Notice>
        {error && <Notice kind="error">{error}</Notice>}
      </>
    );
  }

  const routes = data.routes || [];
  const current = routes.find((r) => r.route_id === activeRoute) || routes[0];

  return (
    <>
      <PageHeader title="Worker" badges={["implemented", "simulated"]} />
      {error && <Notice kind="error">{error}</Notice>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-3)" }}>
        {routes.map((r) => (
          <Button
            key={r.route_id}
            variant={r.route_id === current?.route_id ? "primary" : "secondary"}
            size="sm"
            onClick={() => setActiveRoute(r.route_id)}
          >
            {r.vehicle_id} ({r.stream}){r.stream === "food" ? " — ends at compost stop" : ""}
          </Button>
        ))}
      </div>

      {current && (
        <Card title={`${current.vehicle_id} — ${current.stream}`}>
          {(current.stops || [])
            .slice()
            .sort((a, b) => a.seq - b.seq)
            .map((stop) => {
              const key = `${current.route_id}:${stop.bin_id}`;
              const isBusy = busy === key;
              const err = stopError[key];
              return (
                <div
                  key={stop.bin_id}
                  style={{
                    padding: "var(--space-2) 0",
                    borderBottom: "1px solid var(--color-border)",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", flexWrap: "wrap" }}>
                    <span style={{ fontWeight: 600, minWidth: 28 }}>{stop.seq}.</span>
                    <span>{stop.name}</span>
                    {stop.done && (
                      <span style={{ color: "var(--color-success)", fontSize: "0.875rem" }}>
                        ✓ {localTime(stop.completed_at)}
                      </span>
                    )}
                  </div>

                  {!stop.done && (
                    <div style={{ marginTop: "var(--space-2)", display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
                      <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
                        <select
                          value={levels[key] || ""}
                          onChange={(e) => setLevels((p) => ({ ...p, [key]: e.target.value || undefined }))}
                          style={{ minHeight: 48, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)" }}
                        >
                          <option value="">Level (optional)</option>
                          <option value="low">Low</option>
                          <option value="medium">Medium</option>
                          <option value="full">Full</option>
                        </select>
                        <input
                          type="text"
                          placeholder="Note (optional)"
                          value={notes[key] || ""}
                          onChange={(e) => setNotes((p) => ({ ...p, [key]: e.target.value }))}
                          style={{ minHeight: 48, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", flex: 1, minWidth: 120 }}
                        />
                      </div>
                      <Button
                        variant="primary"
                        disabled={isBusy}
                        onClick={() => handleConfirm(current.route_id, stop.bin_id)}
                      >
                        {isBusy ? "Saving..." : "Done"}
                      </Button>
                      {err && (
                        <Notice kind="error">
                          {err.toLowerCase().includes("already confirmed") ? "Already confirmed" : err}
                        </Notice>
                      )}
                    </div>
                  )}

                  <div style={{ marginTop: "var(--space-1)" }}>
                    <ReportOverflowButton binId={stop.bin_id} binName={stop.name} onReported={load} />
                  </div>
                </div>
              );
            })}

          {current.stream === "food" && current.all_done && !current.compost_delivered && (
            <div style={{ marginTop: "var(--space-3)" }}>
              <Button
                variant="primary"
                disabled={compostBusy}
                onClick={() => handleCompost(current.route_id)}
              >
                {compostBusy ? "Registering..." : "Arrived at compost stop"}
              </Button>
            </div>
          )}
          {current.stream === "food" && current.compost_delivered && (
            <Notice kind="success">
              Delivered to compost stop (delivery only, no compost output claimed).
            </Notice>
          )}
        </Card>
      )}

      {routes.length === 0 && <EmptyState title="No routes in this plan" />}
    </>
  );
}
