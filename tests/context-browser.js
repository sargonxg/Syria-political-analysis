// Run against the generated public snapshot. No private case data or live collection.
async function testContext(page) {
  const checks = [],
    errors = [],
    network = [];
  const screenshotRoot =
    typeof process !== "undefined" &&
    process.env.CONTEXT_CAPTURE_SCREENSHOTS === "1"
      ? "docs/images"
      : "output/playwright";
  const ok = (value, label) => {
    if (!value) throw new Error(label);
    checks.push(label);
  };
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("request", (request) => network.push(request.url()));
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("http://127.0.0.1:8766/");
    await page
      .getByRole("heading", { name: "Middle East context desk", exact: true })
      .waitFor();
    const original = await page.locator("#context-data").textContent();
    const pack = JSON.parse(original);
    ok(
      pack.format === "policy-context-layers/1",
      "Actual source-qualified context format",
    );
    ok(
      (await page.locator(".layer-choice").count()) === 7,
      "Seven selectable context layers",
    );
    await page
      .getByRole("heading", {
        name: "A dated normative expression",
        exact: true,
      })
      .waitFor();
    ok(
      (await page.locator("#inspector").innerText()).includes("false"),
      "Normative statement does not assert implementation or human review",
    );
    const selected = await page.locator("#inspector .record-copy").innerText();
    await page
      .getByRole("button", { name: "Add to cited brief", exact: true })
      .click();
    await page
      .getByRole("searchbox", { name: "Find a record" })
      .fill("nonexistent-record-908117");
    ok(
      (await page.locator("#graph .graph-node").count()) === 0,
      "Search filters the graph without inventing matches",
    );
    await page.getByRole("button", { name: "Reset view", exact: true }).click();
    ok(
      (await page.locator("#graph .graph-node").count()) ===
        pack.records.length,
      "Reset restores the real record count",
    );
    await page
      .getByRole("button", { name: "Build a brief", exact: true })
      .click();
    await page
      .getByLabel("Your interpretation", { exact: true })
      .fill("Provisional browser-test assessment.");
    await page
      .getByLabel("An alternative explanation", { exact: true })
      .fill("An alternative remains open.");
    let pending = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Download full context JSON", exact: true })
      .click();
    const download = await pending;
    const stream = await download.createReadStream(),
      chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const exported = JSON.parse(Buffer.concat(chunks).toString());
    ok(
      JSON.stringify(exported.records) === JSON.stringify(pack.records),
      "JSON preserves every original record and qualification",
    );
    ok(
      exported.assessment.interpretation ===
        "Provisional browser-test assessment.",
      "Authored assessment is a separate layer",
    );
    ok(
      exported.assessment.selected_record_ids.length === 1,
      "Selection retained without dropping unselected evidence",
    );
    pending = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Download cited brief", exact: true })
      .click();
    const briefStream = await (await pending).createReadStream(),
      briefChunks = [];
    for await (const chunk of briefStream) briefChunks.push(chunk);
    const brief = Buffer.concat(briefChunks).toString();
    ok(
      brief.includes(selected) &&
        brief.includes("Qualification:") &&
        brief.includes("Operative paragraph"),
      "Cited Markdown retains selected source and its paragraph locator",
    );
    ok(
      brief.includes("## Analyst interpretation") &&
        brief.includes("An alternative remains open."),
      "Brief keeps interpretation and alternatives separate",
    );
    ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "No page overflow at " + width,
    );
    await page
      .getByRole("button", { name: "Explore layers", exact: true })
      .click();
    await page.screenshot({
      path:
        screenshotRoot +
        "/context-" +
        (width === 1440 ? "desktop" : "mobile") +
        ".png",
      fullPage: width === 1440,
    });
  }
  ok(errors.length === 0, "No uncaught browser errors");
  ok(
    network.every((url) =>
      /^http:\/\/127\.0\.0\.1:8766\/(?:$|favicon.ico$)/.test(url),
    ),
    "Snapshot requires no API, tracker or remote asset",
  );
  return { passed: checks.length, checks, errors };
}
