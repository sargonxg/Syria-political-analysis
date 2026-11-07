// Run only against an explicitly enabled same-origin research API and real data.
// Local SQLite-adapter evidence is labelled separately from deployed D1 evidence.
async function testObservationsDatabase(
  page,
  baseURL = "http://127.0.0.1:8790",
) {
  const checks = [],
    errors = [],
    requests = [];
  const onError = (error) => errors.push(error.message);
  const onRequest = (request) => requests.push(request.url());
  const ok = (value, label) => {
    if (!value) throw new Error(label);
    checks.push(label);
  };
  const readResponse = async (pending) => {
    const response = await pending;
    const failure = await response.finished();
    if (failure) throw new Error("Research API response did not finish");
    return response.json();
  };
  page.on("pageerror", onError);
  page.on("request", onRequest);
  try {
    await page.setViewportSize({ width: 1440, height: 1100 });
    await page.goto(baseURL.replace(/\/$/, "") + "/observations/");
    await page.waitForFunction(
      () =>
        document.querySelector('#data-source [value="database"]').disabled ===
        false,
      null,
      { timeout: 60000 },
    );
    ok(
      (await page.locator("#data-source").inputValue()) === "static",
      "An available database does not silently replace the static snapshot",
    );
    ok(
      requests.every((url) => !new URL(url).pathname.startsWith("/api/research")),
      "Opening the configured atlas makes no database probes until Database is explicitly selected",
    );
    const firstResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/research/events?") &&
        response.status() === 200,
    );
    await page.locator("#data-source").selectOption("database");
    const first = await readResponse(firstResponse);
    await page.waitForFunction(
      () =>
        document
          .querySelector("#load-status")
          .textContent.includes("Current page only."),
      null,
      { timeout: 60000 },
    );
    ok(
      first.records.length === first.returned &&
        first.returned <= 200 &&
        first.matched >= first.returned,
      "The actual server result is bounded and declares global matched versus page-returned counts",
    );
    ok(
      (await page.locator("#connection-badge").innerText()) ===
        (first.backend === "sqlite"
          ? "Local SQLite query"
          : "D1 database query"),
      "The browser distinguishes local SQLite from D1",
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
    ok(
      Object.keys(
        JSON.parse(await page.locator("#event-inspector pre").textContent()),
      ).length === 49 &&
        (await page.locator("#event-inspector").innerText()).includes(
          "not a static-manifest transport verification",
        ),
      "Database detail retains 49 fields and discloses its different verification basis",
    );
    await page.locator("#actor-search").fill("SDF");
    const actorResponse = page.waitForResponse(
      (response) =>
        response.url().includes("/api/research/events?") &&
        response.url().includes("actor=sdf") &&
        response.status() === 200,
    );
    await page.locator("#apply-query").click();
    const actor = await readResponse(actorResponse);
    await page.waitForFunction(
      () =>
        document.querySelector("#map-card").getAttribute("aria-busy") ===
        "false",
    );
    const pending = page.waitForEvent("download", { timeout: 60000 });
    await page.locator("#export-json").click();
    const stream = await (await pending).createReadStream();
    const chunks = [];
    for await (const chunk of stream) chunks.push(chunk);
    const bytes = Buffer.concat(chunks),
      pack = JSON.parse(bytes.toString("utf8"));
    ok(
      pack.records.length > 0 &&
        pack.records.every(
          (row) =>
            Object.keys(row.attributes).length === 49 &&
            (row.attributes.side_a + " " + row.attributes.side_b)
              .toLowerCase()
              .includes("sdf"),
        ),
      "A real server actor query exports original fields for the matching recorded sides",
    );
    ok(
      pack.counts.matched === actor.matched &&
        pack.counts.exported === pack.records.length &&
        pack.counts.truncated === pack.counts.matched > pack.counts.exported &&
        bytes.length <= 1024 * 1024 &&
        pack.filters.events.query_source === "database" &&
        pack.filters.events.database_backend === actor.backend,
      "Export counts, size, backend and snapshot receipt describe the bounded database selection",
    );
    if (actor.has_more) {
      const nextResponse = page.waitForResponse((response) => response.url().includes("/api/research/events?") && response.status() === 200);
      await page.locator("#database-next").click();
      const next = await readResponse(nextResponse);
      await page.waitForFunction(
        () =>
          document
            .querySelector("#database-page-status")
            .textContent.includes("Database page 2"),
        null,
        { timeout: 60000 },
      );
      ok(next.matched === null && next.count_scope === "not_requested" && (await page.locator("#database-page-status").innerText()).includes(`${new Intl.NumberFormat("en").format(actor.matched)} matched`),
        "Continuation skips the count query and retains the exact first-page count bound to the same filters and snapshot");
    }
    const outage = async (route) =>
      route.fulfill({
        status: 503,
        contentType: "application/json",
        body: JSON.stringify({
          status: "unavailable",
          message: "Deliberate browser-test outage",
        }),
      });
    await page.route("**/api/research/events?**", outage);
    await page.locator("#apply-query").click();
    await page.waitForFunction(() =>
      document
        .querySelector("#load-status")
        .textContent.includes("Database query failed"),
    );
    ok(
      (await page.locator("#data-source").inputValue()) === "database" &&
        (await page.locator("#event-rows button").count()) === 0 &&
        (await page.locator("#load-status").innerText()).includes(
          "No static results have replaced it",
        ),
      "A chosen database failure clears stale results and never silently falls back",
    );
    await page.unroute("**/api/research/events?**", outage);
    let quotaCalls = 0;
    const retryAt = new Date();
    retryAt.setUTCHours(24, 0, 0, 0);
    const quota = async (route) => {
      quotaCalls++;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({
        status: "unavailable", error: { code: "DB_QUOTA_EXHAUSTED", message: "Synthetic quota outage: choose Verified static snapshot." },
        retry_at: retryAt.toISOString(),
      }) });
    };
    await page.route("**/api/research/**", quota);
    await page.locator("#apply-query").click();
    await page.waitForFunction(() => document.querySelector("#load-status").textContent.includes("Synthetic quota outage"));
    await page.locator("#retry-load").click();
    await page.waitForFunction(() => document.querySelector("#load-status").textContent.includes("paused until"));
    ok(quotaCalls === 1 && (await page.locator("#event-rows button").count()) === 0,
      "A typed quota outage prevents repeated API calls and keeps the failed database selection empty");
    await page.reload();
    await page.waitForFunction(() => document.querySelector('#data-source [value="database"]').disabled === false);
    await page.locator("#data-source").selectOption("database");
    await page.waitForFunction(() => document.querySelector("#load-status").textContent.includes("paused until"));
    ok(quotaCalls === 1, "Per-tab quota backoff survives reload without probing D1 or storing research filters");
    await page.unroute("**/api/research/**", quota);
    await page.locator("#data-source").selectOption("static");
    await page.waitForFunction(
      () =>
        document
          .querySelector("#load-status")
          .textContent.includes("historical records loaded") &&
        !document
          .querySelector("#load-status")
          .textContent.includes("Current page only."),
      null,
      { timeout: 60000 },
    );
    ok(
      (await page.locator("#connection-badge").innerText()) ===
        "Static snapshot",
      "The user can explicitly return to verified static files after an outage",
    );
    ok(
      requests.every(
        (url) =>
          url.startsWith("data:") ||
          url.startsWith("blob:") ||
          new URL(url).origin === new URL(baseURL).origin,
      ),
      "The database flow makes no cross-origin API requests",
    );
    ok(
      errors.length === 0,
      "No browser JavaScript errors in the database flow",
    );
    return { passed: true, checks, errors };
  } finally {
    page.off("pageerror", onError);
    page.off("request", onRequest);
  }
}
