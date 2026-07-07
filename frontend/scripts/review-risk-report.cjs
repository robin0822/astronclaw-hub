const { execFileSync } = require('node:child_process');

const args = new Set(process.argv.slice(2));
const stagedOnly = args.has('--staged');
const repoRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();

function git(args) {
  try {
    return execFileSync('git', args, { cwd: repoRoot, encoding: 'utf8' }).trim();
  } catch {
    return '';
  }
}

function lines(output) {
  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);
}

function unique(items) {
  return [...new Set(items)].sort();
}

function changedFiles() {
  if (stagedOnly) return lines(git(['diff', '--cached', '--name-only', '--diff-filter=ACMR']));

  const workingTree = lines(git(['diff', '--name-only', '--diff-filter=ACMR']));
  const staged = lines(git(['diff', '--cached', '--name-only', '--diff-filter=ACMR']));
  const active = unique([...workingTree, ...staged]);
  if (active.length > 0) return active;

  const lastCommit = git(['rev-parse', '--verify', 'HEAD~1']);
  if (!lastCommit) return [];
  return lines(git(['diff', '--name-only', '--diff-filter=ACMR', 'HEAD~1', 'HEAD']));
}

function fileMatches(files, patterns) {
  return files.some((file) => patterns.some((pattern) => pattern.test(file)));
}

function addRisk(risks, title, level, when, checks) {
  risks.push({ title, level, when, checks });
}

const frontendFiles = changedFiles().filter((file) => file.startsWith('frontend/'));
if (frontendFiles.length === 0) {
  console.log('Review risk report: no frontend changes detected.');
  process.exit(0);
}

const risks = [];

if (
  fileMatches(frontendFiles, [
    /^frontend\/src\/store\/auth-context\.tsx$/,
    /^frontend\/src\/store\/permissions\.ts$/,
    /^frontend\/src\/store\/route-config\.ts$/,
    /^frontend\/src\/store\/RequireAuth\.tsx$/,
    /^frontend\/src\/routes\//,
    /^frontend\/src\/pages\/LoginPage\.tsx$/,
  ])
) {
  addRisk(risks, 'Auth and permission behavior', 'high', 'route, login, session, or permission files changed', [
    'Verify unauthenticated users are redirected and return to the original path after login.',
    'Verify users without a required permission cannot open the route or execute protected actions.',
    'Verify logout clears session state and does not leave stale Authorization headers.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/api\//, /^frontend\/vite\.config\.ts$/, /^frontend\/\.env\.example$/])) {
  addRisk(risks, 'Backend API contract', 'high', 'API client, proxy, or runtime API config changed', [
    'Verify request paths, query serialization, body encoding, timeout, Blob/FormData handling, and 401 behavior.',
    'Verify API failures do not silently fall back to demo data when demo mode is disabled.',
    'Check whether backend documentation or mock data needs to change with the contract.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/components\//, /^frontend\/src\/store\/StoreContext\.tsx$/, /^frontend\/src\/index\.css$/, /^frontend\/src\/App\.tsx$/])) {
  addRisk(risks, 'Shared UI or state regression', 'medium', 'shared component, global style, app shell, or store changed', [
    'Smoke test at least two unrelated pages that consume the changed shared component or store data.',
    'Check empty, loading, error, and long-text states where the shared component appears.',
    'Check desktop and narrow viewport layouts for overflow or overlapping controls.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/pages\//, /^frontend\/src\/components\//, /^frontend\/src\/store\//])) {
  addRisk(risks, 'Render performance', 'medium', 'page, component, or store files changed', [
    'Look for expensive filtering, sorting, mapping, or object creation inside render paths without memoization.',
    'Verify effects do not refetch in loops and async effects clean up stale responses when inputs change.',
    'For large lists, verify pagination, limits, virtualization, or server-side filtering keeps DOM size bounded.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/package\.json$/, /^frontend\/package-lock\.json$/, /^frontend\/src\/routes\//])) {
  addRisk(risks, 'Bundle size and dependency impact', 'medium', 'dependencies or route loading changed', [
    'Compare Vite build chunk sizes and confirm heavy pages remain lazy-loaded.',
    'Check new dependencies for size, maintenance risk, and whether an existing package already covers the need.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/store\/StoreContext\.tsx$/, /^frontend\/src\/pages\/ModelsPage\.tsx$/, /^frontend\/src\/store\/types\.ts$/])) {
  addRisk(risks, 'Sensitive data persistence', 'high', 'store, model credential, or data shape files changed', [
    'Verify secrets, API keys, tokens, passwords, and tenant credentials are not persisted or logged.',
    'Verify persisted local/session storage remains backward compatible or has a safe migration path.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/pages\/Share/, /^frontend\/src\/pages\/SharingPage\.tsx$/, /^frontend\/src\/api\/modules\/share/])) {
  addRisk(risks, 'Sharing and authorization scope', 'high', 'share page, share grants, or public share API changed', [
    'Verify share links are validated by the backend, include expiry/scope checks, and do not read private local store data.',
    'Verify revoked, expired, missing-token, and unauthorized states fail closed.',
  ]);
}

if (fileMatches(frontendFiles, [/^frontend\/src\/pages\//, /^frontend\/src\/utils\//])) {
  addRisk(risks, 'Destructive operation handling', 'medium', 'page or utility code changed', [
    'For delete, revoke, archive, stop, restore, and overwrite actions, verify confirmation and backend authorization exist.',
    'Verify user-facing feedback and audit/logging behavior for success and failure paths.',
  ]);
}

console.log(`Review risk report (${stagedOnly ? 'staged files' : 'active or latest commit'}):`);
for (const file of frontendFiles) console.log(`- ${file}`);

if (risks.length === 0) {
  console.log('\nNo specific risk category matched. Apply the standard review checklist.');
  process.exit(0);
}

console.log('\nSuggested review focus:');
for (const risk of risks) {
  console.log(`\n[${risk.level}] ${risk.title}`);
  console.log(`Reason: ${risk.when}.`);
  for (const check of risk.checks) console.log(`- ${check}`);
}
