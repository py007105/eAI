# Hand-back: documentation and manual QA
- Branch: team/sanskar-docs-final (the branch actually pushed; earlier drafts of this note named
  `team/sanskar-docs-runbooks-qa`, which was not the pushed branch. Corrected by the main session on 2026-10-24.)
- Starting commit: 65dd9fe014e2bdfe6cede2cd9f69b0a014604f93    - Final commit of Sanskar's work: f8d6941
  ("QA docs: hand-back submission details"). Corrections after that are separate main-session commits.
- Documents describe the system at commit: 65dd9fe (no checkpoint merged)
- Written by Sanskar's AI writing assistant (Claude Code) on 2026-10-23, after Prem lifted the freeze for this
  documentation work only (relayed by Sanskar). Git, a text editor and read-only shell commands only: no Docker, no
  Python, no tests, no application code changed.

## Files
- docs/team-qa/README.md: what is in the folder, audience, evidence levels, baseline commit, nothing executed.
- docs/team-qa/RUNBOOKS_EXPLAINED.md: the four runbooks with the seven required headings, plus the safety rules.
- docs/team-qa/MANUAL_TEST_CHECKLIST.md: 37 manual checks (groups A-H), all Not executed.
- docs/team-qa/TROUBLESHOOTING.md: the 12 required topics plus 3 extra, all sourced.
- docs/team-qa/BUG_REPORT_TEMPLATE.md: the form and one example marked "EXAMPLE ONLY: fictional, not a real bug."
- docs/team-qa/HANDBACK.md: this note.

## Milestones
| # | status (done / partial / not done) | notes |
|---|---|---|
| 1 runbooks | done | every section has the seven headings; benchmark-v2 evidence labelled "previous policy"; `recreate_container` and `clear_temp_path` have no live evidence, which is stated |
| 2 checklist | done | 37 checks, A-H; every expected result cites a source |
| 3 troubleshooting | done | 15 entries; all quoted messages are in source or results files |
| 4 bug template | done | all fields from section 2.6 |
| 5 manual run | prepared, not executed | no demo instance supplied |

## Manual checklist summary
- Pass: 0  Fail: 0  Blocked: 0  Not executed: 37   (environment: none)

## Bugs found
- none (no check was executed, so no bug was observed)

