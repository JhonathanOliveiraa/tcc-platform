# golden-path/base/

Contrato comum de toda aplicação do TCC:

| Recurso | O que garante |
|---|---|
| `Deployment` `app` | porta 8080 `http`, não-root, `readOnlyRootFilesystem`, sem capabilities, seccomp, `/tmp` em `emptyDir`, rolling update sem indisponibilidade, probes (padrão `/healthz`), OTLP para o Alloy |
| `Service` `app` | porta 80 → `http` |
| `HTTPRoute` `app` | anexada ao listener `https-tcc` do Gateway `kong/kong`; host definido no overlay |
| `ExternalSecret` `ghcr` | pull das imagens privadas do GHCR a partir do OCI Vault |
| `ServiceAccount` `app` | sem token montado |
| `NetworkPolicy` `bloqueia-metadados-da-vm` | saída liberada, exceto `169.254.169.254` (identidade da VM / Instance Principal) |
| anotação `reloader.stakater.com/auto` | rolling update quando um Secret usado pelo pod muda (troca no Vault) |

O namespace não é um arquivo: é `<app>-<amb>`, criado pelo ApplicationSet com os labels
`tcc/exposto=true` (exigido pelo listener do Gateway) e `tcc/ambiente`.

Convenção: os recursos se chamam `app` e a identidade vem do namespace `<app>-<amb>`. Cada aplicação
ajusta o contrato em `apps/<app>/base` e cada ambiente em `apps/<app>/<amb>`.

## Requisitos vindos das arquiteturas das aplicações

Registrados a partir dos spines do BMAD (`_bmad-output/planning-artifacts/architecture/` de cada app).
O base precisa permitir que cada overlay defina estes valores sem alterar o template:

| Item | catalogo-api (AD-11) | catalogo-front (AD-8) |
|---|---|---|
| Porta do contêiner | 8080 | 8080 |
| Usuário | não-root da imagem (chiseled) | não-root da imagem (UID 101) |
| Liveness | `GET /health/live` | `GET /healthz` |
| Readiness | `GET /health` (inclui PostgreSQL; 503 com o banco fora) | `GET /healthz` |
| `readOnlyRootFilesystem` | sim | sim, com `emptyDir` em `/tmp` (onde o `config.json` é gerado) e em `/var/cache/nginx` |
| Variáveis do overlay | `Cors__OrigensPermitidas`, `OTEL_*`, connection string por `ExternalSecret` | `API_BASE_URL` (o contêiner não sobe sem ela) |

As probes e o `readOnlyRootFilesystem` precisam ser parametrizáveis por aplicação (patch no overlay),
porque os caminhos e os volumes graváveis diferem entre a API e o front.
