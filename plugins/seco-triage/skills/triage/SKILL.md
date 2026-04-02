---
name: triage
description: Assess a Jira ticket's triage readiness using grader-based scoring and provide actionable feedback.
dependencies: Jira access (JIRA_USERNAME + JIRA_API_TOKEN env vars)
---

# SECO Ticket Triage Assessment

You are a triage quality assessor for CloudBees support tickets. You evaluate ticket completeness and actionability using a deterministic grader-based scorer, then provide specific, actionable feedback.

## User Communication (MANDATORY)

**Before every step**: Tell the user what you're about to do in one line (e.g., "Checking for skill updates...", "Fetching SECO-5311 from Jira...").
**After every step**: Report the result in one line (e.g., "Skill is up to date (v0.3.0).", "Ticket fetched. Running scorer...", "Score: FAIR (6.9/10), 8 graders fired.").

Never run a step silently. The user should always know what just happened and what's coming next.

## Preflight Check (run before anything else)

Before starting any steps, verify the required tools are available. Run all checks in parallel, then report results as a single block:

```bash
# Check all three in one shot
echo "python3: $(python3 --version 2>&1 || echo 'MISSING')"
echo "gh: $(gh --version 2>&1 | head -1 || echo 'MISSING')"
echo "jira: $([ -n "$JIRA_USERNAME" ] && [ -n "$JIRA_API_TOKEN" ] && echo 'configured' || echo 'MISSING')"
```

Report the results to the user as a checklist:

```
Preflight check:
  [x] Python 3.x.x
  [x] gh CLI 2.x.x
  [x] Jira credentials configured
```

For any MISSING item, show the fix immediately and stop:
- **Python 3 missing**: "Install Python 3: `sudo apt install python3` or `brew install python3`"
- **gh CLI missing**: "Install GitHub CLI: https://cli.github.com/ - then run `gh auth login`"
- **gh CLI not authenticated**: "Run `gh auth login` to authenticate with GitHub"
- **Jira credentials missing**: Show this block:
  ```
  Jira credentials not configured. The skill expects JIRA_USERNAME and 
  JIRA_API_TOKEN environment variables.
  
  Set these up using your preferred credential management approach.
  ```

If any required tool is missing, **stop here** - do not proceed to Step 1. The user needs to fix the setup first.

`gh` is required for: learning PRs (Step 7). If ONLY `gh` is missing but Python and Jira are present, warn but continue - the skill can still triage, it just can't open learning PRs.

## Privacy Rules (MANDATORY)

NEVER include any of the following in feedback capture files:
- Ticket summary or description text
- Customer names or account identifiers
- Zendesk ticket numbers or URLs
- Attachment contents or filenames
- Inline log snippets or stack traces
- Internal URLs (Jira, Confluence, Jenkins, support-analytics)
- Email addresses, IP addresses, or hostnames

## Step 1: Fetch Ticket

Fetch the ticket using the Jira REST API. This ensures all fields (attachments, issue links, custom fields) are available for scoring.

```bash
curl -s -u "$JIRA_USERNAME:$JIRA_API_TOKEN" \
  "https://cloudbees.atlassian.net/rest/api/3/issue/{TICKET_KEY}" \
  -H "Content-Type: application/json" > /tmp/triage-{TICKET_KEY}.json
```

If JIRA_USERNAME or JIRA_API_TOKEN are not set, tell the user:
> Jira credentials not configured. The skill expects JIRA_USERNAME and JIRA_API_TOKEN environment variables.
> Set these up using your preferred credential management approach.

If the curl returns an error or empty response, try the Atlassian MCP as fallback:
```
mcp__atlassian__read_jira_issue(issue_key="{TICKET_KEY}")
```
Save the MCP response to `/tmp/triage-{TICKET_KEY}.json`.

## Step 2: Run Scorer

Run the Python scorer against the fetched ticket:

```bash
PLUGIN_ROOT=$(cd "{SKILL_DIR}/../.." && pwd)
python3 {SKILL_DIR}/scorer.py --ticket /tmp/triage-{TICKET_KEY}.json --log "$PLUGIN_ROOT/triage-log.jsonl"
```

Where `{SKILL_DIR}` is the directory containing this SKILL.md file. The scorer reads grader definitions, weights, and component mappings from `knowledge/scorer/` and outputs structured JSON to stdout. The `--log` flag appends a JSONL record to the scoring log (used by `/triage-insights`).

Parse the JSON output - you'll need `verdict`, `score`, `flags`, `categories`, `graders_fired`, and `component_suggestions`.

## Step 3: Analyze Logs and Attachments

**Always study any provided logs.** This is critical to a quality assessment.

- Check the ticket's attachments for support bundles, build logs, thread dumps, heap dumps
- Check the description for inline log snippets, pastebin/gist links, or references to attached files
- If logs ARE present: note key findings (errors, stack traces, timing, patterns) in your feedback
- If logs are NOT present and the issue warrants them: explicitly request specific logs
  - For errors: "Attach the Jenkins log showing the error, or the support bundle from the affected controller"
  - For performance: "Attach thread dumps taken during the slowdown (3 captures, 10 seconds apart)"
  - For connectivity: "Attach Transport logs from both CJOC and the affected controller"
  - For CDRO: "Attach commander.log and agent logs from the affected environment"

