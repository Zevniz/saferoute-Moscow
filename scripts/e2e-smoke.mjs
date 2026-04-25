import { chromium } from "playwright";

const appUrl = process.env.APP_URL || "http://127.0.0.1:5173/";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleIssues = [];
const pageErrors = [];

page.on("console", (message) => {
  if (["error", "warning"].includes(message.type())) {
    consoleIssues.push(`${message.type()}: ${message.text()}`);
  }
});
page.on("pageerror", (error) => pageErrors.push(error.message));

try {
  const response = await page.goto(appUrl, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForTimeout(1200);
  const tabRail = page.getByRole("navigation", { name: "Разделы SafeRoute" });
  await tabRail.getByRole("button", { name: "Слои" }).click();
  await page.getByRole("button", { name: "Качество тротуаров" }).click();
  await page.waitForTimeout(500);
  await tabRail.getByRole("button", { name: "Поиск" }).click();
  await page.getByPlaceholder("Куда едем по Москве?").fill("Кремль");
  await page.waitForSelector("text=Московский Кремль, Москва", { timeout: 12000 });
  await page.locator("button").filter({ hasText: "Московский Кремль, Москва" }).first().click();
  const startButton = page.getByRole("button", { name: "Начать навигацию" });
  await startButton.waitFor({ state: "visible", timeout: 60000 });
  const routeCards = await page.locator(".route-card").count();
  await page.getByRole("button", { name: "Авто" }).click();
  await startButton.waitFor({ state: "visible", timeout: 60000 });
  await page.waitForFunction(() => {
    const button = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Начать навигацию"),
    );
    return button && !button.disabled;
  });
  await startButton.click();
  await page.getByLabel("Открыть маршруты").waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Завершить").first().click();
  await page.waitForSelector("text=Начните с поиска", { timeout: 12000 });

  const overlayCount = await page
    .locator(".vite-error-overlay, #webpack-dev-server-client-overlay, [data-nextjs-dialog]")
    .count();
  const bodyText = (await page.locator("body").innerText()).trim();
  const filteredConsole = consoleIssues.filter((item) => !item.includes("GPU stall due to ReadPixels"));
  const result = {
    status: response?.status(),
    hasContent: bodyText.length > 0,
    routeCards,
    overlayCount,
    consoleIssues: filteredConsole,
    ignoredWebglWarnings: consoleIssues.length - filteredConsole.length,
    pageErrors,
  };
  console.log(JSON.stringify(result, null, 2));
  if (!response || response.status() >= 400 || overlayCount || pageErrors.length || filteredConsole.length || routeCards < 1) {
    process.exitCode = 1;
  }
} finally {
  await browser.close();
}
