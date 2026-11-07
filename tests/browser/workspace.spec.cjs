const fs = require("fs");
const os = require("os");
const pageEvidence = new WeakMap();
const { test, expect } = require("@playwright/test");
const AxeBuilder = require("@axe-core/playwright").default;

test("P5.4 recorded collection overlay separates observations and restores the static preset", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("button", { name: "Nearby", exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page
    .getByLabel("Relationship visibility preset")
    .selectOption("internal_candidates");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByLabel("Runtime collection window").selectOption(
    await page
      .getByLabel("Runtime collection window")
      .getByRole("option", { name: /qa-observed-a/ })
      .getAttribute("value"),
  );
  const observed = page.waitForResponse(
    (r) =>
      r.url().endsWith("/viewport/frame") &&
      r.request().postDataJSON()?.filter?.runtime_window?.environment ===
        "qa-observed-a",
  );
  await page
    .getByRole("checkbox", { name: "Runtime overlay", exact: true })
    .check();
  const response = await observed;
  const payload = response.request().postDataJSON(),
    data = (await response.json()).data;
  expect(payload.filter.resolution_statuses).toEqual([
    "exact",
    "candidate",
    "observed",
  ]);
  await expect(page.getByRole("note", { name: "Analysis mode" })).toHaveText(
    "STATIC + OBSERVED",
  );
  expect(
    data.relationships.some(
      (r) =>
        r.family === "runtime" &&
        r.resolution_status === "observed" &&
        r.aggregated_weight === 72 &&
        r.weight_unit === "call_count",
    ),
  ).toBe(true);
  await expect(
    page.getByRole("region", { name: "Runtime collection", exact: true }),
  ).toContainText("72 observed calls");
  await page
    .getByRole("checkbox", { name: "Runtime overlay", exact: true })
    .uncheck();
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(page.getByLabel("Relationship visibility preset")).toHaveValue(
    "internal_candidates",
  );
  await expect(page.locator(".error-banner")).toHaveCount(0);
});

test("P5.4 collection selection, evidence and saved runtime scope round-trip", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("button", { name: "Nearby", exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByLabel("Runtime collection window").selectOption(
    await page
      .getByLabel("Runtime collection window")
      .getByRole("option", { name: /qa-observed-b/ })
      .getAttribute("value"),
  );
  await page
    .getByRole("checkbox", { name: "Runtime overlay", exact: true })
    .check();
  await expect(
    page.getByRole("region", { name: "Runtime collection", exact: true }),
  ).toContainText("48 observed calls");
  await page
    .getByRole("button", { name: "Inspect collection coverage", exact: true })
    .click();
  await expect(page.locator(".collection-report")).toContainText(
    "sys.setprofile",
  );
  await expect(page.locator(".collection-report")).toContainText(
    "resume_segments_ignored",
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "Observed b");
  await page.reload();
  await page.getByLabel("Restore saved view").selectOption("Observed b");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "Runtime overlay", exact: true }),
  ).toBeChecked();
  await expect(page.getByLabel("Runtime collection window")).toHaveValue(
    await page
      .getByLabel("Runtime collection window")
      .getByRole("option", { name: /qa-observed-b/ })
      .getAttribute("value"),
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("button", { name: "ui", exact: true }).click();
  await page.getByRole("tab", { name: "Links", exact: true }).click();
  await page
    .locator(".relationship-list button")
    .filter({ hasText: "observed" })
    .first()
    .click();
  await expect(page.locator(".selected-relationship")).toContainText(
    "48 call_count",
  );
  await expect(page.locator(".witness-card").first()).toContainText("observed");
  await page.screenshot({
    path: "output/qa/p54-runtime-overlay.png",
    fullPage: true,
  });
});

test("P5.4 switching to a source-only snapshot disables runtime without a stale request", async ({
  page,
}) => {
  await ready(page);
  await page.getByText("Scope & filters", { exact: true }).click();
  await page
    .getByRole("checkbox", { name: "Runtime overlay", exact: true })
    .check();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByText("Scope & filters", { exact: true }).click();
  const options = page.getByLabel("Repository snapshot").getByRole("option");
  const base = await options
    .filter({ hasText: "fixture-v1" })
    .getAttribute("value");
  await page.getByLabel("Repository snapshot").selectOption(base);
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "Runtime overlay", exact: true }),
  ).not.toBeChecked();
  await expect(
    page.getByRole("checkbox", { name: "Runtime overlay", exact: true }),
  ).toBeDisabled();
});

