/* Optional end-to-end browser check. Use a seeded DEVELOPMENT database only.
   Creates two test accounts and a delivered donation. See README for setup.
   npm install --no-save playwright && npx playwright install chromium
   node tests/browser_smoke.cjs
*/
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { chromium } = require("playwright");

(async () => {
  let options = { headless: true };
  if (process.env.USE_SPARTICUZ) {
    const pkg = require("@sparticuz/chromium");
    const chrom = pkg.default || pkg;
    options = {
      ...options,
      executablePath: await chrom.executablePath(),
      args: chrom.args,
    };
  }
  const browser = await chromium.launch(options);
  const page = await browser.newPage({
    viewport: { width: 1440, height: 1000 },
  });
  const base = process.env.BASE_URL || "http://127.0.0.1:5000";
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    if (response.status() >= 500)
      errors.push(`${response.status()} ${response.url()}`);
  });
  const visit = async (path) => {
    const r = await page.goto(base + path);
    assert.equal(r.status(), 200, path);
  };
  const fill = async (key, value) =>
    page.locator(`[name="${key}"]:visible`).fill(String(value));
  const click = async (name) => {
    await page.getByRole("button", { name, exact: true }).click();
    await page.waitForLoadState("networkidle");
  };
  const bodyHas = async (text) =>
    assert((await page.locator("body").innerText()).includes(text), text);
  const noOverflow = async () =>
    assert(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
      "horizontal overflow: " + page.url(),
    );
  const login = async (role) => {
    await visit("/login");
    await page.locator(`[data-demo="${role}"]`).click();
    await click("Log in to your account");
    assert(page.url().endsWith("/dashboard"));
  };
  const logout = async () => {
    await click("Log out");
  };
  fs.mkdirSync("test-results", { recursive: true });
  await visit("/");
  await page.screenshot({
    path: "test-results/home-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of [
    "/",
    "/about",
    "/how-it-works",
    "/find-food",
    "/charities",
    "/login",
    "/register",
  ]) {
    await visit(path);
    await noOverflow();
  }
  await visit("/");
  await page.screenshot({
    path: "test-results/home-mobile.png",
    fullPage: true,
  });
  await page.getByRole("button", { name: "Toggle navigation" }).click();
  assert.equal(
    await page.locator(".menu-toggle").getAttribute("aria-expanded"),
    "true",
  );
  await page.setViewportSize({ width: 1440, height: 1000 });
  const suffix = Date.now();
  const emails = [
    `browser-donor-${suffix}@example.test`,
    `browser-charity-${suffix}@example.test`,
  ];
  for (const [index, role] of ["donor", "charity"].entries()) {
    await visit("/register");
    await page
      .locator(`input[name="role"][value="${role}"]`)
      .check({ force: true });
    await fill("name", `Browser ${role}`);
    await fill("email", emails[index]);
    await fill("password", "Browser@123");
    await fill("confirm_password", "Browser@123");
    await fill("organization", `Browser ${role} organization`);
    await fill("phone", "9000012345");
    await fill("location", "Indiranagar, Bengaluru");
    await fill("latitude", "12.9784");
    await fill("longitude", "77.6408");
    if (role === "charity")
      await page
        .locator('input[name="categories"][value="Vegetables"]')
        .check();
    await click("Create your account");
    await bodyHas("Your account is ready");
    if (role === "donor") {
      await visit("/donate");
      await fill("name", `Browser fresh vegetables ${suffix}`);
      await page.selectOption('[name="category"]', "Vegetables");
      await fill("quantity", "25");
      await fill(
        "expires_at",
        new Date(Date.now() + 12 * 3600000).toISOString().slice(0, 16),
      );
      await click("Publish & find matches");
      await bodyHas("Your donation is live");
      await bodyHas("BEST MATCH");
      fs.writeFileSync("test-results/browser-donation-url.txt", page.url());
    }
    await logout();
  }
  await login("charity");
  const donationUrl = fs.readFileSync(
    "test-results/browser-donation-url.txt",
    "utf8",
  );
  await page.goto(donationUrl);
  await click("Accept food");
  await bodyHas("Donation accepted!");
  await click("Mark as collected");
  await bodyHas("marked as collected");
  await click("Mark as delivered");
  await bodyHas("marked as delivered");
  await visit("/dashboard?tab=history");
  await bodyHas(`Browser fresh vegetables ${suffix}`);
  await logout();
  await login("admin");
  assert.equal(await page.locator(".chart-bar").count(), 5);
  await page.screenshot({
    path: "test-results/admin-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ["/dashboard", "/dashboard?tab=users", "/profile"]) {
    await visit(path);
    await noOverflow();
  }
  await page.setViewportSize({ width: 1440, height: 1000 });
  await logout();
  await login("donor");
  await visit("/donate");
  await page.screenshot({
    path: "test-results/donate-desktop.png",
    fullPage: true,
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await noOverflow();
  assert.deepEqual(errors, []);
  console.log(
    "PASS: responsive pages, mobile navigation, donor and charity registration, CSRF-protected donation creation, matching, acceptance, collection, delivery, history, admin charts.",
  );
  console.log("Development records created:", emails.join(", "), donationUrl);
  await browser.close();
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
