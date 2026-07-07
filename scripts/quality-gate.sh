#!/bin/sh
set -eu

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

fail() {
  echo "quality gate failed: $*" >&2
  exit 1
}

need_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    fail "missing command '$1'"
  fi
}

resolve_base_ref() {
  if [ -n "${QUALITY_GATE_BASE_REF:-}" ]; then
    printf '%s\n' "$QUALITY_GATE_BASE_REF"
    return 0
  fi

  upstream="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null || true)"
  if [ -n "$upstream" ]; then
    git merge-base HEAD "$upstream"
    return 0
  fi

  if git rev-parse --verify HEAD~1 >/dev/null 2>&1; then
    git rev-parse HEAD~1
    return 0
  fi

  printf '\n'
}

need_command git
need_command node

base_ref="$(resolve_base_ref)"

if [ -n "$base_ref" ]; then
  changed_files="$(git diff --name-only --diff-filter=ACMR "$base_ref"...HEAD)"
  range_args="--base $base_ref"
else
  changed_files="$(git ls-files)"
  range_args=""
fi

if [ -z "$changed_files" ] && [ "${QUALITY_GATE_SCOPE:-changed}" != "all" ]; then
  echo "Quality gate: no committed changes to check."
  exit 0
fi

echo "Quality gate: diff-to-test mapping"
# shellcheck disable=SC2086
node scripts/diff-to-test-map.cjs $range_args

echo "Quality gate: Agent internal code review"
# shellcheck disable=SC2086
node scripts/agent-code-review.cjs $range_args

run_backend=0
run_frontend=0

if [ "${QUALITY_GATE_SCOPE:-changed}" = "all" ]; then
  run_backend=1
  run_frontend=1
else
  printf '%s\n' "$changed_files" | grep -Eq '^backend/(app|tests|pyproject\.toml)' && run_backend=1 || true
  printf '%s\n' "$changed_files" | grep -Eq '^frontend/(src|e2e|package(-lock)?\.json|vite\.config\.ts|tsconfig.*\.json|playwright\.config\.ts|\.oxlintrc\.json|\.prettierrc\.json)' && run_frontend=1 || true
fi

if [ "$run_backend" -eq 1 ]; then
  echo "Quality gate: backend lint and coverage"
  python_cmd="${PYTHON:-python3}"
  command -v "$python_cmd" >/dev/null 2>&1 || fail "missing Python command '$python_cmd'"

  "$python_cmd" -m ruff --version >/dev/null 2>&1 || fail "backend dev dependencies missing; run: python3 -m pip install -r backend/requirements-dev.txt"
  "$python_cmd" -m pytest --version >/dev/null 2>&1 || fail "backend test dependencies missing; run: python3 -m pip install -r backend/requirements-dev.txt"

  (
    cd backend
    "$python_cmd" -m ruff check app tests
    "$python_cmd" -m pytest tests -q --cov=app --cov-report=term-missing --cov-fail-under="${BACKEND_COVERAGE_MIN:-70}"
  )
else
  echo "Quality gate: backend unchanged, skipped."
fi

if [ "$run_frontend" -eq 1 ]; then
  echo "Quality gate: frontend lint, tests, build, review"
  if [ ! -d frontend/node_modules ]; then
    fail "frontend dependencies missing; run: npm --prefix frontend ci"
  fi
  npm --prefix frontend run review:ci
else
  echo "Quality gate: frontend unchanged, skipped."
fi

echo "Quality gate passed."
