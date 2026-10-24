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
