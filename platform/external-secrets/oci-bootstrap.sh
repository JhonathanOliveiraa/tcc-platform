#!/usr/bin/env bash
# Cria na OCI (tenancy pessoal, perfil "jhone") o que o External Secrets Operator precisa:
#   Vault "tcc" (padrão, NUNCA virtual private: US$ 3,72/h), chave "tcc" (AES-256, Software),
#   Dynamic Group com a VM do cluster e Policy de leitura dos segredos desse Vault.
# Idempotente: o que já existe é reaproveitado. No fim imprime os OCIDs para o secret-store.yaml.
#
#   platform/external-secrets/oci-bootstrap.sh
set -euo pipefail
PERFIL=${OCI_PERFIL:-jhone}
VM_NOME=${VM_NOME:-k3s}
GRUPO=k3s-jhone
o() { oci --profile "$PERFIL" "$@"; }

T=$(awk -v p="[$PERFIL]" '$0==p{f=1;next} /^\[/{f=0} f&&/^tenancy=/{sub("tenancy=","");print}' ~/.oci/config)
VM=$(o compute instance list -c "$T" --display-name "$VM_NOME" --lifecycle-state RUNNING --query 'data[0].id' --raw-output)
[[ "$VM" == ocid1.instance.* ]] || { echo "VM $VM_NOME não encontrada" >&2; exit 1; }

VAULT=$(o kms management vault list -c "$T" --all --query "data[?\"display-name\"=='tcc' && \"lifecycle-state\"!='DELETED' && \"lifecycle-state\"!='PENDING_DELETION'] | [0].id" --raw-output 2>/dev/null || true)
if [[ "$VAULT" != ocid1.vault.* ]]; then
  echo "criando Vault tcc (alguns minutos)..."
  VAULT=$(o kms management vault create -c "$T" --display-name tcc --vault-type DEFAULT \
          --wait-for-state ACTIVE --query 'data.id' --raw-output)
fi
ENDPOINT=$(o kms management vault get --vault-id "$VAULT" --query 'data."management-endpoint"' --raw-output)

KEY=$(o kms management key list -c "$T" --endpoint "$ENDPOINT" --all --query "data[?\"display-name\"=='tcc' && \"lifecycle-state\"=='ENABLED'] | [0].id" --raw-output 2>/dev/null || true)
if [[ "$KEY" != ocid1.key.* ]]; then
  echo "criando chave tcc..."
  KEY=$(o kms management key create -c "$T" --endpoint "$ENDPOINT" --display-name tcc \
        --key-shape '{"algorithm":"AES","length":32}' --protection-mode SOFTWARE \
        --wait-for-state ENABLED --query 'data.id' --raw-output)
fi

if ! o iam dynamic-group list -c "$T" --all --query "data[?name=='$GRUPO'] | [0].id" --raw-output 2>/dev/null | grep -q ocid1; then
  echo "criando Dynamic Group $GRUPO..."
  o iam dynamic-group create -c "$T" --name "$GRUPO" \
    --description "VM do k3s pessoal (CaIA + TCC): External Secrets por Instance Principal" \
    --matching-rule "instance.id = '$VM'" >/dev/null
fi

if ! o iam policy list -c "$T" --all --query "data[?name=='tcc-eso-le-vault'] | [0].id" --raw-output 2>/dev/null | grep -q ocid1; then
  echo "criando Policy tcc-eso-le-vault..."
  o iam policy create -c "$T" --name tcc-eso-le-vault \
    --description "External Secrets do k3s lê os segredos do Vault tcc" \
    --statements "[\"Allow dynamic-group 'Default'/'$GRUPO' to read secret-family in tenancy where target.vault.id = '$VAULT'\"]" >/dev/null
fi

cat <<FIM

OK. Preencha platform/external-secrets/secret-store.yaml e scripts/vault.conf com:
  VAULT_OCID=$VAULT
  CHAVE_OCID=$KEY
  COMPARTIMENTO_OCID=$T
FIM