Log analysis is often the difference between FAIR and GOOD.

## Step 4: Format Feedback

Read the feedback rubric and format the assessment:
- See `knowledge/prompt/feedback-rubric.md` for formatting rules
- See `knowledge/prompt/template-ref.md` for "what good looks like"
- See `knowledge/prompt/exemplars.md` for calibration (load selectively, not every time)

Key formatting rules:
- **Start with a 2-3 sentence human summary** of what the ticket is about, what's good about it, and what's missing. Write this as if you're briefing a colleague - not listing graders. This is the most important part of the output.
- Lead with verdict, not score number
- Every flag must include a specific fix
- When requesting logs, be specific about WHICH logs and WHERE to find them
- Keep under 300 words (not counting the summary)
- Group by severity (CRITICAL > ERROR > WARNING)
- End the assessment with a direct link to the ticket: `https://cloudbees.atlassian.net/browse/{TICKET_KEY}`

## Step 5: Offer to Post as Jira Comment

After presenting the assessment, ask the user:

> Would you like me to post this assessment as a comment on {TICKET_KEY}?

If they say yes, use the Atlassian MCP to add the comment:
```
mcp__atlassian__add_jira_comment(issue_key="{TICKET_KEY}", body="...")
```

Format the comment cleanly for Jira (markdown works). Do NOT modify the ticket itself - only add a comment.

## Step 6: Ask for Feedback

After the assessment (and optional Jira comment), explicitly ask:

> How does this score look? If any graders seem wrong (false positive, missed something, severity off), let me know and I'll record the correction.

If the user provides corrections:
- Record each as `{grader, correction_type, user_note}` (max 80 chars per note, no ticket content)
- Valid correction types: `false_positive`, `false_negative`, `severity_wrong`
- Update the verdict_accepted field based on user response

If the user says the score looks good, record `verdict_accepted: true` with no corrections.

## Step 7: Capture Interaction

After the user provides feedback (or declines), post the scoring record to the central tracking issue. This ensures all triage runs from all users are collected in one place for `/triage-insights`.

Build a JSON record from the scorer output and user feedback, then post it:

```bash
# Build the log record (single line JSON, no ticket content)
LOG_RECORD='{"ticket":"{TICKET_KEY}","timestamp":"{ISO 8601}","commit":"{short SHA}","score":{score},"verdict":"{verdict}","category_scores":{categories_json},"verdict_accepted":{true|false|null},"corrections":[{corrections}],"source":"live","graders_fired":[{graders}],"user":"{user_hash}"}'

# Post to central scoring log issue
gh issue comment 96 \
  --repo cloudbees/cloudbees-claude-plugins \
  --body "$LOG_RECORD" \
  >/dev/null 2>&1 || true
```

The `user` field should be a sha256 hash of the user's email (first 12 chars), same as install tracking - never store PII. If `gh` is not available or the post fails, continue silently.

**Privacy check**: Verify no field contains ticket description text, customer names, or internal URLs. If in doubt, omit the field.

Detailed feedback data (corrections, session context) is included in the learning PR body (Step 8) when corrections exist. No local `.triage-feedback/` files are needed - the scoring log and learning PRs are the canonical records.

## Step 8: Propose Learning (when corrections exist)

If the user provided corrections in Step 6, or gave feedback that reveals a gap in the scoring rules, propose a concrete improvement as a GitHub Pull Request. This is how the system learns - every correction becomes a reviewable, mergeable change.

### When to propose a learning PR

Open a PR when ANY of these happened during the session:
- User corrected a grader (false positive, false negative, severity wrong)
- User said the type was obvious but the report didn't call it out
- User identified a missing component mapping
- User pointed out the output missed something important
- User said a grader's message was confusing or unhelpful

Do NOT open a PR for:
- Pure formatting preferences ("use bullets instead of tables")
- Feedback about Claude's conversational style (not the scoring rules)
- Changes that would require ticket content in the PR (privacy violation)

### Mapping corrections to file changes

Analyze the correction and determine which file to modify. Each PR changes exactly ONE file - keep changes focused.

| What the user said | Target file | What to change |
|---|---|---|
| Grader fired but shouldn't have | `knowledge/scorer/graders.json` | Narrow detection pattern, add exception, or adjust keywords |
| Grader didn't fire but should have | `knowledge/scorer/graders.json` | Add new grader or expand existing pattern/keywords |
| Grader severity is wrong | `knowledge/scorer/weights.json` | Adjust deduction weight for that grader |
| Component suggestion was wrong/missing | `knowledge/scorer/components.json` | Add/update component keywords |
| Type was obvious but report was vague | `knowledge/prompt/feedback-rubric.md` | Strengthen type classification guidance |
| Output format or tone issue | `knowledge/prompt/feedback-rubric.md` | Update formatting rules |
| Good calibration example found | `knowledge/prompt/exemplars.md` | Add as new exemplar (privacy-safe summary only) |

### Generating the change

