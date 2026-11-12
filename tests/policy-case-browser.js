// Run against the generated local public-domain example, never private analyst data.
async function testPolicyCase(page) {
  const base = (typeof process !== "undefined" && process.env.POLICY_CASE_BASE_URL) || "http://127.0.0.1:8768";
  const checks = [], errors = [], network = [];
  const ok = (value, label) => { if (!value) throw new Error(label); checks.push(label); };
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => network.push(request.url()));
  for (const width of [1440, 390, 320]) {
    await page.setViewportSize({ width, height: 1000 });
    await page.goto(base, { waitUntil: "networkidle" });
    await page.getByRole("heading", { level: 1 }).waitFor();
    const question = page.getByRole("combobox", { name: "Research question", exact: true });
    for (const task of ["action-plan", "memoranda", "review", "limits"]) {
      await question.selectOption(task);
      const panel = page.locator(`[data-task="${task}"]`);
      ok(await panel.isVisible(), `${width} ${task}: selected task opens`);
      ok(await page.locator("[data-task]:visible").count() === 1, "One task at a time");
      ok((await panel.innerText()).toLowerCase().includes("unreviewed draft"), "Draft state remains visible");
      if (task !== "limits") ok((await panel.innerText()).includes("appropriations-limit"), "Legal/funding dependency stays attached");
      const pending = page.waitForEvent("download");
      await panel.getByRole("link", { name: "Context JSON", exact: true }).click();
      const download = await pending;
      const stream = await download.createReadStream();
      const chunks = []; for await (const chunk of stream) chunks.push(chunk);
      const value = JSON.parse(Buffer.concat(chunks).toString("utf8"));
      ok(value.context.format === "policy-document-knowledge/1", "Versioned context is downloadable");
      ok(Buffer.byteLength(value.prompt, "utf8") === value.prompt_bytes, "Exact complete prompt byte accounting");
      ok(value.context.assertions.every(a => !a.implementation_established && !a.human_review_recorded), "No review or implementation promotion");
    }
    await question.selectOption("action-plan");
    const panel = page.locator('[data-task="action-plan"]');
    await panel.getByRole("link", { name: "Inspect appropriations-limit", exact: true }).focus();
    await page.keyboard.press("Enter");
    ok(new URL(page.url()).hash === "#action-plan-appropriations-limit", "Graph works by keyboard and resolves to the real claim");
    const detail = panel.locator("#action-plan-appropriations-limit");
    await detail.getByText("Exact source passages and local UTF-8 spans", { exact: true }).click();
    ok((await detail.innerText()).includes("subject to the availability of appropriations"), "Exact qualification text can be inspected");
    ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}: no horizontal page overflow`);
    await page.screenshot({ path: `output/playwright/policy-case-${width}.png`, fullPage: true });
  }
  ok(network.every(url => url.startsWith(base) || url.startsWith("data:")), "No external runtime requests");
  ok(errors.length === 0, "No browser exceptions");
  return { passed: checks.length, checks, errors };
}
