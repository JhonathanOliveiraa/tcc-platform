# tcc-platform

Repositório GitOps da plataforma do TCC: **tudo o que o Argo CD aplica no cluster** (k3s na VM ARM64
da OCI). Fonte única da verdade — depois do bootstrap, nenhuma mudança é feita com `kubectl apply`.

```text
bootstrap/                único apply manual: instala o Argo CD e a Application raiz
clusters/oci-k3s/         Application raiz (app-of-apps)
platform/                 componentes comuns
  gateway/                Kong como implementação da Gateway API: GatewayClass, Gateway, kong-values, faixas do Cloudflare
  cert-manager/           ClusterIssuers Let's Encrypt (DNS-01 no Cloudflare)
  external-secrets/       External Secrets Operator + ClusterSecretStore do OCI Vault
  observability/          Grafana Alloy (k8s-monitoring) → Grafana Cloud, receptor OTLP
  argocd/                 rota da UI do Argo CD
  argocd-projects/        AppProjects com destinos limitados
golden-path/base/         template das aplicações: Deployment, Service, probes, resources, OTel
apps/<aplicação>/         overlay de cada aplicação (a esteira grava aqui a tag da imagem)
docs/                     roteiro de reconstrução e testes
```

## Repositórios relacionados

| Repositório | Papel |
|---|---|
| `tcc-pipeline-templates` | Templates de CI (backend e frontend) consumidos pelas aplicações |
| `catalogo-api` | API de Produtos (ASP.NET Core) — código, Dockerfile e `ci.yml` |
| `catalogo-front` | Frontend de Catálogo (Angular) — código, Dockerfile e `ci.yml` |
| `tcc-documentacao` | Texto do TCC, apresentação e planejamento |

O CI de uma aplicação **só escreve** em `apps/<aplicação>/kustomization.yaml`; o restante deste
repositório é mantido pela equipe de plataforma.

## Ambientes e hosts

**Exposição pela Gateway API, nunca por Ingress:** um `Gateway` do Kong (`platform/gateway/`) com
listeners HTTPS por host, e um `HTTPRoute` por aplicação e ambiente no overlay. Os `Ingress` que existem
no cluster são do CaIA e não servem de modelo.

Subzona própria `tcc.altasistemas.com.br`, separada dos tenants do CaIA (que usam
`*.altasistemas.com.br` e `*.hml.altasistemas.com.br` no mesmo Kong). Hosts exatos, registros DNS only
(sem proxy do Cloudflare), certificados Let's Encrypt por DNS-01.

| Ambiente | Front (`catalogo-front`) | API (`catalogo-api`) |
|---|---|---|
| hml | `hml-catalogo.tcc.altasistemas.com.br` | `hml-catalogo-api.tcc.altasistemas.com.br` |
| prd | `catalogo.tcc.altasistemas.com.br` | `catalogo-api.tcc.altasistemas.com.br` |

Variáveis que ligam os dois: no front, `API_BASE_URL=https://<host da API>`; na API,
`Cors__OrigensPermitidas=https://<host do front>` — definidas nos overlays `apps/<app>/<ambiente>`.

## Segredos

Nenhum valor no Git. Os valores ficam no **OCI Vault**; aqui ficam apenas `ExternalSecret` com os nomes
(padrão `<AMB>-TCC-<APP>-<CHAVE>`). A VM se autentica por Instance Principal.

## Reconstruir do zero

[`docs/RECONSTRUIR_CLUSTER.md`](docs/RECONSTRUIR_CLUSTER.md) — roteiro por fases, com versões
fixadas e verificação ao fim de cada fase. Execute os comandos a partir da raiz deste repositório.
