// Synthetic local/CI browser verification. No real keys, people or incident claims.
async function testDesk(page) {
  const checks = [];
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const ok = (v, l) => {
    if (!v) throw new Error(l);
    checks.push(l);
  };
  await page.context().clearCookies();
  await page.goto("http://127.0.0.1:8770/");
  // Accept synthetic draft-discard prompts without opening a runner modal.
  await page.evaluate(() => {
    window.confirm = () => true;
  });
  await page
    .locator("#access-key")
    .fill("test-only-not-a-deployment-key-00000000");
  await page.locator("#login-form button").click();
  await page.locator("#workspace").waitFor({ state: "visible" });
  const caseName = "Synthetic browser QA " + Date.now();
  await page.getByText("Create a case", { exact: true }).click();
  await page.locator("#case-title").fill(caseName);
  await page.locator("#case-form button").click();
  await page.waitForFunction(
    (name) =>
      document.querySelector("#case option:checked")?.textContent === name &&
      !document.getElementById("case-desk").hidden,
    caseName,
  );
  ok(
    (await page.locator("#record-list").innerText()).includes(
      "No records match",
    ),
    "Empty case state",
  );
  const create = async (kind, title, body = "", prepare = null) => {
    await page.locator("#new-record").click();
    await page.locator("#record-kind").selectOption(kind);
    await page.locator("#record-title").fill(title);
    await page.locator("#record-body").fill(body);
    if (prepare) await prepare();
    await page.locator("#save-record").click();
    await page.waitForFunction(() =>
      document
        .getElementById("save-state")
        .textContent.startsWith("Saved revision"),
    );
    ok(
      (await page.locator("#record-heading").innerText()) === title,
      "Create " + kind,
    );
  };
  await create("source", "Synthetic source", "Fixture only", async () => {
    await page.locator("#record-url").fill("https://example.org/source");
  });
  const sourceId = await page.evaluate(async () => {
    const c = document.getElementById("case").value;
    return (
      await (await fetch("/api/cases/" + c + "/records?kind=source")).json()
    ).items[0].id;
  });
  await create(
    "document",
    "Synthetic document",
    "A public report describes a proposal. Implementation remains unconfirmed.",
    async () => {
      await page.locator("#source-id").selectOption(sourceId);
      await page.locator("#published-on").fill("2020-01-01");
      await page.locator("#reviewed-on").fill("2026-11-02");
    },
  );
  const documentId = await page.evaluate(async () => {
    const c = document.getElementById("case").value;
    return (
      await (await fetch("/api/cases/" + c + "/records?kind=document")).json()
    ).items[0].id;
  });
  await page.locator("#new-record").click();
  await page.locator("#record-kind").selectOption("claim");
  await page.locator("#record-title").fill("Synthetic attributed claim");
  await page.locator("#document-id").selectOption(documentId);
  await page.locator("#excerpt").fill("Invented excerpt");
  await page.locator("#locator").fill("Sentence 1");
  await page.locator("#save-record").click();
  await page.waitForFunction(() =>
    document
      .getElementById("record-error")
      .textContent.includes("exact claim excerpt"),
  );
  ok(
    (await page.locator("#excerpt").inputValue()) === "Invented excerpt",
    "Invalid citation preserves draft",
  );
  await page.locator("#excerpt").fill("A public report describes a proposal.");
  await page.locator("#confidence").selectOption("low");
  await page
    .locator("#confidence-reason")
    .fill("One synthetic fixture; no corroboration.");
  await page.locator("#save-record").click();
  await page.waitForFunction(
    () =>
      document.getElementById("save-state").textContent === "Saved revision 1",
  );
  ok(true, "Claim saves exact cited excerpt and confidence rationale");
  await create(
    "note",
    "Synthetic assessment",
    "Evidence: proposal only.\nAssessment: unresolved.\nAlternative: reporting error.\nGap: original implementation record.",
    async () => {
      await page.locator("#links").selectOption(documentId);
    },
  );
  for (const [kind, title] of [
    ["actor", "Synthetic institution"],
    ["event", "Synthetic research event"],
    ["theme", "Synthetic governance theme"],
  ])
    await create(kind, title, "Fixture only; no real-world claim.");
  await page.locator("#search").fill("Synthetic assessment");
  await page.waitForFunction(
    () => document.querySelectorAll(".record-link").length === 1,
  );
  await page.locator(".record-link").click();
  await page.waitForFunction(
    () =>
      document.getElementById("record-heading").textContent ===
      "Synthetic assessment",
  );
  await page.locator("#record-body").fill("Second saved assessment.");
  await page.locator("#save-record").click();
  await page.waitForFunction(
    () =>
      document.getElementById("save-state").textContent === "Saved revision 2",
  );
  await page.locator("#record-body").fill("Third saved assessment.");
  await page.locator("#save-record").click();
  await page.waitForFunction(
    () =>
      document.getElementById("save-state").textContent === "Saved revision 3",
  );
  await page.locator("#history-panel summary").click();
  await page.waitForFunction(
    () => document.querySelectorAll("#history article").length === 3,
  );
  ok(true, "Repeated edits retain three revisions");
  // A second authenticated request simulates a stale browser tab.
  const current = await page.evaluate(async () => {
    const c = (await (await fetch("/api/cases")).json()).items.find(
      (c) =>
        c.title ===
        document.getElementById("case").selectedOptions[0].textContent,
    );
    return (
      await (
        await fetch("/api/cases/" + c.id + "/records?q=Synthetic%20assessment")
      ).json()
    ).items[0];
  });
  const payload = Object.fromEntries(
    [
      "kind",
      "title",
      "body",
      "url",
      "source_id",
      "document_id",
      "excerpt",
      "locator",
      "published_on",
      "reviewed_on",
      "event_on",
      "confidence",
      "confidence_reason",
      "tags",
      "links",
    ].map((k) => [k, current[k]]),
  );
  const response = await page.request.put(
    "http://127.0.0.1:8770/api/records/" + current.id,
    {
      headers: { "X-Desk-Request": "1" },
      data: { ...payload, body: "Other tab update.", revision: 3 },
    },
  );
  ok(response.ok(), "Concurrent edit fixture saved");
  await page.locator("#record-body").fill("Unsaved stale draft.");
  await page.locator("#save-record").click();
  await page.waitForFunction(() =>
    document.getElementById("record-error").textContent.includes("changed"),
  );
  ok(
    (await page.locator("#record-body").inputValue()) ===
      "Unsaved stale draft.",
    "409 preserves draft",
  );
  await page.locator("#reload-record").click();
  await page.waitForFunction(
    () => document.getElementById("record-body").value === "Other tab update.",
  );
  await page.locator("#search").fill("no such fixture");
  await page.waitForFunction(() =>
    document
      .getElementById("result-count")
      .textContent.startsWith("0 matching"),
  );
  ok(
    (await page.locator("#record-list").innerText()).includes("No records"),
    "Search no-results feedback",
  );
  await page.locator("#search").fill("");
  await page.locator("#kind-filter").selectOption("document");
  await page.waitForFunction(
    () => document.querySelectorAll(".record-link").length === 1,
  );
  await page.locator(".record-link").click();
  await page.waitForFunction(
    () =>
      document.getElementById("record-heading").textContent ===
      "Synthetic document",
  );
  ok(
    (await page.locator("#backlinks").innerText()).includes(
      "Synthetic attributed claim",
    ),
    "Document backlinks include citation",
  );
  const graphButton = page.locator("#record-graph [role=button]").first();
  await graphButton.focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(
    () => document.activeElement.id === "record-title",
  );
  ok(true, "Graph record keyboard control preserves focus");
  const dl = page.waitForEvent("download");
  await page.locator("#export").click();
  const exportFile = await dl;
  await exportFile.saveAs("output/playwright/desk-case.json");
  ok(
    exportFile.suggestedFilename() === "analysis-case.json",
    "Case export downloads",
  );
  for (const width of [320, 768, 1440]) {
    await page.setViewportSize({ width, height: 1000 });
    ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "No page overflow at " + width,
    );
  }
  await page.locator("#theme").click();
  ok(
    await page.locator("body").evaluate((e) => e.classList.contains("dark")),
    "Dark theme works",
  );
  await page.locator("#theme").click();
  await page.screenshot({ path: "output/playwright/desk-mobile.png" });
  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.screenshot({ path: "output/playwright/desk-desktop.png" });
  await page.reload();
  await page.locator("#workspace").waitFor({ state: "visible" });
  ok(
    (await page.locator("#case").innerText()).includes("Synthetic browser QA"),
    "Reload retains authenticated database cases",
  );
  await page.locator("#logout").click();
  await page.locator("#login-panel").waitFor({ state: "visible" });
  ok(
    (await page.request.get("http://127.0.0.1:8770/api/cases")).status() ===
      401,
    "Logout protects direct API",
  );
  ok(errors.length === 0, "No uncaught browser JavaScript errors");
  return { passed: checks.length, checks, errors };
}
