// OWNER: P2
// "Report overflow" for staff: opens a small inline confirm with an optional photo.
import { useEffect, useState } from "react";
import { Button, Notice } from "../ui";
import { postReport } from "../api";

export default function ReportOverflowButton({ binId, binName, onReported }) {
  const [open, setOpen] = useState(false);
  const [photo, setPhoto] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [sent, setSent] = useState(null);

  // a different bin starts fresh
  useEffect(() => {
    setOpen(false);
    setPhoto(null);
    setError(null);
    setSent(null);
  }, [binId]);

  async function send() {
    setSending(true);
    setError(null);
    const form = new FormData();
    form.append("bin_id", binId);
    form.append("kind", "overflow");
    form.append("reporter_role", "staff");
    if (photo) form.append("photo", photo);
    try {
      const result = await postReport(form);
      setOpen(false);
      setPhoto(null);
      setSent(result);
      if (onReported) onReported(result);
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <div>
        <Button variant="danger" size="sm" onClick={() => { setOpen(true); setSent(null); }}>
          Report overflow
        </Button>
        {sent && (
          <Notice kind="success">
            Overflow reported{sent.merged ? " (merged with an earlier report)" : ""}.
          </Notice>
        )}
      </div>
    );
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
      <span>Report {binName || binId} as overflowing?</span>
      <label>
        Photo (optional){" "}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          disabled={sending}
          onChange={(e) => setPhoto(e.target.files[0] || null)}
        />
      </label>
      {error && <Notice kind="error">{error}</Notice>}
      <div style={{ display: "flex", gap: 8 }}>
        <Button variant="danger" size="sm" disabled={sending} onClick={send}>
          {sending ? "Sending..." : "Confirm report"}
        </Button>
        <Button variant="ghost" size="sm" disabled={sending} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
