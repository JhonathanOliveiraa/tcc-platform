# apps/

Uma pasta por aplicação: `base/` (o que é da app sobre o `golden-path/base`) e um overlay por ambiente
(`hml/`, `prd/`). O overlay do ambiente é o **único** lugar em que a esteira de CI da app escreve.

```text
apps/<app>/
  base/           imagem, probes, recursos, volumes e dependências (ex.: PostgreSQL da API)
  hml/ prd/       namespace <app>-<amb>, host, variáveis, chaves do Vault, tag da imagem
```

Um push na `main` da aplicação publica em `hml`; `prd` recebe a mesma imagem pelo workflow
`promover` (Actions deste repositório). A esteira atualiza `newTag` e `digest` do bloco `images:`:

```yaml
images:
  - name: ghcr.io/jhonathanoliveiraa/<app>
    newTag: sha-<12 primeiros do commit>   # gravado pela esteira
    digest: sha256:<...>                    # idem; o Kustomize renderiza <imagem>:<tag>@<digest>
```

Cada pasta `apps/<app>/<amb>` vira a Application `<app>-<amb>` no namespace `<app>-<amb>`
(ApplicationSet com gerador de diretórios do Git; `base/` é ignorada).

## Segredos esperados no OCI Vault (`ClusterSecretStore` `oci-vault-tcc`)

| Chave no Vault | Usada por |
|---|---|
| `TCC-GHCR-USUARIO`, `TCC-GHCR-TOKEN` | pull das imagens (todas as apps, todos os ambientes; token `read:packages`) |
| `<AMB>-TCC-CATALOGO-API-POSTGRES-USUARIO`, `<AMB>-TCC-CATALOGO-API-POSTGRES-SENHA` | PostgreSQL e `ConnectionStrings__Catalogo` da API |

`<AMB>` = `HML` ou `PRD`.
