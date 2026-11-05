// Run against the generated, real-data snapshot; no external API or fixtures.
async function testObservations(page, baseURL = "http://127.0.0.1:8766") {
  const checks = [];
  const errors = [];
  const requests = [];
  const origin = new URL(baseURL).origin;
  const atlasURL = baseURL.replace(/\/$/, "") + "/observations/";
  const onError = (error) => errors.push(error.message);
  const onRequest = (request) => requests.push(request.url());
  page.on("pageerror", onError);
  page.on("request", onRequest);
  const ok = (value, label) => {
    if (!value) throw new Error(label);
    checks.push(label);
  };
  const ready = async (countryName) => {
    await page.waitForFunction(
      (name) => {
        const status = document.querySelector("#load-status").textContent;
        return (
          status.includes("historical records loaded") &&
          status.includes(name + ",")
        );
      },
      countryName,
      { timeout: 60000 },
    );
  };
  const downloadSelection = async () => {
    const pending = page.waitForEvent("download", { timeout: 60000 });
    await page.locator("#export-json").click();
    const download = await pending;
    const stream = await download.createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const bytes = Buffer.concat(chunks);
    return { pack: JSON.parse(bytes.toString("utf8")), bytes };
  };
  try {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(atlasURL);
    await ready("Syria");
    await page.waitForFunction(
      () =>
        document
          .querySelector("#indicator-status")
          .textContent.includes("source observations"),
      null,
      { timeout: 60000 },
    );
    ok(
      (await page.locator("#edition-coverage").innerText()).includes("113,656"),
      "Manifest describes the real 113,656-record historical subset",
    );
    ok(
      (await page.locator("#event-rows tr").count()) > 0 &&
        (await page.locator("#event-rows tr").count()) <= 15,
      "The directory renders a bounded page from the loaded records",
    );
    ok(
      (await page.locator("#mapped-count").innerText()).includes("5,263"),
      "Default Syria 2020–2025 selection maps the actual 5,263 records",
    );
    await page.locator("#event-rows button").first().click();
    await page.waitForFunction(
      () =>
        document
          .querySelector("#event-inspector details summary")
          ?.textContent.includes("49 original provider fields"),
      null,
      { timeout: 30000 },
    );
    const inspectorFields = JSON.parse(
      await page.locator("#event-inspector pre").textContent(),
    );
    ok(
      Object.keys(inspectorFields).length === 49 &&
        Object.values(inspectorFields).every(
          (value) => typeof value === "string",
        ),
      "Lazy inspection preserves all 49 original string-valued UCDP fields",
    );
    await page
      .locator("#brief-question")
      .fill(
        "What do these historical records establish, and what evidence is missing?",
      );
    const eventDownload = await downloadSelection();
    const pack = eventDownload.pack;
    ok(
      pack.format === "policy-research-selection/1" &&
        pack.records.length === 200 &&
        eventDownload.bytes.length <= 1024 * 1024,
      "The real event download uses the distinct research-selection contract and both size limits",
    );
    ok(
      pack.counts.matched === 5263 &&
        pack.counts.exported === pack.records.length &&
        pack.counts.truncated === pack.counts.matched > pack.counts.exported,
      "Matched, exported and omitted event counts agree exactly",
    );
    ok(
      pack.records.every(
        (row) =>
          row.kind === "conflict_event" &&
          Object.keys(row.attributes).length === 49,
      ),
      "Downloaded event records carry full original attributes rather than compact plotting fields",
    );
    ok(
      pack.datasets.every(
        (dataset) =>
          Object.keys(dataset).sort().join(",") ===
          "id,license,publisher,sha256,title,url,version",
      ),
      "Every dataset has exactly the seven cross-repository provenance fields",
    );
    await page.locator("#event-type").selectOption("1");
    await page.locator("#location-precision").selectOption("1");
    const filtered = (await downloadSelection()).pack;
    ok(
      filtered.records.length > 0 &&
        filtered.records.every(
          (row) =>
            row.attributes.type_of_violence === "1" &&
            row.attributes.where_prec === "1",
        ) &&
        filtered.filters.events.type_of_violence === "1" &&
        filtered.filters.events.where_prec === "1",
      "Provider category and geographic precision filter both the records and exported filter receipt",
    );
    await page.locator("#network-view").click();
    await page.waitForFunction(
      () => document.querySelectorAll("#network-pairs li").length > 0,
    );
    ok(
      (await page.locator(".network-rule").innerText()).includes(
        "does not mean affiliation",
      ) && (await page.locator("#network-pairs li").count()) <= 8,
      "Recorded opposing-side counts have an explicit relationship limit and text fallback",
    );
    await page.locator("#export-kind").selectOption("indicators");
    const annual = (await downloadSelection()).pack;
    ok(
      annual.records.length === 66 &&
        annual.records.every(
          (row) =>
            row.kind === "country_indicator" &&
            row.attributes.display_unit === "persons",
        ) &&
        !Object.hasOwn(annual.filters, "events") &&
        annual.filters.country_indicators.indicator_code === "SP.POP.TOTL",
      "Annual population values retain their units and never claim event filters were applied",
    );
    ok(
      annual.records.some(
        (row) =>
          row.attributes.obs_status === "" &&
          row.attributes.source_status_interpretation.includes(
            "Blank provider status",
          ),
      ),
      "Blank provider status is preserved with its source interpretation",
    );
    await page.locator("#country").selectOption("LB");
    await page.locator("#country").selectOption("IQ");
    await page.locator("#country").selectOption("JO");
    await ready("Jordan");
    ok(
      (await page.locator("#map-title").innerText()) === "Jordan",
      "Rapid country changes finish on the final country without stale records",
    );
    await page.locator("#country").selectOption("SY");
    await ready("Syria");
    await page.locator("#event-type").selectOption("");
    await page.locator("#location-precision").selectOption("");
    await page.locator("#map-view").click();
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1100 });
      await page.waitForTimeout(100);
      ok(
        await page.evaluate(
          () => document.documentElement.scrollWidth <= innerWidth,
        ),
        "No page overflow at " + width,
      );
      await page.locator("#event-rows button").first().focus();
      await page.keyboard.press("Enter");
      await page.waitForFunction(
        () => document.activeElement?.id === "inspector-title",
      );
      ok(
        await page.locator("#event-inspector").isVisible(),
        "Keyboard directory selection opens the source inspector at " + width,
      );
    }
    const external = requests.filter(
      (url) =>
        !url.startsWith("blob:") &&
        !url.startsWith("data:") &&
        new URL(url).origin !== origin,
    );
    ok(
      external.length === 0,
      "All requested assets and JSON remain on the atlas origin; no external API calls",
    );
    ok(errors.length === 0, "No browser JavaScript errors");
    return { passed: true, checks, errors };
  } finally {
    page.off("pageerror", onError);
    page.off("request", onRequest);
  }
}
