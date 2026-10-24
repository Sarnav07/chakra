"""P2 overflow / missed-collection reports (SPEC 11; SPEC 19 T8)."""
import io
import struct
import zlib

import pytest
from PIL import Image

from app.db import get_conn
from app.reports.service import active_reports_by_bin, create_report
from app.routers import reports as reports_router

PLAN_ID = "P-2026-10-25-abc123"
NOW = "2026-10-24T20:30:00+05:30"
BINS = [("HA-1", "Rajendra Bhawan bin 1", "hostel", "Rajendra Bhawan", "general", 29.8661, 77.8942, 240),
        ("M1-G1", "Jawahar Bhawan Mess general bin 1", "mess", "Jawahar Bhawan Mess", "general", 29.8645, 77.8981, 660),
        ("M1-F1", "Jawahar Bhawan Mess food bin 1", "mess_food", "Jawahar Bhawan Mess", "food", 29.8647, 77.8984, 120)]
# bin_id -> (selected, reason_code)
DECISIONS = {"HA-1": (0, "below_tau"), "M1-G1": (1, "p_over_tau"), "M1-F1": (0, "below_tau")}


@pytest.fixture
def data(conn):
    """3 bins, one committed plan and its decisions (no seed needed)."""
    conn.executemany("INSERT INTO bins VALUES (?, ?, ?, ?, ?, ?, ?, ?)", BINS)
    conn.execute("INSERT INTO plans (plan_id, plan_date, tau, created_at, chosen_fleet_size, "
                 "status, response_json) VALUES (?, '2026-10-25', 0.5, ?, 2, 'committed', '{}')",
                 (PLAN_ID, NOW))
    for bin_id, (selected, code) in DECISIONS.items():
        conn.execute("INSERT INTO pickup_decisions (plan_id, plan_date, bin_id, tau, selected, "
                     "reason_code, reason, p_overflow, created_at) "
                     "VALUES (?, '2026-10-25', ?, 0.5, ?, ?, 'test', 0.2, ?)",
                     (PLAN_ID, bin_id, selected, code, NOW))
    conn.commit()
    return conn


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """Save report photos under tmp_path instead of backend/data."""
    data_dir = tmp_path / "data"
    monkeypatch.setattr(reports_router, "DATA_DIR", data_dir)
    monkeypatch.setattr(reports_router, "UPLOAD_DIR", data_dir / "uploads")
    return data_dir


def _report(client, bin_id, role="staff", kind="overflow", files=None):
    return client.post("/api/reports", data={"bin_id": bin_id, "kind": kind,
                                             "reporter_role": role}, files=files)


def _missed(conn, bin_id):
    return conn.execute("SELECT missed FROM pickup_decisions WHERE plan_id = ? AND bin_id = ?",
                        (PLAN_ID, bin_id)).fetchone()["missed"]


def _tiny_png() -> bytes:
    """A valid 1x1 red PNG built by hand."""
    def chunk(tag, body):
        return (struct.pack(">I", len(body)) + tag + body
                + struct.pack(">I", zlib.crc32(tag + body) & 0xFFFFFFFF))
    header = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)    # 1x1, 8-bit RGB
    pixels = zlib.compress(b"\x00\xff\x00\x00")               # filter byte + one red pixel
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", pixels)
            + chunk(b"IEND", b""))


def test_below_tau_report_is_missed_collection_then_merged(client, data):
    first = _report(client, "HA-1", role="staff")
    assert first.status_code == 200
    body = first.json()
    assert body["missed_collection"] is True and body["merged"] is False
    assert body["report"]["verified"] == 1 and body["report"]["status"] == "open"
    assert "mock" not in body
    assert _missed(data, "HA-1") == 1

    second = _report(client, "HA-1", role="qr").json()
    assert second["merged"] is True
    assert second["missed_collection"] is False          # missed is set only once
    assert second["report"]["report_id"] == body["report"]["report_id"]
    assert second["report"]["report_count"] == 2
    assert second["report"]["verified"] == 1             # stays verified
    active = data.execute("SELECT COUNT(*) FROM overflow_reports WHERE bin_id = 'HA-1' "
                          "AND status IN ('open', 'in_plan')").fetchone()[0]
    assert active == 1
    assert _missed(data, "HA-1") == 1


