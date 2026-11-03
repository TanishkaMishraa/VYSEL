#!/usr/bin/env node
/**
 * VYSEL Monorepo Test Runner
 * Runs:
 * 1. Design system validation (tokens, contrast, brand SVGs, icons)
 * 2. Web frontend unit tests (preferences, savedLooks, shades, landmarks, sampleReport)
 * 3. Backend service unit tests (color math, face shape classification, etc.)
 */
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');

function runStep(name, cmd, args, env = {}) {
  console.log(`\n========================================`);
  console.log(`  STEP: ${name}`);
  console.log(`========================================`);
  const res = spawnSync(cmd, args, {
    cwd: root,
    stdio: 'inherit',
    shell: true,
    env: { ...process.env, ...env },
  });
  if (res.status !== 0) {
    console.error(`\n❌ Step '${name}' failed with code ${res.status}`);
    return false;
  }
  console.log(`\n✅ Step '${name}' passed!`);
  return true;
}

let passed = true;

// 1. Design System Validation
passed = runStep('Design System Validation', 'node', ['scripts/validate-design-system.mjs']) && passed;

// 2. Frontend Unit Tests
passed = runStep(
  'Frontend Unit Tests',
  'node',
  ['--experimental-strip-types', '--test', 'apps/web/tests/*.test.mjs']
) && passed;

// 3. Backend Core Service Tests (Python PyTest)
passed = runStep(
  'Backend Core Service Tests (PyTest)',
  'python',
  ['-m', 'pytest', 'apps/api/tests/test_color.py', 'apps/api/tests/test_face_shape.py'],
  {
    PYTHONPATH: 'apps/api',
    DATABASE_URL: 'sqlite:///:memory:',
    JWT_SECRET: 'test-secret-long-enough-32-chars-at-least-123456',
  }
) && passed;

if (!passed) {
  console.error('\n❌ Some test suites failed.');
  process.exit(1);
} else {
  console.log('\n🎉 ALL TESTS AND CHECKS PASSED SUCCESSFULLY!\n');
  process.exit(0);
}

