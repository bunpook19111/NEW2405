#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/github_quick_start.sh YOUR_GITHUB_USERNAME inburi-flood-watch-ai

USER_NAME="${1:-}"
REPO_NAME="${2:-inburi-flood-watch-ai}"

if [[ -z "$USER_NAME" ]]; then
  echo "Usage: $0 YOUR_GITHUB_USERNAME [REPO_NAME]"
  exit 1
fi

git init
git add .
git commit -m "Initial Inburi flood watch AI system"
git branch -M main
git remote add origin "https://github.com/${USER_NAME}/${REPO_NAME}.git"
git push -u origin main

echo "Done. Add GitHub Secret MAKE_WEBHOOK_URL and set Variable DRY_RUN=false when ready."
