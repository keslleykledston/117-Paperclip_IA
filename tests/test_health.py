import asyncio
from pathlib import Path

import httpx

import app.main as gateway
from app.main import app


def _prepare_tmp_audit(tmp_dir: Path) -> None:
    gateway.LOG_DIR = tmp_dir / "gateway"
    gateway.AUDIT_FILE = gateway.LOG_DIR / "audit.jsonl"


async def _check_health(tmp_dir: Path):
    _prepare_tmp_audit(tmp_dir)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "paperclip-tool-gateway"


def test_health(tmp_path):
    asyncio.run(_check_health(tmp_path))
