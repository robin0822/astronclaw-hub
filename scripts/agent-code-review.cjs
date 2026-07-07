#!/usr/bin/env node
const { execFileSync } = require('node:child_process');
const { existsSync, readFileSync } = require('node:fs');
const { join } = require('node:path');

const repoRoot = execFileSync('git', ['rev-parse', '--show-toplevel'], { encoding: 'utf8' }).trim();
const args = process.argv.slice(2);

function argValue(name) {
  const index = args.indexOf(name);
  return index === -1 ? '' : args[index + 1] || '';
}

function git(commandArgs) {
  try {
    return execFileSync('git', commandArgs, { cwd: repoRoot, encoding: 'utf8' }).trim();
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

function resolveBase() {
  const explicit = argValue('--base');
  if (explicit) return explicit;

  const upstream = git(['rev-parse', '--abbrev-ref', '--symbolic-full-name', '@{u}']);
  if (upstream) return git(['merge-base', 'HEAD', upstream]);

  if (git(['rev-parse', '--verify', 'HEAD~1'])) return 'HEAD~1';
  return '';
}

function changedFiles() {
  if (args.includes('--staged')) return lines(git(['diff', '--cached', '--name-only', '--diff-filter=ACMR']));

  const range = argValue('--range');
  if (range) return lines(git(['diff', '--name-only', '--diff-filter=ACMR', range]));

  const base = resolveBase();
  if (!base) return lines(git(['ls-files']));
  return lines(git(['diff', '--name-only', '--diff-filter=ACMR', `${base}...HEAD`]));
}

function readFile(file) {
  const path = join(repoRoot, file);
  if (!existsSync(path)) return '';
  return readFileSync(path, 'utf8');
}

function isTextFile(file) {
  return /\.(cjs|css|env|html|js|json|jsx|md|mjs|py|sh|sql|ts|tsx|txt|yaml|yml)$/.test(file);
}

function isProductionCode(file) {
  if (/^backend\/app\/.*\.py$/.test(file)) return true;
  if (/^frontend\/src\/.*\.(ts|tsx)$/.test(file)) {
    if (/\/(__tests__|test)\//.test(file)) return false;
    if (/\.(test|spec)\.(ts|tsx)$/.test(file)) return false;
    return true;
  }
  return false;
}

const findings = [];
const reviewNotes = [];
const files = changedFiles().filter(isTextFile);

for (const file of files) {
  const content = readFile(file);

  if (/(^|\/)\.env($|\.)/.test(file) && file !== 'frontend/.env.development' && !file.endsWith('.env.example')) {
    findings.push(`${file}: env files with runtime values must not be committed; use env examples or backend-managed secrets.`);
  }

  if (isProductionCode(file) && /\b(sk|ak)-[A-Za-z0-9_-]{20,}\b/.test(content)) {
    findings.push(`${file}: possible model/provider secret key committed in production code.`);
  }

  if (
    isProductionCode(file) &&
    /\b(apiKey|secret|token|password)\b\s*[:=]\s*['"][^'"\n*]{12,}['"]/i.test(content)
  ) {
    findings.push(`${file}: possible hard-coded credential in production code.`);
  }

  if (file.startsWith('frontend/src/') && /\/api\/v1\/bot\b|CLAW_PROXY|bridgeToken/i.test(content)) {
    findings.push(`${file}: frontend must call /api/v1/astron-claw only; Claw Proxy and bridge credentials stay behind backend.`);
  }

  if (file === 'backend/app/api/v1/routes.py' && /@(router|app)\.(post|put|patch|delete)\(/.test(content) && !/audit/i.test(content)) {
    findings.push(`${file}: mutating API routes must leave an audit trail.`);
  }

  if (isProductionCode(file)) {
    if (file.startsWith('backend/')) reviewNotes.push(`${file}: check RBAC, audit log, error mapping, idempotency, and transaction boundaries.`);
    if (file.startsWith('frontend/')) reviewNotes.push(`${file}: check loading/error/empty states, permission gating, API failures, and narrow viewport layout.`);
  }
}

console.log('Agent internal code review:');

if (reviewNotes.length === 0) {
  console.log('- no production-code review focus detected.');
} else {
  for (const note of [...new Set(reviewNotes)].sort()) console.log(`- ${note}`);
}

if (findings.length > 0) {
  console.error('\nActionable review findings:');
  for (const finding of findings) console.error(`- ${finding}`);
  process.exit(1);
}

console.log('Agent internal code review passed.');
