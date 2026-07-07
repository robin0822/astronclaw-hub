const { execFileSync } = require('node:child_process');
const { chmodSync, existsSync } = require('node:fs');
const { join } = require('node:path');

function run(command, args, options = {}) {
  return execFileSync(command, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'], ...options }).trim();
}

const repoRoot = run('git', ['rev-parse', '--show-toplevel']);
const hooksPath = '.githooks';
const absoluteHooksPath = join(repoRoot, hooksPath);

if (!existsSync(absoluteHooksPath)) {
  throw new Error(`Git hooks directory not found: ${absoluteHooksPath}`);
}

run('git', ['config', 'core.hooksPath', hooksPath], { cwd: repoRoot });

for (const hookName of ['commit-msg', 'pre-commit', 'pre-push']) {
  const hookPath = join(absoluteHooksPath, hookName);
  if (existsSync(hookPath)) chmodSync(hookPath, 0o755);
}

console.log(`Git review hooks enabled: ${hooksPath}`);
