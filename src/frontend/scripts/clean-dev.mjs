/**
 * Prestart cleanup for `dev:all` (runs automatically as `predev:all`).
 *
 * Uvicorn --reload workers can outlive a force-killed terminal and keep holding
 * backend/gateway/web ports with stale code. Normal Ctrl+C stops the whole tree
 * cleanly; this script is the safety net: it tree-kills whatever still LISTENs
 * on the dev ports, then waits for the OS to release them.
 */
import { execSync } from 'node:child_process';
import { connect } from 'node:net';
import { fileURLToPath } from 'node:url';

const PORTS = [8000, 4099, 5173];

export function pidsForPorts(netstatOutput, ports) {
  const wanted = new Set(ports);
  const pids = new Set();
  for (const line of String(netstatOutput).split('\n')) {
    const match = line.match(/TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)/i);
    if (match && wanted.has(Number(match[1]))) pids.add(match[2]);
  }
  return [...pids];
}

function treeKill(pid) {
  try {
    execSync(`taskkill /PID ${pid} /T /F`, { stdio: 'ignore' });
    console.log(`clean-dev: stopped stale process ${pid}`);
  } catch {
    // Already gone (e.g. ghost TCP table entries) — nothing to stop.
  }
}

function portBusy(port) {
  return new Promise((resolve) => {
    const socket = connect({ host: '127.0.0.1', port, timeout: 1000 });
    socket.on('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.on('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.on('error', () => resolve(false));
  });
}

async function main() {
  if (process.platform !== 'win32') {
    console.log('clean-dev: non-Windows platform, skipping port cleanup.');
    return;
  }
  let output = '';
  try {
    output = execSync('netstat -ano', { encoding: 'utf8' });
  } catch {
    console.log('clean-dev: netstat unavailable, skipping port cleanup.');
    return;
  }
  for (const pid of pidsForPorts(output, PORTS)) treeKill(pid);
  for (let attempt = 0; attempt < 15; attempt += 1) {
    const busy = await Promise.all(PORTS.map(portBusy));
    if (busy.every((held) => !held)) return;
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  console.log(
    'clean-dev: warning: a dev port still answers after cleanup; ' +
      'the backend will fail fast to bind if it is really held.',
  );
}

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  await main();
}
