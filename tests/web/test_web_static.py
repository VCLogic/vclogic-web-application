from pathlib import Path

from fastapi.testclient import TestClient
import pytest

from vclogic_web.app import create_app
from vclogic_web.cli import validate_host


def test_compiled_frontend_falls_back_to_index(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<main>app</main>", encoding="utf-8")
    assets = tmp_path / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('ok')", encoding="utf-8")
    client = TestClient(create_app(static_root=tmp_path, testing=True))

    assert client.get("/sessions/example").text == "<main>app</main>"
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/missing").status_code == 404


def test_remote_binding_requires_explicit_authorization() -> None:
    assert validate_host("127.0.0.1", allow_remote=False) == "127.0.0.1"
    with pytest.raises(ValueError, match="allow-remote"):
        validate_host("0.0.0.0", allow_remote=False)
    assert validate_host("0.0.0.0", allow_remote=True) == "0.0.0.0"