test("P5.3 every abstraction and breadth preserves a usable workspace and saved scope", async ({
  page,
}) => {
  await ready(page);
  for (const radius of ["Path", "Nearby", "Wider"]) {
    await page
      .getByRole("group", { name: "Context breadth" })
      .getByRole("button", { name: radius, exact: true })
      .click();
    await expect(page.locator(".view-content")).toHaveAttribute(
      "aria-busy",
      "false",
    );
    await expect(
      page
        .getByRole("group", { name: "Context breadth" })
        .getByRole("button", { name: radius, exact: true }),
    ).toHaveAttribute("aria-pressed", "true");
  }
  for (const mode of [
    "repository",
    "directory",
    "file",
    "class",
    "atomic",
    "conceptual",
    "mixed",
  ]) {
    await page.getByLabel("Abstraction grouping").selectOption(mode);
    await expect(page.locator(".view-content")).toHaveAttribute(
      "aria-busy",
      "false",
    );
    await expect(page.locator(".error-banner")).toHaveCount(0);
    await expect(page.locator(".filter-count")).not.toHaveText(
      "0 groups · 0 curves",
    );
  }
  await page.getByLabel("Abstraction grouping").selectOption("file");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "File-level wider");
  await page.reload();
  await page.getByLabel("Restore saved view").selectOption("File-level wider");
  await expect(page.getByLabel("Abstraction grouping")).toHaveValue("file");
  await expect(
    page.getByRole("button", { name: "Wider", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("P5.3 live rules reject malformed reload and retain prior versions", async ({
  page,
}) => {
  await ready(page);
  await page
    .getByRole("button", { name: "Configure rules", exact: true })
    .click();
  const previous = await page.getByLabel("Selected rules model").inputValue();
  await page
    .getByLabel("Rules YAML", { exact: true })
    .fill('version: "1.0"\nworld_policy: banana');
  await page
    .getByRole("button", { name: "Validate and activate rules", exact: true })
    .click();
  await expect(page.locator(".rules-editor [role=status]")).not.toBeEmpty();
  await expect(page.getByLabel("Selected rules model")).toHaveValue(previous);
  const rules =
    'version: "1.0"\nworld_policy: open\ncomponents:\n  - id: Everything\n    selectors: [{repo_id: qa, path_glob: "**"}]\nrules: []\n';
  await page.getByLabel("Rules YAML", { exact: true }).fill(rules);
  await page
    .getByRole("button", { name: "Validate and activate rules", exact: true })
    .click();
  await expect(page.locator(".rules-editor [role=status]")).toContainText(
    "validated and activated",
  );
  await expect(page.getByLabel("Selected rules model")).not.toHaveValue(
    previous,
  );
  await page.getByLabel("Abstraction grouping").selectOption("conceptual");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.locator(".error-banner")).toHaveCount(0);
  await page.getByLabel("Selected rules model").selectOption(previous);
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
});

test("P5.3 outgoing impact keeps original arrows and highlights a grounded path", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "ui/runner.py.run", "function ui/runner.py.run");
  await page.getByLabel("Impact direction").selectOption("outgoing");
  await page
    .getByRole("button", { name: "Find dependencies", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: /dependencies in this result/ }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Highlight / pin path to transform",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("region", { name: "Highlighted witness path" }),
  ).toContainText("ui/runner.py.run → core/logic.py.transform");
  await expect(
    page.getByRole("region", { name: "Highlighted witness path" }),
  ).toContainText("original directed steps");
});

test("P5.3 folded source, documentary context and review overlay remain distinct", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "ui/runner.py.run", "function ui/runner.py.run");
  await page.getByRole("tab", { name: "Investigate", exact: true }).click();
  await page
    .getByRole("button", {
      name: "Open folded source and documents",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Verbatim focal source", exact: true }),
  ).toBeVisible();
  await expect(page.locator(".investigation")).toContainText("return result");
  await expect(
    page.getByRole("heading", {
      name: "Documentary hierarchy T_D",
      exact: true,
    }),
  ).toBeVisible();
  await page.getByText("Source/process evidence card", { exact: true }).click();
  await expect(page.locator(".investigation")).toContainText(
    "Lexical statement order is not an execution sequence",
  );
  await page
    .getByLabel("Review annotation", { exact: true })
    .fill("Review hypothesis only; retain parser certainty");
  await page
    .getByLabel("Review decision", { exact: true })
    .selectOption("accepted");
  await page
    .getByRole("button", { name: "Save review decision", exact: true })
    .click();
  await expect(page.locator(".investigation")).toContainText(
    "accepted: Review hypothesis only",
  );
  await page.getByLabel("Show review overlay", { exact: true }).uncheck();
  await expect(page.locator(".investigation")).not.toContainText(
    "accepted: Review hypothesis only",
  );
  await page.getByLabel("Show review overlay", { exact: true }).check();
  await expect(page.locator(".investigation")).toContainText(
    "canonical facts unchanged",
  );
});

