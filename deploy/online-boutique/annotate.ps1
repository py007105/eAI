param([string]$Namespace = 'shop')
$ErrorActionPreference = 'Stop'
kubectl -n $Namespace annotate deployment frontend 'eternalai.io/depends-on=adservice,cartservice,checkoutservice,currencyservice,productcatalogservice,recommendationservice,shippingservice' --overwrite
if ($LASTEXITCODE -ne 0) { throw 'frontend annotation failed' }
kubectl -n $Namespace annotate deployment checkoutservice 'eternalai.io/depends-on=cartservice,currencyservice,emailservice,paymentservice,productcatalogservice,shippingservice' --overwrite
if ($LASTEXITCODE -ne 0) { throw 'checkoutservice annotation failed' }
kubectl -n $Namespace annotate deployment recommendationservice 'eternalai.io/depends-on=productcatalogservice' --overwrite
if ($LASTEXITCODE -ne 0) { throw 'recommendationservice annotation failed' }
kubectl -n $Namespace annotate deployment cartservice 'eternalai.io/depends-on=redis-cart' --overwrite
if ($LASTEXITCODE -ne 0) { throw 'cartservice annotation failed' }
