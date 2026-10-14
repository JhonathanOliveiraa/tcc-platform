# apps/

Uma pasta por aplicação: `base/` (o que é da app sobre o `golden-path/base`) e um overlay por ambiente
(`hml/`, `prd/`). O overlay do ambiente é o **único** lugar em que a esteira de CI da app escreve.

```text
apps/<app>/
  base/           imagem, probes, recursos, volumes e dependências (ex.: PostgreSQL da API)
  hml/ prd/       namespace <app>-<amb>, host, variáveis, chaves do Vault, tag da imagem
```

O `ci.yml` da aplicação escolhe o overlay pela branch (`develop` → `hml`, `main` → `prd`). A esteira
atualiza o `newTag` do bloco `images:`:

```yaml
images:
  - name: ghcr.io/jhonathanoliveiraa/<app>
    newTag: sha-<12 primeiros do commit>   # gravado pela esteira
```

## Segredos esperados no OCI Vault (`ClusterSecretStore` `oci-vault-tcc`)

| Chave no Vault | Usada por |
|---|---|
| `TCC-GHCR-USUARIO`, `TCC-GHCR-TOKEN` | pull das imagens (todas as apps, todos os ambientes; token `read:packages`) |
| `<AMB>-TCC-CATALOGO-API-POSTGRES-USUARIO`, `<AMB>-TCC-CATALOGO-API-POSTGRES-SENHA` | PostgreSQL e `ConnectionStrings__Catalogo` da API |

`<AMB>` = `HML` ou `PRD`.
