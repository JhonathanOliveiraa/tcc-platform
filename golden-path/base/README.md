# golden-path/base/

Template base das aplicações: Deployment (probes, resources, securityContext, variáveis OTel), Service,
`HTTPRoute` (Gateway API, ligada ao Gateway do Kong) e exemplo de ExternalSecret.

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