test("P5.3 triage is explicit about locality and documentary search is navigable", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("tab", { name: "Investigate", exact: true }).click();
  await page
    .getByRole("button", { name: "Load review queue", exact: true })
    .click();
  await expect(page.locator(".investigation")).toContainText(
    "DYNAMIC_ATTR_DISPATCH",
  );
  await expect(page.locator(".investigation")).toContainText(
    "unknown target degree is not estimated",
  );
  await page
    .getByLabel("Search intent", { exact: true })
    .selectOption("documentation");
  await page
    .getByRole("searchbox", { name: "Search entities" })
    .fill("Pipeline");
  await expect(page.locator(".search-results")).toContainText("docs/guide.md");
});

test("P5.3 subtype and family scope persist without admitting hidden relationships", async ({
  page,
}) => {
  await ready(page);
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("checkbox", { name: "imports", exact: true }).uncheck();
  await page.getByRole("checkbox", { name: "inherits", exact: true }).uncheck();
  const next = page.waitForResponse(
    (r) =>
      r.url().endsWith("/viewport/frame") &&
      r.request().postDataJSON()?.filter?.families?.length === 0,
  );
  await page.getByRole("checkbox", { name: "Static", exact: true }).uncheck();
  const data = (await (await next).json()).data;
  expect(data.relationships).toEqual([]);
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "No dependency families");
  await page.reload();
  await page
    .getByLabel("Restore saved view")
    .selectOption("No dependency families");
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(
    page.getByRole("checkbox", { name: "Static", exact: true }),
  ).not.toBeChecked();
});

test("P5.3 pins ground an original call bridge and folded source opens its documentary section", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "transform", "function core/logic.py.transform");
  await page.getByRole("button", { name: "Pin entity", exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await searchSelect(page, "ui/runner.py.run", "function ui/runner.py.run");
  await page.getByRole("tab", { name: "Investigate", exact: true }).click();
  await page
    .getByRole("button", { name: "Find bounded call paths", exact: true })
    .click();
  await expect(page.locator(".investigation")).toContainText("original steps");
  await expect(
    page.getByRole("button", {
      name: "Highlight this witness path",
      exact: true,
    }),
  ).toBeVisible();
  await page
    .getByRole("button", {
      name: "Open folded source and documents",
      exact: true,
    })
    .click();
  await expect(
    page.getByRole("heading", { name: "Verbatim focal source", exact: true }),
  ).toBeVisible();
  await page.screenshot({
    path: "output/qa/p53-investigation-dark.png",
    fullPage: true,
  });
  await page
    .getByRole("button", {
      name: "Open documentary section Pipeline",
      exact: true,
    })
    .click();
  await expect(
    page.getByLabel("Document content", { exact: true }),
  ).toContainText("run function uses transform");
});

test("P5.3 conceptual controls and investigation remain accessible in a narrow light layout", async ({
  page,
}) => {
  await ready(page);
  await page.getByLabel("Abstraction grouping").selectOption("conceptual");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page
    .getByRole("button", { name: "Use light theme", exact: true })
    .click();
  await page.screenshot({
    path: "output/qa/p53-conceptual-light.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.getByRole("button", { name: "Inspector", exact: true }).click();
  await page.getByRole("tab", { name: "Investigate", exact: true }).click();
  const result = await new AxeBuilder({ page }).analyze();
  expect(result.violations).toEqual([]);
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth,
    ),
  ).toBe(true);
  await page.screenshot({
    path: "output/qa/p53-investigation-narrow.png",
    fullPage: true,
  });
});

test("relationship visibility presets apply and survive a saved view", async ({
  page,
}) => {
  await ready(page);
  const preset = page.getByRole("combobox", {
    name: "Relationship visibility preset",
  });
  await expect(preset).toHaveValue("exact");
  const internalFrame = page.waitForResponse(
    (r) =>
      r.url().endsWith("/viewport/frame") &&
      r.request().postDataJSON()?.filter?.include_external === false,
  );
  await preset.selectOption("internal_candidates");
  const response = await internalFrame;
  expect(response.request().postDataJSON().filter.resolution_statuses).toEqual([
    "exact",
    "candidate",
  ]);
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "Internal candidate scope");
  await preset.selectOption("all_uncertainty");
  await expect(preset).toHaveValue("all_uncertainty");
  await page
    .getByLabel("Restore saved view")
    .selectOption("Internal candidate scope");
  await expect(preset).toHaveValue("internal_candidates");
  await page.reload();
  await page
    .getByLabel("Restore saved view")
    .selectOption("Internal candidate scope");
  await expect(preset).toHaveValue("internal_candidates");
});

test("open diagnostics recompute when the dependency filter changes", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("button", { name: "ui", exact: true }).click();
  await page.getByText("Advanced diagnostics", { exact: true }).click();
  const outgoing = page
    .locator(".diagnostic-row")
    .filter({ has: page.getByText("outgoing", { exact: true }) })
    .locator("code");
  await expect(outgoing).toHaveText("1.000");
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("checkbox", { name: "tests", exact: true }).check();
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(outgoing).toHaveText("0.926");
});

