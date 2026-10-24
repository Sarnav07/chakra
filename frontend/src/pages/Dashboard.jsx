// OWNER: P3
import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import {
  LineChart, Line, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  PageHeader, Card, Stat, DataTable, Loading, EmptyState, Notice, Button, CHART,
} from "../ui";
import { getDashboard, getForecastEval, runForecasts } from "../api";

const fmt = (v, dp = 1) => (v == null ? "-" : Number(v).toFixed(dp));
const fmtInt = (v) => (v == null ? "-" : String(v));

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [evalData, setEvalData] = useState(null);
  const [evalError, setEvalError] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [runningForecast, setRunningForecast] = useState(false);

  const load = useCallback(async () => {
    try {
      const [dash, evalRes] = await Promise.allSettled([
        getDashboard(),
        getForecastEval(),
      ]);
      if (dash.status === "fulfilled") {
        setData(dash.value);
        setError(null);
      } else {
        setError(dash.reason?.message || "Failed to load dashboard");
      }
      if (evalRes.status === "fulfilled") {
        setEvalData(evalRes.value);
        setEvalError(null);
      } else {
        setEvalError(evalRes.reason?.message || "Forecast eval unavailable");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  async function handleRunForecast() {
    setRunningForecast(true);
    try {
      await runForecasts();
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setRunningForecast(false);
    }
  }

  if (loading) return <Loading text="Loading dashboard..." />;
  if (error && !data) return <Notice kind="error">{error}</Notice>;

  const { plan, forecast, fill_trend, pickups, reports, batches, mess } = data;

  const mealColumns = [
    { key: "meal", label: "Meal" },
    { key: "avg_kg", label: "Avg kg/day" },
  ];
  const mealRows = mess?.by_meal_avg_kg
    ? Object.entries(mess.by_meal_avg_kg).map(([meal, avg]) => ({
        id: meal, meal, avg_kg: fmt(avg),
      }))
    : [];

  return (
    <>
      <PageHeader title="Dashboard" badges={["implemented", "simulated"]} />
      {error && <Notice kind="error">{error}</Notice>}

      <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
        <Stat label="Plan km" value={fmt(plan?.km)} />
        <Stat label="Baseline km" value={fmt(plan?.baseline_km)} />
        <Stat label="Simulated saving" value={plan?.saving_pct != null ? fmt(plan.saving_pct) : "-"} unit="%" />
        <Stat label="Pickups today" value={fmtInt(pickups?.today)} />
        <Stat label="Open reports" value={fmtInt(reports?.open)} />
        <Stat label="Missed collections" value={fmtInt(reports?.missed_collections)} />
        <Stat label="Litres pending handoff" value={fmt(batches?.pending_handoff_l)} />
        <Stat label="Litres delivered to compost stop" value={fmt(batches?.delivered_to_compost_l)} />
      </div>

      {!plan && (
        <EmptyState title="No plan committed yet">
          <Link to="/plan" style={{ color: "var(--color-primary)" }}>Go to Plan tomorrow</Link>
        </EmptyState>
      )}

      {!forecast && (
        <EmptyState title="No forecast yet">
          <Button variant="primary" disabled={runningForecast} onClick={handleRunForecast}>
            {runningForecast ? "Running..." : "Run forecast"}
          </Button>
        </EmptyState>
      )}

      {fill_trend && fill_trend.length > 0 && (
        <Card title="Fill trend (14 days)">
          <div style={{ height: 280 }}>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={fill_trend}>
                <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
                <XAxis dataKey="date" fontSize={CHART.fontSize} />
                <YAxis yAxisId="left" fontSize={CHART.fontSize} unit="%" domain={[0, "auto"]} />
                <YAxis yAxisId="right" orientation="right" fontSize={CHART.fontSize} allowDecimals={false} />
                <Tooltip />
                <Line yAxisId="left" type="monotone" dataKey="avg_fill_pct" name="Avg fill %" stroke={CHART.series[0]} dot={false} />
                <Line yAxisId="right" type="monotone" dataKey="full_bins" name="Full bins" stroke={CHART.series[1]} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
      )}

      <Card title="Mess leftovers">
        <Stat label="Last 7 days total" value={fmt(mess?.last7_total_kg)} unit="kg" />
        <DataTable columns={mealColumns} rows={mealRows} emptyText="No mess data" />
      </Card>

      <Card title="Forecast quality">
        {evalError ? (
          <EmptyState title={evalError} />
        ) : evalData ? (
          <>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--space-3)" }}>
              <Stat label="MAE (model)" value={fmt(evalData.mae_model, 2)} />
              <Stat label="MAE (last-value baseline)" value={fmt(evalData.mae_baseline, 2)} />
              <Stat label="Interval coverage" value={fmt(evalData.interval_coverage * 100, 1)} unit="%" />
              <Stat label="Validation bins" value={fmtInt(evalData.n_val)} />
            </div>
            <p style={{ fontSize: "0.8rem", color: "var(--color-muted)", marginTop: "var(--space-2)" }}>
              time-split test on simulated history
            </p>
          </>
        ) : null}
      </Card>
    </>
  );
}
