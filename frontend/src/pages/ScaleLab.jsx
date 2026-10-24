// OWNER: P2
// Scale lab (/scale): three-stage planner vs nearest neighbour on the campus
// and a synthetic city instance. Every number comes from the API response.
import { useEffect, useState } from "react";
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import { Button, Card, CHART, Loading, Notice, PageHeader, Stat } from "../ui";
import { getScaleLab, runScaleLab } from "../api";

function capitalise(text) {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

function feasibleHint(method) {
  return method.feasible ? "feasible" : "infeasible";
}

function isNotCached(err) {
  return err.message.toLowerCase().includes("not cached");
}

export default function ScaleLab() {
  const [result, setResult] = useState(null);
  const [notCached, setNotCached] = useState(false);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    getScaleLab()
      .then((data) => setResult(data))
      .catch((err) => (isNotCached(err) ? setNotCached(true) : setError(err.message)))
      .finally(() => setLoading(false));
  }, []);

  async function handleRun() {
    setRunning(true);
    setError(null);
    try {
      setResult(await runScaleLab());
      setNotCached(false);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  const instances = result?.instances || [];
  const chartData = instances.map((inst) => ({
    name: capitalise(inst.name),
    "Three-stage": inst.three_stage.km,
    "Nearest neighbour": inst.nearest_neighbor.km,
  }));

  return (
    <>
      <PageHeader
        title="Scale lab"
        subtitle="Same planner on a campus and a 2,000-bin city instance"
        badges={["simulated"]}
      />
      {error && <Notice kind="error">{error}</Notice>}
      {loading && <Loading text="Loading scale lab..." />}
      {running && <Loading text="Running scale lab..." />}

      {!loading && notCached && !result && (
        <>
          <Notice kind="info">Scale lab not cached yet</Notice>
          <Button disabled={running} onClick={handleRun}>
            Run scale lab (takes a minute)
          </Button>
        </>
      )}

      {result && (
        <>
          <div style={{ display: "grid", gap: "var(--space-4)",
                        gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))" }}>
            {instances.map((inst) => (
              <Card key={inst.name} title={capitalise(inst.name)}>
                {inst.source === "synthetic_fallback" && (
                  <Notice kind="info">campus data: synthetic fallback - seed not loaded</Notice>
                )}
                <div style={{ display: "grid", gap: "var(--space-3)",
                              gridTemplateColumns: "repeat(2, minmax(0, 1fr))" }}>
                  <Stat label="bins" value={inst.bins} />
                  <Stat label="vehicles" value={inst.vehicles} />
                  <Stat label="three-stage km" value={inst.three_stage.km.toFixed(1)} unit="km"
                        hint={feasibleHint(inst.three_stage)} />
                  <Stat label="nearest-neighbour km" value={inst.nearest_neighbor.km.toFixed(1)}
                        unit="km" hint={feasibleHint(inst.nearest_neighbor)} />
                  <Stat label="three-stage runtime" value={inst.three_stage.runtime_s.toFixed(2)}
                        unit="s" />
                  <Stat label="nearest-neighbour runtime"
                        value={inst.nearest_neighbor.runtime_s.toFixed(2)} unit="s" />
                </div>
              </Card>
            ))}
          </div>

          <Card title="km per instance">
            <div style={{ height: 280 }}>
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART.grid} />
                  <XAxis dataKey="name" fontSize={CHART.fontSize} />
                  <YAxis fontSize={CHART.fontSize} />
                  <Tooltip />
                  <Legend wrapperStyle={{ fontSize: CHART.fontSize }} />
                  <Bar dataKey="Three-stage" fill={CHART.series[0]} />
                  <Bar dataKey="Nearest neighbour" fill={CHART.series[1]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </Card>

          <p style={{ fontSize: "0.85rem", color: "var(--color-muted)" }}>
            Straight-line distance x detour factor; synthetic city instance. Simulated results,
            not field measurements.
            {result.generated_at && ` Generated ${new Date(result.generated_at).toLocaleString()}.`}
          </p>
          <Button variant="secondary" disabled={running} onClick={handleRun}>
            Run again
          </Button>
        </>
      )}
    </>
  );
}
