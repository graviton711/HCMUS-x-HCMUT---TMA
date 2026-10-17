import ngrok from '@ngrok/ngrok';
import { getNgrokAuthToken, getNgrokDomain } from './ngrok-config.mjs';

const authToken = getNgrokAuthToken();
if (!authToken) {
  console.error('ngrok: set NGROK_AUTH_TOKEN in the repository .env file or environment.');
  process.exit(1);
}

let listener;
let closing = false;

try {
  const domain = getNgrokDomain();
  listener = await ngrok.forward({
    addr: '127.0.0.1:5173',
    authtoken: authToken,
    domain,
  });
  console.log(`ngrok: ${listener.url()} -> http://127.0.0.1:5173`);
  process.stdin.resume();

  const close = async () => {
    if (closing) return;
    closing = true;
    await listener.close();
    process.exit(0);
  };
  process.once('SIGINT', () => void close());
  process.once('SIGTERM', () => void close());
} catch (error) {
  console.error(`ngrok: failed to start tunnel: ${error.message}`);
  process.exit(1);
}
