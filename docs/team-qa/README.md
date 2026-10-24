# Team QA documents: runbooks, manual checks, troubleshooting

This folder holds plain-language documentation and a manual QA kit for EternalAI. It was written by Sanskar (with an AI
writing assistant) for teammates, judges and testers who need to understand or check the system without reading the code.

**Commit described:** every `path:line` citation in this folder refers to commit
`65dd9fe014e2bdfe6cede2cd9f69b0a014604f93` (`65dd9fe`, the head of `plan-complete` when this work started on 2026-10-23).
If the code moves, line numbers may no longer match.

## What is in this folder

| file | for whom | content |
|---|---|---|
| [`RUNBOOKS_EXPLAINED.md`](RUNBOOKS_EXPLAINED.md) | everyone | the four recovery actions (runbooks), when they are proposed, who must approve them, how success is checked, evidence |
| [`MANUAL_TEST_CHECKLIST.md`](MANUAL_TEST_CHECKLIST.md) | testers | manual checks of the dashboard and the approval workflow; **prepared, not executed** |
| [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) | presenters, testers | set-up and demo problems, with the exact messages the code or logs show |
| [`BUG_REPORT_TEMPLATE.md`](BUG_REPORT_TEMPLATE.md) | testers | a bug-report form and one clearly fictional example |
| [`HANDBACK.md`](HANDBACK.md) | Claude (integration owner), Prem | what was done, what was not, source discrepancies and questions |

## Evidence levels (same words as the rest of the project)

- **implemented only:** the code exists; nobody has shown it working.
- **unit-tested:** automatic tests pass (this folder does not run them; it only names them where relevant).
- **live verified:** a committed script ran it against the real running system and wrote a results file, for example
  `docs/results/live_check_phase1.md` (17 checks, 2026-10-21). Note: that live check ran at commit `a24bc69`
  (`docs/results/live_check_phase1.md:3`), earlier than the `65dd9fe` these documents cite; it was not re-run at `65dd9fe`.

Two more labels are used in this folder:

- **benchmark under the previous policy:** results from `docs/results/benchmark_v2.md`, measured under
  `eternalai/rulebooks/benchmark-v2.yaml`, where recreate and rollback could run automatically. The current rulebook
  (`eternalai/rulebooks/default.yaml`) is stricter, so these results do not show what the current approval rules do.
- **inferred from code:** what the source says should happen. This is **not** a test result. Every expected result in the
  checklist is of this kind until someone performs the check.

## What was and was not done

- Nothing in this folder was observed on a running system by the author. No Docker, no Python, no test runs were used.
- Every manual check is **Not executed**: no demo instance was supplied for this work.
- Only messages that appear in the source at `65dd9fe` or in existing results files are quoted.

## Rules for using these documents

- Never write, paste, photograph or screenshot an approval token, API key or password. If Prem types a token during a
  check, record only "token entered by Prem".
- Corrections to documents outside this folder are not made here; they are listed in `HANDBACK.md` for Claude.
