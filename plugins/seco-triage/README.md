# SECO Triage Skill

Grader-based ticket quality assessment for CloudBees SECO and BEE tickets. Scores tickets against 25+ deterministic graders across 4 categories (template completeness, evidence quality, routing readiness, classification clarity) and provides actionable feedback.

## Prerequisites

1. **Jira API access** - You need to query CloudBees Jira via the REST API. The skill expects `JIRA_USERNAME` and `JIRA_API_TOKEN` environment variables.

2. **GitHub API access** - You need authenticated access to `cloudbees/cloudbees-claude-plugins` for learning PRs and install tracking. The skill uses the `gh` CLI.

3. **Python 3** - The scorer runs as a Python script. No pip dependencies needed (stdlib only).

4. **Atlassian MCP server** (optional) - If configured, the skill can fall back to MCP for ticket fetching and can post assessment comments directly to Jira tickets. Not required for basic scoring.

## Installation

The plugin is distributed via the CloudBees shared marketplace. All org members have access.

### 1. Add the marketplace (if not already added)

Most CloudBees engineers already have this. If not:

```
/plugin marketplace add cloudbees/cloudbees-claude-plugins
```

If you already have the marketplace, update it to pick up the new plugin:

```
/plugin marketplace update cloudbees-marketplace
```

### 2. Install the plugin

```
/plugin install seco-triage@cloudbees-marketplace
/reload-plugins
```

### Upgrading from a previous install

If you had an older version installed (e.g., from `mikecirioli-cloudbees-plugins` or `cloudbees-dev-marketplace`), uninstall it first:

```
/plugin uninstall seco-triage@mikecirioli-cloudbees-plugins
/reload-plugins
```

Then follow the install steps above.

### Updating

The skill checks for updates automatically when you invoke any triage command. If a newer version is available, it tells you how to update. You can also enable auto-updates for the marketplace so updates happen at session start without manual intervention:

```
/plugin
# Select "Marketplaces" > "cloudbees-marketplace" > "Enable auto-update"
```

## Usage

```
/seco-triage:triage SECO-5311
/seco-triage:triage BEE-70598
```

The skill will:
1. Fetch the ticket from Jira (REST API)
2. Run the scorer (25+ deterministic graders)
3. Present a verdict with actionable feedback
4. Offer to post the assessment as a Jira comment
5. Ask for your feedback on the score accuracy

### Insights

```
/seco-triage:triage-insights
/seco-triage:triage-insights --include-testbed
```

Shows usage stats, verdict distributions, grader fire rates, learning PR activity, and data-driven recommendations. All data comes from the scoring log and git history - no manual tracking needed. Testbed records are excluded by default.

### Support

```
/seco-triage:triage-support
```

Something not working? This collects context from your session (scorer output, errors, environment), scrubs it for PII, shows you exactly what will be filed, and creates a GitHub issue after you approve. Nothing gets sent without your explicit OK.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| **BLOCK** | Critical information missing - can't triage |
| **NEEDS_WORK** | Significant gaps that will slow triage |
| **FAIR** | Enough to start, but likely to bounce |
| **GOOD** | Well-structured, minor improvements possible |
| **EXCELLENT** | Ready for engineering |

## Scoring Categories

- **Template completeness** (3.5 pts) - SECO template sections filled, product/version present
- **Evidence quality** (2.5 pts) - Logs, error messages, repro steps, metrics
- **Routing readiness** (2.5 pts) - Component assigned, summary quality, Zendesk linked
- **Classification clarity** (1.5 pts) - Issue type clear, impact stated, ask specific

## Feedback

