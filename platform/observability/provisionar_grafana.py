#!/usr/bin/env python3
"""Provisiona no Grafana Cloud (stack altasistemas) o que a plataforma do TCC declara como código:
regras de alerta (Quadro 8 do TCC), verificações sintéticas e o painel das aplicações.

Idempotente: recria pelos UIDs fixos. Uso:
  GRAFANA_URL=https://altasistemas.grafana.net GRAFANA_TOKEN=<service account, Admin> \
    python3 -I platform/observability/provisionar_grafana.py [--sinteticos]

O token nunca fica no Git (guarde-o fora do repositório, ex.: ~/.config/tcc-grafana-token).
"""
import json
import os
import pathlib
import sys
import urllib.request

URL = os.environ.get("GRAFANA_URL", "https://altasistemas.grafana.net").rstrip("/")
TOKEN = os.environ.get("GRAFANA_TOKEN") or pathlib.Path(os.path.expanduser("~/.config/tcc-grafana-token")).read_text().strip()
AQUI = pathlib.Path(__file__).resolve().parent
PASTA_UID = "tcc"


def api(metodo, caminho, corpo=None, ok=(200, 201, 202, 204), extra=None):
    req = urllib.request.Request(URL + caminho, method=metodo,
                                 data=json.dumps(corpo).encode() if corpo is not None else None,
                                 headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json",
                                          "X-Disable-Provenance": "true", **(extra or {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            dado = r.read()
            return json.loads(dado) if dado else {}
    except urllib.error.HTTPError as e:
        if e.code in ok:
            return {}
        raise RuntimeError(f"{metodo} {caminho}: {e.code} {e.read().decode()[:400]}")


def datasource(tipo):
    ds = [d for d in api("GET", "/api/datasources") if d["type"] == tipo and d["name"].startswith("grafanacloud-")]
    if not ds:
        raise RuntimeError(f"datasource {tipo} não encontrado")
    return ds[0]["uid"]


def pasta():
    try:
        api("GET", f"/api/folders/{PASTA_UID}")
    except RuntimeError:
        api("POST", "/api/folders", {"uid": PASTA_UID, "title": "TCC"})


def regra(uid, titulo, expr, limite, para, ds_prom, descricao):
    return {
        "uid": uid, "title": titulo, "folderUID": PASTA_UID, "ruleGroup": "tcc", "condition": "C",
        "for": para, "noDataState": "OK", "execErrState": "Error",
        "annotations": {"summary": titulo, "description": descricao},
        "labels": {"plataforma": "tcc"},
        "data": [
            {"refId": "A", "relativeTimeRange": {"from": 600, "to": 0}, "datasourceUid": ds_prom,
             "model": {"refId": "A", "expr": expr, "instant": True, "intervalMs": 15000, "maxDataPoints": 43200}},
            {"refId": "C", "datasourceUid": "__expr__",
             "model": {"refId": "C", "type": "threshold", "expression": "A",
                       "conditions": [{"evaluator": {"type": "gt", "params": [limite]}}]}},
        ],
    }


def alertas(ds_prom):
    regras = [
        regra("tcc-erros-5xx-api", "Erros 5xx na API",
              'sum by (deployment_environment) (rate(http_server_request_duration_seconds_count{job="catalogo-api", http_response_status_code=~"5.."}[2m]))'
              ' / sum by (deployment_environment) (rate(http_server_request_duration_seconds_count{job="catalogo-api"}[2m]))',
              0.05, "2m", ds_prom, "Mais de 5% das requisições da API com status 5xx (métricas OTLP)."),
        regra("tcc-replica-indisponivel", "Pod sem réplica pronta",
              'max by (namespace) (kube_deployment_status_replicas_unavailable{cluster="k3s-oci", namespace=~"catalogo-.*", deployment="app"})',
              0, "3m", ds_prom, "Deployment de aplicação com réplica indisponível (kube-state-metrics)."),
        regra("tcc-aplicacao-indisponivel", "Aplicação indisponível",
              '1 - min by (instance) (probe_success{job=~"tcc-.*"})',
              0, "2m", ds_prom, "Verificação sintética de uma rota pública falhando (Synthetic Monitoring)."),
    ]
    for r in regras:
        try:
            api("PUT", f"/api/v1/provisioning/alert-rules/{r['uid']}", r)
        except RuntimeError:
            api("POST", "/api/v1/provisioning/alert-rules", r)
        print("alerta:", r["title"])
    api("PUT", f"/api/v1/provisioning/folder/{PASTA_UID}/rule-groups/tcc", {"interval": 30, "rules": regras, "title": "tcc"})


def painel(ds_prom, ds_loki, ds_tempo):
    d = json.loads((AQUI / "painel-tcc.json").read_text(encoding="utf-8"))
    s = json.dumps(d).replace("${DS_PROM}", ds_prom).replace("${DS_LOKI}", ds_loki).replace("${DS_TEMPO}", ds_tempo)
    api("POST", "/api/dashboards/db", {"dashboard": json.loads(s), "folderUid": PASTA_UID, "overwrite": True})
    print("painel:", d["title"], f"{URL}/d/{d['uid']}")


def sinteticos():
    """Checks HTTP pelo proxy do datasource do Synthetic Monitoring (usa o token que o app já guarda)."""
    uid = next(d["uid"] for d in api("GET", "/api/datasources") if d["type"] == "synthetic-monitoring-datasource")
    base = f"/api/datasources/proxy/uid/{uid}/sm"
    sondas = api("GET", f"{base}/probe/list")
    # Cota gratuita: 100 mil execuções/mês no stack (já há checks de outros projetos). 4 checks,
    # 1 ponto de prova (São Paulo, se houver), a cada 5 min = 34.560 execuções/mês.
    publicas = [p for p in sondas if p.get("public") and p.get("online")]
    ids = [next((p for p in publicas if "Paulo" in p["name"]), publicas[0])["id"]]
    existentes = {c["job"]: c for c in api("GET", f"{base}/check/list")}
    alvos = [
        ("tcc-front-hml", "https://hml-catalogo.tcc.altasistemas.com.br/healthz"),
        ("tcc-api-hml", "https://hml-catalogo-api.tcc.altasistemas.com.br/health"),
        ("tcc-front-prd", "https://catalogo.tcc.altasistemas.com.br/healthz"),
        ("tcc-api-prd", "https://catalogo-api.tcc.altasistemas.com.br/health"),
    ]
    for job, alvo in alvos:
        check = {"job": job, "target": alvo, "frequency": 300000, "timeout": 10000, "enabled": True,
                 "probes": ids, "labels": [{"name": "plataforma", "value": "tcc"}],
                 "settings": {"http": {"method": "GET", "validStatusCodes": [200], "ipVersion": "V4", "failIfNotSSL": True}},
                 "basicMetricsOnly": True, "alertSensitivity": "none"}
        if job in existentes:
            check["id"] = existentes[job]["id"]; check["tenantId"] = existentes[job]["tenantId"]
            api("POST", f"{base}/check/update", check)
        else:
            api("POST", f"{base}/check/add", check)
        print("sintético:", job, alvo)


if __name__ == "__main__":
    pasta()
    prom, loki, tempo = datasource("prometheus"), datasource("loki"), datasource("tempo")
    alertas(prom)
    painel(prom, loki, tempo)
    if "--sinteticos" in sys.argv:
        sinteticos()
