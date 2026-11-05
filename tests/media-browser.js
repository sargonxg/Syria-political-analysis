async function testMedia(page) {
  const errors = [],
    checks = [];
  page.on("pageerror", (e) => errors.push(e.message));
  const ok = (value, label) => {
    if (!value) throw Error(label);
    checks.push(label);
  };
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto("http://127.0.0.1:8766/sources/");
    await page
      .getByRole("button", { name: "Assess framing", exact: true })
      .click();
    await page
      .locator("#assessment-question")
      .fill("How is this synthetic claim described?");
    const fields = page.locator("#assessment-reports textarea");
    await fields.nth(1).fill("Synthetic selected passage A.");
    await page
      .locator("#assessment-interpretation")
      .fill("An unreviewed test interpretation.");
    const upstream = page.getByLabel(
      "Upstream document, wire or statement URL",
      { exact: true },
    );
    await upstream.nth(0).fill("https://example.org/original?utm_source=first");
    await upstream.nth(1).fill("https://example.org/original");
    await page.waitForFunction(() =>
      document
        .querySelector("#assessment-lineage")
        .textContent.includes("same upstream URL"),
    );
    ok(
      true,
      "Shared entered reference is disclosed without a corroboration claim",
    );
    let pending = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Export context JSON", exact: true })
      .click();
    let chunks = [];
    for await (const chunk of await (await pending).createReadStream())
      chunks.push(chunk);
    const exported = JSON.parse(Buffer.concat(chunks).toString());
    ok(
      exported.format === "media-framing-assessment/1" &&
        exported.human_review_recorded === false,
      "Unreviewed comparison contract",
    );
    ok(
      exported.reports[0].evidence.attribution.passage ===
        "Synthetic selected passage A.",
      "Selected passage keeps its publisher attribution",
    );
    ok(
      exported.assessment.interpretation ===
        "An unreviewed test interpretation.",
      "Interpretation stays separate",
    );
    await page.evaluate((value) => {
      window.lastMediaExport = value;
    }, exported);
    if (width === 1440) {
      await page.evaluate(() => {
        window.originalMediaDigest = crypto.subtle.digest.bind(crypto.subtle);
        crypto.subtle.digest = (...args) =>
          new Promise((resolve) => {
            window.releaseMediaDigest = () =>
              resolve(window.originalMediaDigest(...args));
          });
      });
      const raceDownload = page.waitForEvent("download");
      await page
        .getByRole("button", { name: "Export context JSON", exact: true })
        .click();
      await page.waitForFunction(
        () => typeof window.releaseMediaDigest === "function",
      );
      await page.locator("#assessment-source-a").selectOption("daraj");
      await page
        .getByLabel("Your interpretation", { exact: true })
        .fill("A later note.");
      await page.evaluate(() => {
        window.releaseMediaDigest();
        crypto.subtle.digest = window.originalMediaDigest;
      });
      const raceChunks = [];
      for await (const chunk of await (await raceDownload).createReadStream())
        raceChunks.push(chunk);
      const raced = JSON.parse(Buffer.concat(raceChunks).toString());
      ok(
        raced.reports[0].source_id === exported.reports[0].source_id &&
          raced.reports[0].evidence.attribution.passage ===
            "Synthetic selected passage A.",
        "Export captures the publisher and passage before asynchronous hashing",
      );
      ok(
        raced.assessment.interpretation ===
          "An unreviewed test interpretation.",
        "Export captures one consistent assessment revision",
      );
      await page
        .getByLabel("Your interpretation", { exact: true })
        .fill("An unreviewed test interpretation.");
    }
    await page.locator("#assessment-source-a").selectOption("daraj");
    ok(
      (await fields.nth(1).inputValue()) === "",
      "A new publisher does not inherit earlier quotations",
    );
    ok(
      (await page
        .getByLabel("Your interpretation", { exact: true })
        .inputValue()) === "An unreviewed test interpretation.",
      "Explicit analyst notes are retained separately",
    );
    await page
      .getByRole("button", { name: "Data & tools", exact: true })
      .click();
    ok(
      (await page.locator(".resource-card").count()) === 8,
      "Eight separately typed resource references",
    );
    ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "No overflow at " + width,
    );
    await page
      .getByRole("button", { name: "Assess framing", exact: true })
      .click();
    await page.screenshot({
      path: "output/playwright/media-" + width + ".png",
      fullPage: true,
    });
  }
  ok(errors.length === 0, "No uncaught browser errors");
  return { passed: checks.length, errors };
}
