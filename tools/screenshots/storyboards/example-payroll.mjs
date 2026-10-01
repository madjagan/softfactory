// EXAMPLE storyboard (from the HRMS project this factory was extracted from) — copy, rename to
// <subject>.mjs, and replace every login, group id, label and setup call with THIS app's.
// A storyboard is data: the library (../lib.mjs + ../app.config.mjs) knows how to sign in, open
// groups, draw and shoot. One `shot` per guide step, in the guide's order; a step whose result
// is worth seeing becomes two shots (the click, then the result with `click: false`).
export default {
  title: 'Payroll test guide',
  guide: 'docs/PAYROLL_TEST_GUIDE.md',
  outDir: new URL('../../../docs/screenshots/payroll-guide', import.meta.url).pathname,
  // The state the guide assumes, made true through the API — idempotent, so reruns are clean
  // (a 409 "already there" is fine). Never edit the database by hand.
  async setup(api) {
    const fin = await api('admin@example.com');
    console.log('setup: approve the previous month →', (await fin.put('/pay-runs/PR-2026-05', { status: 'approved' })).status);
  },
  parts: [
    // One part per login. `shotSignIn` captures the sign-in screen once, for the role the guide is about.
    { title: 'Part A — run the month', login: 'admin@example.com', shotSignIn: 'Sign in as the payroll operator',
      async run(cap, page) {
        const fin = await cap.group('grp_finance');                                   // sidebar group id from app.config.mjs's nav
        await cap.shot(fin.getByText('Payroll', { exact: true }), 'Finance → Payroll');
        await cap.shot(page.getByRole('button', { name: 'Process Payroll' }), 'Open the Process Payroll tab', { wait: 900 });
        await cap.shot(page.getByRole('button', { name: '+ Add entry' }), 'Optional: + Add entry for a one-off amount', { click: false });
        // Tabs and the big action can share a label — pick .last()/.first() deliberately and say why.
        const run = page.getByRole('button', { name: 'Process Payroll' }).last();   // the action button, below the tab of the same name
        await cap.shot(run, 'Process Payroll', { click: !(await run.isDisabled()), wait: 2500 });
        await cap.shot(page.locator('tr', { hasText: 'Jun 2026' }).first(), 'The run appears in Pay Run History as Draft — open it', { wait: 900 });
        await cap.shot(page.getByRole('button', { name: /^Approve (Run|v\d+)$/ }), 'Approve Run → Approved', { wait: 2500 });   // regex: the label carries a version
        await cap.shot(page.getByText(/Approved/).first(), 'Status reads Approved', { click: false });
      } },
    { title: 'Part B — the employee sees the payslip', login: 'employee@example.com',
      async run(cap, page) {
        const me = await cap.group('grp_me');
        await cap.shot(me.getByText('My Portal', { exact: true }), 'My Space → My Portal');
        await cap.shot(page.getByRole('button', { name: /Payslip Download/ }).first(), 'Choose Payslip Download', { wait: 800 });
        await cap.shot(null, 'Your Payslips — the new month is there', { file: 'payslips' });   // a bare shot: no ring, just the state
      } },
  ],
};