## Source discrepancies and integration requests (for Claude)
| document / file | what looks wrong or missing | proposed correction |
|---|---|---|
| `SANSKAR_TASKS.md` header | says the freeze is still in force and only Milestone 0 is allowed | for the record: Sanskar relayed that Prem lifted the freeze for this assignment; please confirm |
| `SANSKAR_TASKS.md` 2.5, worked example 3 ("often because of a pasted space or line break"); same idea in `docs/DEMO.md` line 46 | the dashboard strips leading and trailing spaces and line breaks before sending (`dashboard/app.py:82`); a line break inside the value gives "Token contains invalid characters" (`dashboard/app.py:87-89`), not 403 | TROUBLESHOOTING entry 3 uses the corrected cause; consider the same wording in `docs/DEMO.md` |
| `dashboard/labels.py:16` (`backend_offline`) | the message suggests `uvicorn eternalai.api:app --port 8000`, while the Docker demo restarts the brain with `docker compose -p eai up -d eternalai` (`docs/DEMO.md` line 99) | decide whether the message should mention the Docker command |
| `dashboard/app.py:106-112` | the mode options, token placeholder and Kill switch button text are built without `lang`, so they stay English after choosing हिन्दी, although `labels.py` has a Hindi `killswitch` (line 158). Inferred from code, not observed | check during A-02; translate if intended |
| `dashboard/app.py:106-108,195` | the mode selector has no initial value (placeholder "Mode"), so it does not show the current mode; the status pill shows the raw value (`ask-first`), not the label "Ask first". Inferred, not observed | confirm whether intended |
| `docs/results/live_check_phase1.md:3` | the live evidence is from commit `a24bc69`, not `65dd9fe` | state the commit wherever "live verified" is quoted for 65dd9fe (done in README) |
| `AGENTS.md` | requires `python -m pytest` after every commit and a full read of `docs/HANDOFF_FRIEND.md`; the assignment says no tests and gives its own rules | tests were not run (assignment wins for this package); `docs/HANDOFF_FRIEND.md` was not read in full (its Codex/D:\eAI rules apply to Prem's machine, as section 8 of the assignment says) |
| `docs/DEMO.md` line 79 | narration says the card shows "low risk"; a card can be medium or high (`default.yaml:18,21-23,26-27`) | say "`<risk>` risk" |

## Questions requiring Claude's technical review
1. **recreate/rollback and data volumes.** `_recreate_from` passes `HostConfig.Binds` (`eternalai/executor.py:69-70`). The
   compose services use named volumes (`docker-compose.yml:17,23,29`). Does Docker report those in `Binds` for compose
   containers, or only in `Mounts`? If only in `Mounts`, the recreated container would not get its data volume. The
   runbook document repeats the code's claim ("same volumes", `executor.py:64`) without verifying it.
   **Answer (main session, 2026-10-24):** checked read-only on the running stack with Docker Compose 5.6.0:
   `HostConfig.Binds` contains `eai_inventory-data:/data:rw` (and the same for orders and payments), so `_recreate_from`
   passes the data volume **in that tested configuration**. This is not a general guarantee: whether Docker lists named
   volumes in `Binds` can depend on the Compose/Engine version and on how the volume is declared. No live check recreates
   a container and verifies its data afterwards.
2. **No restore on a failed recreate.** The old container is removed before the new one is created
   (`executor.py:77-82`); a creation failure leaves no container. Is this intended, and is "stuck service: force-recreate"
   (TROUBLESHOOTING 11) the intended recovery?
   **Answer (main session, 2026-10-24):** correct, and still a known limitation: there is **no automatic rollback** to
   the old container if creating the new one fails. The manual recovery is
   `docker compose -p eai up -d --force-recreate <service>`.
3. **Medium-risk restarts in Autopilot.** Error-spike and latency-spike restarts are medium (`default.yaml:26-27`) and
   therefore wait for approval in Autopilot (`policy.py:91-95`). Benchmark v2 ran them automatically. Please confirm the
   documents should present this as intended current behaviour.
4. **Kill switch on with a card already waiting.** The card stays until it expires; Approve gets 409
   (`engine.py:453-454`), but Reject is not refused by the kill switch (`engine.py:459-467`). Intended?
5. **Expiry visibility (R4/R5).** Unresolved in the rehearsal reports. Checklist D-07 asks the tester to record what the
   queue showed; no new information was produced here.
6. **Order of checks.** In Watch only, cooldown/breaker/hourly cap are checked first, so a Watch-only proposal can be
   recorded as "blocked" rather than "observe_only" (`policy.py:68-83`). Is that the intended wording for users?

## Verification done
- citations checked against 65dd9fe: yes. All 221 distinct `path:line` citations resolve to an existing file with the
  line in range (scripted with `git show 65dd9fe:<path>`); the content of each cited line was read while writing. The
  line numbers listed in assignment section 2.2 all matched the source.
- Markdown preview checked: no (no viewer opened; tables were written in standard GitHub Markdown).
- git diff --stat shows only docs/team-qa/: yes.
- secret check (assignment section 7 step 6) before every commit: no matches.

## Submission
- Push and PR authorised by Prem (relayed by Sanskar) on 2026-10-23. Only `team/sanskar-docs-final` is pushed
  (no force-push); the PR targets `plan-complete` and is not merged by the author. The PR link is in the PR itself and in
  the message to Prem. No bundle or zip was made.
- Checks re-run before the push: 232 distinct citations in range at `65dd9fe` (one scripted false positive,
  `docker-compose.yml:17,23,29`, checked by hand); 37 checks Not executed, 0 Pass/Fail/Blocked; diff only under
  `docs/team-qa/`; secret check no matches; `origin/plan-complete` still at `65dd9fe`, so no merge was needed.

## Integration order and rollback
- Independent of all other branches (documentation only).
- Rollback: Claude merges with `git merge --no-ff`; `git revert -m 1 <merge commit>` undoes it without rewriting history.
