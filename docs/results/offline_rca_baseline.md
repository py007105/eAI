# Offline root-cause baselines (training runs)

**OFFLINE comparison on the training runs. Not a live arm, not a benchmark result.** Methods are untrained and re-implemented (not the RCAEval or PyRCA packages); intervals are bootstrap 95% resampling whole runs. The learned ranker's out-of-fold figure is in `docs/results/models_cv.md` (same incident definition) and is not recomputed here. RE2/RE3 were not downloaded.

Runs: 55; incidents per method: 236.

| method | top-1 [95%] | top-3 [95%] |
|---|---|---|
| BARO-style robust z (re-implementation) | 0.441 [0.331, 0.549] | 0.864 [0.786, 0.930] |
| random walk with restart on call graph (PyRCA/RCD-style, simplified) | 0.441 [0.331, 0.549] | 0.881 [0.808, 0.942] |
| error-ratio z only (naive) | 0.411 [0.295, 0.529] | 0.835 [0.729, 0.927] |
| random | 0.271 [0.218, 0.325] | 0.733 [0.675, 0.786] |

## Top-1 by fault scenario

| scenario    |   baro |   errors |   random |   walk |   incidents |
|:------------|-------:|---------:|---------:|-------:|------------:|
| bad_deploy  |  0.656 |    0.656 |    0.312 |  0.656 |          32 |
| cpu_burn    |  0.286 |    0.036 |    0.25  |  0.286 |          28 |
| crash       |  0.031 |    0     |    0.156 |  0.031 |          32 |
| disk_fill   |  0.4   |    0.45  |    0.175 |  0.4   |          40 |
| error_spike |  0.656 |    0.656 |    0.312 |  0.656 |          32 |
| latency     |  0.438 |    0.5   |    0.25  |  0.438 |          32 |
| memory_leak |  0.575 |    0.5   |    0.425 |  0.575 |          40 |
