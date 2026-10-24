import { useState, useEffect, useRef } from "react";
import {
  PageHeader, Notice, Loading, Button, Card, DataTable, CHART,
} from "../ui";
import { getTwin, runTwin } from "../api";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  ScatterChart, Scatter, LabelList, CartesianGrid, Cell,
} from "recharts";

const POLICY_LABELS = {
  A_fixed: "A Fixed route (every bin daily)",
  B_rule70: "B Simple rule (> 70% full)",
  C_chakra: "C CHAKRA",
};

const SHORT_LABELS = { A_fixed: "A Fixed", B_rule70: "B 70% rule", C_chakra: "C CHAKRA" };

function policyLabel(p) {
  if (p.policy === "C_chakra") return `C CHAKRA (tau ${p.tau})`;
  return POLICY_LABELS[p.policy] || p.policy;
}

function fmt(mean, min, max) {
  if (mean == null) return "—";
  const m = typeof mean === "number" ? mean.toFixed(1) : mean;
  const lo = typeof min === "number" ? min.toFixed(1) : min;
  const hi = typeof max === "number" ? max.toFixed(1) : max;
  return `${m} (${lo}–${hi})`;
}

function readTau() {
  try {
    const v = parseFloat(localStorage.getItem("chakra.tau"));
    if (!isNaN(v) && v >= 0 && v <= 1) return v;
  } catch {}
  return 0.5;
}

