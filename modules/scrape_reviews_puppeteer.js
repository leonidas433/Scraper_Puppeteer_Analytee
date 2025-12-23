// autos: Leox433
// Metodo: AI
// Version: V4.2
// Fecha de última modificación: 2025-10-18 (Fix HTTP 407, randomDelay error, proxy filtering, max-reviews, partial saves)

const fs = require("fs");
const path = require("path");
const puppeteer = require("puppeteer-extra");
const StealthPlugin = require("puppeteer-extra-plugin-stealth");
const AnonymizeUAPlugin = require("puppeteer-extra-plugin-anonymize-ua");

puppeteer.use(StealthPlugin());
puppeteer.use(AnonymizeUAPlugin());

const sleep = (ms) => new Promise((res) => setTimeout(res, ms));
const randomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;
const randomScrollAmount = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0',
  'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0'
];

const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 1536, height: 864 },
  { width: 1440, height: 900 },
  { width: 1280, height: 720 }
];

function loadProxies() {
  const proxyFile = path.join(process.cwd(), "Webshare_10_proxies.txt");
  if (!fs.existsSync(proxyFile)) {
    console.log("⚠️ Archivo de proxies no encontrado. Continuando sin proxy.");
    return [];
  }
  try {
    const content = fs.readFileSync(proxyFile, "utf-8");
    const lines = content.split('\n').filter(line => line.trim());
    const failedProxy = "84.247.60.125:6095";
    const proxies = lines
      .filter(line => !line.includes(failedProxy))
      .map(line => {
        const [host, port, username, password] = line.trim().split(':');
        return { host, port, username, password, full: `http://${username}:${password}@${host}:${port}` };
      });
    console.log(`✅ Cargados ${proxies.length} proxies desde ${proxyFile} (excluido ${failedProxy})`);
    return proxies;
  } catch (error) {
    console.log(`⚠️ Error al leer proxies: ${error.message}`);
    return [];
  }
}

function selectRandomProxy(proxies) {
  if (proxies.length === 0) return null;
  return proxies[Math.floor(Math.random() * proxies.length)];
}

async function testProxy(page, proxy) {
  try {
    console.log(`\n🧪 Probando conectividad del proxy ${proxy.host}:${proxy.port}...`);
    const startTime = Date.now();
    const response = await page.goto('https://api.ipify.org?format=json', {
      waitUntil: 'networkidle2',
      timeout: 15000
    });

    if (response.status() === 407) throw new Error("HTTP 407");

    const ipData = await page.evaluate(() => {
      try {
        return JSON.parse(document.body.innerText);
      } catch {
        return { ip: document.body.innerText.trim() };
      }
    });

    const responseTime = Date.now() - startTime;
    console.log(`✅ Proxy funcionando correctamente`);
    console.log(`   📡 IP detectada: ${ipData.ip}`);
    console.log(`   ⏱️  Tiempo de respuesta: ${responseTime}ms\n`);
    return true;
  } catch (error) {
    console.log(`❌ Error probando proxy ${proxy.host}:${proxy.port}: ${error.message}`);
    return false;
  }
}

async function gotoWithRetry(page, url, options = {}, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      await page.goto(url, { ...options, timeout: 30000 });
      return true;
    } catch (e) {
      console.error(`❌ Intento ${i + 1} fallido para goto ${url}: ${e.message}`);
      if (i === retries - 1) return false;
      await sleep(randomDelay(2000, 5000));
    }
  }
  return false;
}

async function clickWithRetry(page, selector, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      const element = await page.waitForSelector(selector, { timeout: 5000 });
      await element.click();
      return true;
    } catch (e) {
      console.error(`❌ Intento ${i + 1} fallido para click en ${selector}: ${e.message}`);
      if (i === retries - 1) return false;
      await sleep(randomDelay(1000, 3000));
    }
  }
  return false;
}

