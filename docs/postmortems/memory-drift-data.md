# Memory versus uptime and prior load (read-only diagnosis on seen data)

## 1. Surge captures, in the order the runs were made (non-benchmark seeds)

|   seed |   level | run start   |   web MB before |   web MB peak |   web uptime min |   orders MB before |   orders MB peak |   orders uptime min |   inventory MB before |   inventory MB peak |   inventory uptime min |   payments MB before |   payments MB peak |   payments uptime min |
|-------:|--------:|:------------|----------------:|--------------:|-----------------:|-------------------:|-----------------:|--------------------:|----------------------:|--------------------:|-----------------------:|---------------------:|-------------------:|----------------------:|
|   3600 |      25 | 08:23:23    |            67.4 |          76.9 |              6.7 |               73.6 |             73.6 |                23   |                  66.5 |                75.9 |                   15.4 |                 66.9 |               66.8 |                  23   |
|   3601 |      25 | 08:26:32    |            67.5 |          77.5 |              1.5 |               73.6 |             73.6 |                26.1 |                  71.6 |                76.2 |                   18.6 |                 66.8 |               66.9 |                  26.1 |
|   3602 |      25 | 08:28:28    |            66.4 |          76.6 |              0.8 |               73.6 |             73.6 |                28   |                  71.8 |                76.5 |                   20.5 |                 66.8 |               66.9 |                  28.1 |
|   3603 |      25 | 08:30:24    |            67.4 |          77.2 |              0.8 |               73.6 |             73.6 |                30   |                  72.6 |                76   |                   22.4 |                 66.9 |               66.9 |                  30   |
|   3605 |      25 | 08:32:16    |            66.9 |          76.7 |              0.8 |               73.6 |             73.7 |                31.9 |                  72.1 |                76   |                   24.3 |                 66.9 |               66.9 |                  31.9 |
|   3606 |      25 | 08:34:12    |            67   |          76.6 |              0.8 |               73.6 |             73.8 |                33.8 |                  72.6 |                76.8 |                   26.2 |                 66.9 |               66.9 |                  33.8 |

`uptime min` is the container's age when the run started; a service not targeted by the surge (all but `web`) is not recreated between runs, so its uptime grows by the run length. Read down a column: a value that rises from run to run without a recreation is memory the process keeps after load (a high-water mark).

## 2. Training runs: median pre-injection memory (MB) per service, by hour of the collection

|   hour of collection |   web |   orders |   inventory |   payments |   runs |
|---------------------:|------:|---------:|------------:|-----------:|-------:|
|                    0 |  66.8 |     70.8 |        65.3 |       64.2 |     25 |
|                    1 |  67.4 |     70.9 |        65.3 |       64.4 |     16 |
|                   14 |  67   |     68.9 |        65.1 |       64.4 |     22 |
|                   15 |  66.7 |     68.8 |        65.4 |       65.4 |      8 |
|                   16 |  66.4 |     68.5 |        67.1 |       65.6 |      1 |

All 72 training runs: median per service web 66.8 MB (min 65.3, max 71.1), orders 70.1 MB (min 67.0, max 71.8), inventory 65.3 MB (min 64.5, max 67.2), payments 64.4 MB (min 63.8, max 65.6).

## 3. v1 benchmark: memory share of limit reported in the preserved incidents' forecast evidence (integer percent), by 2-hour bin

| hour            |   inventory |   orders |   payments |   web |   incidents |
|:----------------|------------:|---------:|-----------:|------:|------------:|
| 10-17 14:00 UTC |          25 |       26 |        nan |    25 |          13 |
| 10-17 16:00 UTC |          28 |       27 |         25 |    26 |          29 |

For scale: training medians in percent of the 256 MiB limit are about web 25%, orders 26%, inventory 24%, payments 24%.
