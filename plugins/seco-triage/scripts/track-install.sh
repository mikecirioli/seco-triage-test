#!/bin/bash
# Track unique installs/updates for seco-triage plugin
# Fires once per commit SHA per user (via SessionStart hook)
# Adds a comment to the tracking issue - no signed commits needed

set -euo pipefail

TRACKING_REPO="cloudbees/cloudbees-claude-plugins"
TRACKING_ISSUE="93"

# Get current commit SHA from plugin cache path
COMMIT_SHA="${CLAUDE_PLUGIN_COMMIT_SHA:-unknown}"
if [ "$COMMIT_SHA" = "unknown" ]; then
  COMMIT_SHA=$(basename "${CLAUDE_PLUGIN_ROOT:-unknown}" | cut -c1-12)
fi
SHORT_SHA="${COMMIT_SHA:0:12}"

# Hash the user identity (email -> sha256 -> first 12 chars)
USER_HASH=$(git config user.email 2>/dev/null | sha256sum 2>/dev/null | cut -c1-12)
if [ -z "$USER_HASH" ] || [ "$USER_HASH" = "e3b0c44298fc" ]; then
  USER_HASH=$(whoami 2>/dev/null | sha256sum 2>/dev/null | cut -c1-12)
fi

# Marker file: skip if this SHA was already counted for this user
MARKER_DIR="${CLAUDE_PLUGIN_DATA:-.}/.install-markers"
MARKER_FILE="$MARKER_DIR/${SHORT_SHA}-${USER_HASH}"
if [ -f "$MARKER_FILE" ]; then
  exit 0
fi

# Check gh is available and authenticated
if ! command -v gh &>/dev/null; then
  exit 0
fi
if ! gh auth status &>/dev/null 2>&1; then
  exit 0
fi

# Post comment to tracking issue
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
BODY="install | ${TIMESTAMP} | commit:${SHORT_SHA} | user:${USER_HASH}"

if gh issue comment "$TRACKING_ISSUE" \
  --repo "$TRACKING_REPO" \
  --body "$BODY" \
  >/dev/null 2>&1; then
  # Success - create marker so we don't count again
  mkdir -p "$MARKER_DIR"
  echo "$TIMESTAMP" > "$MARKER_FILE"
fi
