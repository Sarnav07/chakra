import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getDashboard, getForecastEval } from "../api";
import { Card, CHART, EmptyState, Loading, Notice, PageHeader, Stat } from "../ui";

function number(value, places = 1) {
  return value == null ? "—" : Number(value).toFixed(places);
}

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [quality, setQuality] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    getDashboard().then(setData).catch((err) => setError(err.message));
    getForecastEval().then(setQuality).catch(() => setQuality(null));
  }, []);

  if (!data && !error) return <Loading text="Loading dashboard..." />;
  const plan = data?.plan;
  return (
    <>
      <PageHeader title="Dashboard" subtitle="Campus collection at a glance"
        badges={["implemented", "simulated"]} />
      {error && <Notice kind="error">{error}</Notice>}
      {data && (
        <>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 12, marginBottom: 20 }}>
            <Stat label="Plan distance" value={number(plan?.km)} unit="km"
              hint={plan ? `vs ${number(plan.baseline_km)} km nearest-neighbour baseline` : "Choose a plan first"} />
            <Stat label="Simulated saving" value={number(plan?.saving_pct)} unit="%" />
            <Stat label="Pickups today" value={data.pickups.today} />
            <Stat label="Open reports" value={data.reports.open} />
            <Stat label="Missed collections" value={data.reports.missed_collections} />
            <Stat label="Pending handoff" value={number(data.batches.pending_handoff_l)} unit="L" />
            <Stat label="Delivered to compost stop"
              value={number(data.batches.delivered_to_compost_l)} unit="L" />
          </div>
          <Card title="Fill trend · last 14 days">
            {data.fill_trend.length ? (
              <div style={{ height: 280 }}>
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={data.fill_trend}>
                    <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                    <XAxis dataKey="date" fontSize={CHART.fontSize} />
                    <YAxis fontSize={CHART.fontSize} />
                    <Tooltip />
                    <Line dataKey="avg_fill_pct" name="Average fill %" stroke={CHART.series[0]} />
                    <Line dataKey="full_bins" name="Full readings" stroke={CHART.series[2]} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            ) : <EmptyState title="No fill readings yet" />}
          </Card>
          <Card title="Mess food waste">
            <p>Last 7 days: <strong>{number(data.mess.last7_total_kg)} kg</strong></p>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 12 }}>
              {Object.entries(data.mess.by_meal_avg_kg).map(([meal, kg]) => (
                <Stat key={meal} label={meal} value={number(kg)} unit="kg average per entry" />
              ))}
            </div>
          </Card>
          <Card title="Forecast quality">
            {quality ? (
              <>
                <p>Model MAE: <strong>{number(quality.mae_model, 2)}</strong> · Last-value baseline MAE:{" "}
                  <strong>{number(quality.mae_baseline, 2)}</strong></p>
                <p>Interval coverage: <strong>{number(quality.interval_coverage * 100)}%</strong></p>
                <p>Time-split test on simulated history.</p>
              </>
            ) : <EmptyState title="Forecast evaluation unavailable" />}
          </Card>
          <p>Simulated scenario data; delivery to the compost stop does not mean compost was produced.</p>
        </>
      )}
    </>
  );
}
