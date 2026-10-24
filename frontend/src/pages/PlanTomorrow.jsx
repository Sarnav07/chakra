// OWNER: P3 (stub created by P3)
import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  PageHeader, Notice, Loading, EmptyState, Stat, Card, Button,
  Slider, StatusPill, DataTable, CHART,
} from "../ui";
import {
  getScenario, postDecisions, postRoutes, choosePlan,
} from "../api";
import RouteMap from "../components/RouteMap";

function readTau() {
  try {
    const v = parseFloat(localStorage.getItem("chakra.tau"));
    if (!isNaN(v) && v >= 0.05 && v <= 0.95) return v;
  } catch {}
  return 0.5;
}

function saveTau(v) {
  try { localStorage.setItem("chakra.tau", String(v)); } catch {}
}

function statusForReason(rc) {
  if (rc === "overflowing_now") return "overflowing";
  if (rc === "reported") return "reported";
  if (rc === "needs_review") return "review";
  if (rc === "p_over_tau") return "selected";
  return "skipped";
}

export default function PlanTomorrow() {
  const [tau, setTau] = useState(readTau);
  const [assumptions, setAssumptions] = useState({ tau_min: 0.05, tau_max: 0.95, detour_factor: null });
  const [nodes, setNodes] = useState([]);
  const [summary, setSummary] = useState(null);
  const [decisions, setDecisions] = useState([]);
  const [isMock, setIsMock] = useState(false);
  const [plan, setPlan] = useState(null);
  const [planning, setPlanning] = useState(false);
  const [choosing, setChoosing] = useState(false);
  const [chosen, setChosen] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showTable, setShowTable] = useState(false);
  const [selectedFleet, setSelectedFleet] = useState(null);

  const reqCounter = useRef(0);
  const debounceTimer = useRef(null);

  const loadDecisions = useCallback(async (t) => {
    const id = ++reqCounter.current;
    try {
      const d = await postDecisions(t);
      if (id < reqCounter.current) return;
      setSummary(d.summary);
      setDecisions(d.decisions || []);
      setIsMock(!!d.mock);
    } catch (err) {
      if (id < reqCounter.current) return;
      setError(err.message);
    }
  }, []);

  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const s = await getScenario();
        setAssumptions(s.assumptions || { tau_min: 0.05, tau_max: 0.95, detour_factor: null });
        setNodes(s.nodes || []);
      } catch {}
      await loadDecisions(tau);
      setLoading(false);
    }
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    return () => { if (debounceTimer.current) clearTimeout(debounceTimer.current); };
  }, []);

  function handleTauChange(val) {
    const rounded = Math.round(val * 100) / 100;
    setTau(rounded);
    saveTau(rounded);
    if (debounceTimer.current) clearTimeout(debounceTimer.current);
    debounceTimer.current = setTimeout(() => loadDecisions(rounded), 300);
  }

  async function handlePlanRoutes() {
    setPlanning(true);
    setError(null);
    setChosen(null);
    try {
      const p = await postRoutes({ tau });
      setPlan(p);
      const rec = p.recommended_fleet_size;
      if (rec != null) {
        setSelectedFleet(rec);
      } else if (p.alternatives && p.alternatives.length > 0) {
        setSelectedFleet(p.alternatives[0].fleet_size);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setPlanning(false);
    }
  }

  async function handleChoose(planId, fleetSize) {
    setChoosing(true);
    setError(null);
    try {
      await choosePlan(planId, fleetSize);
      setChosen(fleetSize);
    } catch (err) {
      setError(err.message);
    } finally {
      setChoosing(false);
    }
  }

  if (loading) return <Loading text="Loading..." />;

  const rec = plan?.recommended_fleet_size;
  const recAlt = plan?.alternatives?.find((a) => a.fleet_size === rec);
  const baseline = plan?.baseline;
  const savings = plan?.savings_vs_baseline;
  const showAlt = plan?.alternatives?.find((a) => a.fleet_size === selectedFleet);

  const decisionColumns = [
    { key: "name", label: "Bin" },
    { key: "reason_code", label: "Status", render: (v) => <StatusPill status={statusForReason(v)} /> },
    { key: "p_overflow", label: "P(overflow)", render: (v) => v != null ? `${(v * 100).toFixed(0)}%` : "—" },
    { key: "reason", label: "Reason" },
  ];

  return (
    <>
      <PageHeader
        title="Plan tomorrow"
        badges={["implemented", "simulated"]}
      />
      {assumptions.detour_factor != null && (
        <p style={{ fontSize: "0.8125rem", color: "var(--color-muted)", marginTop: 0 }}>
          Distances are straight-line &times; detour factor {assumptions.detour_factor}
        </p>
      )}

      {isMock && <Notice kind="info">Mock data from the backend</Notice>}
      {error && <Notice kind="error">{error}</Notice>}
      {chosen && (
        <Notice kind="success">
          Plan committed (fleet size {chosen}). <Link to="/worker">Go to Worker</Link>
        </Notice>
      )}

      <Card>
        <Slider
          label="Risk threshold tau"
          min={assumptions.tau_min}
          max={assumptions.tau_max}
          step={0.05}
          value={tau}
          onChange={handleTauChange}
          hint="Visit a bin if its chance of overflowing tomorrow is above tau. Overflowing, reported and no-reading bins are always visited."
        />
        <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.75rem", color: "var(--color-muted)", marginTop: "-8px", marginBottom: tau < 0.5 ? "var(--space-3)" : 0 }}>
          <span>← Careful – visit more bins</span>
          <span>Saving – visit fewer bins →</span>
        </div>
        {tau < 0.5 && (
          <Notice kind="info">Safety mode: tau below 0.5 visits more bins than the median-forecast rule.</Notice>
        )}
      </Card>

      {summary && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
          <Stat label="Selected" value={summary.selected ?? 0} />
          <Stat label="Skipped" value={summary.skipped ?? 0} />
          <Stat label="Needs review" value={summary.needs_review ?? 0} />
          <Stat label="Reported" value={summary.reported ?? 0} />
          <Stat label="Overflowing now" value={summary.overflowing_now ?? 0} />
          <Stat label="Expected overflows among skipped" value={(summary.expected_overflows_skipped ?? 0).toFixed(2)} />
        </div>
      )}

      <div style={{ marginBottom: "var(--space-4)" }}>
        <Button variant="primary" onClick={handlePlanRoutes} disabled={planning}>
          {planning ? "Planning..." : "Plan routes"}
        </Button>
        {planning && <Loading text="Computing routes..." />}
      </div>

      {plan && (
        <>
          {rec == null && (
            <Notice kind="error">No feasible alternative</Notice>
          )}

          <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap", marginBottom: "var(--space-3)" }}>
            {plan.alternatives.map((alt) => (
              <Button
                key={alt.fleet_size}
                variant={alt.fleet_size === selectedFleet ? "primary" : "secondary"}
                size="sm"
                onClick={() => setSelectedFleet(alt.fleet_size)}
              >
                Fleet {alt.fleet_size} {alt.fleet_size === rec ? " ★" : ""}
              </Button>
            ))}
          </div>

          {plan.alternatives.map((alt) => (
            <Card
              key={alt.fleet_size}
              title={`Fleet size ${alt.fleet_size}${alt.fleet_size === rec ? " — Recommended" : ""}`}
              actions={
                alt.feasible && !chosen ? (
                  <Button variant="primary" size="sm" onClick={() => handleChoose(plan.plan_id, alt.fleet_size)} disabled={choosing}>
                    Choose this plan
                  </Button>
                ) : null
              }
            >
              {!alt.feasible && (
                <Notice kind="error">
                  Manual dispatch required — unassigned bins: {alt.unassigned_bin_ids.join(", ")}
                </Notice>
              )}
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(120px, 1fr))", gap: "var(--space-2)" }}>
                <Stat label="Total km" value={alt.total_km.toFixed(1)} />
                <Stat label="Minutes" value={alt.completion_minutes.toFixed(0)} />
                <Stat label="Cost" value={`Rs ${alt.total_cost_rs.toFixed(0)}`} />
                <Stat label="Vehicles" value={alt.vehicles_used} />
              </div>
            </Card>
          ))}

          <Card title="Nearest-neighbour baseline (same bins, same fleet)">
            {baseline ? (
              <div>
                <div style={{ display: "flex", gap: "var(--space-4)", flexWrap: "wrap", marginBottom: "var(--space-2)" }}>
                  <Stat label="Baseline km" value={baseline.total_km.toFixed(1)} />
                  <Stat label="Baseline cost" value={`Rs ${baseline.total_cost_rs.toFixed(0)}`} />
                  {recAlt && (
                    <>
                      <Stat label="Recommended km" value={recAlt.total_km.toFixed(1)} />
                      <Stat label="Recommended cost" value={`Rs ${recAlt.total_cost_rs.toFixed(0)}`} />
                    </>
                  )}
                </div>
                {savings ? (
                  <p style={{ fontSize: "0.875rem" }}>
                    Simulated saving: {savings.km.toFixed(1)} km ({savings.km_pct.toFixed(1)}%), Rs {savings.cost_rs.toFixed(0)}
                  </p>
                ) : (
                  <p style={{ fontSize: "0.875rem", color: "var(--color-muted)" }}>No feasible plan to compare</p>
                )}
              </div>
            ) : (
              <EmptyState title="No baseline available" />
            )}
          </Card>

          {showAlt && (
            <RouteMap alternative={showAlt} nodes={nodes} />
          )}

          <div style={{ marginTop: "var(--space-4)" }}>
            <Button variant="ghost" size="sm" onClick={() => setShowTable(!showTable)}>
              {showTable ? "Hide decisions table" : "Show decisions table"}
            </Button>
            {showTable && (
              <DataTable
                columns={decisionColumns}
                rows={decisions}
                emptyText="No decisions"
              />
            )}
          </div>
        </>
      )}
    </>
  );
}
