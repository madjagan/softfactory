// EXAMPLE storyboard (an invoicing flow) — copy, rename to
// <subject>.mjs, and replace every login, group id, label and setup call with THIS app's.
// A storyboard is data: the library (../lib.mjs + ../app.config.mjs) knows how to sign in, open
// groups, draw and shoot. One `shot` per guide step, in the guide's order; a step whose result
// is worth seeing becomes two shots (the click, then the result with `click: false`).
export default {
  title: 'Invoices test guide',
  guide: 'docs/INVOICES_TEST_GUIDE.md',
  outDir: new URL('../../../docs/screenshots/invoices-guide', import.meta.url).pathname,
  // The state the guide assumes, made true through the API — idempotent, so reruns are clean
  // (a 409 "already there" is fine). Never edit the database by hand.
  async setup(api) {
    const admin = await api('admin@example.com');
    console.log('setup: approve the previous invoice →', (await admin.put('/invoices/INV-2026-05', { status: 'approved' })).status);
  },
  parts: [
    // One part per login. `shotSignIn` captures the sign-in screen once, for the role the guide is about.
    { title: 'Part A — raise and approve an invoice', login: 'admin@example.com', shotSignIn: 'Sign in as the billing admin',
      async run(cap, page) {
        const billing = await cap.group('grp_billing');                               // sidebar group id from app.config.mjs's nav
        await cap.shot(billing.getByText('Invoices', { exact: true }), 'Billing → Invoices');
        await cap.shot(page.getByRole('button', { name: 'New Invoice' }), 'Open the New Invoice tab', { wait: 900 });
        await cap.shot(page.getByRole('button', { name: '+ Add line' }), 'Optional: + Add line for a one-off charge', { click: false });
        // Tabs and the big action can share a label — pick .last()/.first() deliberately and say why.
        const create = page.getByRole('button', { name: 'New Invoice' }).last();     // the action button, below the tab of the same name
        await cap.shot(create, 'New Invoice', { click: !(await create.isDisabled()), wait: 2500 });
        await cap.shot(page.locator('tr', { hasText: 'Jun 2026' }).first(), 'The invoice appears in Invoice History as Draft — open it', { wait: 900 });
        await cap.shot(page.getByRole('button', { name: /^Approve (Invoice|v\d+)$/ }), 'Approve Invoice → Approved', { wait: 2500 });   // regex: the label carries a version
        await cap.shot(page.getByText(/Approved/).first(), 'Status reads Approved', { click: false });
      } },
    { title: 'Part B — the customer sees the invoice', login: 'customer@example.com',
      async run(cap, page) {
        const account = await cap.group('grp_account');
        await cap.shot(account.getByText('My Account', { exact: true }), 'Account → My Account');
        await cap.shot(page.getByRole('button', { name: /Download Invoice/ }).first(), 'Choose Download Invoice', { wait: 800 });
        await cap.shot(null, 'Your Invoices — the new month is there', { file: 'invoices' });   // a bare shot: no ring, just the state
      } },
  ],
};
