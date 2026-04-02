---
name: triage-insights
description: Show triage usage stats, verdict distributions, grader fire rates, and learning PR activity from the scoring log and git history.
---

# Triage Insights

Show how the triage skill is being used, what it's finding, and whether the learning loop is working. All data comes from the scoring log and git history - no manual tracking needed.

## Audience and Tone

This report is for **anyone** - not just the person who built the skill. A DSE, a manager, or a curious teammate should be able to read it and immediately understand:
- Is the tool being used?
- Is it accurate?
- Is it getting smarter over time?

**Rules**:
- Lead with plain English, not grader names. Say "85% of tickets are missing logs" not "logs_present fires at 85%".
- Use grader names only in parentheses for traceability, e.g., "Missing logs (logs_present) - 85%"
- Avoid jargon. "Learning PRs" should be explained as "corrections that became code changes".
- Every number should have context. "12 runs" means nothing. "12 tickets triaged this week (up from 4 last week)" tells a story.
- Keep the whole report scannable in under 60 seconds.

## Data Sources

### Primary: Central scoring log (GitHub issue comments)

All triage runs from all users are posted as comments on the central tracking issue:

```bash
gh api repos/cloudbees/cloudbees-claude-plugins/issues/96/comments \
  --paginate --jq '.[].body' 2>/dev/null
```

Each comment is a single JSON record:
```json
{"ticket": "SECO-5323", "timestamp": "...", "commit": "a72edbb", "score": 9.0, "verdict": "EXCELLENT", "graders_fired": ["component_assigned"], "category_scores": {...}, "verdict_accepted": true, "corrections": [], "source": "live", "user": "465470447c12"}
```

Parse each comment body as JSON. Skip any comments that aren't valid JSON (e.g., discussion comments).

If no comments exist or `gh` is unavailable, fall back to the local JSONL file.

### Fallback: triage-log.jsonl

Location: `{PLUGIN_ROOT}/triage-log.jsonl`

Where `{PLUGIN_ROOT}` is the root of the `seco-triage` plugin directory (two levels above `{SKILL_DIR}`). Discover it dynamically:

```bash
PLUGIN_ROOT=$(cd "{SKILL_DIR}/../.." && pwd)
LOG_FILE="$PLUGIN_ROOT/triage-log.jsonl"
```

This file contains local-only records. The central log (issue #96) is the primary source for cross-user insights.

If both sources are empty:
> No triage records found yet. Run `/triage SECO-XXXX` to start collecting data.

### Secondary: git history

From the plugin repo:
- **Triage commits**: `git -C "$PLUGIN_ROOT" log --oneline --grep="triage:"`
- **Learning PRs**: `gh pr list --repo cloudbees/cloudbees-claude-plugins --state all --json number,title,state,author,createdAt,mergedAt`
- **Contributors**: unique authors from triage commits

## Filtering

Records may have a `source` field:
- `"source": "testbed"` - seeded from testbed validation runs
- `"source": "live"` or absent - real user triage sessions

**Default behavior**: exclude testbed records. Show a note: "Excluding {N} testbed records. Use `--include-testbed` to include them."

If the user says `--include-testbed` or "include testbed" or "show everything", include all records.

## Report Sections

### 1. At a Glance

A 3-line summary anyone can understand:

```
Triage Insights - {date}
{N} tickets assessed ({date range}) by {N} people
Average quality: {avg score}/10 ({verdict}) - {trend if enough data}
```

If there's enough data for a trend (2+ weeks): "Improving", "Steady", or "Declining" based on week-over-week average score.

### 2. Who's Using It

- Total tickets assessed
- This week vs last week (if data exists)
- People using the tool (from git author on triage commits)

Derive unique user count from the `user` field (hashed email) in the central log records. Count distinct hashes. If central log is unavailable, fall back to git log:
```bash
git -C "$PLUGIN_ROOT" log --oneline --grep="triage:" --format="%an" | sort | uniq -c | sort -rn
```

### 3. What It's Finding

Show the verdict breakdown with plain labels:

```
Ready for engineering:      N (XX%)  ========
Good, minor suggestions:    N (XX%)  ======
Passable, gaps likely:      N (XX%)  ====
Needs significant work:     N (XX%)  ==
Missing critical info:      N (XX%)  =
```

Use simple ASCII bars.

### 4. Most Common Gaps

Top issues found across all tickets, in plain English with grader name in parentheses for reference:

```
Missing logs or evidence          (logs_present)       85%
No Zendesk ticket linked          (zendesk_linked)     72%
Product version not specified     (environment_version) 68%
No component assigned             (component_assigned)  55%
...
```

Frame these as "these are the most common reasons tickets get flagged." Show top 8-10.

Also note graders that never fired: "These checks have never triggered - they may need tuning or removal: {list}"

### 5. Where Tickets Lose Points

Average score per quality area, expressed as a percentage of max:

```
Template sections filled:    86% (3.0 / 3.5)
Evidence and logs:           71% (1.8 / 2.5)  <-- biggest gap
Routing info:                60% (1.2 / 2.0)
Classification clarity:      93% (1.4 / 1.5)
```

Call out the weakest area: "Biggest quality gap: evidence and logs. Most tickets are missing error messages, reproduction steps, or supporting data."

### 6. Is It Getting Smarter?

Track whether the learning loop is working:

- **Corrections submitted**: N out of M runs (X%) - "Users corrected the score {N} times"
- **Corrections that became code changes**: N opened, N merged, N pending review
- **Accuracy trend**: X% of scores accepted as-is - "The tool agreed with the human {X}% of the time"
- **Most-corrected check**: "{grader description}" ({N} corrections) - "This is the check we're still calibrating"

If no corrections exist yet:
> No corrections submitted yet. When users flag a score as wrong, the tool proposes a fix as a code change for review.

### 7. By Ticket Type

If both SECO and BEE tickets are present:
- SECO tickets: N assessed, avg score X.X/10
- BEE tickets: N assessed, avg score X.X/10

### 8. What Should We Do Next

Based on the data, suggest 2-3 concrete actions. Examples:

- "85% of tickets are missing logs. This is either a real systemic gap in how tickets are filed, or the check is too strict. Worth investigating."
- "The '{grader description}' check has never triggered. It might be dead weight - consider removing or rewriting it."
- "Only {X}% of scores were accepted without corrections. The scorer might be miscalibrated on {most-corrected grader}."
- "{X}% of tickets scored the same verdict. The score thresholds may need adjustment."

Only include recommendations where the data actually supports them. Don't pad with generic advice.

## Formatting

- Use markdown throughout
- ASCII bar charts for distributions (no unicode blocks - keep it terminal-friendly)
- Bold section headers
- Include raw numbers AND percentages
- If sample size < 10, add caveat: "Note: {N} records - trends may not be reliable yet."
- Keep total output under 600 words unless user asks for detail

## Error Handling

- **No log file**: Show the "no records" message, but still check git for learning PRs (those exist independently).
- **No git access**: Produce report from JSONL only, note that git-derived stats (users, learning PRs) are unavailable.
- **No gh CLI**: Skip learning PR section, note it's unavailable.
- **Mixed scorer versions**: Show stats per version if significantly different, otherwise aggregate.