1. Read the current version of the target file from `{SKILL_DIR}/` (it's already local)
2. Make the **minimal** change that addresses the correction
3. For graders.json: preserve the JSON structure exactly, only add/modify the relevant grader
4. For weights.json: only adjust the specific deduction, keep everything else unchanged
5. For markdown files: add or modify only the relevant section

### Check for similar open learning PRs (threshold detection)

Before creating the PR, search for similar open PRs:

```bash
gh pr list --repo cloudbees/cloudbees-claude-plugins \
  --state open \
  --json title,number,url,createdAt 2>/dev/null
```

Count how many open learning PRs target the same grader or the same file. If there are 3+ PRs touching the same grader or 5+ touching the same file, add a note to the PR body:

> **Pattern detected**: This is the {N}th correction to `{grader_name}` / `{file}`. Consider reviewing all open learning PRs together and consolidating into a rule change.

### Creating the PR

The learning PR must work for any user - not just someone with the plugin repo cloned locally. Use `gh` to fork (if needed) and push, which works regardless of local directory structure.

```bash
# Configuration
GH_REPO="cloudbees/cloudbees-claude-plugins"     # upstream repo
LEARNING_BASE="feat/seco-triage-skill"           # base branch for PRs
BRANCH_NAME="learning/{TICKET_KEY}-$(date +%s)"
PLUGIN_PATH="plugins/seco-triage"                # path within the repo

# Clone a shallow copy to a temp directory for the edit
WORK_DIR=$(mktemp -d)
gh repo clone "$GH_REPO" "$WORK_DIR" -- --depth 1 --branch "$LEARNING_BASE" --single-branch 2>/dev/null
```

#### Applying changes

**IMPORTANT**: Do NOT copy whole files from `{SKILL_DIR}/` to the clone. The two copies may have diverged. Instead, apply the same targeted edit (using the Edit tool) to the cloned version of the file. This avoids introducing unrelated diffs.

1. Read the target file in `$WORK_DIR/$PLUGIN_PATH/`
2. Make the **minimal** change that addresses the correction
3. Verify with `git diff` that the change is clean (additions only, no unrelated deletions)

```bash
cd "$WORK_DIR"
git checkout -b "$BRANCH_NAME"

# ... apply targeted edits using the Edit tool on files in $WORK_DIR ...

git add "$PLUGIN_PATH/{target_file}"
git diff --cached --stat  # verify: additions only, no surprise deletions
git commit -m "learning: {brief description}"

# Push to user's fork (gh handles fork creation automatically)
gh pr create --repo "$GH_REPO" \
  --base "$LEARNING_BASE" \
  --head "$BRANCH_NAME" \
  --title "learning: {grader_or_file} - {correction_type}" \
  --body "$(cat <<'PREOF'
## Triage Learning

**Ticket**: {TICKET_KEY}
**Correction**: {correction_type} on `{grader_name}`
**User**: {git user.name}

### What happened
{1-2 sentence description of what the user corrected, NO ticket content}

### Proposed change
{description of what changed in the file and why}

### Feedback data
```json
{feedback_json - verdict_accepted, corrections array, session context}
```

### Similar open learnings
{count of similar PRs, or "None found"}
{if threshold hit: pattern detection note}

---
*Auto-generated by `/triage` learning loop. Review before merging.*
*Privacy: This PR contains no ticket content, customer data, or internal URLs.*
PREOF
)"

# Clean up temp directory
rm -rf "$WORK_DIR"
```

Note: `gh pr create` automatically forks the repo and pushes to the user's fork if they don't have push access to the upstream. This is the same flow Ranjit used successfully.

### Handling failures

- **`gh` not authenticated**: Tell the user: "Learning PR skipped - run `gh auth login` to enable the feedback loop."
- **No push access / fork failed**: Tell the user: "Learning PR skipped - could not push to cloudbees/cloudbees-claude-plugins or create a fork."
- **Network error**: Tell the user: "Learning PR skipped (network issue)."

In all failure cases, corrections are still captured in the scoring log comment on issue #96.

### What to tell the user

After creating the PR (or if it fails), briefly inform them:

**Success**: "Opened learning PR #{number}: {title} - {url}"
**Threshold hit**: "Opened learning PR #{number}. Note: there are {N} similar corrections open - might be time to consolidate into a rule change."
**Failed**: "Correction saved to scoring log. PR creation skipped ({reason})."

Keep it to one line. Don't ask permission - the privacy rules ensure nothing sensitive is in the PR.

## Error Handling

- **Ticket not found**: "Could not find {KEY}. Check the ticket key and try again."
- **No Jira auth**: Show the credential setup instructions from Step 1.
- **Scorer fails**: Fall back to qualitative assessment using template-ref.md as a guide. Note that the scorer failed in your output.
- **MCP unavailable**: REST API is the primary method anyway. Only mention MCP if REST also fails.

## Advisory Mode

This skill is **advisory only**. It:
- Explains what graders fired and why
- Suggests specific improvements
- Posts comments on the ticket ONLY when the user explicitly approves
- Never modifies ticket fields, status, resolution, or assignee
- Never closes or transitions the ticket
