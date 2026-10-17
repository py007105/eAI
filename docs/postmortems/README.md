# Post-mortems

One short document per benchmark non-recovery (and per surprising result), written from **existing run logs only**, never by changing code
or re-running a scenario inside the v1 tree. Generate the skeleton with:

```
python scripts/postmortem_extract.py --arm <arm> --scenario <scenario> --seed <seed>
```

Questions, always in this order (the skeleton answers each from the stored row and says "NOT IN THE STORED ROW" where it cannot):

1. Was the fault detected, and how fast?
2. Was it classified, and was the injected service ranked first?
3. Did the policy allow an action?
4. Did the executor run?
5. Did verification fail?
6. Did EternalAI preserve evidence, stop repeated attempts and escalate cleanly?
7. Triage class with evidence, following `docs/EVALUATION_PLAN.md` section 9: **(a)** harness artifact, **(b)** system bug, **(c)** design limitation. Leave it
   **unclassified** when the evidence is missing; say what evidence is needed and where it is.

A clean escalation (honest report, no wrong action, evidence kept, no repeated attempts) is valid, demo-worthy behaviour. It is still a missed recovery
when a runbook existed for the cause, and the document must say so.

Index:

- [crash-orders-seed100-v1.md](crash-orders-seed100-v1.md): `eternalai_autopilot`, crash of `orders`, not recovered.
