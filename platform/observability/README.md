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
