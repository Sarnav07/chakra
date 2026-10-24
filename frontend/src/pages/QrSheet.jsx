// OWNER: P2
// Printable QR codes, one per bin, linking to /bin/:binId/report (/qr).
import { useEffect, useState } from "react";
import { QRCodeSVG } from "qrcode.react";
import { Button, Card, Loading, Notice, PageHeader } from "../ui";
import { getBins } from "../api";

const PAGE_CSS = `
.qr-sheet__grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 16px; }
.qr-sheet__card { text-align: center; }
.qr-sheet__url { font-family: var(--font-mono); font-size: 0.7rem; word-break: break-all; }
@media print {
  .ck-topbar, .ck-backdrop, .ck-notice, .qr-sheet__screen-only { display: none !important; }
  .qr-sheet__grid { grid-template-columns: repeat(3, 1fr); gap: 8mm; }
  .qr-sheet__card { break-inside: avoid; page-break-inside: avoid; }
}
`;

function reportUrl(binId) {
  return `${window.location.origin}/bin/${binId}/report`;
}

export default function QrSheet() {
  const [bins, setBins] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    getBins()
      .then((data) => setBins(data.bins || []))
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, []);

  const host = window.location.hostname;
  const isLocalOnly = host === "localhost" || host === "127.0.0.1";

  return (
    <>
      <style>{PAGE_CSS}</style>
      <PageHeader title="QR codes" subtitle="One code per bin: scan to report it" badges={["implemented"]} />
      <div className="qr-sheet__screen-only" style={{ marginBottom: 16 }}>
        <Notice kind="info">
          Phones must reach this laptop: run npm run dev -- --host and use the laptop's Wi-Fi
          address.
        </Notice>
        {isLocalOnly && (
          <Notice kind="error">
            This page is open on {host}, so these codes point to {host}, which a phone cannot
            open. Reopen this page using the laptop's Wi-Fi address before printing.
          </Notice>
        )}
        <Button variant="secondary" size="sm" onClick={() => window.print()}>
          Print
        </Button>
      </div>
      {error && <Notice kind="error">{error}</Notice>}
      {loading ? (
        <Loading text="Loading bins..." />
      ) : (
        <div className="qr-sheet__grid">
          {bins.map((bin) => (
            <div key={bin.bin_id} className="qr-sheet__card">
              <Card title={bin.name}>
                <QRCodeSVG value={reportUrl(bin.bin_id)} size={160} level="M" includeMargin />
                <p>{bin.bin_id} - {bin.group_name}</p>
                <p className="qr-sheet__url">{reportUrl(bin.bin_id)}</p>
              </Card>
            </div>
          ))}
        </div>
      )}
    </>
  );
}
