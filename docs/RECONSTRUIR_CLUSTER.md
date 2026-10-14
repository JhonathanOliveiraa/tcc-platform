# Reconstruir o cluster do zero (OCI + k3s + GitOps)

Roteiro para montar, numa VM nova, a mesma plataforma que hoje roda o CaIA — na ordem certa,
com verificação ao fim de cada fase. Escrito a partir do ambiente real (versões lidas do cluster em
2026-10-03) e dos problemas registrados em `APRENDIZADOS_MIGRACAO_CAIA.md` (repositório `tcc-documentacao`, pasta `planejamento/`).

> **Padrão de Git/CI deste roteiro: GitHub + GHCR + GitHub Actions** (como no planejamento do TCC).
> O CaIA usa Azure Repos + Azure Pipelines + Docker Hub por preferência do projeto; onde muda algo,
> há uma nota **[Azure]**.

Arquivos de apoio (caminhos a partir da raiz deste repositório; **execute os comandos da raiz**):

| Arquivo | Para quê |
|---|---|
| `platform/gateway/kong-values.yaml` | Kong com os dois ajustes obrigatórios (roteador e IP real) |
| `platform/gateway/faixas-cloudflare.sh` | Gera o `trusted_ips` do Kong com as faixas atuais do Cloudflare |
| `platform/cert-manager/cluster-issuers.yaml` | Let's Encrypt staging/prod com DNS-01 no Cloudflare |
| `platform/argocd/argocd-rota.yaml` | UI do Argo CD com TLS e restrição por IP |
| `docs/testes/teste-roteamento.yaml` | Matriz de hosts com backends falsos para testar o Kong |
| repositório `tcc-pipeline-templates` | Esteira: testes → Trivy → build arm64 → Trivy → tag no overlay |

---

## 0. Antes de começar

### Versões de referência (ambiente atual)

| Componente | Versão | Instalação |
|---|---|---|
| Ubuntu | 24.04 LTS, **aarch64** | imagem da OCI |
| k3s | **v1.36.4+k3s1** | script oficial |
| Kong | chart `kong/ingress` **0.24.0** (Kong 3.9) | Helm |
| cert-manager | **v1.21.2** | Helm |
| Argo CD | **v3.5.3** | manifesto oficial |
| Monitoramento | `grafana/k8s-monitoring` **4.5.2** (Alloy 1.19) | Helm, comando gerado pelo Grafana Cloud |

### Variáveis usadas no roteiro

| Variável | Exemplo (CaIA) | Onde aparece |
|---|---|---|
| `<IP_PUBLICO>` | 163.176.1.147 | DNS, `--tls-san`, testes |
| `<IP_PRIVADO>` | 172.0.0.240 | `--node-ip` |
| `<SEU_IP>` | IP público de onde você administra | Security List (22/6443), restrição do Argo |
| `<DOMINIO>` | altasistemas.com.br | DNS, certificados, Ingress |
| `<EMAIL>` | dev@altasistemas.com.br | Let's Encrypt, alertas |

### Contas e ferramentas

- Contas: OCI, Cloudflare (DNS do domínio), GitHub, Grafana Cloud (opcional, recomendado).
- Na máquina de administração: `kubectl`, `helm` (≥ 3.20), `ssh`, `curl`, `dig`.
- Cofre de senhas (ex.: Bitwarden) para tokens e Secrets — **nada disso vai para o Git**.

---

## Fase 1 — VM na OCI

1. **Criar a instância:** Compute → Instances → Create.
   - Shape **VM.Standard.A1.Flex** (Ampere), 2 OCPU / 12 GB (dentro do Always Free).
   - Imagem **Ubuntu 24.04** (aarch64), chave SSH pública sua.
   - Rede: na VNIC, já escolher **Reserved public IP** (criar em Networking → IP Management →
     Reserved Public IPs). ⚠️ Um IP efêmero **não** vira reservado depois — trocar gera outro número
     (Aprendizados 4.2).
2. **Security List** (ou NSG) da subnet — regras de entrada:

   | Origem | Protocolo | Porta destino | Source Port Range |
   |---|---|---|---|
   | `<SEU_IP>/32` | TCP | 22 | **All** |
   | `<SEU_IP>/32` | TCP | 6443 | **All** |
   | `0.0.0.0/0` | TCP | 80 | **All** |
   | `0.0.0.0/0` | TCP | 443 | **All** |

   ⚠️ *Source Port Range* deve ser **All**: a porta de origem do cliente é efêmera.
