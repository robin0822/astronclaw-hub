const { spawnSync } = require('node:child_process');

const command = process.platform === 'win32' ? 'npx.cmd' : 'npx';
const result = spawnSync(command, ['playwright', 'test', 'e2e/api-contract.spec.ts'], {
  stdio: 'inherit',
  env: { ...process.env, E2E_ENABLE_API_CONTRACT: '1' },
});

process.exit(result.status ?? 1);
