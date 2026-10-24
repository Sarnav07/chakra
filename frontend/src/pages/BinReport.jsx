// OWNER: P2
// Phone page opened from a bin's QR code (/bin/:binId/report). No Layout.
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Button, Card, Loading, Notice, PageHeader } from "../ui";
import { getBins, postReport } from "../api";

const PAGE_CSS = `
.bin-report { max-width: 480px; margin: 0 auto; padding: 16px; }
.bin-report__actions { display: flex; flex-direction: column; gap: 12px; margin-top: 16px; }
.bin-report__actions .ck-btn { width: 100%; padding: 16px; font-size: 1.1rem; }
.bin-report__photo { display: block; margin-top: 16px; }
.bin-report__photo input { display: block; margin-top: 6px; max-width: 100%; }
`;

export default function BinReport() {
  const { binId } = useParams();
  const [bin, setBin] = useState(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getBins()
      .then((data) => {
        if (!cancelled) setBin((data.bins || []).find((b) => b.bin_id === binId) || null);
      })
      .catch((err) => {
        if (!cancelled) setLoadError(err.message);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [binId]);

  async function send(kind) {
    setSending(true);
    setError(null);
    const form = new FormData();
    form.append("bin_id", binId);
    form.append("kind", kind);
    form.append("reporter_role", "qr");
    if (photo) form.append("photo", photo);
    try {
      setResult(await postReport(form));
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  let body;
  if (loading) {
    body = <Loading text="Loading bin..." />;
  } else if (loadError) {
    body = <Notice kind="error">Could not load bin details right now ({loadError}). Please try again in a minute.</Notice>;
  } else if (!bin) {
    body = (
      <Notice kind="error">
        We could not find bin "{binId}". Please check the QR code on the bin, or tell the
        campus staff.
      </Notice>
    );
  } else if (result) {
    body = (
      <Notice kind="success">
        Thanks - this bin will be added to the next plan.
        {result.merged && " (merged with an earlier report)"}
      </Notice>
    );
  } else {
    body = (
      <Card title={bin.name}>
        <p>{bin.group_name}</p>
        <div className="bin-report__actions">
          <Button variant="danger" disabled={sending} onClick={() => send("overflow")}>
            This bin is overflowing
          </Button>
          <Button variant="secondary" disabled={sending} onClick={() => send("missed_collection")}>
            Pickup was missed
          </Button>
        </div>
        <label className="bin-report__photo">
          Add a photo (optional)
          <input
            type="file"
            accept="image/*"
            capture="environment"
            disabled={sending}
            onChange={(e) => setPhoto(e.target.files[0] || null)}
          />
        </label>
        {sending && <Loading text="Sending..." />}
        {error && <Notice kind="error">{error}</Notice>}
      </Card>
    );
  }

  return (
    <div className="bin-report">
      <style>{PAGE_CSS}</style>
      <PageHeader title="Report a bin" badges={["implemented"]} />
      {body}
    </div>
  );
}