export default function TwinLab() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const [error, setError] = useState(null);
  const timerRef = useRef(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const d = await getTwin();
      setData(d);
    } catch (err) {
      if (err.message.includes("404") || err.message.toLowerCase().includes("not found") || err.message.toLowerCase().includes("not cached")) {
        setData(null);
      } else {
        setError(err.message);
      }
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    if (running) {
      setElapsed(0);
      timerRef.current = setInterval(() => setElapsed((s) => s + 1), 1000);
    }
    return () => clearInterval(timerRef.current);
  }, [running]);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      await runTwin();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  if (loading) return <Loading text="Loading twin lab..." />;

  if (!data) {
    return (
      <>
        <PageHeader title="Twin lab" badges={["simulated"]} />
        <Notice kind="info">Twin results not cached</Notice>
        {error && <Notice kind="error">{error}</Notice>}
        {running ? (
          <Loading text={`Running twin simulation… ${elapsed}s`} />
        ) : (
          <Button onClick={handleRun}>Run twin (takes minutes)</Button>
        )}
      </>
    );
  }

  const { days, seeds, policies, sweep, sensitivity, assumptions } = data;
  const userTau = readTau();

  // --- Policy table ---
  const policyCols = [
    { key: "label", label: "Policy" },
    { key: "km", label: "km", render: (_, r) => fmt(r.mean?.km, r.min?.km, r.max?.km) },
    { key: "overflow", label: "Overflow events", render: (_, r) => fmt(r.mean?.overflow_events, r.min?.overflow_events, r.max?.overflow_events) },
    { key: "pickups", label: "Pickups", render: (_, r) => fmt(r.mean?.pickups, r.min?.pickups, r.max?.pickups) },
    { key: "cost", label: "Cost (Rs)", render: (_, r) => fmt(r.mean?.cost_rs, r.min?.cost_rs, r.max?.cost_rs) },
  ];
  const policyRows = (policies || []).map((p) => ({ ...p, id: p.policy, label: policyLabel(p) }));

  // --- Bar chart data ---
  const barKm = policyRows.map((p) => ({ name: SHORT_LABELS[p.policy] || p.policy, km: p.mean?.km ?? 0 }));
  const barOverflow = policyRows.map((p) => ({ name: SHORT_LABELS[p.policy] || p.policy, overflow: p.mean?.overflow_events ?? 0 }));

  // --- Scatter chart ---
  const scatterData = (sweep || []).map((s) => ({
    x: s.mean?.km ?? 0,
    y: s.mean?.overflow_events ?? 0,
    tau: s.tau,
  }));

  let highlightIdx = scatterData.findIndex((s) => Math.abs(s.tau - userTau) < 1e-6);
  if (highlightIdx === -1 && scatterData.length > 0) {
    let best = 0;
    let bestDist = Math.abs(scatterData[0].tau - userTau);
    for (let i = 1; i < scatterData.length; i++) {
      const d = Math.abs(scatterData[i].tau - userTau);
      if (d < bestDist) { best = i; bestDist = d; }
    }
    highlightIdx = best;
  }

  // --- Sensitivity table ---
  const sensCols = [
    { key: "detour_factor", label: "Detour factor" },
    { key: "policy", label: "Policy", render: (v) => SHORT_LABELS[v] || v },
    { key: "km", label: "km", render: (v) => (typeof v === "number" ? v.toFixed(1) : v) },
    { key: "overflow_events", label: "Overflow events", render: (v) => (typeof v === "number" ? v.toFixed(1) : v) },
  ];
  const sensRows = (sensitivity || []).map((s, i) => ({ ...s, id: i }));

  return (
    <>
      <PageHeader
        title="Twin lab"
        subtitle={`${days} simulated days, ${seeds?.length ?? 0} random seeds`}
        badges={["simulated"]}
      />
      {error && <Notice kind="error">{error}</Notice>}

      {/* Policy table */}
      <Card title="Policy comparison">
        <DataTable columns={policyCols} rows={policyRows} emptyText="No policies" />
      </Card>

      {/* Bar charts */}
      <div className="twin-bars" style={{ display: "grid", gap: "var(--space-4)", marginTop: "var(--space-4)" }}>
        <style>{`
          .twin-bars { grid-template-columns: 1fr; }
          @media (min-width: 900px) { .twin-bars { grid-template-columns: 1fr 1fr !important; } }
        `}</style>
        <Card title="km per policy">
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barKm}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                <XAxis dataKey="name" fontSize={CHART.fontSize} />
                <YAxis fontSize={CHART.fontSize} />
                <Tooltip />
                <Bar dataKey="km" fill={CHART.series[0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card title="Overflow events per policy">
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={barOverflow}>
                <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                <XAxis dataKey="name" fontSize={CHART.fontSize} />
                <YAxis fontSize={CHART.fontSize} />
                <Tooltip />
                <Bar dataKey="overflow" fill={CHART.series[1]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>
      </div>

      {/* Trade-off scatter chart */}
      <Card title="Trade-off: km vs overflow events" style={{ marginTop: "var(--space-4)" }}>
        <div style={{ height: 340 }}>
          <ResponsiveContainer width="100%" height="100%">
            <ScatterChart margin={{ top: 20, right: 30, bottom: 30, left: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
              <XAxis
                dataKey="x" type="number" name="km"
                fontSize={CHART.fontSize}
                label={{ value: `km (${days} days)`, position: "bottom", offset: 10, fontSize: CHART.fontSize }}
              />
              <YAxis
                dataKey="y" type="number" name="overflow events"
                fontSize={CHART.fontSize}
                label={{ value: "overflow events", angle: -90, position: "insideLeft", fontSize: CHART.fontSize }}
              />
              <Tooltip
                formatter={(val, name) => [typeof val === "number" ? val.toFixed(1) : val, name]}
                labelFormatter={() => ""}
              />
              <Scatter data={scatterData}>
                <LabelList
                  dataKey="tau"
                  position="top"
                  fontSize={10}
                  formatter={(v) => {
                    const idx = scatterData.findIndex((s) => s.tau === v);
                    if (idx === highlightIdx) return `τ=${v} (${Math.abs(scatterData[idx].tau - userTau) < 1e-6 ? "your tau" : "nearest to your tau"})`;
                    return `τ=${v}`;
                  }}
                />
                {scatterData.map((_, i) => (
                  <Cell
                    key={i}
                    fill={i === highlightIdx ? CHART.series[3] : CHART.series[0]}
                    r={i === highlightIdx ? 8 : 5}
                  />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <p style={{ fontSize: "0.8125rem", color: "var(--color-muted)", marginTop: "var(--space-2)" }}>
          Each dot is one slider position run for {days} simulated days. Left = fewer km, down = fewer overflows.
        </p>
      </Card>

      {/* Sensitivity */}
      <Card title="Sensitivity analysis" style={{ marginTop: "var(--space-4)" }}>
        <DataTable columns={sensCols} rows={sensRows} emptyText="No sensitivity data" />
      </Card>

      {/* Assumptions */}
      {assumptions && (
        <Card title="Assumptions" style={{ marginTop: "var(--space-4)" }}>
          <dl style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "var(--space-1) var(--space-3)", margin: 0, fontSize: "0.875rem" }}>
            {Object.entries(assumptions).map(([k, v]) => (
              <div key={k} style={{ display: "contents" }}>
                <dt style={{ fontWeight: 500, color: "var(--color-muted)" }}>{k}</dt>
                <dd style={{ margin: 0 }}>{typeof v === "object" ? JSON.stringify(v) : String(v)}</dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      {/* Caption */}
      <p style={{ fontSize: "0.8125rem", color: "var(--color-muted)", marginTop: "var(--space-4)" }}>
        All policies use the same router, so the differences come from which bins are visited. Simulated results, not field measurements.
      </p>
    </>
  );
}
