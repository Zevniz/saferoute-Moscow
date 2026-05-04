import { chromium } from "playwright";

const appUrl = process.env.APP_URL || "http://127.0.0.1:5173/";

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
const consoleIssues = [];
const pageErrors = [];
const feedbackNetworkRequests = [];

page.on("console", (message) => {
  if (["error", "warning"].includes(message.type())) {
    consoleIssues.push(`${message.type()}: ${message.text()}`);
  }
});
page.on("pageerror", (error) => pageErrors.push(error.message));
page.on("request", (request) => {
  const url = request.url().toLowerCase();
  if (url.includes("telemetry") || url.includes("feedback")) {
    feedbackNetworkRequests.push(`${request.method()} ${request.url()}`);
  }
});

try {
  const response = await page.goto(appUrl, { waitUntil: "domcontentloaded", timeout: 20000 });
  await page.waitForTimeout(1200);
  const initialGlassControls = await page.locator("[data-liquid-glass]").count();
  if (initialGlassControls < 3) {
    throw new Error("liquid glass controls are missing from the map-first home screen");
  }
  const initialPanelClass = await page.locator(".planner-panel").first().getAttribute("class", { timeoutMs: 12000 });
  if (!initialPanelClass?.includes("pointer-events-none")) {
    throw new Error("initial home screen should be map-first with the route panel closed");
  }
  const openSections = async () => {
    await page.getByRole("button", { name: /Открыть разделы|Закрыть разделы/ }).click();
    const sections = page.getByRole("navigation", { name: "Разделы SafeRoute" });
    await sections.waitFor({ state: "visible", timeout: 12000 });
    return sections;
  };

  let sections = await openSections();
  await sections.getByRole("button", { name: /^О сервисе/ }).click();
  await page.getByText("Публичная бета").waitFor({ state: "visible", timeout: 12000 });
  sections = await openSections();
  await sections.getByRole("button", { name: /^Карта/ }).click();
  const telemetryOverlayRows = await page.getByText("H3-ячейки телеметрии").count();
  if (telemetryOverlayRows !== 0) {
    throw new Error("telemetry overlay is visible without real telemetry data");
  }
  await page.waitForTimeout(500);
  sections = await openSections();
  await sections.getByRole("button", { name: /^Маршрут/ }).click();
  await page.getByPlaceholder("Куда едем по Москве?").fill("Кремль");
  await page.waitForSelector("text=Московский Кремль, Москва", { timeout: 12000 });
  await page.locator("button").filter({ hasText: "Московский Кремль, Москва" }).first().click();
  const startButton = page.getByRole("button", { name: "Начать навигацию" });
  await startButton.waitFor({ state: "visible", timeout: 60000 });
  const routeCards = await page.locator(".route-card").count();
  const routeCardTexts = await page.locator(".route-card").allTextContents();
  if (routeCardTexts.some((text) => /Данные OSM|Valhalla/i.test(text))) {
    throw new Error("route card shows technical source labels");
  }
  const routeDetailsSummary = page.locator("summary.route-details-summary").first();
  await routeDetailsSummary.scrollIntoViewIfNeeded();
  await routeDetailsSummary.click();
  await page.locator(".route-insight-panel").first().waitFor({ state: "visible", timeout: 12000 });
  if (await page.locator(".route-insight-panel [data-liquid-glass]").count()) {
    throw new Error("liquid glass must not wrap long trust/explainability sections");
  }
  await page.getByText("Почему этот маршрут").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Уверенность данных").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Оценка маршрута").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Неизвестные риски").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Что мы знаем").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Что мы не знаем").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("не гарантия").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Что по пути").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Заметка о маршруте").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("не влияет на маршруты").first().waitFor({ state: "visible", timeout: 12000 });
  const feedbackRequestStart = feedbackNetworkRequests.length;
  await page.getByRole("button", { name: "Было спокойно" }).first().click();
  await page.waitForTimeout(350);
  if (feedbackNetworkRequests.length > feedbackRequestStart) {
    throw new Error(`local feedback sent a network request: ${feedbackNetworkRequests.slice(feedbackRequestStart).join(", ")}`);
  }
  await page.getByText("Данные OSM").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("Оценка учитывает").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("© OpenStreetMap contributors").first().waitFor({ state: "visible", timeout: 12000 });
  await page.getByText("CARTO").first().waitFor({ state: "visible", timeout: 12000 });
  const activeLayerText = await page.locator("[data-testid='data-layer-badges']").first().innerText();
  const forbiddenActiveClaims = [
    "curb active",
    "traffic active",
    "pedestrian density active",
    "telemetry active",
    "official micromobility active",
    "бордюры активны",
    "измеренный трафик активен",
    "плотность пешеходов активна",
    "телеметрия активна",
    "зоны СИМ активны",
  ];
  for (const claim of forbiddenActiveClaims) {
    if (activeLayerText.toLowerCase().includes(claim)) {
      throw new Error(`inactive safety layer is claimed active in UI: ${claim}`);
    }
  }
  if (await page.getByRole("button", { name: "Авто" }).count()) {
    throw new Error("car profile is visible in the public planner");
  }
  await page.waitForFunction(() => {
    const button = Array.from(document.querySelectorAll("button")).find((node) =>
      node.textContent?.includes("Начать навигацию"),
    );
    return button && !button.disabled;
  }, { timeout: 60000 });
  await startButton.click();
  await page.getByLabel("Открыть навигационное меню").waitFor({ state: "visible", timeout: 12000 });
  await page.locator(".maplibregl-ctrl-zoom-in").click({ timeout: 12000 });
  await page.getByText("Завершить").first().click();
  await page.getByPlaceholder("Куда едем по Москве?").waitFor({ state: "visible", timeout: 12000 });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  await page.getByPlaceholder("Куда едем по Москве?").waitFor({ state: "visible", timeout: 12000 });
  const hasHorizontalOverflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
  if (hasHorizontalOverflow) {
    throw new Error("mobile viewport has horizontal overflow");
  }

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
