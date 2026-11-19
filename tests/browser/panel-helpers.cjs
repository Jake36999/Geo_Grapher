// Where controls live now: the right panel has three modes (Inspect, Graphs, Build), the theme and panel
// widths are in the Settings menu in the top bar, and Configure rules and the QI grouping are in
// the Scope & filters panel. Each helper returns `page` so a call can sit in front of a locator:
// `(await showGraphsMode(page)).getByRole(...)`.
async function showGraphsMode(page) {
  const tab = page.getByRole('tab', { name: 'Graphs', exact: true });
  if ((await tab.getAttribute('aria-selected')) !== 'true') await tab.click();
  return page;
}

async function showInspectMode(page) {
  const tab = page.getByRole('tab', { name: 'Inspect', exact: true });
  if ((await tab.getAttribute('aria-selected')) !== 'true') await tab.click();
  return page;
}

async function showBuildMode(page) {
  const tab = page.getByRole('tab', { name: 'Build', exact: true });
  if ((await tab.getAttribute('aria-selected')) !== 'true') await tab.click();
  return page;
}

async function openSettings(page) {
  const menu = page.locator('.settings-menu');
  if (!(await menu.evaluate((element) => element.open))) await menu.locator(':scope > summary').click();
  return page;
}

async function openScope(page) {
  const scope = page.locator('details.popover', { has: page.locator(':scope > summary', { hasText: 'Scope & filters' }) });
  if (!(await scope.evaluate((element) => element.open))) await scope.locator(':scope > summary').click();
  return scope;
}

async function useTheme(page, theme) {
  await openSettings(page);
  await page.getByRole('button', { name: `Use ${theme} theme`, exact: true }).click();
  await page.keyboard.press('Escape'); // close the menu so it does not sit over what the test does next
  return page;
}

module.exports = { showGraphsMode, showInspectMode, showBuildMode, openSettings, openScope, useTheme };
