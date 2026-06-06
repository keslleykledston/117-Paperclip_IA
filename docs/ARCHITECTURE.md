# Paperclip Tool Gateway — Arquitetura MVP

## Objetivo

O Paperclip Tool Gateway é a camada segura de ferramentas locais para o ecossistema K3G AI Stack.

Ele permite que orquestradores como Paperclip e executores como Hermes consultem recursos locais de forma controlada.

## Princípios

- Read-only por padrão.
- Sem comandos destrutivos.
- Respostas em JSON.
- Auditoria por requisição.
- Integração local com llama.cpp.
- Docker consultado em modo leitura.
- Repositórios acessados de forma restrita.

## Componentes

```text
Paperclip / Hermes
       |
       v
Paperclip Tool Gateway :18090
       |
       +--> Docker socket read-only
       +--> Git repos read-only
       +--> llama.cpp :18088
       +--> audit logs
```