3. **Firewall da própria VM** (a imagem Ubuntu da OCI vem com `REJECT` para tudo além de SSH):
   ```bash
   ssh ubuntu@<IP_PUBLICO>
   sudo apt-get update && sudo apt-get upgrade -y
   N=$(sudo iptables -L INPUT -n --line-numbers | awk '/REJECT/ {print $1; exit}')
   sudo iptables -I INPUT $N -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT
   sudo iptables -I INPUT $N -p tcp -m state --state NEW -m tcp --dport 80  -j ACCEPT
   sudo iptables -I INPUT $N -p tcp -m state --state NEW -m tcp --dport 6443 -j ACCEPT
   # Persistir editando o arquivo (não usar "netfilter-persistent save" depois do k3s:
   # gravaria as chains dinâmicas do Kubernetes)
   sudo sed -i '/--dport 22 -j ACCEPT/a -A INPUT -p tcp -m state --state NEW -m tcp --dport 80 -j ACCEPT\n-A INPUT -p tcp -m state --state NEW -m tcp --dport 443 -j ACCEPT\n-A INPUT -p tcp -m state --state NEW -m tcp --dport 6443 -j ACCEPT' /etc/iptables/rules.v4
   sudo iptables-restore --test < /etc/iptables/rules.v4 && echo "rules.v4 ok"
   ```
   ⚠️ Não remova as regras para `169.254.0.0/16` — são os serviços de metadados da instância.

**Verificação** (de fora da VM):
```bash
for p in 22 80 443; do timeout 6 bash -c "</dev/tcp/<IP_PUBLICO>/$p" && echo "$p aberta" || echo "$p falhou"; done
```
Esperado: 22 aberta; 80/443 com **"connection refused" imediato** (nada escutando ainda).
Timeout = Security List; recusa imediata = rede ok.

---

## Fase 2 — k3s

```bash
ssh ubuntu@<IP_PUBLICO>
curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION=v1.36.4+k3s1 sh -s - server \
  --disable=traefik \
  --node-ip=<IP_PRIVADO> \
  --tls-san=<IP_PUBLICO>
```

| Flag | Por quê |
|---|---|
| `--disable=traefik` | O Ingress será o Kong; evita dois controladores disputando 80/443 |
| `--node-ip=<IP_PRIVADO>` | Fixa a interface da VCN como IP do nó |
| `--tls-san=<IP_PUBLICO>` | A OCI faz NAT 1:1: o IP público **não existe na VM**; sem ele no certificado, o `kubectl` remoto falha na validação TLS |

**Não instale MetalLB.** O modo L2 depende de GARP, que a VCN da OCI não suporta; o ServiceLB
(klipper), que já vem no k3s, atende os Services `LoadBalancer` publicando as portas no IP do nó
(Aprendizados 4.0).

**kubeconfig na sua máquina:**
```bash
ssh ubuntu@<IP_PUBLICO> 'sudo cat /etc/rancher/k3s/k3s.yaml' > ~/.kube/config-novo
sed -i 's|https://127.0.0.1:6443|https://<IP_PUBLICO>:6443|' ~/.kube/config-novo
chmod 600 ~/.kube/config-novo && export KUBECONFIG=~/.kube/config-novo
```
Fora da rede autorizada: `ssh -L 6443:127.0.0.1:6443 ubuntu@<IP_PUBLICO>` e `server: https://127.0.0.1:6443`.

**Verificação:**
```bash
kubectl get nodes -o wide              # Ready, arm64, INTERNAL-IP = <IP_PRIVADO>
kubectl -n kube-system get pods        # coredns, local-path-provisioner, metrics-server; sem traefik
kubectl get storageclass               # local-path (default)
```

---

## Fase 3 — Entrada HTTP (Kong + Gateway API sobre o ServiceLB)

> **Padrão do TCC: Gateway API, não Ingress.** Instale os CRDs do canal *standard* da Gateway API
> **antes** do Kong (o controlador só habilita a Gateway API se os CRDs existirem na subida), depois
> aplique `GatewayClass` + `Gateway` de `platform/gateway/`. As aplicações usam `HTTPRoute`. Os exemplos
> com `Ingress` abaixo (Argo CD, teste de roteamento) vêm do CaIA e devem ser convertidos para `HTTPRoute`.

