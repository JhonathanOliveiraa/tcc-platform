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

Ordem adotada depois (a mesma do norte-k3s, que só usa Gateway API):

1. Certificados emitidos e `Ready` antes de qualquer listener referenciá-los.
2. Argo CD migrado de `Ingress` para `HTTPRoute` (`platform/argocd/argocd-rota.yaml`).
3. Gateway aplicado observando os logs do `kong-controller`, com o `delete` pronto para reverter.
