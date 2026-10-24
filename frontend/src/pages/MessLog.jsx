// OWNER: P3
import { useState, useEffect, useCallback } from "react";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  PageHeader, Notice, Loading, Card, Button, DataTable, CHART,
} from "../ui";
import { getBins, postMessLog, getMessLogs } from "../api";

const MEALS = ["breakfast", "lunch", "snacks", "dinner"];
const CATEGORIES = ["plate", "kitchen_prep", "unserved"];

function mealByHour() {
  const h = new Date().getHours();
  if (h < 10) return "breakfast";
  if (h < 15) return "lunch";
  if (h < 18) return "snacks";
  return "dinner";
}

const LOG_COLUMNS = [
  { key: "date", label: "Date" },
  { key: "meal", label: "Meal" },
  { key: "category", label: "Category" },
  { key: "weight_kg", label: "kg" },
  { key: "weighed", label: "Weighed", render: (v) => (v ? "Yes" : "No") },
  { key: "source", label: "Source" },
];

export default function MessLog() {
  const [messes, setMesses] = useState([]);
  const [messId, setMessId] = useState("");
  const [meal, setMeal] = useState(mealByHour);
  const [category, setCategory] = useState("plate");
  const [weightKg, setWeightKg] = useState("");
  const [weighed, setWeighed] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState(null);
  const [saveOk, setSaveOk] = useState(false);

  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getBins()
      .then((res) => {
        const bins = res.bins || res || [];
        const names = [...new Set(
          bins
            .filter((b) => b.group_type === "mess" || b.group_type === "mess_food")
            .map((b) => b.group_name),
        )].sort();
        setMesses(names);
        if (names.length && !messId) setMessId(names[0]);
      })
      .catch(() => {});
  }, []);

  const loadLogs = useCallback(async () => {
    try {
      const d = await getMessLogs(14, messId || "");
      setData(d);
      setError(null);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [messId]);

  useEffect(() => { loadLogs(); }, [loadLogs]);

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaveOk(false);
    try {
      const body = {
        mess_id: messId,
        meal,
        category,
        weight_kg: parseFloat(weightKg),
        weighed,
      };
      await postMessLog(body);
      setSaveOk(true);
      setWeightKg("");
      await loadLogs();
    } catch (err) {
      setSaveError(err.message);
    } finally {
      setSaving(false);
    }
  }

  const canSave = messId && weightKg && parseFloat(weightKg) > 0;

  const chartData = (data?.daily || []).slice().reverse();

  return (
    <>
      <PageHeader title="Mess Log" badges={["implemented", "simulated"]} />
      {error && <Notice kind="error">{error}</Notice>}

      <Card title="New entry">
        <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
          <label>
            Mess
            <select
              value={messId}
              onChange={(e) => setMessId(e.target.value)}
              style={{ display: "block", width: "100%", minHeight: 48, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", marginTop: 4 }}
            >
              {messes.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>

          <label>
            Meal
            <select
              value={meal}
              onChange={(e) => setMeal(e.target.value)}
              style={{ display: "block", width: "100%", minHeight: 48, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", marginTop: 4 }}
            >
              {MEALS.map((m) => (
                <option key={m} value={m}>{m}</option>
              ))}
            </select>
          </label>

          <div>
            <span style={{ display: "block", marginBottom: 4 }}>Category</span>
            <div style={{ display: "flex", gap: "var(--space-2)", flexWrap: "wrap" }}>
              {CATEGORIES.map((c) => (
                <Button
                  key={c}
                  variant={category === c ? "primary" : "secondary"}
                  size="sm"
                  onClick={() => setCategory(c)}
                >
                  {c.replace("_", " ")}
                </Button>
              ))}
            </div>
          </div>

          <label>
            Weight (kg)
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="500"
              value={weightKg}
              onChange={(e) => setWeightKg(e.target.value)}
              style={{ display: "block", width: "100%", minHeight: 48, padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius)", border: "1px solid var(--color-border)", marginTop: 4 }}
            />
          </label>

          <label style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
            <input
              type="checkbox"
              checked={weighed}
              onChange={(e) => setWeighed(e.target.checked)}
              style={{ width: 20, height: 20 }}
            />
            Weighed on scale
          </label>

          <Button variant="primary" disabled={!canSave || saving} onClick={handleSave}>
            {saving ? "Saving..." : "Save"}
          </Button>
          {saveError && <Notice kind="error">{saveError}</Notice>}
          {saveOk && <Notice kind="success">Saved</Notice>}
        </div>
      </Card>

      {loading ? (
        <Loading text="Loading logs..." />
      ) : (
        <>
          {chartData.length > 0 && (
            <Card title="Daily totals (kg)">
              <ResponsiveContainer width="100%" height={260}>
                <BarChart data={chartData}>
                  <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
                  <XAxis dataKey="date" fontSize={CHART.fontSize} />
                  <YAxis fontSize={CHART.fontSize} />
                  <Tooltip />
                  <Bar dataKey="total_kg" name="kg" fill={CHART.series[0]} />
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          <Card title="Latest logs">
            <DataTable
              columns={LOG_COLUMNS}
              rows={(data?.logs || []).map((r) => ({ ...r, id: r.log_id }))}
              emptyText="No logs yet"
            />
            <p style={{ fontSize: "0.8rem", color: "var(--color-muted)", marginTop: "var(--space-2)" }}>
              Food waste is delivered to compost stop (delivery only, no compost output claimed).
            </p>
          </Card>
        </>
      )}
    </>
  );
}
