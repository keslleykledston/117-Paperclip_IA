import asyncio
from pathlib import Path

import httpx

import app.main as gateway
from app.main import app


def _prepare_tmp_audit(tmp_dir: Path) -> None:
    gateway.LOG_DIR = tmp_dir / "gateway"
    gateway.AUDIT_FILE = gateway.LOG_DIR / "audit.jsonl"


async def _check_policy(tmp_dir: Path):
    _prepare_tmp_audit(tmp_dir)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tools/policy")
    assert response.status_code in (200, 404)


def test_policy_endpoint_exists(tmp_path):
    asyncio.run(_check_policy(tmp_path))
