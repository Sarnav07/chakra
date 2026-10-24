// OWNER: P2
// Dispatcher queue of overflow / missed-pickup reports (/reports).
import { useCallback, useEffect, useState } from "react";
import { Button, DataTable, Loading, Notice, PageHeader } from "../ui";
import { getReports, rejectReport } from "../api";

const STATUSES = [
  { value: "open", label: "Open" },
  { value: "in_plan", label: "In plan" },
  { value: "resolved", label: "Resolved" },
  { value: "rejected", label: "Rejected" },
  { value: "all", label: "All" },
];

const KIND_TEXT = { overflow: "overflow", missed_collection: "missed pickup" };

function fmtTime(iso) {
  const d = new Date(iso);
  return isNaN(d) ? iso : d.toLocaleString();
}

export default function ReportsQueue() {
  const [status, setStatus] = useState("open");
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [busyId, setBusyId] = useState(null);

  const load = useCallback(async () => {
    try {
      const data = await getReports(status);
      setReports(data.reports || []);
      setError(null);
    } catch (err) {
      setError(err.message);
    }
  }, [status]);

  useEffect(() => {
    setLoading(true);
    load().finally(() => setLoading(false));
  }, [load]);

  async function handleReject(reportId) {
    setBusyId(reportId);
    try {
      await rejectReport(reportId);
      await load();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusyId(null);
    }
  }

  const columns = [
    { key: "bin_name", label: "Bin", render: (name, r) => `${name} (${r.bin_id})` },
    { key: "kind", label: "Kind", render: (kind) => KIND_TEXT[kind] || kind },
    { key: "reporter_role", label: "Role" },
    { key: "verified", label: "Verified", render: (v) => (v ? "verified" : "unverified") },
    { key: "report_count", label: "Count" },
    { key: "status", label: "Status", render: (s) => s.replace("_", " ") },
    { key: "reported_at", label: "Reported at", render: fmtTime },
    {
      key: "action",
      label: "Action",
      render: (_, r) =>
        r.status === "open" ? (
          <Button
            variant="danger"
            size="sm"
            disabled={busyId !== null}
            onClick={() => handleReject(r.report_id)}
          >
            {busyId === r.report_id ? "Rejecting..." : "Reject"}
          </Button>
        ) : null,
    },
  ];

  return (
    <>
      <PageHeader
        title="Reports"
        subtitle="Overflow and missed-pickup reports from staff and bin QR codes"
        badges={["implemented"]}
      />
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 16 }}>
        {STATUSES.map((s) => (
          <Button
            key={s.value}
            variant={status === s.value ? "primary" : "secondary"}
            size="sm"
            onClick={() => setStatus(s.value)}
          >
            {s.label}
          </Button>
        ))}
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {loading ? (
        <Loading text="Loading reports..." />
      ) : (
        <DataTable
          columns={columns}
          rows={reports.map((r) => ({ ...r, id: r.report_id }))}
          emptyText={`No ${status === "all" ? "" : status.replace("_", " ") + " "}reports`}
        />
      )}
    </>
  );
}
