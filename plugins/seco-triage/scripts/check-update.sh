#!/bin/bash
# Check for seco-triage plugin updates before skill execution
# Fires on PostToolUse for Skill tool, filters to triage sub-skills
# Compares installed commit SHA vs remote HEAD via GitHub API

# Only run for triage sub-skills
if ! echo "$CLAUDE_TOOL_ARGS" | grep -qE '^(triage|triage-insights|triage-support|triage-installs)'; then
  exit 0
fi

# Debounce: check at most once per hour
CACHE_FILE="/tmp/triage-update-check-cache"
if [ -f "$CACHE_FILE" ]; then
  LAST_CHECK=$(cat "$CACHE_FILE" 2>/dev/null || echo 0)
  NOW=$(date +%s)
  if [ $((NOW - LAST_CHECK)) -lt 300 ]; then
    exit 0
  fi
fi
date +%s > "$CACHE_FILE"

# Find installed commit SHA from Claude's metadata
INSTALLED_SHA=$(python3 -c "
import json, sys, os
path = os.path.expanduser('~/.claude/plugins/installed_plugins.json')
with open(path) as f:
    data = json.load(f)
for key, entries in data.get('plugins', {}).items():
    if 'seco-triage' in key and 'dev' not in key:
        print(entries[0].get('gitCommitSha', ''))
        break
" 2>/dev/null)

if [ -z "$INSTALLED_SHA" ]; then
  exit 0
fi

# Check remote HEAD via GitHub API
if ! command -v gh &>/dev/null; then
  exit 0
fi

REMOTE_SHA=$(gh api repos/cloudbees/cloudbees-claude-plugins/git/ref/heads/feat/seco-triage-skill --jq '.object.sha' 2>/dev/null)

if [ -z "$REMOTE_SHA" ]; then
  exit 0
fi

if [ "$REMOTE_SHA" != "$INSTALLED_SHA" ]; then
  echo "seco-triage update available"
  echo "   Current: ${INSTALLED_SHA:0:7}"
  echo "   Latest:  ${REMOTE_SHA:0:7}"
  echo ""
  echo "   Update: /plugin marketplace update cloudbees-marketplace"
  echo "   Then:   /reload-plugins"
fi
