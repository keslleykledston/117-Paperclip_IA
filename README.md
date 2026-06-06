# K3G Paperclip Tool Gateway

Gateway MVP para tools locais do ecossistema Paperclip/Hermes.

## Endpoints

- `GET /health`
- `GET /tools/docker/status`
- `GET /tools/git/diff?repo_path=/workspace/repos/NOME`
- `POST /tools/llama/chat`
- `GET /tools/audit/logs`
- `GET /tools/policy`

## Subir

```bash
cd /opt/k3g-ai-stack/gateway
docker compose up -d --build
```
