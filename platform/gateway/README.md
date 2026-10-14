# platform/gateway/

Entrada HTTP/HTTPS da plataforma pela **Gateway API** (decisão do TCC: sem `Ingress`).

- CRDs do canal *standard* da Gateway API, instalados antes do Kong (o controlador detecta na subida).
- `GatewayClass` do Kong e um `Gateway` com um listener HTTPS por host da plataforma; os certificados
  são `Certificate` do cert-manager cujos Secrets o listener referencia.
- Cada aplicação declara um `HTTPRoute` no seu overlay (`apps/<app>/<ambiente>`), com `parentRefs` para
  esse Gateway.
- `kong-values.yaml`: ajustes obrigatórios do Kong neste cluster (`router_flavor: traditional_compatible`,
  `externalTrafficPolicy: Local`); `faixas-cloudflare.sh` gera o `trusted_ips`.

O Kong do cluster também atende os `Ingress` do CaIA; os dois modelos convivem no mesmo controlador.

## Incidente de 2026-10-14 (primeira tentativa)

Gateway aplicado com o listener HTTPS apontando para um Secret ainda não emitido (`tcc-wildcard-tls`),
num cluster em que o mesmo KIC também atendia `Ingress` com TLS (Argo CD e CaIA). O Kong passou a
rejeitar a configuração (`certificate: value must be null` nos três certificados dos Ingress), o KIC
aplicou a configuração de fallback **sem os certificados** e o Argo CD serviu o certificado autoassinado
do Kong por ~2 min, até o Gateway ser removido.

**Causa confirmada na terceira tentativa:** o `HTTPRoute` de redirecionamento HTTP→HTTPS (`RequestRedirect`
sem `hostname`). No KIC 3.5 + Kong 3.9 ele vira um plugin inválido e o Kong recusa a configuração
inteira; os erros de `certificate` no log são consequência (ver issue Kong/kubernetes-ingress-controller#7831).
Sem o redirect, o mesmo Gateway foi aceito sem nenhum erro, convivendo com os `Ingress` do CaIA.
O mesmo limite está registrado no norte-k3s (`k8s/PADROES.md`). Hoje HTTP responde **426**. Uma rota por host com `requestRedirect.hostname`
explícito é aceita, mas fica instável (ver `redirect-https.yaml.desativado`).

Ordem adotada depois (a mesma do norte-k3s, que só usa Gateway API):

1. Certificados emitidos e `Ready` antes de qualquer listener referenciá-los.
2. Argo CD migrado de `Ingress` para `HTTPRoute` (`platform/argocd/argocd-rota.yaml`).
3. Gateway aplicado observando os logs do `kong-controller`, com o `delete` pronto para reverter.
