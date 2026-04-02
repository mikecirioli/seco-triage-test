---
name: triage-support
description: File a bug report for the triage skill. Collects session context, scrubs PII, shows you exactly what will be sent, and creates a GitHub issue.
---

# Triage Support

Help users file useful bug reports when the triage skill misbehaves. Collect the right context automatically, scrub it for privacy, and create a GitHub issue - but always show the user what's being sent before sending it.

## Principles

1. **Transparent**: Narrate every step. The user should never wonder what you're doing.
2. **Privacy-first**: Scrub before showing, scrub again before filing. When in doubt, redact.
3. **Low-effort**: The user already hit a problem. Don't make them do homework to report it.
4. **Useful**: The issue should contain enough for the maintainer to reproduce or diagnose without a back-and-forth.

## Step 1: Acknowledge and Explain

Tell the user what's about to happen:

> I'll collect some context from this session to file a bug report. Here's the process:
> 1. I'll gather technical details (skill version, scorer output, error messages)
> 2. I'll scrub anything that could identify customers or internal systems
> 3. I'll show you **exactly** what the issue will contain - nothing gets filed until you approve
> 4. Once you approve, I'll create a GitHub issue
>
> You can cancel at any point.

## Step 2: Collect Context

Gather these from the current conversation and environment. **Do not read files outside the plugin directory** - only use what's already in the conversation context and what the environment provides.

### Environment info (always collect)

```bash
echo "=== Environment ==="
echo "Python: $(python3 --version 2>&1)"
echo "gh: $(gh --version 2>&1 | head -1)"
PLUGIN_ROOT=$(cd "{SKILL_DIR}/../.." && pwd)
echo "Skill version: $(cat "$PLUGIN_ROOT/VERSION" 2>/dev/null || echo 'unknown')"
echo "Scorer version: $(python3 -c "import json; print(json.load(open('$PLUGIN_ROOT/skills/triage/knowledge/scorer/graders.json'))['_version'])" 2>/dev/null || echo 'unknown')"
echo "OS: $(uname -s -r)"
echo "Date: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### From the conversation (extract if present)

- **Ticket key** being triaged (e.g., SECO-5311) - just the key, never the content
- **Scorer JSON output** - the structured result from scorer.py (scores, graders, verdict)
- **Error messages** - any Python tracebacks, command failures, or unexpected output
- **What the user expected** vs what happened - from the user's description
- **Steps that led to the problem** - which step in the triage flow broke

### What the user was trying to do

Ask the user one question:

> What were you trying to do, and what went wrong?

If the user already described the problem in conversation, don't ask again - extract it from what they said.

## Step 3: Scrub for Privacy

Apply these rules to ALL collected text before showing or filing:

### MUST redact (replace with placeholder)

| Pattern | Replacement |
|---------|-------------|
| Customer names | `[CUSTOMER]` |
| Email addresses | `[EMAIL]` |
| Zendesk ticket IDs or URLs | `[ZENDESK]` |
| Salesforce IDs or URLs | `[SALESFORCE]` |
| Internal hostnames (*.cloudbees.com, *.beescloud.com) | `[INTERNAL_HOST]` |
| IP addresses | `[IP_ADDRESS]` |
| API tokens, passwords, credentials | `[CREDENTIAL]` |
| License keys | `[LICENSE_KEY]` |
| Account IDs | `[ACCOUNT_ID]` |
| Jira ticket description/summary text | `[TICKET_CONTENT]` |
| Log snippets from customer systems | `[CUSTOMER_LOG]` |
| Attachment filenames | `[ATTACHMENT]` |
| Jenkins/Confluence/internal tool URLs | `[INTERNAL_URL]` |

### Safe to include

- Ticket keys (SECO-XXXX, BEE-XXXXX)
- Signal names and fired/not-fired status
- Scores, verdicts, category scores
- Error messages from the scorer itself (Python tracebacks from scorer.py)
- Skill/scorer version numbers
- Command invocations (what the user typed)
- Generic descriptions of the problem

### How to scrub

1. Scan every field in the collected data against the patterns above
2. For scorer JSON output: keep grader results, scores, verdict, version. Remove any field that could contain ticket text (summary, description, customer-provided text).
3. For error messages: keep the traceback structure but redact any file paths outside the plugin directory and any interpolated ticket content.
4. When uncertain whether something is PII: redact it. False redactions are annoying but safe. Missed PII is a trust violation.

## Step 4: Show the User

Present the complete issue body in a fenced code block:

> Here's what I'd file as a GitHub issue. **Review this carefully** - make sure nothing sensitive slipped through. I can edit anything before filing.

```markdown
{the full issue body}
```

Then ask:

> Does this look right? I can:
> - **File it** as-is
> - **Edit** anything you want changed
> - **Cancel** if you'd rather handle it differently

**Do not proceed until the user explicitly approves.**

## Step 5: Create the Issue

File as a markdown document in the plugin's `.issues/` directory. This keeps bug reports co-located with the code in the PR branch - no external repo access needed.

```bash
PLUGIN_ROOT=$(cd "{SKILL_DIR}/../.." && pwd)
ISSUES_DIR="$PLUGIN_ROOT/.issues"
mkdir -p "$ISSUES_DIR"

