# platform/external-secrets/

Segredos das aplicações vêm do **OCI Vault `tcc`** pelo External Secrets Operator (ESO), com
Instance Principal. Nenhum valor no Git.

1. `./oci-bootstrap.sh` — cria Vault, chave, Dynamic Group e Policy (idempotente) e imprime os OCIDs.
2. Preencher `VAULT_OCID` em `secret-store.yaml` e os três OCIDs em `scripts/vault.conf`.
3. Instalar o ESO (bootstrap, antes do Argo gerenciar):
   `helm install external-secrets external-secrets/external-secrets --version 2.11.0 -n external-secrets --create-namespace`
4. `kubectl apply -f secret-store.yaml` e conferir `kubectl get clustersecretstore oci-vault-tcc` → `Valid`.
5. `scripts/publicar-segredos.sh` — publica os segredos listados em `apps/README.md`.