def test_qr_report_is_unverified_and_selected_bin_not_missed(client, data):
    body = _report(client, "M1-G1", role="qr").json()
    assert body["missed_collection"] is False            # it was selected
    assert body["report"]["verified"] == 0
    assert _missed(data, "M1-G1") == 0


def test_reject_only_from_open(client, data):
    report_id = _report(client, "M1-F1", role="qr").json()["report"]["report_id"]
    first = client.post(f"/api/reports/{report_id}/reject")
    assert first.status_code == 200
    assert first.json()["report"]["status"] == "rejected"
    assert client.post(f"/api/reports/{report_id}/reject").status_code == 409
    assert "M1-F1" not in active_reports_by_bin(data)
    assert client.post("/api/reports/9999/reject").status_code == 404


def test_photo_upload_png(client, data, uploads):
    png = _tiny_png()
    Image.open(io.BytesIO(png)).verify()                  # the bytes are a real PNG
    r = _report(client, "HA-1", files={"photo": ("bin.png", png, "image/png")})
    assert r.status_code == 200
    photo_path = r.json()["report"]["photo_path"]
    assert photo_path.startswith("uploads/reports/") and photo_path.endswith(".png")
    saved = uploads / photo_path
    assert saved.exists() and saved.read_bytes() == png


def test_photo_must_be_jpeg_or_png(client, data, uploads):
    text = _report(client, "HA-1", files={"photo": ("notes.txt", b"hello", "text/plain")})
    assert text.status_code == 400
    disguised = _report(client, "HA-1", files={"photo": ("fake.png", b"hello", "image/png")})
    assert disguised.status_code == 400
    assert not (uploads / "uploads" / "reports").exists() or not any(
        (uploads / "uploads" / "reports").iterdir())


def test_unknown_bin_and_bad_fields(client, data):
    assert _report(client, "NOPE-1").status_code == 404
    assert _report(client, "HA-1", kind="bad").status_code == 422
    assert _report(client, "HA-1", role="bad").status_code == 422


def test_list_reports_with_bin_name(client, data):
    _report(client, "HA-1")
    rejected_id = _report(client, "M1-F1", role="qr").json()["report"]["report_id"]
    client.post(f"/api/reports/{rejected_id}/reject")

    every = client.get("/api/reports?status=all").json()["reports"]
    assert {r["bin_id"] for r in every} == {"HA-1", "M1-F1"}
    assert {r["bin_name"] for r in every} == {"Rajendra Bhawan bin 1", "Jawahar Bhawan Mess food bin 1"}
    assert [r["bin_id"] for r in client.get("/api/reports").json()["reports"]] == ["HA-1"]
    assert [r["status"] for r in client.get("/api/reports?status=rejected").json()["reports"]] \
        == ["rejected"]
    assert client.get("/api/reports?status=bad").status_code == 422


def test_reported_bin_is_selected_by_decide(request):
    from app.selection.select import decide
    try:
        decide(None, 0.5)
    except NotImplementedError:
        pytest.skip("decide() not pushed yet")
    except Exception:
        pass   # the real decide() cannot run on conn=None; that is fine here
    conn = get_conn(request.getfixturevalue("seeded_db_path"))
    try:
        before = decide(conn, 0.5)["decisions"]
        target = next((d for d in before if d["reason_code"] == "below_tau"), None)
        if target is None:
            pytest.skip("no below_tau bin in the seeded scenario at tau 0.5")
        create_report(conn, target["bin_id"], "overflow", "qr", None)
        after = {d["bin_id"]: d for d in decide(conn, 0.5)["decisions"]}
        assert after[target["bin_id"]]["reason_code"] == "reported"
        assert after[target["bin_id"]]["selected"]
    finally:
        conn.close()
