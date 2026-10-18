# (fault, target) coverage: training vs benchmark v1

Training runs counted from `data/runs/*.json` (72, including those excluded from fitting); benchmark runs are per arm (paired seeds give every arm the same targets). 'First incident abstained' uses the autopilot arm's first recorded incident in each run, including healthy scenarios.

| fault         | target    |   training runs |   benchmark runs per arm | autopilot first incident abstained   |
|:--------------|:----------|----------------:|-------------------------:|:-------------------------------------|
| bad_deploy    | inventory |               3 |                        1 | 0/1                                  |
| bad_deploy    | orders    |               2 |                        1 | 0/1                                  |
| bad_deploy    | payments  |               0 |                        3 | 0/3                                  |
| bad_deploy    | web       |               3 |                        0 | 0/0                                  |
| cpu_burn      | inventory |               4 |                        2 | 2/2                                  |
| cpu_burn      | orders    |               2 |                        1 | 1/1                                  |
| cpu_burn      | payments  |               2 |                        1 | 1/1                                  |
| cpu_burn      | web       |               0 |                        1 | 0/1                                  |
| crash         | inventory |               2 |                        2 | 0/2                                  |
| crash         | orders    |               1 |                        2 | 2/2                                  |
| crash         | payments  |               3 |                        0 | 0/0                                  |
| crash         | web       |               2 |                        1 | 0/1                                  |
| disk_fill     | inventory |               4 |                        2 | 0/2                                  |
| disk_fill     | orders    |               1 |                        1 | 0/1                                  |
| disk_fill     | payments  |               1 |                        1 | 0/1                                  |
| disk_fill     | web       |               2 |                        1 | 0/1                                  |
| error_spike   | inventory |               3 |                        3 | 0/3                                  |
| error_spike   | orders    |               1 |                        2 | 0/2                                  |
| error_spike   | payments  |               3 |                        0 | 0/0                                  |
| error_spike   | web       |               1 |                        0 | 0/0                                  |
| good_deploy   | inventory |               3 |                        1 | 0/1                                  |
| good_deploy   | orders    |               2 |                        4 | 3/4                                  |
| good_deploy   | payments  |               2 |                        0 | 0/0                                  |
| good_deploy   | web       |               1 |                        0 | 0/0                                  |
| latency       | inventory |               4 |                        0 | 0/0                                  |
| latency       | orders    |               2 |                        2 | 0/2                                  |
| latency       | payments  |               1 |                        1 | 0/1                                  |
| latency       | web       |               1 |                        2 | 0/2                                  |
| memory_leak   | inventory |               4 |                        2 | 0/2                                  |
| memory_leak   | orders    |               1 |                        1 | 0/1                                  |
| memory_leak   | payments  |               2 |                        0 | 0/0                                  |
| memory_leak   | web       |               1 |                        2 | 0/2                                  |
| traffic_surge | web       |               8 |                        5 | 1/5                                  |