```bash
helm repo add kong https://charts.konghq.com && helm repo update
kubectl get svc -A | awk '$3=="LoadBalancer"'      # deve vir vazio: o klipper publica 1 Service por porta
helm install kong kong/ingress --version 0.24.0 -n kong --create-namespace -f platform/gateway/kong-values.yaml
```

Os dois ajustes do `kong-values.yaml` são obrigatórios neste cenário:
- `router_flavor: traditional_compatible` — senão `*.<DOMINIO>` captura `x.hml.<DOMINIO>` (Aprendizados 4.3);
- `externalTrafficPolicy: Local` — senão o Kong vê todo cliente como `10.42.0.1` (Aprendizados 4.4).

**Verificação:**
```bash
kubectl -n kong get svc kong-gateway-proxy           # LoadBalancer, EXTERNAL-IP = <IP_PRIVADO>, 80/443
kubectl -n kube-system get pods | grep svclb         # svclb-kong-gateway-proxy-* Running
curl -i http://<IP_PUBLICO>                          # 404 "no Route matched" do Kong
```
`<pending>`: outro Service `LoadBalancer` ocupa a porta (o pod `svclb` não sobe por conflito de `hostPort`).

---

## Fase 4 — DNS, certificados e teste de roteamento

1. **Cloudflare:** Add a site → `<DOMINIO>` (plano Free). Se o domínio já tem registros, **importar
   a zona** (arquivo BIND) e **comparar com a lista do painel do provedor antigo**, registro a registro
   — varredura por nomes conhecidos não acha o que você não sabe que existe (Aprendizados 4.6).
   Desmarcar "Proxy imported DNS records". Trocar os nameservers no registrador.
2. **Token da API** (My Profile → API Tokens → Custom): `Zone:DNS:Edit` + `Zone:Zone:Read`, só a zona
   `<DOMINIO>`, filtro de IP `<IP_PUBLICO>`.
3. **cert-manager:**
   ```bash
   helm repo add jetstack https://charts.jetstack.io && helm repo update
   helm install cert-manager jetstack/cert-manager -n cert-manager --create-namespace --version v1.21.2 \
     --set crds.enabled=true \
     --set 'extraArgs={--dns01-recursive-nameservers-only,--dns01-recursive-nameservers=1.1.1.1:53\,8.8.8.8:53}'
   read -rs CF_TOKEN && kubectl -n cert-manager create secret generic cloudflare-api-token \
     --from-literal=api-token="$CF_TOKEN"; unset CF_TOKEN
   sed 's/<EMAIL>/seu@email/' platform/cert-manager/cluster-issuers.yaml | kubectl apply -f -
   kubectl get clusterissuer                          # READY True nos dois
   ```
4. **Teste de emissão (staging)** — prova token + DNS-01 sem gastar a cota de produção:
   ```bash
   kubectl create ns cert-test
   kubectl -n cert-test apply -f - <<EOF
   apiVersion: cert-manager.io/v1
   kind: Certificate
   metadata: { name: teste }
   spec:
     secretName: teste-tls
     issuerRef: { kind: ClusterIssuer, name: letsencrypt-staging }
     dnsNames: ["*.<DOMINIO>"]
   EOF
   kubectl -n cert-test get certificate -w            # READY True em ~1–2 min
   kubectl delete ns cert-test
   ```
5. **DNS das aplicações** (A → `<IP_PUBLICO>`, **DNS only**): `api`, `*`, `hml-api`, `*.hml`, `argo`.
6. **Teste de roteamento** (antes de qualquer aplicação):
   ```bash
   kubectl create ns route-test
   sed 's/<DOMINIO>/exemplo.com.br/g' docs/testes/teste-roteamento.yaml | kubectl -n route-test apply -f -   # troque pelo seu domínio
   for h in api:api-prod tenant1:front-prod hml-api:api-hml tenant1.hml:front-hml x.y:front-prod; do
     n=${h%%:*}.<DOMINIO>; esperado=${h##*:}
     r=$(curl -s --resolve $n:80:<IP_PUBLICO> http://$n/ | awk '/^Name:/ {print $2}')
     [ "$r" = "$esperado" ] && echo "ok   $n → $r" || echo "ERRO $n → $r (esperado $esperado)"
   done
   kubectl delete ns route-test
   ```
