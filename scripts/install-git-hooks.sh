#!/bin/sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

git config core.hooksPath .githooks

chmod +x .githooks/pre-push
chmod +x .githooks/pre-commit
chmod +x .githooks/commit-msg
chmod +x scripts/quality-gate.sh
chmod +x scripts/install-git-hooks.sh

echo "Git hooks enabled: .githooks"
