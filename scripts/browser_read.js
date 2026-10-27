const fs = require('fs');
const path = require('path');

async function main() {
  const url = process.argv[2];
  if (!url) throw new Error('url is required');
  const puppeteerPath = process.env.XJJ_PUPPETEER_PATH || 'D:/yige-personal-kb/.runtime/dsh-personal/home/profiles/personal/node_modules/puppeteer-core';
  const chromePath = process.env.XJJ_CHROME_PATH || 'C:/Program Files/Google/Chrome/Application/chrome.exe';
  const profile = process.env.XJJ_BROWSER_PROFILE || 'D:/yige-personal-kb/.runtime/browser-worker-profile';
  const puppeteer = require(puppeteerPath);
  fs.mkdirSync(profile, { recursive: true });
  const browser = await puppeteer.launch({
    executablePath: chromePath,
    headless: true,
    userDataDir: profile,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
  });
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });
    const result = await page.evaluate(() => ({
      title: document.title || '',
      url: location.href,
      text: (document.body && document.body.innerText ? document.body.innerText : '').slice(0, 12000)
    }));
    process.stdout.write(JSON.stringify(result));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});