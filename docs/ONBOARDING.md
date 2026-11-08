# Incorporar uma aplicação pelo Golden Path

Guia para a **equipe de aplicação**. Não exige acesso ao cluster nem conhecimento do Argo CD, do Kong ou
do Vault. Tudo o que você altera fica no repositório da sua aplicação e em `apps/<app>/` deste
repositório. Se precisar mexer em qualquer outro lugar, é falha do Golden Path: avise a equipe de
plataforma e **não** contorne.

Tempo de referência: ver o Capítulo 5 do TCC. Cronometre do passo 1 até o passo 6.

## O contrato

| # | Artefato | Onde | Exigência |
|---|---|---|---|
| 1 | Dockerfile | repositório da app | multi-stage, compila em `--platform=$BUILDPLATFORM`, imagem final `linux/arm64`, usuário não-root, escuta na **porta 8080** |
| 2 | Health check | código da app | **liveness** (só o processo; não testa dependências) e **readiness** (inclui dependências obrigatórias). Front estático: `/healthz` no servidor web |
| 3 | Telemetria | código da app | SDK OpenTelemetry configurado **só** pelas variáveis `OTEL_*` (o Deployment base já injeta endpoint e protocolo); front estático: nada |
| 4 | `ci.yml` | repositório da app | chama `backend-service.yml` ou `frontend-service.yml` de `tcc-pipeline-templates` com `overlay-path: apps/<app>/hml` |
| 5 | Overlay | `apps/<app>/{base,hml,prd}` | `base` herda `golden-path/base`; cada ambiente define host, variáveis, chaves do Vault e o bloco `images:` |
| 6 | Rota | overlay do ambiente | host `<amb>-<app>.tcc.altasistemas.com.br` (hml) ou `<app>.tcc...` (prd) no `HTTPRoute` herdado do base — TLS já é do Gateway |
| 7 | Namespace | (nenhum arquivo) | `<app>-<amb>`, criado pelo Argo CD a partir do nome da pasta |
| 8 | Segredos | OCI Vault + `ExternalSecret` no overlay | chave `<AMB>-TCC-<APP>-<NOME>`; nenhum valor no Git; peça à equipe de plataforma para gravar o valor |

## Passo a passo

1. **Repositório da app**: Dockerfile, health checks e OpenTelemetry (itens 1–3). Use a `catalogo-api`
   (.NET) ou o `catalogo-front` (Angular) como exemplo.
2. **`.github/workflows/ci.yml`** (item 4), copiando o da app de exemplo e trocando `overlay-path`.
   Secret do repositório: `PLATFORM_REPO_TOKEN` (fine-grained, só `tcc-platform`, Contents: Read and write).
3. **Overlay**: copie `apps/catalogo-front/` (sem banco) ou `apps/catalogo-api/` (com PostgreSQL) para
   `apps/<app>/` e troque, nos três `kustomization.yaml`/patches: nome da imagem
   (`ghcr.io/jhonathanoliveiraa/<app>`), hosts, variáveis, probes e recursos. Confira com
   `kubectl kustomize apps/<app>/hml`.
4. **Segredos** (se houver): liste as chaves para a equipe de plataforma gravar no Vault.
5. **Commit** do overlay na `main` deste repositório. O ApplicationSet cria `<app>-hml` e `<app>-prd`
   sozinho (até 3 min). Antes do primeiro build o pod fica em `ImagePullBackOff` — esperado.
6. **Push na `main` da app**: a esteira testa, analisa, publica a imagem e grava tag + digest em
   `apps/<app>/hml`. O Argo CD sincroniza; pronto quando a Application fica `Synced` e `Healthy` e
   `https://hml-<app>.tcc.altasistemas.com.br` responde.
7. **Produção**: Actions → `promover` → escolha a app. A mesma imagem (mesmo digest) vai para `prd`.

## O que você ganha sem configurar

- HTTPS com certificado renovado automaticamente.
- Métricas de pod, logs do contêiner e eventos no Grafana Cloud (painéis de Kubernetes, filtro por
  namespace `<app>-<amb>`); traces e métricas de aplicação quando o SDK OTel está no código.
- Rollback: `git revert` do commit `deploy(<app>): ...` neste repositório.
- Rolling update sem indisponibilidade; uma versão que não fica pronta não substitui a anterior.
- Reinício automático quando um segredo muda no Vault (Reloader).
- Bloqueio do serviço de metadados da VM (NetworkPolicy do base).