7. **IP real no Kong:**
   ```bash
   curl -s -o /dev/null --resolve t.<DOMINIO>:80:<IP_PUBLICO> http://t.<DOMINIO>/ip-real-teste
   kubectl -n kong logs deploy/kong-gateway -c proxy --since=1m | grep ip-real-teste   # 1ª coluna = seu IP público
   ```

---

## Fase 5 — Argo CD

```bash
kubectl create namespace argocd
kubectl apply --server-side -n argocd \
  -f https://raw.githubusercontent.com/argoproj/argo-cd/v3.5.3/manifests/install.yaml
kubectl -n argocd rollout status deploy/argocd-server
```

**Credencial do Git** (repositório privado):
- **GitHub:** *fine-grained token* com `Contents: Read` nos repositórios (ou *deploy key* por repo).
  ```bash
  read -rs PAT && kubectl -n argocd create secret generic github-creds \
    --from-literal=type=git --from-literal=url=https://github.com/<owner> \
    --from-literal=username=git --from-literal=password="$PAT" \
    && kubectl -n argocd label secret github-creds argocd.argoproj.io/secret-type=repo-creds; unset PAT
  ```
- **[Azure]** `url=https://dev.azure.com/<org>`, PAT com `Code: Read`.

**UI com TLS e restrição por IP:**
```bash
kubectl apply -f platform/argocd/argocd-rota.yaml   # HTTPRoute + ReferenceGrant + ip-restriction (ajuste host e IPs)
kubectl -n argocd annotate svc argocd-server konghq.com/protocol=https --overwrite
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```
Entrar em `https://argo.<DOMINIO>` (usuário `admin`), **trocar a senha**, guardar no cofre e apagar
o `argocd-initial-admin-secret`.

**Verificação:** `https://argo.<DOMINIO>` → 200 do seu IP; de qualquer outro IP → **403**.

---

## Fase 6 — Observabilidade (Grafana Cloud)

1. Grafana Cloud → Observability → Kubernetes → Configuration:
   - **Install** (regras de alerta/recording do kit Kubernetes);
   - plataforma **Kubernetes**; perfil **Lightweight**; cluster name ex. `k3s-oci`; namespace `monitoring`;
   - Metrics: **Cluster metrics** e **Pod & Service metrics by annotation**; desligar Cost, Energy e
     Prometheus Operator objects;
   - Logs/Events: **Cluster events**, **Pod logs**, **Node logs** (journal do k3s); desligar Kubernetes manifests;
   - *Managed discovery pipeline*: **Do not create**.
2. Rodar no terminal o `helm upgrade --install grafana-cloud ...` exibido (contém o token — **não** colar em chat/Git).
3. Alertas: contact point de e-mail; rotas para a pasta própria e `severity=critical`; regras de nó
   (memória > 85% com **NoData → Alerting**, CPU > 85%, disco > 80%).
4. Synthetic Monitoring: checks HTTPS das URLs públicas (5 min, 2 regiões) + alerta de certificado < 14 dias.

**Verificação:** `kubectl top pods -n monitoring` (~125 MB no total); cluster visível em
Observability → Kubernetes; e-mail de teste do contact point recebido.

*(Alternativa self-hosted — Prometheus/Loki/Tempo/Grafana no cluster: ver Fase 4 do
`PLANEJAMENTO_DEVOPS.md`; custa ~1,5–2 GB de RAM no nó e para de alertar se a VM cair.)*

---

## Fase 7 — Aplicações

1. **Namespaces e Secrets** (por ambiente; valores do cofre, nunca do Git):
   ```bash
   for ns in app-prod app-hml; do
     kubectl create ns $ns
     # zsh; em bash: read -p "Usuario: " GU && read -s -p "Token (read:packages): " GT && echo
     read "GU?Usuario: " && read -s "GT?Token (read:packages): " && echo && \
     kubectl -n $ns create secret docker-registry registry-pull \
       --docker-server=ghcr.io --docker-username="$GU" --docker-password="$GT"; unset GU GT
   done
   kubectl -n app-prod create secret generic app-secrets --from-env-file=<(tr -d '\r' < ~/segredos/app-prod.env)
   ```
   **[Azure/Docker Hub]** `--docker-server=https://index.docker.io/v1/` e token *read-only* do Docker Hub.
