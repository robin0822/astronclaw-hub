# Frontend Review Process

This project treats AI-generated code as untrusted until a human reviewer accepts it. Every change should pass local hooks, CI, and an explicit PR review before merging.

## Required Flow

1. Create a feature branch. Do not commit directly to `main` or `master`.
2. Run `npm run review:install-hooks` once per clone to enable local Git hooks.
3. Commit normally. The pre-commit hook runs formatting, lint, typecheck, and staged secret scan.
4. Push normally. The pre-push hook runs the full CI review gate.
5. Open a pull request and complete the PR checklist.
6. Merge only after CI passes and the required human approvals are complete.

## Commands

```bash
npm run review:install-hooks
npm run review:commit
npm run review:ci
npm run review:risk
npm run review:secrets
```

## Automated Gates

Local commits that include staged `frontend/` changes run:

- `format:check`: source formatting must match Prettier.
- `lint`: lint warnings are surfaced before commit.
- `typecheck`: TypeScript project references must compile.
- `review:risk:staged`: changed frontend files are mapped to review focus areas such as auth, API contracts, shared UI, performance, sharing, and sensitive data.
- `review:secrets:staged`: staged files are scanned for tokens, model keys, and hard-coded credential-like values.

Pushes run the full CI gate:

- `format:check`
- `lint`
- `test`
- `build`
- `review:risk`
- `review:secrets`

The risk report is intentionally advisory. It does not prove that a change is safe; it tells reviewers what areas deserve extra attention.

## Risk Levels

- Low: isolated copy, style, documentation, or formatting changes with no shared logic or data contract changes.
- Medium: page behavior, shared component, global style, store, routing, API client, or dependency changes.
- High: authentication, permissions, secrets, public sharing, destructive operations, data migration, release workflow, or backend/frontend contract changes.

High-risk changes require stronger evidence: a clear PR description, targeted manual verification, and preferably two human approvals.

## Branch Protection

Configure the Git hosting platform for protected branches:

- Require pull requests before merging.
- Require at least 1 approval for ordinary changes and 2 approvals for auth, permissions, secrets, release, or destructive-operation changes.
- Require the `frontend-review` status check.
- Require conversations to be resolved.
- Dismiss stale approvals when new commits are pushed.
- Do not allow bypassing branch protection, including administrators.
- Restrict who can push directly to protected branches.

## Code Owner Review

If the repository uses GitHub, add real owners to `.github/CODEOWNERS`, for example:

```text
/frontend/ @your-org/frontend-reviewers
/frontend/src/api/ @your-org/security-reviewers
/frontend/src/store/auth-context.tsx @your-org/security-reviewers
/frontend/src/store/permissions.ts @your-org/security-reviewers
```

Do not enable code-owner enforcement until the owners are real users or teams in the organization.

## What Reviewers Must Check

- Authenticated routes, menu entries, and buttons all consume the same permission model.
- Sensitive values are not stored in `localStorage`, bundled env vars, seed data, logs, screenshots, or fixtures.
- Sharing links are validated by the backend and have expiry/scope checks.
- Production code does not silently show demo data on API failure.
- Dangerous operations require confirmation, backend authorization, and auditability.
- API clients handle timeout, 401, Blob/FormData, and non-JSON responses correctly.
- UI text and layout still work at common desktop/mobile widths.
- Tests or manual verification match the risk level of the change.

## Performance Review Rules

Reviewers should look for:

- Render loops caused by effects that update state and depend on values recreated each render.
- Repeated API calls caused by unstable dependencies, missing cleanup, or eager refetching on every keystroke.
- Expensive `filter`, `sort`, `map`, grouping, or aggregation work inside render paths without `useMemo` or server-side pagination.
- Large tables, cards, logs, or audit lists rendered without pagination, limits, virtual scrolling, or backend filtering.
- New dependencies that materially increase bundle size or duplicate existing functionality.
- Shared context updates that force broad rerenders when state could be scoped more narrowly.
- Global CSS changes that trigger layout instability, overlap, or unreadable text at mobile and desktop widths.

For performance-sensitive changes, include one of the following in the PR:

- Before/after Vite build chunk size notes.
- Manual smoke result for the affected page with realistic list sizes.
- Explanation of why the changed render path remains bounded.

## Regression Review Rules

Any change to shared code must be reviewed against more than the page where it was developed:

- `Layout`, `AppRoutes`, auth, permissions, or route config: verify login, logout, unauthorized access, default redirect, and at least two protected routes.
- `StoreContext`, shared types, or seed adapters: verify pages that read the affected data still handle empty and demo-mode states.
- `Select`, `Modal`, `ui`, global CSS, or app shell: verify representative forms, tables, detail modals, notification panels, and narrow viewport behavior.
- API client changes: verify success, business error, HTTP error, timeout/network error, unauthorized redirect, and Blob download behavior where applicable.
- Sharing changes: verify valid, missing-token, expired/revoked, and unauthorized links fail closed.
- Destructive action changes: verify confirm/cancel, success, failure, permission denied, and audit/log feedback.

## Required Verification Evidence

PRs should state:

- Which pages or workflows were manually checked.
- Which risk level applies and why.
- Whether `npm run review:ci` passed.
- Any known residual risks, skipped checks, or backend assumptions.
