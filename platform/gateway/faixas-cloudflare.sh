#!/usr/bin/env bash
# Imprime o bloco "trusted_ips" do kong-values.yaml com as faixas atuais do Cloudflare.
set -euo pipefail
v4=$(curl -fsS https://www.cloudflare.com/ips-v4 | tr -d '\r' | grep -E '^[0-9]' | paste -sd, -)
v6=$(curl -fsS https://www.cloudflare.com/ips-v6 | tr -d '\r' | grep -E '^[0-9a-f]' | paste -sd, -)
echo "    trusted_ips: \"$v4,$v6\""
echo "    real_ip_header: CF-Connecting-IP"
echo "    real_ip_recursive: \"on\""
