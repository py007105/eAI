# Frozen classifier on training crash windows, by target (offline proxy, IN-SAMPLE)

Read-only replay of `models-v1` on the training crash runs. These runs are part of the models' training data, so this is not a generalisation estimate; the benchmark rows hold no feature windows, so the benchmark's own orders-crash runs cannot be replayed. Novelty threshold in force: 1.0. Abstain-below confidence: 0.4.

| run        | target    | rel_s   |   windows |   answered |   abstain_novel |   abstain_low_conf | top labels                                                  |   median novelty |
|:-----------|:----------|:--------|----------:|-----------:|----------------:|-------------------:|:------------------------------------------------------------|-----------------:|
| crash_1000 | inventory | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.049 |
| crash_1000 | inventory | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1000 | inventory | 30-40   |         4 |          4 |               0 |                  0 | {'down': np.int64(4)}                                       |            0     |
| crash_1100 | web       | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.274 |
| crash_1100 | web       | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1100 | web       | 30-40   |         2 |          2 |               0 |                  0 | {'down': np.int64(2)}                                       |            0     |
| crash_1200 | payments  | 10-20   |         5 |          4 |               1 |                  0 | {'down': np.int64(4), 'insufficient_evidence': np.int64(1)} |            0.6   |
| crash_1200 | payments  | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1200 | payments  | 30-40   |         3 |          3 |               0 |                  0 | {'down': np.int64(3)}                                       |            0     |
| crash_1300 | payments  | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.346 |
| crash_1300 | payments  | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1300 | payments  | 30-40   |         4 |          4 |               0 |                  0 | {'down': np.int64(4)}                                       |            0     |
| crash_1400 | orders    | 10-20   |         5 |          4 |               1 |                  0 | {'down': np.int64(4), 'insufficient_evidence': np.int64(1)} |            0.893 |
| crash_1400 | orders    | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1400 | orders    | 30-40   |         3 |          3 |               0 |                  0 | {'down': np.int64(3)}                                       |            0     |
| crash_1500 | payments  | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.198 |
| crash_1500 | payments  | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1500 | payments  | 30-40   |         3 |          3 |               0 |                  0 | {'down': np.int64(3)}                                       |            0     |
| crash_1600 | web       | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.331 |
| crash_1600 | web       | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1600 | web       | 30-40   |         4 |          4 |               0 |                  0 | {'down': np.int64(4)}                                       |            0     |
| crash_1700 | inventory | 10-20   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0.301 |
| crash_1700 | inventory | 20-30   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
| crash_1700 | inventory | 30-40   |         5 |          5 |               0 |                  0 | {'down': np.int64(5)}                                       |            0     |
