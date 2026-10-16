const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

(async () => {
  const files = process.argv.slice(2);
  const browser = await chromium.launch();
  for (const f of files) {
    const dir = path.dirname(f);
    const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
    await page.goto('file://' + path.resolve(f));
    await page.evaluate(() => document.fonts.ready);
    const slides = await page.$$('.slide');
    for (let i = 0; i < slides.length; i++) {
      await slides[i].screenshot({ path: path.join(dir, `slide-${i + 1}.png`) });
    }
    console.log(f, slides.length, 'slides');
    await page.close();
  }
  await browser.close();
})();
