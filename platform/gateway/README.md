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
