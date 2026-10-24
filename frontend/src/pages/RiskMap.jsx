// OWNER: P3 (stub created by P3)
import { useState, useEffect, useRef, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  PageHeader, Notice, Loading, EmptyState, Stat, Card, StatusPill,
  Button, MapLegend, cssVar,
} from "../ui";
import { getScenario, postDecisions, postObservation, runForecasts } from "../api";
import BinMap from "../components/BinMap";
import ReportOverflowButton from "../components/ReportOverflowButton";

function readTau() {
  try {
    const v = parseFloat(localStorage.getItem("chakra.tau"));
    if (!isNaN(v) && v >= 0.05 && v <= 0.95) return v;
  } catch {}
  return 0.5;
}

function statusForBin(d) {
  if (d.reason_code === "overflowing_now") return "overflowing";
  if (d.reason_code === "reported") return "reported";
  if (d.reason_code === "needs_review") return "review";
  if (d.reason_code === "p_over_tau") return "selected";
  return "skipped";
}

function fmtPct(v) {
  if (v == null) return "no reading";
  return `${v.toFixed(0)}%`;
}

export default function RiskMap() {
  const [tau] = useState(readTau);
  const [scenario, setScenario] = useState(null);
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState("all");
  const [saving, setSaving] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [isMock, setIsMock] = useState(false);
  const reqCounter = useRef(0);

  const loadDecisions = useCallback(async () => {
    const id = ++reqCounter.current;
    try {
      const d = await postDecisions(tau);
      if (id < reqCounter.current) return;
      setData(d);
      setIsMock(!!d.mock);
      setError(null);
    } catch (err) {
      if (id < reqCounter.current) return;
      setError(err.message);
    }
  }, [tau]);

  useEffect(() => {
    async function init() {
      setLoading(true);
      try {
        const s = await getScenario();
        setScenario(s);
      } catch {}
      await loadDecisions();
      setLoading(false);
    }
    init();
  }, [loadDecisions]);

  async function handleObservation(binId, level) {
    setSaving(true);
    try {
      await postObservation({ bin_id: binId, level });
      await loadDecisions();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try {
      await runForecasts();
      await loadDecisions();
    } catch (err) {
      setError(err.message);
    } finally {
      setRefreshing(false);
    }
  }

  if (loading) return <Loading text="Loading risk map..." />;

  const decisions = data?.decisions || [];
  const summary = data?.summary || {};
  const nodes = scenario?.nodes || [];

  const filtered = filter === "all"
    ? decisions
    : decisions.filter((d) => {
        if (filter === "selected") return d.reason_code === "p_over_tau";
        if (filter === "skipped") return d.reason_code === "below_tau";
        if (filter === "review") return d.reason_code === "needs_review";
        if (filter === "reported") return d.reason_code === "reported";
        return true;
      });

  const reviewBins = decisions.filter((d) => d.reason_code === "needs_review");
  const selected = decisions.find((d) => d.bin_id === selectedId);

  return (
    <>
      <PageHeader
        title="Risk map"
        subtitle="Chance each bin overflows by the end of tomorrow"
        badges={["implemented", "simulated"]}
      />

      {isMock && <Notice kind="info">Mock data from the backend</Notice>}
      {error && <Notice kind="error">{error}</Notice>}

      <div style={{ marginBottom: "var(--space-3)" }}>
        <span style={{ fontSize: "0.875rem", color: "var(--color-muted)" }}>
          tau = {tau.toFixed(2)}{" "}
          <Link to="/plan" style={{ fontSize: "0.8125rem" }}>
            change on Plan tomorrow
          </Link>
        </span>
      </div>

      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-2)", marginBottom: "var(--space-4)" }}>
        <Stat label="Selected" value={summary.selected ?? 0} />
        <Stat label="Skipped" value={summary.skipped ?? 0} />
        <Stat label="Needs review" value={summary.needs_review ?? 0} />
        <Stat label="Reported" value={summary.reported ?? 0} />
        <Stat label="Overflowing now" value={summary.overflowing_now ?? 0} />
        <Stat
          label="Expected overflows among skipped bins"
          value={(summary.expected_overflows_skipped ?? 0).toFixed(2)}
        />
      </div>

      <div style={{ marginBottom: "var(--space-3)", display: "flex", gap: "var(--space-2)", flexWrap: "wrap", alignItems: "center" }}>
        <label style={{ fontSize: "0.875rem", fontWeight: 500 }}>Filter: </label>
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ minHeight: 44, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)" }}
        >
          <option value="all">All</option>
          <option value="selected">Selected</option>
          <option value="skipped">Skipped</option>
          <option value="review">Needs review</option>
          <option value="reported">Reported</option>
        </select>
        <Button variant="secondary" size="sm" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? "Refreshing..." : "Refresh forecast"}
        </Button>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: "var(--space-4)" }}
           className="riskmap-columns">
        <style>{`@media (min-width: 900px) { .riskmap-columns { grid-template-columns: 1fr 360px !important; } }`}</style>

        <div>
          <BinMap
            items={filtered}
            nodes={nodes}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
          <MapLegend items={[
            { color: cssVar("--color-risk-low"), label: "Low risk" },
            { color: cssVar("--color-risk-mid"), label: "Medium risk" },
            { color: cssVar("--color-risk-high"), label: "High risk" },
            { color: cssVar("--color-overflow"), label: "Overflowing now" },
            { color: cssVar("--color-reported"), label: "Reported" },
            { color: cssVar("--color-review"), label: "Needs review", dashed: true },
            { color: cssVar("--color-primary"), label: "Depot" },
            { color: cssVar("--color-success"), label: "Compost stop" },
          ]} />
        </div>

        <div>
          {selected ? (
            <Card title={selected.name}>
              <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-3)" }}>
                <div>{selected.group_name} <StatusPill status={statusForBin(selected)} /></div>
                <div>Current fill: <strong>{fmtPct(selected.current_fill_pct)}</strong></div>
                <div>Predicted fill: <strong>{fmtPct(selected.predicted_fill_pct)}</strong></div>
                <div>P(overflow): <strong>{selected.p_overflow != null ? `${(selected.p_overflow * 100).toFixed(0)}%` : "no reading"}</strong></div>
                <div style={{ fontSize: "0.875rem", color: "var(--color-muted)" }}>{selected.reason}</div>
                <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
                  {["low", "medium", "full"].map((level) => (
                    <Button
                      key={level}
                      variant="secondary"
                      size="sm"
                      disabled={saving}
                      onClick={() => handleObservation(selected.bin_id, level)}
                    >
                      {level.charAt(0).toUpperCase() + level.slice(1)}
                    </Button>
                  ))}
                </div>
                <ReportOverflowButton binId={selected.bin_id} binName={selected.name} onReported={loadDecisions} />
              </div>
            </Card>
          ) : (
            <EmptyState title="Tap a bin on the map" />
          )}

          {reviewBins.length > 0 && (
            <Card title="Review queue">
              {reviewBins
                .filter((d) => filter === "all" || filter === "review")
                .map((d) => (
                  <div
                    key={d.bin_id}
                    onClick={() => setSelectedId(d.bin_id)}
                    style={{
                      padding: "var(--space-2)",
                      cursor: "pointer",
                      borderBottom: "1px solid var(--color-border)",
                      background: d.bin_id === selectedId ? "var(--color-bg)" : undefined,
                    }}
                  >
                    {d.name} <StatusPill status="review" />
                  </div>
                ))}
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
