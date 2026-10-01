// PROJECT-OWNED: how the capture library drives THIS app. Written once by install.sh; edit freely.
// lib.mjs imports it. Everything that names a selector, a URL or a credential lives here, so the
// library stays product-agnostic. Keep the sign-in and sidebar selectors in step with the UI —
// a selector that times out is a stale entry here or a wrong label in the guide.
export default {
  base: process.env.SHOTS_BASE || 'http://localhost:5174',          // the dev server stack.sh starts
  api: process.env.SHOTS_API || 'http://127.0.0.1:3002/api',         // the API stack.sh starts
  password: process.env.SHOTS_PASSWORD || 'demo123',                // the shared demo password (factory.yaml → seed.password)
  viewport: { width: 1440, height: 900 },
  ring: '#D92D20',                                                   // annotation colour

  // Sign-in: how to reach the first screen after login.
  login: {
    email: 'input[type="email"]',
    password: 'input[type="password"]',
    submit: 'button:has-text("Sign In")',
    ready: '[aria-label^="nav-group-"]',                            // appears once the shell is up
    // API login for storyboard SETUP calls: path and body shape.
    apiPath: '/auth/login',
    apiBody: (email, password) => ({ email, password }),
    tokenField: 'token',
  },

  // Sidebar: a collapsible group and its items container, by group id.
  nav: {
    group: (gid) => `[aria-label="nav-group-${gid}"]`,
    items: (gid) => `[aria-label="nav-group-items-${gid}"]`,
    // An optional second-level group (e.g. Administration → sub-groups); leave null if none.
    admin: '[aria-label="nav-administration"]',
    adminGroup: (gid) => `[aria-label="nav-admin-group-${gid}"]`,
    adminItems: (gid) => `[aria-label="nav-admin-group-items-${gid}"]`,
  },
};
