import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const DOTENV_PATH = resolve(REPO_ROOT, '.env');

export const DEFAULT_NGROK_DOMAIN = 'unharping-preascetic-alonzo.ngrok-free.dev';

function readDotEnvValue(key) {
  let contents;
  try {
    contents = readFileSync(DOTENV_PATH, 'utf8');
  } catch {
    return undefined;
  }

  const line = contents
    .split(/\r?\n/)
    .find((candidate) => new RegExp(`^\\s*(?:export\\s+)?${key}\\s*=`).test(candidate));
  if (!line) return undefined;

  const value = line.slice(line.indexOf('=') + 1).trim();
  if (value.length >= 2 && ['"', "'", '`'].includes(value[0]) && value.at(-1) === value[0]) {
    return value.slice(1, -1);
  }
  return value.replace(/\s+#.*$/, '').trim();
}

export function getNgrokAuthToken() {
  return (
    process.env.NGROK_AUTH_TOKEN ||
    process.env.NGROK_AUTHTOKEN ||
    readDotEnvValue('NGROK_AUTH_TOKEN') ||
    readDotEnvValue('NGROK_AUTHTOKEN')
  );
}

export function getNgrokDomain() {
  const configured = process.env.NGROK_DOMAIN || readDotEnvValue('NGROK_DOMAIN');
  const domain = (configured || DEFAULT_NGROK_DOMAIN)
    .trim()
    .replace(/^https?:\/\//i, '')
    .replace(/\/$/, '')
    .toLowerCase();

  if (!/^(?=.{1,253}$)([a-z0-9](?:[a-z0-9-]*[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$/i.test(domain)) {
    throw new Error('NGROK_DOMAIN must be a hostname, such as example.ngrok-free.dev.');
  }

  return domain;
}
