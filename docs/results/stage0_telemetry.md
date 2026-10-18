# Stage 0: telemetry condition (pre-registered rule, Amendment 4 section K)

Six surge runs at intensity 40, two per condition, v2 brain in watch-only mode, apps recreated before every run. Training medians: web 66.8 MB, inventory 65.3 MB; limits: increment and distance at most 3.0 MB.

| condition   |   seed |   web before MB |   web peak MB |   web increment MB |   inventory before MB |   inventory peak MB |   inventory increment MB |   incidents in window |
|:------------|-------:|----------------:|--------------:|-------------------:|----------------------:|--------------------:|-------------------------:|----------------------:|
| T1          |   3621 |            66.3 |          69.4 |                3.1 |                  65.1 |                67.6 |                      2.5 |                     1 |
| T1          |   3624 |            65.8 |          68.8 |                3   |                  65.1 |                68.1 |                      3.1 |                     1 |
| T2          |   3604 |            66.9 |          76.6 |                9.7 |                  66.2 |                75.6 |                      9.4 |                     1 |
| T2          |   3608 |            67.4 |          77.1 |                9.7 |                  66.2 |                76.1 |                      9.9 |                     1 |
| T3          |   3614 |            64.5 |          65   |                0.5 |                  63.6 |                64.2 |                      0.5 |                     0 |
| T3          |   3620 |            64.7 |          65.2 |                0.6 |                  63.7 |                64.2 |                      0.5 |                     0 |

Qualifies: T1 = False, T2 = False, T3 = True

**Chosen: T3** (qualifies (first in the order T3, T1, T2)).