2. **Repositório da aplicação:** `k8s/base` + `k8s/overlays/{prod,hml}` (modelo: `k8s/` do CaIA), com:
   probes (`startupProbe` generosa se houver migrations), `initContainer` que espera dependências
   externas (a rede de um pod novo leva ~3 s — Aprendizados 4.5), `resources`, usuário não-root,
   `Certificate` do ambiente (referenciado no listener do `Gateway`) e `HTTPRoute` para o `Gateway` do Kong.
3. **Esteira:** no repositório da aplicação, um `.github/workflows/ci.yml` curto que chama o template
   compartilhado (`backend-service.yml` ou `frontend-service.yml`) do repositório `tcc-pipeline-templates`
   — mesmo modelo dos templates `extends` usados em ambiente corporativo. O template publica a imagem no
   GHCR e grava a nova tag em `apps/<app>/kustomization.yaml` **deste** repositório.
   **[Azure]** `extends` do `Alta.DevOps.Pipelines` (o build service precisa de *Contribute* — Aprendizados 4.8).
   Os Dockerfiles devem compilar com `FROM --platform=$BUILDPLATFORM` e gerar `linux/arm64`.
4. **Applications do Argo CD** (uma por app/ambiente):
   ```yaml
   apiVersion: argoproj.io/v1alpha1
   kind: Application
   metadata: { name: app-api-hml, namespace: argocd }
   spec:
     project: default
     source: { repoURL: https://github.com/<owner>/<repo>, targetRevision: develop, path: k8s/overlays/hml }
     destination: { server: https://kubernetes.default.svc, namespace: app-hml }
     syncPolicy: { automated: { prune: true, selfHeal: true } }
   ```
   Criar só **depois** que o primeiro pipeline gravar uma tag real no overlay.
5. **Testar antes do DNS** apontar: `curl --resolve <host>:443:<IP_PUBLICO> https://<host>/...`.

⚠️ Nos PRs `develop → main`, **não** marcar "Delete source branch" — o Argo CD perde a referência da
`develop` (Aprendizados 4.11).

---

## Fase 8 — Proxy do Cloudflare (opcional)

1. SSL/TLS → **Full (strict)**; Always Use HTTPS; TLS mínimo 1.2; **Bot Fight Mode desligado**
   (desafia os probes do Synthetic Monitoring).
2. Kong confiando nas faixas do Cloudflare: `./platform/gateway/faixas-cloudflare.sh`, colar em
   `kong-values.yaml` e `helm upgrade kong kong/ingress -n kong --reuse-values -f platform/gateway/kong-values.yaml`.
3. Ligar o proxy só onde faz sentido: fronts estáticos sim; APIs com requisições > 100 s não
   (limite do plano Free — Aprendizados 4.12); `*.hml` não (certificado grátis não cobre 2º nível);
   e-mail/DKIM **nunca**.

**Verificação:** `cf-cache-status: HIT` em assets; IP real nos logs do Kong; cabeçalho
`CF-Connecting-IP` falsificado vindo de fora do Cloudflare é ignorado.

---

## Checklist final

| # | Item | Tempo de referência |
|---|---|---|
| 1 | VM, IP reservado, Security List (Source Port All), iptables | — |
| 2 | k3s `Ready`, sem Traefik, sem MetalLB | ~1 min |
| 3 | Kong: 404 "no Route matched" de fora | ~1 min |
| 4 | Certificado staging emitido; matriz de roteamento ok; IP real no log | ~2 min (certificado) |
| 5 | Argo CD em `https://argo.<DOMINIO>`, 403 de outros IPs, senha trocada | — |
| 6 | Cluster no Grafana Cloud, e-mail de teste recebido, checks externos verdes | ~5 min |
| 7 | Applications `Synced/Healthy`, certificado do ambiente `Ready` | ~1–2 min após o pipeline |
| 8 | (opcional) proxy do Cloudflare validado | — |

## O que este roteiro não cobre

- O que é específico da migração do CaIA (saída da AWS, migração de zona da Hostinger, R2, aliases
  de tenant) — ver `RepoAltaSistemas/MIGRACAO-OCI-K3S.md`.
- Backup/restauração de dados (o banco é gerenciado fora do cluster; o `local-path` não tem backup).
- Alta disponibilidade (um nó só).
