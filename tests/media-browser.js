async function testMedia(page, baseURL = "http://127.0.0.1:8766") {
  const errors = [],
    checks = [],
    requests = [];
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("request", (request) => requests.push(request.url()));
  const ok = (value, label) => {
    if (!value) throw Error(label);
    checks.push(label);
  };
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(baseURL + "/sources/");
    await page
      .getByRole("button", { name: "Assess framing", exact: true })
      .click();
    ok(
      !(await page.locator("#lineage-viewport").isVisible()) &&
        (await page.locator(".lineage-edge").count()) === 0,
      "An empty worksheet draws no invented report relationships",
    );
    await page
      .locator("#assessment-question")
      .fill("How is this synthetic claim described?");
    const fields = page.locator("#assessment-reports textarea");
    await fields.nth(1).fill("Synthetic selected passage A.");
    await page
      .getByLabel("Report URL", { exact: true })
      .nth(0)
      .fill("https://example.org/report-a");
    await page
      .getByLabel("Passage locator · Who speaks?", { exact: true })
      .nth(0)
      .fill("Paragraph 2, entered locator");
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
    ok(
      (await page.locator('[data-node-kind="reference"]').count()) === 1 &&
        (await page.locator('[data-relation="named_upstream"]').count()) === 2,
      "Two entered upstream relationships converge on one canonical reference",
    );
    const quoteA = page
      .locator('[data-node-kind="quotations"]')
      .filter({ hasText: "Report A" });
    await quoteA.focus();
    await page.keyboard.press("Enter");
    ok(
      (await quoteA.getAttribute("aria-pressed")) === "true" &&
        (await page.locator("#lineage-inspector blockquote").textContent()) ===
          "Synthetic selected passage A." &&
        (await page.locator("#lineage-inspector").textContent()).includes(
          "Paragraph 2, entered locator",
        ),
      "Keyboard selection exposes exact entered wording and its locator",
    );
    ok(
      (await page
        .locator('[data-from="analyst-reading"], [data-to="analyst-reading"]')
        .count()) === 0 &&
        (await page.locator('[data-node-kind="interpretation"]').count()) === 1,
      "Analyst interpretation is separate and has no fabricated support edge",
    );
    const reference = page.locator('[data-node-kind="reference"]');
    await reference.focus();
    await page.keyboard.press("Space");
    ok(
      (await reference.getAttribute("aria-pressed")) === "true" &&
        (await page.locator("#lineage-inspector").textContent()).includes(
          "?utm_source=first",
        ),
      "Shared-reference inspector preserves the original entered URL forms",
    );
    await page
      .getByRole("button", { name: "Clear selection", exact: true })
      .click();
    ok(
      !(await page.locator("#lineage-inspector").isVisible()),
      "Clear selection closes the record inspector",
    );
    const quotationB = page
      .getByLabel("Selected passage · Who speaks?", { exact: true })
      .nth(1);
    const literal =
      'Literal <img src=x onerror="window.untrustedExecuted=1"> text.\nSecond line.';
    await quotationB.fill(literal);
    const quoteB = page
      .locator('[data-node-kind="quotations"]')
      .filter({ hasText: "Report B" });
    await quoteB.click();
    ok(
      (await page.locator("#lineage-inspector blockquote").textContent()) ===
        literal &&
        (await page.locator("#lineage-inspector img").count()) === 0 &&
        !(await page.evaluate(() => window.untrustedExecuted)),
      "Quotation markup and newlines remain inert exact source data",
    );
    await quotationB.fill("Synthetic selected passage B.");
    await upstream.nth(1).fill("https://example.org/different-document");
    ok(
      (await page.locator('[data-node-kind="reference"]').count()) === 2,
      "Different documents on one host are not merged into a shared reference",
    );
    await upstream.nth(0).fill("javascript:alert(1)");
    await upstream.nth(1).fill("");
    ok(
      (await page.locator('[data-node-kind="reference"]').count()) === 0 &&
        (await page.locator('[data-relation="named_upstream"]').count()) === 0,
      "Unsafe and empty upstream URLs draw no reference or relationship",
    );
    await upstream.nth(0).fill("https://example.org/original?utm_source=first");
    await upstream.nth(1).fill("https://example.org/original#section");
    ok(
      (await page.locator('[data-node-kind="reference"]').count()) === 1,
      "Fragment and tracking variants merge only in the derived view",
    );
    await quoteA.click();
    await fields.nth(1).fill("");
    ok(
      (await page
        .locator('[data-node-kind="quotations"]')
        .filter({ hasText: "Report A" })
        .count()) === 0 &&
        !(await page.locator("#lineage-inspector").isVisible()),
      "Removing selected wording clears its node and stale inspector",
    );
    await fields.nth(1).fill("Synthetic selected passage A.");
    await page.locator("#lineage-text summary").click();
    ok(
      (await page.locator("#lineage-connections").textContent()).includes(
        "entered upstream reference",
      ) &&
        (await page.locator("#lineage-connections").textContent()).includes(
          "no support edge",
        ),
      "Text fallback describes entered relationships and the detached interpretation",
    );
    ok(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "The entered trail scrolls within its panel without page overflow at " +
        width,
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
        .locator('[data-node-kind="quotations"]')
        .filter({ hasText: "Report A" })
        .count()) === 0 &&
        (await page
          .locator('[data-node-kind="quotations"]')
          .filter({ hasText: "Report B" })
          .count()) === 1,
      "Changing a publisher clears only its entered evidence trail",
    );
    ok(
      (await page.locator('[data-relation="named_upstream"]').count()) === 1 &&
        !(await page.locator("#assessment-lineage").textContent()).includes(
          "same upstream URL",
        ),
      "A removed report does not leave a stale shared-reference claim",
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
  ok(
    requests.every((url) => new URL(url).hostname === "127.0.0.1"),
    "Entered source text and URLs trigger no external requests",
  );
  ok(errors.length === 0, "No uncaught browser errors");
  return { passed: checks.length, errors };
}
