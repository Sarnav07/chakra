// OWNER: P1
import { useEffect, useState } from "react";
import { classifyItem, getClassifierStatus } from "../api";
import { Button, Card, Loading, Notice, PageHeader } from "../ui";

const TESTS = [
  ["random_test", "Random test"],
  ["shift_test", "RealWaste shift test"],
  ["campus_test", "Campus test"],
];

function percent(value) {
  return `${(Number(value) * 100).toFixed(1)}%`;
}

export default function CheckItem() {
  const [status, setStatus] = useState(null);
  const [statusError, setStatusError] = useState(null);
  const [photo, setPhoto] = useState(null);
  const [preview, setPreview] = useState(null);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);

  useEffect(() => {
    let active = true;
    getClassifierStatus()
      .then((data) => active && setStatus(data))
      .catch((err) => active && setStatusError(err.message));
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!photo) {
      setPreview(null);
      return undefined;
    }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);

  async function check(event) {
    event.preventDefault();
    if (!photo || sending) return;
    setSending(true);
    setError(null);
    setResult(null);
    try {
      const body = new FormData();
      body.append("photo", photo);
      setResult(await classifyItem(body));
    } catch (err) {
      setError(err.message);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Check an item"
        subtitle="One photo of one item - not a whole bin"
        badges={["implemented"]}
      />

      {statusError && <Notice kind="error">{statusError}</Notice>}
      {!status && !statusError && <Loading text="Checking classifier status..." />}
      {status && !status.available && (
        <Notice kind="info">
          Classifier model not loaded on this laptop. Copy item_classifier.pt and
          classifier_report.json into backend/data/model/ and restart the backend.
        </Notice>
      )}

      <Card title="Photo of one item">
        <form onSubmit={check}>
          <label htmlFor="item-photo">Take or choose a JPEG or PNG photo</label>
          <input
            id="item-photo"
            type="file"
            accept="image/*"
            capture="environment"
            onChange={(event) => {
              setPhoto(event.target.files?.[0] || null);
              setResult(null);
              setError(null);
            }}
            style={{ display: "block", margin: "12px 0" }}
          />
          {preview && (
            <img
              src={preview}
              alt="Selected waste item preview"
              style={{ display: "block", width: "min(100%, 320px)", maxHeight: 300,
                objectFit: "contain", marginBottom: 16 }}
            />
          )}
          <Button type="submit" disabled={!photo || sending || !status?.available}>
            {sending ? "Checking..." : "Check"}
          </Button>
        </form>
      </Card>

      {error && <Notice kind="error">{error}</Notice>}
      {result && (
        <Card title="Result">
          <p><strong>{result.predicted_class}</strong> ({percent(result.confidence)} confidence)</p>
          {result.hazardous && (
            <Notice kind="danger">
              Hazardous - hand over for special pickup, do not put in any bin.
            </Notice>
          )}
          {result.unsure ? (
            <Notice kind="info">Unsure - ask staff</Notice>
          ) : (
            <p>Suggested bin: <strong>{result.suggested_bin}</strong></p>
          )}
          <p>Top predictions</p>
          <ol>
            {(result.top3 || []).map((item) => (
              <li key={item.class}>{item.class}: {percent(item.confidence)}</li>
            ))}
          </ol>
        </Card>
      )}

      <Card title="How accurate is it?">
        {status?.report ? (
          <>
            {TESTS.filter(([key]) => status.report[key]).map(([key, label]) => (
              <p key={key}>
                <strong>{label}:</strong> {percent(status.report[key].accuracy)} on{" "}
                {status.report[key].n_images} images
              </p>
            ))}
            {status.report.shift_test && (
              <p>Shift test = trained on other datasets, tested on RealWaste photos.</p>
            )}
          </>
        ) : (
          <p>No evaluation report loaded.</p>
        )}
      </Card>
    </>
  );
}
