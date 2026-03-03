/**
 * Purge a cache tag from Workers KV.
 *
 * Usage:
 *   node scripts/purge-tag.js <tag> [--env staging|production]
 *
 * Example:
 *   node scripts/purge-tag.js jobs --env production
 *   node scripts/purge-tag.js courses --env staging
 */

const { execSync } = require('child_process');

const tag = process.argv[2];
const envFlag = process.argv.indexOf('--env');
const env = envFlag !== -1 ? process.argv[envFlag + 1] : 'production';

if (!tag) {
  console.error('Usage: node scripts/purge-tag.js <tag> [--env staging|production]');
  process.exit(1);
}

const timestamp = Date.now().toString();
const key = `purge:${tag}`;

console.log(`Purging cache tag "${tag}" in ${env} environment...`);
console.log(`  KV key: ${key}`);
console.log(`  Value:  ${timestamp}`);

try {
  execSync(
    `npx wrangler kv:key put --binding=EDGE_CACHE --env=${env} "${key}" "${timestamp}" --ttl=3600`,
    { stdio: 'inherit' }
  );
  console.log(`✓ Cache tag "${tag}" purged successfully.`);
} catch (err) {
  console.error(`✗ Failed to purge cache tag "${tag}":`, err.message);
  process.exit(1);
}
