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

function readTestMap() {
  const path = join(repoRoot, 'quality/test-map.json');
  if (!existsSync(path)) return {};
  return JSON.parse(readFileSync(path, 'utf8'));
}

function isBackendProduction(file) {
  return /^backend\/app\/.*\.py$/.test(file);
}

function isFrontendProduction(file) {
  if (!/^frontend\/src\/.*\.(ts|tsx)$/.test(file)) return false;
  if (/\/(__tests__|test)\//.test(file)) return false;
  if (/\.(test|spec)\.(ts|tsx)$/.test(file)) return false;
  return true;
}

function isProduction(file) {
  return isBackendProduction(file) || isFrontendProduction(file);
}

function isTest(file) {
  return (
    /^backend\/tests\/.*\.py$/.test(file) ||
    /^frontend\/src\/.*\/__tests__\/.*\.(ts|tsx)$/.test(file) ||
    /^frontend\/src\/.*\.(test|spec)\.(ts|tsx)$/.test(file) ||
    /^frontend\/e2e\/.*\.spec\.ts$/.test(file)
  );
}

function existing(paths) {
  return paths.filter((file) => existsSync(join(repoRoot, file)));
}

function implicitAnchors(file, changedTests) {
  if (isBackendProduction(file)) return changedTests.filter((test) => test.startsWith('backend/tests/'));
  if (file.startsWith('frontend/src/api/')) {
    return changedTests.filter((test) => test.startsWith('frontend/src/api/') || test.startsWith('frontend/e2e/api-contract'));
  }
  if (file.startsWith('frontend/src/pages/')) {
    return changedTests.filter((test) => test.startsWith('frontend/src/pages/') || test.startsWith('frontend/e2e/'));
  }
  if (file.startsWith('frontend/src/components/')) {
    return changedTests.filter((test) => test.startsWith('frontend/src/components/') || test.startsWith('frontend/e2e/'));
  }
  return changedTests.filter((test) => test.startsWith('frontend/'));
}

const files = changedFiles();
const productionFiles = files.filter(isProduction);

if (productionFiles.length === 0) {
  console.log('Diff-to-test map: no production code changes detected.');
  process.exit(0);
}

const changedTests = files.filter(isTest);
const testMap = readTestMap();
const missing = [];

console.log('Diff-to-test map:');

for (const file of productionFiles) {
  const explicitAnchors = existing(testMap[file] || []);
  const anchors = [...new Set([...explicitAnchors, ...implicitAnchors(file, changedTests)])].sort();

  if (anchors.length === 0) {
    missing.push(file);
    console.log(`- ${file}: missing test anchor`);
    continue;
  }

  console.log(`- ${file}:`);
  for (const anchor of anchors) console.log(`  -> ${anchor}`);
}

if (missing.length > 0) {
  console.error('\nEvery production behavior change must have a concrete test anchor.');
  console.error('Fix by adding/changing tests in the same diff or by maintaining quality/test-map.json for stable existing anchors.');
  process.exit(1);
}