TIMESTAMP=$(date -u +%Y%m%dT%H%M%SZ)
SLUG=$(echo "{title}" | tr '[:upper:]' '[:lower:]' | sed 's/[^a-z0-9]/-/g' | sed 's/--*/-/g' | head -c 60)
FILENAME="${TIMESTAMP}-${SLUG}.md"

cat > "$ISSUES_DIR/$FILENAME" << 'EOF'
{issue body}
EOF
```

Then commit and push to the PR branch:

```bash
REPO_ROOT=$(cd "$PLUGIN_ROOT/../.." && pwd)
git -C "$REPO_ROOT" add "$ISSUES_DIR/$FILENAME"
git -C "$REPO_ROOT" commit -m "bug: {title}"
git -C "$REPO_ROOT" push origin feat/seco-triage-skill
```

### Issue format

```markdown
# {title}

**Status**: open
**Filed**: {ISO 8601 timestamp}
**Reporter**: {from git config user.name}

## What happened

{user's description of the problem}

## Expected behavior

{what should have happened}

## Context

- **Ticket**: {key, e.g., SECO-5311}
- **Skill version**: {version}
- **Scorer version**: {version}
- **Step**: {which triage step failed, if known}

## Scorer Output

{scrubbed scorer JSON, or "scorer did not run" if it didn't get that far}

## Error Details

{scrubbed error messages, tracebacks, or unexpected output}

## Environment

- Python: {version}
- gh: {version}
- OS: {os}

## How to Reproduce

1. Run `/triage {TICKET_KEY}`
2. {additional steps if known}

---
*Filed automatically by `/triage-support`. All customer data has been scrubbed.*
```

### Title format

Keep it specific and grep-able:

- `scorer: false positive on {grader_name} for {ticket_type}`
- `step {N}: {brief description of failure}`
- `install: {brief description}`
- `{general}: {brief description}`

## Step 6: Confirm

After filing, show the file path and commit:

> Filed: `{FILENAME}` in `.issues/`
>
> This has been committed and pushed to the PR branch. The maintainer will see it on the next review.

## Error Handling

- **No push access**: Write the file locally and tell the user: "Issue saved to `.issues/{FILENAME}` but could not push. Run `git push origin feat/seco-triage-skill` when ready."
- **No git repo**: Output the issue body as markdown so the user can save it manually.
- **No triage context in conversation**: Still allow filing. The user might have hit a problem before triage even started (install issue, auth failure, etc.). Collect what you can.
- **User cancels**: Acknowledge and discard. Don't save drafts.