test("pending scope changes cannot act on the previous frame", async ({
  page,
}) => {
  await ready(page);
  let release, started;
  const gate = new Promise((r) => (release = r)),
    held = new Promise((r) => (started = r));
  await page.route("**/api/v1.1/viewport/frame", async (route) => {
    const response = await route.fetch();
    started();
    await gate;
    await route.fulfill({ response });
  });
  const received = page.waitForResponse((r) =>
    r.url().endsWith("/viewport/frame"),
  );
  try {
    await page
      .getByRole("button", { name: "Reveal nearby detail", exact: true })
      .first()
      .click();
    await held;
    await page.getByRole("button", { name: "Matrix", exact: true }).click();
    await expect(page.locator(".view-content")).toHaveAttribute("inert", "");
    await expect(page.locator(".view-content")).toHaveAttribute(
      "aria-busy",
      "true",
    );
    await expect(
      page.getByRole("button", { name: "Save view", exact: true }),
    ).toBeDisabled();
  } finally {
    release();
  }
  await received;
  await expect(page.locator(".view-content")).not.toHaveAttribute("inert", "");
  await expect(
    page.getByRole("button", { name: "Save view", exact: true }),
  ).toBeEnabled();
  await expect(page.getByRole("table")).toBeVisible();
});

test("canvas picking selects a real group and orbiting preserves selection", async ({
  page,
}) => {
  const THREE = await import("three");
  await ready(page);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/viewport/frame") &&
      r.request().postDataJSON().context_radius === 1,
  );
  await page
    .getByRole("button", { name: "Reveal nearby detail", exact: true })
    .first()
    .click();
  const data = (await (await response).json()).data;
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "Before orbit");
  const before = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("geographer.views.v1")).find(
      (x) => x.name === "Before orbit",
    ),
  );
  const node = data.nodes.find(
    (n) => n.qualified_name === "core" && n.kind === "directory",
  );
  expect(node).toBeDefined();
  const sphere = data.spheres.find((s) => s.node_id === node.id);
  expect(sphere).toBeDefined();
  const canvas = page.getByTestId("architecture-canvas");
  const box = await canvas.boundingBox();
  const camera = new THREE.PerspectiveCamera(
    45,
    box.width / box.height,
    0.01,
    1000000,
  );
  camera.position.set(...before.camera.eye);
  camera.up.set(0, 1, 0);
  camera.lookAt(new THREE.Vector3(...before.camera.target));
  camera.updateMatrixWorld();
  const point = new THREE.Vector3(...sphere.center).project(camera);
  const lockedHeading = await page.locator(".entity-heading h2").innerText();
  const hoverRequests = [];
  const watchHover = (request) => {
    if (request.url().includes("/api/")) hoverRequests.push(request.url());
  };
  page.on("request", watchHover);
  await page.mouse.move(
    box.x + ((point.x + 1) * box.width) / 2,
    box.y + ((1 - point.y) * box.height) / 2,
  );
  await expect(page.getByRole("tooltip")).toBeVisible();
  await expect(page.locator(".entity-heading h2")).toHaveText(lockedHeading);
  page.off("request", watchHover);
  expect(hoverRequests).toEqual([]);
  await canvas.click({
    position: {
      x: ((point.x + 1) * box.width) / 2,
      y: ((1 - point.y) * box.height) / 2,
    },
  });
  const picker = page.getByRole("dialog", {
    name: "Choose entity",
    exact: true,
  });
  await expect
    .poll(async () =>
      (await picker.isVisible())
        ? "picker"
        : await page.locator(".entity-heading h2").innerText(),
    )
    .toMatch(/^(picker|core)$/);
  if (await picker.isVisible())
    await picker.getByRole("button", { name: "core", exact: true }).click();
  await expect(page.locator(".entity-heading h2")).toHaveText("core");
  await page.mouse.move(box.x + box.width * 0.8, box.y + box.height * 0.7);
  await page.mouse.down();
  await page.mouse.move(
    box.x + box.width * 0.8 + 60,
    box.y + box.height * 0.7 + 20,
    { steps: 8 },
  );
  await page.mouse.up();
  await expect(page.locator(".entity-heading h2")).toHaveText("core");
  await save(page, "After orbit");
  const after = await page.evaluate(() =>
    JSON.parse(localStorage.getItem("geographer.views.v1")).find(
      (x) => x.name === "After orbit",
    ),
  );
  expect(
    Math.hypot(...after.camera.eye.map((v, i) => v - before.camera.eye[i])),
  ).toBeGreaterThan(0.01);
});

