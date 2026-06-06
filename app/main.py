import json
import os
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from starlette.requests import Request

GATEWAY_NAME = os.getenv("GATEWAY_NAME", "paperclip-tool-gateway")
GATEWAY_MODE = os.getenv("GATEWAY_MODE", "mvp")
LLAMA_BASE_URL = os.getenv("LLAMA_BASE_URL", "http://127.0.0.1:18088/v1").rstrip("/")
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "12000"))

LOG_DIR = Path("/workspace/logs/gateway")
AUDIT_FILE = LOG_DIR / "audit.jsonl"
REPOS_ROOT = Path("/workspace/repos").resolve()
POLICY_FILE = Path("/workspace/docs/OPERATIONAL_POLICY.md")
DOCKER_SOCKET = "/var/run/docker.sock"

app = FastAPI(title="K3G Paperclip Tool Gateway", version="0.1.0")


class LlamaChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    model: str = "local-model"
    temperature: float = 0.2
    max_tokens: int = 1024


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_audit(event: dict[str, Any]) -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with AUDIT_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    audit_id = str(uuid.uuid4())
    start = time.time()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        return response
    finally:
        duration_ms = round((time.time() - start) * 1000, 2)
        write_audit(
            {
                "audit_id": audit_id,
                "timestamp": utc_now(),
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "client": request.client.host if request.client else None,
            }
        )


def run_command(cmd: list[str], cwd: Path | None = None, timeout: int = 15) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return {"returncode": proc.returncode, "stdout": proc.stdout.strip(), "stderr": proc.stderr.strip()}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "command timeout"}


def safe_repo_path(repo_path: str) -> Path:
    candidate = Path(repo_path).resolve()
    if not str(candidate).startswith(str(REPOS_ROOT)):
        raise HTTPException(status_code=403, detail="repo_path fora de /workspace/repos")
    if not candidate.exists():
        raise HTTPException(status_code=404, detail="repo_path não existe")
    if not (candidate / ".git").exists():
        raise HTTPException(status_code=400, detail="repo_path não é um repositório Git")
    return candidate


@app.get("/health")
def health():
    return {"status": "ok", "service": GATEWAY_NAME, "mode": GATEWAY_MODE, "timestamp": utc_now()}


@app.get("/tools/policy")
def policy():
    if not POLICY_FILE.exists():
        raise HTTPException(status_code=404, detail="política operacional não encontrada")
    return {"status": "ok", "path": str(POLICY_FILE), "content": POLICY_FILE.read_text(encoding="utf-8")}


@app.get("/tools/docker/status")
def docker_status():
    if not Path(DOCKER_SOCKET).exists():
        raise HTTPException(status_code=503, detail="docker socket indisponível")
    try:
        transport = httpx.HTTPTransport(uds=DOCKER_SOCKET)
        with httpx.Client(transport=transport, base_url="http://localhost", timeout=15.0) as client:
            resp = client.get("/containers/json?all=1")
            resp.raise_for_status()
            containers = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"erro ao ler Docker socket: {exc}") from exc
    return {"status": "ok", "read_only": True, "containers": containers}


@app.get("/tools/git/diff")
def git_diff(repo_path: str = Query(..., description="Caminho dentro de /workspace/repos")):
    repo = safe_repo_path(repo_path)
    branch = run_command(["git", "branch", "--show-current"], cwd=repo)
    status = run_command(["git", "status", "--short"], cwd=repo)
    diff_stat = run_command(["git", "diff", "--stat"], cwd=repo)
    last_commit = run_command(["git", "log", "-1", "--oneline"], cwd=repo)
    return {
        "status": "ok",
        "repo_path": str(repo),
        "branch": branch["stdout"],
        "git_status": status["stdout"].splitlines() if status["stdout"] else [],
        "diff_stat": diff_stat["stdout"],
        "last_commit": last_commit["stdout"],
    }


@app.post("/tools/llama/chat")
async def llama_chat(payload: LlamaChatRequest):
    prompt_len = len(payload.prompt)
    write_audit(
        {
            "audit_id": str(uuid.uuid4()),
            "timestamp": utc_now(),
            "event": "llama_chat_request",
            "prompt_chars": prompt_len,
            "model": payload.model,
        }
    )
    if prompt_len > MAX_PROMPT_CHARS:
        raise HTTPException(status_code=413, detail=f"prompt excede limite de {MAX_PROMPT_CHARS} caracteres")
    body = {
        "model": payload.model,
        "messages": [{"role": "user", "content": payload.prompt}],
        "temperature": payload.temperature,
        "max_tokens": payload.max_tokens,
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(f"{LLAMA_BASE_URL}/chat/completions", json=body)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"erro ao consultar llama.cpp: {exc}") from exc
    return {"status": "ok", "provider": "llama.cpp", "base_url": LLAMA_BASE_URL, "response": data}


@app.get("/tools/audit/logs")
def audit_logs(limit: int = Query(50, ge=1, le=500)):
    if not AUDIT_FILE.exists():
        return {"status": "ok", "logs": []}
    lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
    selected = lines[-limit:]
    logs = []
    for line in selected:
        try:
            logs.append(json.loads(line))
        except json.JSONDecodeError:
            logs.append({"raw": line})
    return {"status": "ok", "limit": limit, "logs": logs}
