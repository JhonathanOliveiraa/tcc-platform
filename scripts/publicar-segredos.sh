#!/usr/bin/env bash
# Publica no OCI Vault "tcc" os segredos das aplicações (nomes em apps/README.md).
# Nunca imprime valores. Cria o que falta; com --atualizar, versiona os existentes.
#   - TCC-GHCR-USUARIO / TCC-GHCR-TOKEN: pedidos no terminal (token classic, só read:packages).
#   - <AMB>-TCC-CATALOGO-API-POSTGRES-USUARIO / -SENHA: usuário "catalogo" e senha aleatória.
#     ATENÇÃO: trocar a senha depois que o banco existe exige alterá-la também no PostgreSQL.
#
#   scripts/publicar-segredos.sh [--atualizar]
set -euo pipefail
cd "$(dirname "$0")"
source ./vault.conf   # OCI_PERFIL, COMPARTIMENTO_OCID, VAULT_OCID, CHAVE_OCID
ATUALIZAR=${1:-}
o() { oci --profile "$OCI_PERFIL" "$@"; }

publicar() {  # nome valor
  local nome=$1 b64 id
  b64=$(printf '%s' "$2" | base64 -w0)
  id=$(o vault secret list -c "$COMPARTIMENTO_OCID" --vault-id "$VAULT_OCID" --name "$nome" --all \
       --query "data[?\"lifecycle-state\"!='DELETED' && \"lifecycle-state\"!='PENDING_DELETION'] | [0].id" --raw-output 2>/dev/null || true)
  if [[ "$id" != ocid1.vaultsecret.* ]]; then
    o vault secret create-base64 -c "$COMPARTIMENTO_OCID" --vault-id "$VAULT_OCID" --key-id "$CHAVE_OCID" \
      --secret-name "$nome" --secret-content-content "$b64" --description "TCC" >/dev/null
    echo "criado     $nome"
  elif [[ "$ATUALIZAR" == "--atualizar" ]]; then
    o vault secret update-base64 --secret-id "$id" --secret-content-content "$b64" >/dev/null
    echo "atualizado $nome"
  else
    echo "existe     $nome (use --atualizar para versionar)"
  fi
}

read -rp  "Usuário do GitHub (GHCR): " GHCR_USUARIO
read -rsp "Token classic do GitHub com read:packages: " GHCR_TOKEN; echo
publicar TCC-GHCR-USUARIO "$GHCR_USUARIO"
publicar TCC-GHCR-TOKEN   "$GHCR_TOKEN"
unset GHCR_TOKEN

for AMB in HML PRD; do
  publicar "$AMB-TCC-CATALOGO-API-POSTGRES-USUARIO" catalogo
  publicar "$AMB-TCC-CATALOGO-API-POSTGRES-SENHA"   "$(openssl rand -base64 32 | tr -d '/+=' | cut -c1-32)"
done
echo "pronto. O ESO aplica em até 1h; para já: kubectl -n <ns> annotate externalsecret --all force-sync=\$(date +%s) --overwrite"
