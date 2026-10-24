# Pre-integration review of the teammate branches (2026-10-24, about 00:20 IST)

Read-only review while the candidate evaluation runs; nothing merged. Branch heads fetched from GitHub.

| branch | head | base | owned paths only | secret patterns | dependency or manifest changes | tests reproduced here | hand-back claims |
|---|---|---|---|---|---|---|---|
| `team/rajat-zscore-nab` (PR #1) | `121024f` | `65dd9fe` | yes (8 files) | 0 | none | focused: 44 passed | pre-registration `36172c5` committed before the download (`c96e0e9`) and the results (`6a4d82b`); offline public-data evaluation, labelled "not live verified"; 17 series / 30 windows evaluated (the plan's "20 series, 327 events" not reproduced) |
| `team/mihir-dashboard-charts` | `55964ad` | `65dd9fe` | yes (12 files) | 0 | none | focused: 21 passed | synthetic data only; **Milestone 5 (screenshots) not done**, Milestone 6 partial; preview checked by HTTP and callback calls, not in a browser |
| `team/sanskar-docs-final` | `f8d6941` | `65dd9fe` | yes (`docs/team-qa/` only) | 0 | none | n/a (documents) | checklist prepared, not executed (37 checks); **branch name differs from the assigned `team/sanskar-docs-runbooks-qa`, and the hand-back says that name was pushed: to clarify with Sanskar** |

## Answers to Sanskar's technical questions (docs/team-qa/HANDBACK.md)
1. **Named volumes on recreate.** Checked read-only on the running stack (Compose 5.6.0): `HostConfig.Binds` contains
   `eai_inventory-data:/data:rw` (and the same for orders and payments), so `_recreate_from` passes the data volume.
   Not a bug on this version. It is version-dependent behaviour: a recreate check against the volume belongs in a
   future live check.
2. **No restore if a recreate fails after the old container is removed.** Correct; a known limitation (roadmap). The
   manual recovery is `docker compose -p eai up -d --force-recreate <service>`.
3. **Medium-risk restarts wait in autopilot.** Intended under the default rulebook (plan values); benchmark v2 ran under
   `benchmark-v2.yaml`.
4. **Reject while the kill switch is on.** Allowed on purpose: rejecting executes nothing.
5. **Expiry visibility (R4/R5).** Still unresolved.
6. **"blocked" before "observe_only" in watch-only.** Current behaviour (`policy.py` order); wording to be reviewed.

## Integration plan (after the candidate evaluation ends; one branch at a time)
- **Order:** Sanskar (documents), then Rajat (new module and offline scripts, no engine wiring), then Mihir (new
  dashboard modules, no `app.py` wiring).
- **After each merge:** the full suite.
- **After all three:** the combined result needs its own validation. Tonight's candidate results do not cover it.

## Update (2026-10-24 00:28 IST, remote heads re-verified with `git ls-remote`)
- `team/rajat-zscore-nab` moved `121024f` -> `a748eb1` (fast-forward; one commit changing only the submission section of
  `docs/handback/rajat.md`). PR #2 points at `a748eb1`; PR #1 still points at `121024f`. The review above covers `a748eb1`
  (no code or result change). **Integrate `a748eb1` (PR #2) only, after re-verifying that exact commit; PR #1 should be
  closed by Rajat.**
- `team/sanskar-docs-final` is at `f8d6941` (verified). The assigned name `team/sanskar-docs-runbooks-qa` does not exist on
  GitHub. A rename is not required; the hand-back note must be corrected to name the real branch.
- `team/mihir-dashboard-charts` is at `55964ad` (verified); the three preview screenshots are still missing.
