const { execFileSync } = require('node:child_process');
const { existsSync, readFileSync, readdirSync, statSync } = require('node:fs');
const { join, relative } = require('node:path');

const args = new Set(process.argv.slice(2));
const stagedOnly = args.has('--staged');
const repoRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
const frontendRoot = join(repoRoot, 'frontend');

const ignoredDirs = new Set(['.git', 'node_modules', 'dist', 'coverage']);
const ignoredFiles = new Set(['package-lock.json']);
const textExtensions = new Set(['.cjs', '.css', '.env', '.example', '.html', '.js', '.json', '.jsx', '.md', '.mjs', '.ts', '.tsx', '.txt', '.yaml', '.yml']);

const rules = [
  {
    name: 'OpenAI or model style secret key',
    pattern: /\b(sk|ak)-[A-Za-z0-9_-]{20,}\b/,
  },
  {
    name: 'Non-empty debug auth token in env',
    pattern: /^VITE_ASTRONCLAW_AUTH_TOKEN\s*=\s*[^#\s]+/m,
  },
  {
    name: 'Non-empty debug authorization in env',
    pattern: /^VITE_ASTRONCLAW_AUTHORIZATION\s*=\s*[^#\s]+/m,
  },
  {
    name: 'Likely hard-coded credential',
    pattern: /\b(apiKey|secret|token|password)\b\s*[:=]\s*['"][^'"\n*]{12,}['"]/i,
  },
];

function extensionOf(filePath) {
  const lower = filePath.toLowerCase();
  const dot = lower.lastIndexOf('.');
  return dot === -1 ? '' : lower.slice(dot);
}

function isScannable(filePath) {
  const normalized = filePath.replace(/\\/g, '/');
  const baseName = normalized.split('/').pop();
  if (ignoredFiles.has(baseName)) return false;
  if (!stagedOnly && baseName.startsWith('.env') && baseName !== '.env.example') return false;
  if (normalized.includes('/dist/') || normalized.includes('/node_modules/')) return false;
  const ext = extensionOf(filePath);
  return textExtensions.has(ext) || normalized.endsWith('.env.example');
}

function listWorkingTreeFiles(dir, out = []) {
  for (const entry of readdirSync(dir)) {
    if (ignoredDirs.has(entry)) continue;
    const absolute = join(dir, entry);
    const stat = statSync(absolute);
    if (stat.isDirectory()) listWorkingTreeFiles(absolute, out);
    else out.push(relative(repoRoot, absolute).replace(/\\/g, '/'));
  }
  return out;
}

function listFiles() {
  if (!stagedOnly) return listWorkingTreeFiles(frontendRoot).filter(isScannable);

  const output = execFileSync('git', ['diff', '--cached', '--name-only', '--diff-filter=ACMR'], {
    cwd: repoRoot,
    encoding: 'utf8',
  });

  return output
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.startsWith('frontend/'))
    .filter(isScannable);
}

function readFileFromGitIndex(filePath) {
  if (!stagedOnly) return readFileSync(join(repoRoot, filePath), 'utf8');
  return execFileSync('git', ['show', `:${filePath}`], { cwd: repoRoot, encoding: 'utf8' });
}

const findings = [];

for (const filePath of listFiles()) {
  if (!existsSync(join(repoRoot, filePath)) && !stagedOnly) continue;

  let content = '';
  try {
    content = readFileFromGitIndex(filePath);
  } catch {
    continue;
  }

  for (const rule of rules) {
    if (rule.pattern.test(content)) findings.push(`${filePath}: ${rule.name}`);
  }
}

if (findings.length > 0) {
  console.error('Potential secrets found. Remove secrets or use backend-managed secret storage:');
  for (const finding of findings) console.error(`- ${finding}`);
  process.exit(1);
}

console.log(`Secret scan passed (${stagedOnly ? 'staged files' : 'frontend tree'}).`);
