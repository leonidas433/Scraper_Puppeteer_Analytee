// scraper.js
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import AnonymizeUAPlugin from 'puppeteer-extra-plugin-anonymize-ua';

puppeteer.use(StealthPlugin());
puppeteer.use(AnonymizeUAPlugin());

export async function getPrimaryPhotoFromDOM(placeId, logger = null) {
  const log = (msg) => logger?.debug ? logger.debug(msg) : null;

  const browserArgs = [
    '--no-sandbox',
    '--disable-setuid-sandbox',
    '--disable-blink-features=AutomationControlled',
  ];

  let browser;
  try {
    browser = await puppeteer.launch({
      headless: true,
      args: browserArgs,
    });

    const page = await browser.newPage();
    await page.setUserAgent(
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
    );

    const url = `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
    log && log(`Navegando a ${url}`);

    await page.goto(url, { waitUntil: 'networkidle2', timeout: 25000 });

    // Intentar cerrar cookies si aparecen (best-effort, sin romper si falla)
    try {
      await page.evaluate(() => {
        const btns = Array.from(
          document.querySelectorAll('button, div[role="button"]')
        );
        const target = btns.find((b) => {
          const t = (b.innerText || '').toLowerCase();
          return t.includes('aceptar') || t.includes('accept');
        });
        if (target) target.click();
      });
    } catch (_) {}

    // Extraer URL de la imagen principal
    const photoUrl = await page.evaluate(() => {
      const selectors = [
        'button[jsaction*="hero"] img',
        'img[jsaction*="hero"]',
        'img[decoding="async"]',
        'img[role="img"]',
        'img[src*="lh3.googleusercontent.com"]',
      ];

      for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.src && el.src.startsWith('http')) {
          return el.src;
        }
      }
      return null;
    });

    log && log(photoUrl ? 'Foto principal encontrada en DOM' : 'No se encontró foto en DOM');
    return photoUrl || null;
  } catch (err) {
    logger?.warn && logger.warn(`getPrimaryPhotoFromDOM error: ${err.message}`);
    return null;
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch (_) {}
    }
  }
}
