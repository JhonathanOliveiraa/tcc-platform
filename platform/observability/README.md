# platform/observability/

Tudo vai para o **Grafana Cloud** (stack `altasistemas.grafana.net`); no cluster só roda o Grafana
Alloy do chart `grafana/k8s-monitoring` 4.5.2 (release `grafana-cloud`, namespace `monitoring`,
`cluster.name=k3s-oci`), gerenciado pelo Fleet Management. Métricas do cluster, logs de pods e eventos
vêm do pipeline do assistente (`k8s_monitoring_k8s_monitoring_k3s_oci`).

**Traces/métricas OTLP das aplicações**: pipeline manual `tcc_otlp_receiver` no Fleet, conteúdo em
[`otlp-receiver.alloy`](otlp-receiver.alloy). As apps enviam para
`grafana-cloud-otel-receiver.monitoring.svc.cluster.local:4317` (variáveis no `golden-path/base`).

Diagnóstico: sem dado no Tempo, conferir se o receptor está ativo —
`kubectl get --raw "/api/v1/namespaces/monitoring/services/grafana-cloud-otel-receiver:4318/proxy/v1/traces"`
deve responder (405 Method Not Allowed), não 502 — e o log do Alloy
(`kubectl -n monitoring logs ds/grafana-cloud-alloy -c alloy | grep otelcol`).

Não ligar instrumentação automática (Beyla/injeção) para os namespaces `catalogo-*`: a API já se
instrumenta e cada requisição apareceria duas vezes.

## Alertas, verificações sintéticas e painel (como código)

`provisionar_grafana.py` cria/atualiza no Grafana Cloud, pelos UIDs fixos (idempotente):

| O quê | Detalhe |
|---|---|
| Regras de alerta (pasta `TCC`, grupo `tcc`) | **Erros 5xx na API** (> 5% em 2 min, métricas OTLP) · **Pod sem réplica pronta** (kube-state-metrics, 3 min) · **Aplicação indisponível** (`probe_success` dos checks `tcc-*`, 2 min) |
| Synthetic Monitoring (`--sinteticos`) | GET `/healthz` do front e `/health` da API, hml e prd, a cada 5 min, de 1 ponto de prova (São Paulo) — limite da cota gratuita de 100 mil execuções/mês, compartilhada com outros projetos do stack |
| Painel `tcc-aplicacoes` | requisições/status e latência da API, CPU/memória por namespace, sintéticos, logs e traces (`painel-tcc.json`) |

```bash
GRAFANA_TOKEN=$(cat ~/.config/tcc-grafana-token) python3 -I platform/observability/provisionar_grafana.py --sinteticos
```

O token é de uma *service account* com papel Admin no stack e nunca vai para o Git.
