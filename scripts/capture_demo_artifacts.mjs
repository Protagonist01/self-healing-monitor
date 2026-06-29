import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";

const root = process.cwd();
const outDir = path.join(root, "demo_artifacts");
const videoDir = path.join(outDir, "video");

await fs.mkdir(outDir, { recursive: true });
await fs.mkdir(videoDir, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
  recordVideo: { dir: videoDir, size: { width: 1440, height: 1000 } },
});

const page = await context.newPage();

async function save(name, options = {}) {
  await page.screenshot({
    path: path.join(outDir, name),
    fullPage: options.fullPage ?? true,
  });
}

await page.goto("http://localhost:3000", { waitUntil: "networkidle" });
await page.waitForTimeout(2500);
await save("01-dashboard-overview.png");

await page.locator(".queue-panel").scrollIntoViewIfNeeded();
await page.waitForTimeout(600);
await save("02-approval-queue-and-audit.png");

await page.getByRole("button", { name: /high memory demo/i }).click();
await page.waitForTimeout(42000);
await save("03-after-live-demo-trigger.png");

await page.goto("http://localhost:9090/targets", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await save("04-prometheus-targets.png");

await page.goto("http://localhost:9090/alerts", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await save("05-prometheus-alerts.png");

await page.goto("http://localhost:8000/docs", { waitUntil: "networkidle" });
await page.waitForTimeout(1500);
await save("06-healer-api-docs.png");

await context.close();
await browser.close();

const videos = await fs.readdir(videoDir);
const webm = videos.find((file) => file.endsWith(".webm"));
if (webm) {
  await fs.rename(path.join(videoDir, webm), path.join(outDir, "self-healing-monitor-demo.webm"));
}

await fs.rm(videoDir, { recursive: true, force: true });

console.log(`Artifacts written to ${outDir}`);
