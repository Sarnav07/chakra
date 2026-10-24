from app import config


def test_cors_origins_defaults_to_local_vite(monkeypatch):
    monkeypatch.delenv("CHAKRA_CORS_ORIGINS", raising=False)
    assert config.cors_origins() == ["http://localhost:5173", "http://127.0.0.1:5173"]


def test_cors_origins_parses_render_origins(monkeypatch):
    monkeypatch.setenv(
        "CHAKRA_CORS_ORIGINS",
        " https://chakra-web.onrender.com/ , https://preview.example.com ",
    )
    assert config.cors_origins() == [
        "https://chakra-web.onrender.com",
        "https://preview.example.com",
    ]


def test_auto_seed_fills_an_empty_database(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    monkeypatch.setattr(config, "DB_PATH", tmp_path / "hosted.db")
    monkeypatch.setenv("CHAKRA_AUTO_SEED", "1")
    with TestClient(app) as client:
        assert client.get("/api/scenario").json()["bins_count"] == 50
        assert client.get("/api/dashboard").json()["forecast"] is not None
