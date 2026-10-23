#!/usr/bin/env bash
set -euo pipefail
namespace="${1:-shop}"
kubectl -n "$namespace" annotate deployment frontend eternalai.io/depends-on='adservice,cartservice,checkoutservice,currencyservice,productcatalogservice,recommendationservice,shippingservice' --overwrite
kubectl -n "$namespace" annotate deployment checkoutservice eternalai.io/depends-on='cartservice,currencyservice,emailservice,paymentservice,productcatalogservice,shippingservice' --overwrite
kubectl -n "$namespace" annotate deployment recommendationservice eternalai.io/depends-on='productcatalogservice' --overwrite
kubectl -n "$namespace" annotate deployment cartservice eternalai.io/depends-on='redis-cart' --overwrite