After each assessment, the skill asks if the score looks right. Corrections generate learning PRs with the proposed fix and feedback data. Scoring records (including acceptance status) are posted to the central scoring log ([#96](https://github.com/cloudbees/cloudbees-claude-plugins/issues/96)). No ticket content is ever captured - only grader names, correction types, and scores.

### What gets captured (safe to share)
- Ticket key, type, resolution
- Grader results (which fired, which didn't)
- Score and verdict
- Your corrections (grader name + correction type)

### What never gets captured
- Ticket descriptions or summaries
- Customer names or identifiers
- Log content, URLs, email addresses

## Patterns

This skill uses several patterns that are reusable for any self-improving evaluation tool built as a Claude Code plugin.

### Deterministic scorer + LLM interpretation

The scorer (`scorer.py`) runs 25+ deterministic graders against structured ticket data and produces a score, verdict, and list of fired signals. Claude then interprets the results, analyzes logs and attachments, and writes the human-readable assessment. This 2-pass architecture (deterministic scoring then focused LLM interpretation) prevents drift, makes the system auditable, and gives Claude specific things to focus on rather than evaluating from scratch every time.

### Self-learning via correction PRs

When a user corrects a signal (false positive, false negative, severity wrong), the skill maps the correction to a specific file change (signal definition, weight, component mapping) and opens a GitHub PR. One file per PR, minimal diff, clear reasoning. Corrections accumulate as reviewable, mergeable rule changes - the skill gets smarter through normal code review.

### Commit-hash versioning

No VERSION files. Claude Code tracks installed plugins by git commit SHA in `~/.claude/plugins/installed_plugins.json`. The plugin's update check hook compares the installed SHA against the remote branch HEAD via `gh api`. Any push to the branch is a new "version" - no manual bumping, no enforcement hooks, no drift between code changes and version numbers.

### Plugin-shipped hooks

Both operational hooks ship with the plugin itself (in `hooks/hooks.json`), so every user who installs the plugin gets them automatically:

- **Update check** (PostToolUse, matcher: Skill) - Fires when triage commands are invoked. Compares installed commit SHA vs remote HEAD. Debounced to once per hour. Notifies user if an update is available.
- **Install tracking** (SessionStart) - Anonymous usage tracking. Hashes the user's email (sha256, first 12 chars) and creates a unique file in `.analytics/installs/` via the GitHub API. One file per version per user, no PII stored. Fires once per install/update (marker file in `CLAUDE_PLUGIN_DATA` prevents duplicates).

### Privacy by design

Privacy rules are enforced at every layer:
- SKILL.md includes a mandatory privacy section Claude reads before every run
- Feedback capture records only grader names and correction types, never ticket content
- Learning PRs contain the rule change and reasoning, never ticket data
- Install tracking uses hashed identifiers, no usernames or emails

### Scoring log as single source of truth

Every triage run posts a JSON record as a comment on the central tracking issue ([#96](https://github.com/cloudbees/cloudbees-claude-plugins/issues/96)) - the commit SHA, ticket key, verdict, fired graders, user hash, and whether the user accepted the result. This log feeds `/triage-insights` (aggregate metrics), the learning loop (correction patterns), and accuracy tracking. No separate database, no external analytics - issue comments as an append-only log accessible to all team members. A local `triage-log.jsonl` serves as a fallback when `gh` is unavailable.

## Directory Structure

```
plugins/seco-triage/
  README.md                     # This file
  triage-log.jsonl              # Scoring records (auto-pushed)
  hooks/
    hooks.json                  # SessionStart + PostToolUse hooks
  scripts/
    check-update.sh             # Version check (compares SHA vs remote)
    track-install.sh            # Anonymous install tracking
  commands/
    triage.md                   # /triage command entry point
    triage-insights.md          # /triage-insights command entry point
    triage-support.md           # /triage-support command entry point
  skills/
    triage/                     # Orchestrator - score, feedback, learn
      SKILL.md
      scorer.py                 # Grader-based scoring engine (Python)
      knowledge/
        scorer/
          graders.json          # 25+ grader definitions
          weights.json          # Category weights and verdict thresholds
          components.json       # Component keyword mappings
          feedback-schema.json  # Feedback capture schema + privacy rules
        prompt/
          feedback-rubric.md    # Output formatting rules
          template-ref.md       # SECO template reference
          exemplars.md          # Calibration examples
    insights/                   # Usage stats and learning loop health
      SKILL.md
    support/                    # Bug reporting with PII scrubbing
      SKILL.md
```