test.beforeAll(async ({ browser }) => {
  fs.mkdirSync("output/qa", { recursive: true });
  fs.writeFileSync(
    "output/qa/environment.json",
    JSON.stringify(
      {
        browser: browser.version(),
        node: process.version,
        platform: process.platform,
        architecture: process.arch,
        cpu: os.cpus()[0].model,
        memory_bytes: os.totalmem(),
        timestamp: new Date().toISOString(),
        scope: "Isolated extracted two-snapshot fixture, loopback port 8771",
      },
      null,
      2,
    ),
  );
});
test.beforeEach(async ({ page }) => {
  const evidence = { errors: [], external: [], console: [] };
  pageEvidence.set(page, evidence);
  page.on("pageerror", (e) => evidence.errors.push(String(e)));
  page.on("request", (r) => {
    if (
      /^https?:/.test(r.url()) &&
      !r.url().startsWith("http://127.0.0.1:8771/")
    )
      evidence.external.push(r.url());
  });
  page.on("console", (m) => {
    if (
      m.type() === "error" &&
      !m.text().startsWith("Failed to load resource:")
    )
      evidence.console.push(m.text());
  });
});
test.afterEach(async ({ page }, info) => {
  const evidence = pageEvidence.get(page);
  await info.attach("browser-evidence", {
    body: JSON.stringify(evidence),
    contentType: "application/json",
  });
  expect(evidence.errors).toEqual([]);
  expect(evidence.external).toEqual([]);
  expect(evidence.console).toEqual([]);
});

test("changing selection during a source request clears the old loading state", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "transform", "function core/logic.py.transform");
  let release, started;
  const gate = new Promise((r) => (release = r)),
    held = new Promise((r) => (started = r));
  await page.route("**/api/v1/get_entity_content", async (route) => {
    const response = await route.fetch();
    started();
    await gate;
    await route.fulfill({ response });
  });
  try {
    await page
      .getByRole("button", { name: "Inspect source", exact: true })
      .click();
    await held;
    await searchSelect(page, "run", "function ui/runner.py.run");
    await expect(
      page.getByText("Loading evidence…", { exact: true }),
    ).not.toBeVisible();
  } finally {
    release();
  }
});

test("mobile inspector exposes pinning and stores it in saved views", async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  await page.getByRole("button", { name: "Inspector", exact: true }).click();
  await page.getByRole("button", { name: "Pin entity", exact: true }).click();
  await expect(
    page.getByRole("button", { name: "Unpin entity", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await save(page, "Mobile pin");
  expect(
    await page.evaluate(
      () =>
        JSON.parse(localStorage.getItem("geographer.views.v1"))[0].pins.length,
    ),
  ).toBe(1);
});

test("snapshot options remain distinguishable across revisions", async ({
  page,
}) => {
  await ready(page);
  const labels = await page
    .getByLabel("Repository snapshot", { exact: true })
    .getByRole("option")
    .allTextContents();
  expect(labels).toHaveLength(4);
  expect(new Set(labels).size).toBe(4);
  expect(labels.join(" ")).toContain("fixture-v1");
  expect(labels.join(" ")).toContain("fixture-v2");
});

test("empty snapshots explain the next action and refresh after ingestion", async ({
  page,
}) => {
  let empty = true;
  await page.route("**/api/v1/bootstrap", async (route) => {
    if (empty) await route.fulfill({ json: { snapshots: [], models: [] } });
    else await route.continue();
  });
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: "No repository snapshots", exact: true }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Save view", exact: true }),
  ).toBeDisabled();
  empty = false;
  await page
    .getByRole("button", { name: "Refresh snapshots", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("qa");
  await expect(page.locator(".filter-count")).not.toHaveText(
    "0 groups · 0 curves",
  );
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
});

test("clipboard denial is reported without claiming a successful copy", async ({
  page,
}) => {
  await page.addInitScript(() =>
    Object.defineProperty(navigator, "clipboard", {
      value: {
        writeText: () =>
          Promise.reject(new DOMException("Denied", "NotAllowedError")),
      },
    }),
  );
  await ready(page);
  await page.getByRole("button", { name: "Copy ID", exact: true }).click();
  await expect(
    page.getByText(
      "Clipboard unavailable. Select and copy the displayed text directly.",
      { exact: true },
    ),
  ).toBeVisible();
  await expect(
    page.getByText("Entity ID copied", { exact: true }),
  ).not.toBeVisible();
});

for (const viewport of [
  { width: 320, height: 720 },
  { width: 390, height: 844 },
  { width: 768, height: 600 },
  { width: 1280, height: 800 },
]) {
  test(`responsive dark/light and coverage at ${viewport.width}x${viewport.height}`, async ({
    page,
  }, info) => {
    await page.setViewportSize(viewport);
    await ready(page);
    for (const theme of ["dark", "light"]) {
      if (theme === "light")
        await page.getByRole("button", { name: "Use light theme" }).click();
      const scan = await new AxeBuilder({ page }).analyze();
      expect(
        scan.violations.map((v) => ({
          id: v.id,
          targets: v.nodes.map((n) => n.target),
        })),
      ).toEqual([]);
      expect(
        await page.locator("body").evaluate((el) => el.scrollWidth),
      ).toBeLessThanOrEqual(viewport.width);
      await page.screenshot({ path: info.outputPath(theme + ".png") });
    }
    await page.getByRole("button", { name: "Coverage", exact: true }).click();
    const box = await page.locator(".coverage-popover").boundingBox();
    expect(box.x).toBeGreaterThanOrEqual(0);
    expect(box.y).toBeGreaterThanOrEqual(0);
    expect(box.x + box.width).toBeLessThanOrEqual(viewport.width);
    expect(box.y + box.height).toBeLessThanOrEqual(viewport.height);
  });
}

test("search hides stale matches while a newer query is pending", async ({
  page,
}) => {
  await ready(page);
  const search = page.getByRole("searchbox", { name: "Search entities" });
  await search.fill("transform");
  const old = page.getByRole("button", {
    name: "function core/logic.py.transform",
    exact: true,
  });
  await expect(old).toBeVisible();
  let release, started;
  const gate = new Promise((r) => (release = r)),
    held = new Promise((r) => (started = r));
  await page.route("**/api/v1/search_entities", async (route) => {
    if (route.request().postDataJSON().query === "no_such_entity") {
      const response = await route.fetch();
      started();
      await gate;
      await route.fulfill({ response });
    } else await route.continue();
  });
  try {
    await search.fill("no_such_entity");
    await held;
    await expect(old).not.toBeVisible();
  } finally {
    release();
  }
  await expect(
    page.getByText("0 results in this snapshot", { exact: true }),
  ).toBeVisible();
  await search.press("Escape");
  await expect(search).toHaveValue("");
});

test("agent context cannot copy the previous budget while a replacement is pending", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "transform", "function core/logic.py.transform");
  await page.getByRole("tab", { name: "Agent context", exact: true }).click();
  const copy = page.getByRole("button", {
    name: "Copy context JSON",
    exact: true,
  });
  await expect(copy).toBeEnabled();
  let release, started;
  const gate = new Promise((r) => (release = r)),
    held = new Promise((r) => (started = r));
  await page.route("**/api/v1.1/get_architecture_context", async (route) => {
    const response = await route.fetch();
    started();
    await gate;
    await route.fulfill({ response });
  });
  try {
    await page
      .getByRole("combobox", { name: "Context budget", exact: true })
      .selectOption("2048");
    await held;
    await expect(copy).toBeDisabled();
    await expect(page.locator(".agent-json")).not.toContainText(
      '"limit_tokens": 8192',
    );
  } finally {
    release();
  }
});