function savePartialReviews(allReviews, cleanBusinessName, placeId) {
  const dir = path.join(process.cwd(), "clientes", `${cleanBusinessName}_${placeId}`);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  const filePath = path.join(dir, `${cleanBusinessName}_${placeId}_partial.csv`);
  const header = "user,rating,date,text,owner_response,owner_response_date,tipo_comida,precio_persona,comida_rating,servicio_rating,ambiente_rating,nivel_ruido,tiempo_espera\n";
  let csv = header;
  for (const r of allReviews.values()) {
    csv += `"${r.user}","${r.rating}","${r.date}","${r.text.replace(/"/g, '""')}","${r.owner_response.replace(/"/g, '""')}","${r.owner_response_date}","${r.tipo_comida}","${r.precio_persona}","${r.comida_rating}","${r.servicio_rating}","${r.ambiente_rating}","${r.nivel_ruido}","${r.tiempo_espera}"\n`;
  }
  fs.writeFileSync(filePath, "\ufeff" + csv, "utf-8");
}

async function scrapeReviews() {
  const placeId = process.argv[2];
  const maxReviews = parseInt(process.argv[3]?.split('=')[1]) || Infinity;
  if (!placeId) {
    console.error("⚠️ Debes pasar un Place ID como argumento");
    console.error("Ejemplo: node scrape_reviews_puppeteer.js ChIJxxxxxxx [--max-reviews=100]");
    process.exit(1);
  }

  let businessName = null;
  try {
    const files = fs
      .readdirSync(path.join(process.cwd(), "clientes"))
      .map((folder) => path.join(process.cwd(), "clientes", folder))
      .filter((folder) => folder.includes(placeId));

    if (files.length > 0) {
      const metaFile = path.join(files[0], `PlaceID_${placeId}.txt`);
      if (fs.existsSync(metaFile)) {
        const content = fs.readFileSync(metaFile, "utf-8");
        const match = content.match(/Topónimo\s*\n(.+)/);
        if (match) {
          businessName = match[1].trim();
          console.log(`📄 Nombre leído desde metadatos: "${businessName}"`);
        }
      }
    }
  } catch {
    console.log("ℹ️ No se pudo leer metadatos");
  }

  const url = `https://www.google.com/maps/place/?q=place_id:${placeId}`;

  const proxies = loadProxies();
  let selectedProxy = selectRandomProxy(proxies);
  let browser;

  try {
    const browserArgs = [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--disable-blink-features=AutomationControlled',
      '--disable-web-security',
      '--disable-features=IsolateOrigins,site-per-process',
      '--disable-gpu'
    ];

    if (selectedProxy) {
      browserArgs.push(`--proxy-server=${selectedProxy.host}:${selectedProxy.port}`);
      console.log(`🔐 Usando proxy: ${selectedProxy.host}:${selectedProxy.port}`);
    } else {
      console.log("⚠️ Ejecutando sin proxy (riesgo de bloqueo por Google)");
    }

    const randomUserAgent = USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
    const randomViewport = VIEWPORTS[Math.floor(Math.random() * VIEWPORTS.length)];
    console.log(`🔒 User-Agent: ${randomUserAgent.substring(0, 50)}...`);
    console.log(`📐 Viewport: ${randomViewport.width}x${randomViewport.height}`);

    browser = await puppeteer.launch({
      headless: true,
      args: browserArgs
    });

    const page = await browser.newPage();

    if (selectedProxy) {
      await page.authenticate({
        username: selectedProxy.username,
        password: selectedProxy.password
      });
      console.log(`✅ Autenticación de proxy completada`);

      let proxyOk = await testProxy(page, selectedProxy);
      if (!proxyOk) {
        console.log("⚠️ Proxy falló, seleccionando otro...");
        const remainingProxies = proxies.filter(p => p.host !== selectedProxy.host);
        selectedProxy = selectRandomProxy(remainingProxies);
        if (selectedProxy) {
          await browser.close();
          browserArgs.push(`--proxy-server=${selectedProxy.host}:${selectedProxy.port}`);
          browser = await puppeteer.launch({ headless: true, args: browserArgs });
          const newPage = await browser.newPage();
          await newPage.authenticate({ username: selectedProxy.username, password: selectedProxy.password });
          proxyOk = await testProxy(newPage, selectedProxy);
          if (!proxyOk) throw new Error("Todos los proxies fallaron");
          page = newPage;
        } else {
          console.log("⚠️ No hay más proxies disponibles, continuando sin proxy");
          await browser.close();
          browser = await puppeteer.launch({
            headless: true,
            args: browserArgs.filter(arg => !arg.startsWith('--proxy-server'))
          });
          page = await browser.newPage();
        }
      }
    }

    await page.setUserAgent(randomUserAgent);
    await page.setViewport(randomViewport);

    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, 'webdriver', { get: () => false });
      Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
      Object.defineProperty(navigator, 'languages', { get: () => ['es-ES', 'es', 'en-US', 'en'] });
      window.chrome = { runtime: {} };
      const originalQuery = window.navigator.permissions.query;
      window.navigator.permissions.query = (parameters) => (
        parameters.name === 'notifications' ?
          Promise.resolve({ state: Notification.permission }) :
          originalQuery(parameters)
      );
    });

    await page.setRequestInterception(true);
    page.on('request', (req) => {
      if (['image', 'stylesheet', 'font', 'media'].includes(req.resourceType())) {
        req.abort();
      } else {
        req.continue();
      }
    });

    if (!await gotoWithRetry(page, url, { waitUntil: "domcontentloaded" })) {
      throw new Error("No se pudo cargar la página de Google Maps");
    }
    await sleep(randomDelay(3000, 5000));

    await page.mouse.move(randomDelay(0, randomViewport.width), randomDelay(0, randomViewport.height));
    await page.evaluate(scroll => window.scrollBy(0, scroll), randomDelay(100, 500));
    await sleep(randomDelay(1000, 2000));

    try {
      const cookieSelector = 'button[aria-label*="Aceptar"], button[aria-label*="Aceptar todo"], button[aria-label*="Accept all"], button[jsname]';
      if (await clickWithRetry(page, cookieSelector)) {
        console.log("✅ Cookies aceptadas automáticamente");
        await sleep(randomDelay(1500, 2500));
      } else {
        console.log("ℹ️ No apareció popup de cookies");
      }
    } catch {
      console.log("ℹ️ No se pudo interactuar con el popup de cookies");
    }

    const reviewsButtonSelector =
      'button[jsaction*="pane.reviewChart"], button[aria-label*="Reseñas"], button[aria-label*="Reviews"]';
    if (!await clickWithRetry(page, reviewsButtonSelector, 15000)) {
      throw new Error("No se pudo acceder a la sección de reseñas");
    }
    await sleep(randomDelay(3000, 4500));


    // ============================================================
    // === BLOQUE DE ORDENAR RESEÑAS (CORREGIDO)
    // ============================================================

    try {
      const sortBtnSelectors = [
        'button[aria-label*="Ordenar"]',
        'button[aria-label*="Sort"]',
        'button[aria-label*="Más útiles"]',
        'button[aria-label*="Most helpful"]',
        'div[role="button"][aria-label*="Ordenar"]',
        'div[role="button"][aria-label*="Sort"]',
        'button:has(span):not([jsaction*="pane.rating"])',
      ];

      let sortBtnFound = false;
      for (const selector of sortBtnSelectors) {
        if (await clickWithRetry(page, selector, 5000)) {
          sortBtnFound = true;
          console.log(`✅ Botón de ordenar encontrado: ${selector}`);
          break;
        }
      }

      if (sortBtnFound) {
        await sleep(randomDelay(1500, 2500));

        const clicked = await page.evaluate(() => {
          const menuSelectors = [
            '[role="menu"] [role="menuitemradio"]',
            '[role="menu"] [role="menuitem"]',
            '[role="listbox"] [role="option"]',
            'li[role="menuitemradio"]',
            'li[role="menuitem"]',
            'div[role="menuitemradio"]',
            'div[role="menuitem"]',
            'div[role="option"]',
            'button[role="menuitem"]',
            'button[role="menuitemradio"]',
            'div.fxNQSd' // Google Maps nuevo layout
          ];

          let targetElement = null;

          for (const selector of menuSelectors) {
            const items = document.querySelectorAll(selector);
            for (const item of items) {
              const text =
                (item.innerText ||
                 item.textContent ||
                 item.getAttribute('aria-label') ||
                 '').toLowerCase();

              const visible =
                item.offsetParent !== null &&
                window.getComputedStyle(item).display !== 'none' &&
                window.getComputedStyle(item).visibility !== 'hidden';

              if (!visible) continue;

              // Palabras claves actualizadas
              if (
                text.includes("más recientes") ||
                text.includes("mas recientes") ||
                text.includes("más reciente") ||
                text.includes("newest") ||
                text.includes("recent")
              ) {
                targetElement = item;
                break;
              }
            }
            if (targetElement) break;
          }

          if (!targetElement) return false;

          try {
            targetElement.scrollIntoView({ block: 'center' });
            const clickEvent = new MouseEvent('click', {
              bubbles: true,
              cancelable: true,
              view: window,
            });
            targetElement.dispatchEvent(clickEvent);
            return true;
          } catch {
            return false;
          }
        });

        if (clicked) {
          console.log("✅ Reseñas ordenadas por 'Más recientes'");
        } else {
          console.log("⚠️ No se pudo cambiar el orden");
        }

        await sleep(randomDelay(2000, 3000));

      } else {
        console.log("⚠️ No se encontró el botón de ordenar");
      }

    } catch (err) {
      console.log("⚠️ Error al ordenar:", err.message);
    }


    // ============================================================
    // === CONTINÚA EL SCRIPT ORIGINAL SIN NINGÚN CAMBIO
    // ============================================================


    if (!businessName || businessName.startsWith("PLACE_")) {
      const domName = await page.evaluate(() => {
        const selectors = [
          "h1.DUwDvf",
          "h1.fontHeadlineLarge",
          "h1[role='heading']",
          ".DUwDvf"
        ];
        for (const s of selectors) {
          const el = document.querySelector(s);
          if (el && el.innerText.trim()) return el.innerText.trim();
        }
        return document.title.replace(" · Google Maps", "").trim();
      });
      if (domName) {
        businessName = domName;
        console.log(`📍 Nombre detectado en DOM: "${businessName}"`);
      } else {
        businessName = `PLACE_${placeId}`;
        console.log(`⚠️ Usando fallback: "${businessName}"`);
      }
    }

    businessName = businessName.replace(/- Google Maps$/i, "").trim();

    console.log("🔄 Iniciando extracción de reseñas (modo natural)...");
    const allReviews = new Map();
    let unchangedCount = 0;
    let scrollAttempts = 0;
    const MAX_UNCHANGED = 30;
    const MAX_SCROLL_ATTEMPTS = 2000;

    while (unchangedCount < MAX_UNCHANGED && scrollAttempts < MAX_SCROLL_ATTEMPTS && allReviews.size < maxReviews) {
      scrollAttempts++;

      await page.evaluate(() => {
        const moreButtons = document.querySelectorAll('button[aria-label*="Más"], button[jsaction*="review.expandReview"]');
        const randomButtons = Array.from(moreButtons).slice(0, Math.min(5, moreButtons.length));
        randomButtons.forEach(btn => {
          try { btn.click(); } catch (e) {}
        });
      });

      await sleep(randomDelay(400, 800));

      const newReviews = await page.evaluate(() => {
        const nodes = document.querySelectorAll("div.jftiEf");
        return Array.from(nodes).map((n) => {
          const user = n.querySelector(".d4r55")?.innerText || "Anónimo";
          const rating = n.querySelector(".kvMYJc")?.getAttribute("aria-label") || "";
          const date = n.querySelector(".rsqaWe")?.innerText || "";
          const text = n.querySelector(".wiI7pd")?.innerText || "";

          let ownerResponse = "";
          let ownerResponseDate = "";

          const responseCandidates = [
            n.querySelector("div.CDe7pd"),
            n.querySelector("div[class*='owner']"),
            n.querySelector("div[class*='response']"),
            ...Array.from(n.querySelectorAll("div")).filter(div => {
              const text = div.innerText?.toLowerCase() || "";
              return text.includes("respuesta del propietario") ||
                text.includes("response from the owner") ||
                text.includes("propietario") ||
                text.includes("owner");
            })
          ];

          const responseSection = responseCandidates.find(el => el !== null);

          if (responseSection) {
            const responseTextCandidates = [
              responseSection.querySelector("div.wiI7pd"),
              responseSection.querySelector("span.wiI7pd"),
              responseSection.querySelector("div[class*='text']"),
              ...Array.from(responseSection.querySelectorAll("div, span")).filter(el => {
                const txt = el.innerText?.trim() || "";
                return txt.length > 20 &&
                  !txt.toLowerCase().includes("propietario") &&
                  !txt.toLowerCase().includes("owner");
              })
            ];

            const responseTextEl = responseTextCandidates.find(el => el !== null && el.innerText?.trim());
            if (responseTextEl) ownerResponse = responseTextEl.innerText.trim();

            const responseDateCandidates = [
              responseSection.querySelector("span.DZSIDd"),
              responseSection.querySelector("span[class*='date']"),
              ...Array.from(responseSection.querySelectorAll("span")).filter(el => {
                const txt = el.innerText?.toLowerCase() || "";
                return txt.includes("hace") ||
                  txt.includes("ago") ||
                  txt.match(/\d+\s+(día|semana|mes|año|day|week|month|year)/);
              })
            ];

            const responseDateEl = responseDateCandidates.find(el => el !== null && el.innerText?.trim());
            if (responseDateEl) ownerResponseDate = responseDateEl.innerText.trim();
          }

          const extraData = {};
          const allSpans = n.querySelectorAll("span, div");
          let currentKey = null;

          allSpans.forEach(el => {
            const txt = el.innerText?.trim();
            if (!txt) return;

            if (txt.includes("Tipo de comida") || txt.includes("Food type")) {
              currentKey = "tipo_comida";
            } else if (txt.includes("Precio por persona") || txt.includes("Price per person")) {
              currentKey = "precio_persona";
            } else if (txt.match(/^Comida:/i) || txt.match(/^Food:/i)) {
              extraData.comida_rating = txt.split(':')[1]?.trim() || "";
            } else if (txt.match(/^Servicio:/i) || txt.match(/^Service:/i)) {
              extraData.servicio_rating = txt.split(':')[1]?.trim() || "";
            } else if (txt.match(/^Ambiente:/i) || txt.match(/^Atmosphere:/i)) {
              extraData.ambiente_rating = txt.split(':')[1]?.trim() || "";
            } else if (txt.includes("Nivel de ruido") || txt.includes("Noise level")) {
              currentKey = "nivel_ruido";
            } else if (txt.includes("Tiempo de espera") || txt.includes("Wait time")) {
              currentKey = "tiempo_espera";
            } else if (currentKey && txt.length < 50) {
              extraData[currentKey] = txt;
              currentKey = null;
            }
          });

          const uniqueKey = `${user}_${date}_${text.substring(0, 50)}`;

          return {
            user,
            rating,
            date,
            text,
            uniqueKey,
            owner_response: ownerResponse,
            owner_response_date: ownerResponseDate,
            tipo_comida: extraData.tipo_comida || "",
            precio_persona: extraData.precio_persona || "",
            comida_rating: extraData.comida_rating || "",
            servicio_rating: extraData.servicio_rating || "",
            ambiente_rating: extraData.ambiente_rating || "",
            nivel_ruido: extraData.nivel_ruido || "",
            tiempo_espera: extraData.tiempo_espera || ""
          };
        });
      });

      let added = 0;
      newReviews.forEach((r) => {
        if (!allReviews.has(r.uniqueKey)) {
          allReviews.set(r.uniqueKey, r);
          added++;
        }
      });

      if (added > 0) {
        unchangedCount = 0;
        console.log(`➡️ Total reseñas únicas: ${allReviews.size} (+${added}) - Intento ${scrollAttempts}`);
      } else {
        unchangedCount++;
        if (unchangedCount % 5 === 0) {
          console.log(`📊 Sin nuevas reseñas (${unchangedCount}/${MAX_UNCHANGED}) - Intento ${scrollAttempts}`);
        }
      }

      if (allReviews.size > 0 && allReviews.size % 100 === 0) {
        savePartialReviews(
          allReviews,
          businessName.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_"),
          placeId
        );
      }

      const scrollAmount = randomScrollAmount(800, 1500);
      await page.evaluate((amount) => {
        const container =
          document.querySelector("div.m6QErb.DxyBCb.kA9KIf.dS8AEf") ||
          document.querySelector("div.m6QErb");
        if (container) {
          container.scrollBy({ top: amount, behavior: "smooth" });
        }
      }, scrollAmount);

      let pauseTime;
      if (Math.random() < 0.1) {
        pauseTime = randomDelay(3000, 5000);
        console.log("👀 Simulando lectura de reseña...");
      } else if (Math.random() < 0.3) {
        pauseTime = randomDelay(2000, 3000);
      } else {
        pauseTime = randomDelay(1500, 2500);
      }

      await sleep(pauseTime);

      if (allReviews.size >= maxReviews) {
        console.log(`🏁 Detenido: Alcanzado límite de ${maxReviews} reseñas`);
        break;
      }
    }

    if (scrollAttempts >= MAX_SCROLL_ATTEMPTS) {
      console.log(`⚠️ Alcanzado límite de intentos de scroll (${MAX_SCROLL_ATTEMPTS})`);
    }

    if (unchangedCount >= MAX_UNCHANGED) {
      console.log(`🏁 Detenido: ${MAX_UNCHANGED} intentos consecutivos sin nuevas reseñas`);
    }

    const withOwnerResponse = Array.from(allReviews.values()).filter(r => r.owner_response).length;
    console.log(`✅ Scroll completado. Total reseñas: ${allReviews.size}`);
    console.log(`💬 Reseñas con respuesta del propietario: ${withOwnerResponse}`);

    const cleanBusinessName = businessName.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_");
    const dir = path.join(process.cwd(), "clientes", `${cleanBusinessName}_${placeId}`);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });

    const filePath = path.join(dir, `${cleanBusinessName}_${placeId}.csv`);
    const header =
      "user,rating,date,text,owner_response,owner_response_date,tipo_comida,precio_persona,comida_rating,servicio_rating,ambiente_rating,nivel_ruido,tiempo_espera\n";

    let csv = header;
    for (const r of allReviews.values()) {
      csv += `"${r.user}","${r.rating}","${r.date}","${r.text.replace(/"/g, '""')}","${r.owner_response.replace(/"/g, '""')}","${r.owner_response_date}","${r.tipo_comida}","${r.precio_persona}","${r.comida_rating}","${r.servicio_rating}","${r.ambiente_rating}","${r.nivel_ruido}","${r.tiempo_espera}"\n`;
    }

    fs.writeFileSync(filePath, "\ufeff" + csv, "utf-8");
    console.log(`✅ Guardadas ${allReviews.size} reseñas en ${filePath}`);

  } catch (error) {
    console.error("❌ Error general:", error.stack);

    if (typeof allReviews !== 'undefined' && allReviews.size > 0) {
      savePartialReviews(
        allReviews,
        businessName.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_"),
        placeId
      );
    }

  } finally {
    if (browser) await browser.close();
  }
}

scrapeReviews();

// NOTA LEGAL: Este script realiza scraping de Google Maps, lo cual viola los Términos de Servicio de Google.
