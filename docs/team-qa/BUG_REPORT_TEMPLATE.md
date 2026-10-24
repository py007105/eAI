# Bug report template

Copy the template into a new file `docs/team-qa/bugs/BUG-<n>.md` and fill every field. Report only what you saw yourself.
If you are not sure it is a bug, say so in "actual result"; Claude decides at review.

**Never put a token, key or password in a report**, not in the text and not in a screenshot. Write
"token entered by Prem" instead.

## Template

```markdown
# BUG-<n>: <one-line title: what is wrong, where>

| field | value |
|---|---|
| Date and time (IST) | <YYYY-MM-DD HH:MM IST> |
| Reporter | <name> |
| System version | <commit hash or tag of the instance, from Prem> |
| Environment | <whose machine; Prem's demo instance or not; browser> |
| Mode | <Watch only / Ask first / Autopilot> |
| How often | <always / sometimes (n of m tries) / once> |
| Severity | <blocker / major / minor / cosmetic> |
| Related checklist ID | <e.g. D-03, or "none"> |

## Steps to reproduce
1. <first step>
2. <next step>
3. <...>

## Expected result
<what should happen, with the source: `path:line` at the stated commit, or a document section>

## Actual result
<what happened, exactly; quote messages word for word>

## Evidence
- Screenshots: <docs/team-qa/screenshots/MC-<ID>.png, ...> (token field empty or masked)
- Exact messages: <copied text>
- Other: <timeline lines, incident id, time seen>

## Workaround
<what got you past it, or "none known">
```

**Severity guide.** *blocker:* the demo or a check cannot continue. *major:* a feature gives a wrong result or is
unusable, with a workaround. *minor:* small wrong behaviour that does not affect the outcome. *cosmetic:* wording,
layout or translation only.

---

## Example

**EXAMPLE ONLY: fictional, not a real bug.** Nothing below was observed. It only shows how a filled report looks. The
behaviour described is invented; the code at `65dd9fe` is expected to do the opposite.

# BUG-0 (example): countdown on the approval card stays at 120 s

| field | value |
|---|---|
| Date and time (IST) | 2026-01-01 10:00 IST (fictional) |
| Reporter | Example Tester (fictional) |
| System version | `0000000` (fictional) |
| Environment | fictional demo instance; Chrome |
| Mode | Ask first |
| How often | sometimes (2 of 3 tries, fictional) |
| Severity | major |
| Related checklist ID | D-03 |

## Steps to reproduce
1. Open the dashboard; token entered by Prem; mode Ask first.
2. In Demo mode, click **Start hidden challenge**.
3. When a card appears in the Approval queue, watch it for 10 s.

## Expected result
The countdown "Expires in N s unless approved or rejected" decreases every refresh from at most 120 and the bar shrinks
(`dashboard/views.py:236-256`, `dashboard/labels.py:110`, at `65dd9fe`).

## Actual result
(fictional) The text stayed at "Expires in 120 s unless approved or rejected" for 10 s; the bar did not shrink.

## Evidence
- Screenshots: `docs/team-qa/screenshots/MC-D-03.png` (fictional; no such file exists)
- Exact messages: "Expires in 120 s unless approved or rejected"
- Other: incident id not recorded (fictional)

## Workaround
(fictional) Refreshing the browser page made the countdown move again.
