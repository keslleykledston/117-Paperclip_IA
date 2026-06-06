#!/usr/bin/env bash
set -euo pipefail

echo "=== K3G Paperclip Tool Gateway Check ==="

echo
 echo "[1] Container:"
docker ps --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}' | grep k3g-paperclip-tool-gateway || true

echo
 echo "[2] Health:"
curl -sS http://127.0.0.1:18090/health | jq .

echo
 echo "[3] Policy:"
curl -sS http://127.0.0.1:18090/tools/policy | jq '{status, path, content_chars: (.content | length)}'

echo
 echo "[4] Docker status:"
curl -sS http://127.0.0.1:18090/tools/docker/status | jq '{status, read_only, containers_count: (.containers | length)}'

echo
 echo "[5] Llama chat:"
curl -sS -X POST http://127.0.0.1:18090/tools/llama/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Responda apenas OK. Teste do gateway K3G.","max_tokens":32}' | jq '{status, provider}'

echo
 echo "[6] Audit logs:"
curl -sS http://127.0.0.1:18090/tools/audit/logs?limit=5 | jq '{status, logs_count: (.logs | length)}'

echo
 echo "Gateway validado."