test("the narrow matrix scrolls independently of its controls", async ({
  page,
}) => {
  await ready(page);
  await page
    .getByRole("button", { name: "Reveal nearby detail", exact: true })
    .first()
    .click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByRole("button", { name: "Matrix", exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  const matrix = page.getByLabel("Scrollable dependency matrix", {
    exact: true,
  });
  expect(await matrix.evaluate((el) => getComputedStyle(el).overflowX)).toBe(
    "auto",
  );
  expect(await matrix.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(
    true,
  );
  await matrix.focus();
  await page.keyboard.press("ArrowRight");
  await expect
    .poll(() => matrix.evaluate((el) => el.scrollLeft))
    .toBeGreaterThan(0);
  await expect(
    page.getByRole("button", { name: "Next matrix columns" }),
  ).toBeInViewport();
});

test("coverage and rule results show actual extraction limits and violations", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("button", { name: "Coverage", exact: true }).click();
  await expect(
    page.getByText("1 parse failures in this snapshot.", { exact: true }),
  ).toBeVisible();
  await expect(page.locator(".coverage-popover")).toContainText(
    "bad/broken.py",
  );
  await page
    .getByRole("button", { name: "Close coverage", exact: true })
    .click();
  await page.getByText("Architecture rules", { exact: true }).click();
  await page
    .getByRole("button", { name: "Check this scope", exact: true })
    .click();
  await expect(
    page.locator(".finding").filter({ hasText: "Fixture boundary violation" }),
  ).toContainText("forbidden present");
  await expect(
    page.locator(".finding").filter({ hasText: "Fixture boundary violation" }),
  ).toHaveCount(1);
});

test("a failed viewport preserves the previous scene and offers a working retry", async ({
  page,
}) => {
  await ready(page);
  const before = await page.locator(".filter-count").innerText();
  let first = true;
  await page.route("**/api/v1.1/viewport/frame", async (route) => {
    if (first) {
      first = false;
      await route.fulfill({
        status: 503,
        json: { error: { message: "Temporary viewport outage" } },
      });
    } else await route.continue();
  });
  await page
    .getByRole("button", { name: "Reveal nearby detail", exact: true })
    .first()
    .click();
  await expect(page.getByRole("alert")).toContainText(
    "Temporary viewport outage",
  );
  await expect(page.locator(".filter-count")).toHaveText(before);
  await page.getByRole("button", { name: "Retry view", exact: true }).click();
  await expect(page.getByRole("alert")).not.toBeVisible();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.locator(".filter-count")).not.toHaveText(before);
  first = true;
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("checkbox", { name: "external", exact: true }).uncheck();
  await page.getByText("Scope & filters", { exact: true }).click();
  await expect(page.getByRole("alert")).toContainText(
    "Temporary viewport outage",
  );
  await page
    .getByRole("button", { name: "Dismiss error", exact: true })
    .click();
  await page
    .getByRole("button", { name: "Retry requested view", exact: true })
    .click();
  await expect(page.locator(".view-content")).not.toHaveAttribute("inert", "");
  await expect(
    page.getByRole("button", { name: "Save view", exact: true }),
  ).toBeEnabled();
});

test("revealing nearby detail reframes the enlarged focus enclosure", async ({
  page,
}) => {
  await ready(page);
  const response = page.waitForResponse(
    (r) =>
      r.url().endsWith("/viewport/frame") &&
      r.request().postDataJSON().context_radius === 1,
  );
  await page
    .getByRole("button", { name: "Reveal nearby detail", exact: true })
    .first()
    .click();
  const data = (await (await response).json()).data;
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await save(page, "Expanded camera");
  const entry = await page.evaluate(
    () => JSON.parse(localStorage.getItem("geographer.views.v1"))[0],
  );
  const sphere = data.spheres.find(
    (s) => (data.ids?.[s.node_id] ?? s.node_id) === entry.focus,
  );
  const distance = Math.hypot(
    ...entry.camera.eye.map((v, i) => v - entry.camera.target[i]),
  );
  expect(distance).toBeGreaterThan(sphere.radius / Math.sin(Math.PI / 8));
});

async function ready(page) {
  await page.goto("/");
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("qa");
  await expect(page.locator(".filter-count")).not.toHaveText(
    "0 groups · 0 curves",
  );
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
}
async function searchSelect(page, name, qualified) {
  await page.getByRole("searchbox", { name: "Search entities" }).fill(name);
  await page.getByRole("button", { name: qualified, exact: true }).click();
}
async function save(page, name) {
  await page.getByRole("button", { name: "Save view", exact: true }).click();
  await page.getByLabel("View name", { exact: true }).fill(name);
  await page.getByRole("button", { name: "Save", exact: true }).click();
}

test("save dialog has an accessible name and returns keyboard focus", async ({
  page,
}) => {
  await ready(page);
  const trigger = page.getByRole("button", { name: "Save view", exact: true });
  await trigger.click();
  await expect(page.getByRole("dialog")).toHaveAccessibleName(
    "Save this workspace",
  );
  const scan = await new AxeBuilder({ page }).analyze();
  expect(scan.violations).toEqual([]);
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog")).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test("mobile drawers support focus and Escape dismissal", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await ready(page);
  const trigger = page.getByRole("button", { name: "Hierarchy", exact: true });
  await trigger.click();
  await expect(
    page.getByRole("button", { name: "Close hierarchy", exact: true }),
  ).toBeFocused();
  await page.keyboard.press("Escape");
  await expect(
    page.getByRole("button", { name: "Close hierarchy" }),
  ).not.toBeVisible();
  await expect(trigger).toBeFocused();
});

test("saving from the matrix preserves the spatial camera through reload", async ({
  page,
}) => {
  await ready(page);
  await page.getByRole("button", { name: "Zoom in", exact: true }).click();
  await page.getByRole("button", { name: "Matrix", exact: true }).click();
  await save(page, "Camera retained");
  const entry = await page.evaluate(
    () => JSON.parse(localStorage.getItem("geographer.views.v1"))[0],
  );
  expect(entry.camera).toBeDefined();
  expect(entry.camera.eye).toHaveLength(3);
  await page.reload();
  await page.getByLabel("Restore saved view").selectOption("Camera retained");
  await expect(
    page.getByRole("button", { name: "Matrix", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
});

test("bootstrap failure can be retried without reloading the page", async ({
  page,
}) => {
  let first = true;
  await page.route("**/api/v1/bootstrap", async (route) => {
    if (first) {
      first = false;
      await route.fulfill({
        status: 503,
        json: { error: "Temporary bootstrap outage" },
      });
    } else await route.continue();
  });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText(
    "Temporary bootstrap outage",
  );
  await page.getByRole("button", { name: /Retry/ }).click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("qa");
  await expect(page.locator(".filter-count")).not.toHaveText(
    "0 groups · 0 curves",
  );
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
});

test("a failed hierarchy branch has a direct retry action", async ({
  page,
}) => {
  let first = true;
  await page.route("**/api/v1/hierarchy?**", async (route) => {
    if (first) {
      first = false;
      await route.fulfill({
        status: 503,
        json: { error: "Temporary hierarchy outage" },
      });
    } else await route.continue();
  });
  await ready(page);
  await expect(
    page.getByText("Temporary hierarchy outage", { exact: true }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: "Retry hierarchy", exact: true })
    .click();
  await expect(
    page.getByRole("button", { name: "Expand core", exact: true }),
  ).toBeVisible();
});

test("invalid persisted view is rejected rather than sending a corrupt request", async ({
  page,
  request,
}) => {
  const boot = await (await request.get("/api/v1/bootstrap")).json(),
    s = boot.snapshots[0];
  await page.addInitScript(
    (entry) =>
      localStorage.setItem("geographer.views.v1", JSON.stringify([entry])),
    {
      version: 1,
      name: "Broken state",
      snapshot_id: s.snapshot_id,
      focus: s.repositories[0].id,
      selected: s.repositories[0].id,
      revealed: [],
      pins: [],
      contextRadius: "corrupt",
      beta: 0.8,
      lens: false,
      view: "list",
      theme: "dark",
      filter: {
        repo_ids: [],
        families: [],
        subtypes: [],
        resolution_statuses: ["exact"],
        include_tests: false,
        include_generated: false,
        include_vendor: false,
        include_external: true,
        runtime_window: null,
      },
    },
  );
  await ready(page);
  await expect(
    page.getByRole("option", { name: "Broken state", exact: true }),
  ).toHaveCount(0);
});

test("matrix evidence is mandatory and pages through all 24 concrete calls", async ({
  page,
}) => {
  await ready(page);
  await page
    .getByRole("button", { name: "Reveal nearby detail", exact: true })
    .first()
    .click();
  await expect(page.locator(".view-content")).toHaveAttribute(
    "aria-busy",
    "false",
  );
  await page.getByRole("button", { name: "Matrix", exact: true }).click();
  const cell = page.getByRole("button", {
    name: /^ui to core: \d+ witnesses$/,
  });
  await expect(cell).toBeVisible();
  await cell.click();
  const picker = page.getByRole("dialog", { name: "Choose relationship" });
  if (await picker.isVisible())
    await picker.getByRole("button", { name: /static · calls/ }).click();
  await page
    .getByRole("button", { name: "Inspect witnesses", exact: true })
    .click();
  await expect(
    page.getByRole("heading", { name: "Concrete witnesses" }),
  ).toBeVisible();
  for (
    let i = 0;
    i < 10 &&
    (await page
      .getByRole("button", {
        name: "Load more witnesses / evidence",
        exact: true,
      })
      .isVisible());
    i++
  ) {
    const response = page.waitForResponse((r) =>
      r.url().endsWith("/inspect_relationship_witnesses"),
    );
    await page
      .getByRole("button", {
        name: "Load more witnesses / evidence",
        exact: true,
      })
      .click();
    await response;
    await expect(
      page.getByText("Loading evidence…", { exact: true }),
    ).not.toBeVisible();
  }
  await expect(
    page.getByRole("button", {
      name: "Load more witnesses / evidence",
      exact: true,
    }),
  ).not.toBeVisible();
  await expect(page.locator(".witness-card")).toHaveCount(24);
  await page
    .getByRole("button", { name: "Read caller source" })
    .first()
    .click();
  await expect(
    page.getByLabel("Source code from the selected snapshot"),
  ).toContainText("def run(data)");
});

test("pinned scope, filters, theme and original snapshot survive saved-view reload", async ({
  page,
}) => {
  await ready(page);
  await searchSelect(page, "transform", "function core/logic.py.transform");
  await page
    .getByRole("button", { name: "Enter / frame", exact: true })
    .click();
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("transform");
  await page
    .getByRole("button", { name: "Pin selection", exact: true })
    .click();
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("checkbox", { name: "tests", exact: true }).check();
  await page.getByText("Scope & filters", { exact: true }).click();
  await page.getByRole("button", { name: "Use light theme" }).click();
  await save(page, "Pinned scope");
  const saved = await page.evaluate(
    () => JSON.parse(localStorage.getItem("geographer.views.v1"))[0],
  );
  expect(saved.pins).toHaveLength(1);
  await page.reload();
  await page.getByLabel("Repository snapshot").selectOption({ index: 1 });
  await page.getByLabel("Restore saved view").selectOption("Pinned scope");
  await expect(page.getByLabel("Repository snapshot")).toHaveValue(
    saved.snapshot_id,
  );
  await expect(page.getByRole("heading", { level: 1 })).toHaveText("transform");
  await expect(
    page.getByRole("button", { name: "Unpin", exact: true }),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("html")).toHaveAttribute("data-theme", "light");
});
