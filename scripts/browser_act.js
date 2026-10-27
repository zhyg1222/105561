const fs = require('fs');

async function main() {
  const encoded = process.argv[2];
  if (!encoded) throw new Error('actions payload is required');
  const actions = JSON.parse(Buffer.from(encoded, 'base64').toString('utf8'));
  if (!Array.isArray(actions) || actions.length > 20) throw new Error('invalid action list');
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
  const results = [];
  try {
    const page = await browser.newPage();
    await page.setViewport({ width: 1280, height: 900 });
    for (const action of actions) {
      const kind = action && action.action;
      if (kind === 'navigate') {
        if (!/^https?:\/\//i.test(action.url || '')) throw new Error('navigate requires http(s) URL');
        await page.goto(action.url, { waitUntil: 'networkidle2', timeout: 30000 });
      } else if (kind === 'click') {
        if (!action.selector) throw new Error('click requires selector');
        await page.click(action.selector);
      } else if (kind === 'type') {
        if (!action.selector || typeof action.text !== 'string') throw new Error('type requires selector and text');
        await page.type(action.selector, action.text.slice(0, 5000));
      } else if (kind === 'press') {
        if (!action.key) throw new Error('press requires key');
        await page.keyboard.press(action.key);
      } else if (kind === 'wait') {
        await new Promise((resolve) => setTimeout(resolve, Math.max(0, Math.min(10000, Number(action.ms || 500)))));
      } else {
        throw new Error('unsupported action: ' + kind);
      }
      results.push({ action: kind, ok: true });
    }
    const result = await page.evaluate(() => ({
      title: document.title || '',
      url: location.href,
      text: (document.body && document.body.innerText ? document.body.innerText : '').slice(0, 12000)
    }));
    process.stdout.write(JSON.stringify({ results, page: result }));
  } finally {
    await browser.close();
  }
}

main().catch((error) => {
  process.stderr.write(String(error && error.stack ? error.stack : error));
  process.exit(1);
});