// A dev server for the screenshot run, for Vite projects: the repo's own config with the API
// proxy pointed at the screenshot backend (SHOTS_API_PORT, default 3002) on its own port
// (SHOTS_WEB_PORT, default 5174), so the developer's normal dev server is untouched.
// Non-Vite projects: ignore this file and set factory.yaml → screenshots.web to whatever
// starts their dev server against the screenshot API.
import base from '../../vite.config.js';
const apiPort = process.env.SHOTS_API_PORT || '3002';
const webPort = Number(process.env.SHOTS_WEB_PORT || '5174');
export default async (env) => {
  const cfg = typeof base === 'function' ? await base(env) : base;
  return { ...cfg, root: new URL('../..', import.meta.url).pathname,
    server: { ...cfg.server, port: webPort, strictPort: true,
      proxy: { '/api': { target: `http://localhost:${apiPort}`, changeOrigin: true } } } };
};
