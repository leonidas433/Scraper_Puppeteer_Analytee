// autos: Leox433
// Metodo: AI
// Version: V2.0 - Mass Scraper Main (Integración google-review-scraper-1)
// Fecha de última modificación: 2025-01-27
// Descripción: Script principal para scraping masivo de 120,000+ reseñas con funciones mejoradas

// BACKUP AUTOMÁTICO - no tocar
import fs from "fs";
try {
  if (!fs.existsSync("./.backups")) fs.mkdirSync("./.backups");
  fs.writeFileSync(`./.backups/mass_scraper_main.js.bak-${Date.now()}`, fs.readFileSync("./modules/mass_scraper_main.js"));
} catch (e) { console.warn("Backup falló:", e?.message || e); }

import path from "path";
import { fileURLToPath } from "url";
import { dirname } from "path";
import os from "os";
import dotenv from "dotenv";
import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import AnonymizeUAPlugin from "puppeteer-extra-plugin-anonymize-ua";

// === IMPORTACIÓN DE UTILIDADES UNIFICADAS ===
import { 
  sleep, 
  randomDelay, 
  cleanText,
  isValidPlaceId,
  loadProxies,
  selectRandomProxy 
} from "../core/utils.js";

// === IMPORTACIÓN DE ALMACENAMIENTO ===
import { 
  saveReviews, 
  saveMetadata,
  saveCheckpoint,
  createDataDirectory,
  exportAsCSV 
} from "./storage/storage.js";

// Parser flexible de flags (mantener compatibilidad)
const flags = Object.fromEntries(
  process.argv.slice(2).map(a => {
    const [k, v] = a.replace(/^--/, "").split("=");
    return [k, v === undefined ? true : v];
  })
);
const FAST_MODE = !!flags.fast || flags.fast === "true";

// Configuración inline simplificada
const MASS_SCRAPER_CONFIG = {
  TARGET_REVIEWS: 120000,
  MAX_REVIEWS: 200000,
  BATCH_SIZE: 1000,
  MAX_BATCHES: 100,
  MAX_SCROLLS_PER_BATCH: 50,
  SCROLL_DELAY_MIN: 800,
  SCROLL_DELAY_MAX: 1500,
  BATCH_DELAY_MIN: 30000,
  BATCH_DELAY_MAX: 60000,
  PROXY_ROTATION_INTERVAL: 1000,
  CAPTCHA_DELAY: 30000,
  RATE_LIMIT_DELAY: 60000,
  CHECKPOINT_PREFIX: "checkpoint_batch_"
};

const SELECTOR_CONFIG = {
  REVIEW_ELEMENTS: [
    'div.jftiEf',
    'div[data-review-id]',
    'div[jscontroller][data-review-id]',
    'div.fontBodyMedium'
  ],
  PAGINATION_CONTROLS: [
    "button[aria-label*='más']",
    "button[aria-label*='more']",
    "button[aria-label*='ver más']",
    "button[aria-label*='load more']",
    "button[aria-label*='show more']"
  ]
};

// === USER-AGENTS y cabeceras realistas ===
const USER_AGENTS = [
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
  "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0"
];
function pickUserAgent() {
  return USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)];
}

export async function applyHumanHeaders(page) {
  const ua = pickUserAgent();
  await page.setUserAgent(ua);
  await page.setExtraHTTPHeaders({
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
    "DNT": "1",
    "Upgrade-Insecure-Requests": "1"
  });
  await page.setViewport({
    width: 1200 + Math.floor(Math.random() * 220),
    height: 720 + Math.floor(Math.random() * 240)
  });
  console.log("[INFO] UA aplicado:", ua);
}

export async function acceptCookiesIfPresent(page) {
  try {
    const selList = [
      'button[aria-label*="Aceptar"]',
      'button[aria-label*="Aceptar todo"]',
      'button[aria-label*="I agree"]',
      '#L2AGLb', // banner Google
    ];
    for (const s of selList) {
      const btn = await page.$(s);
      if (btn) {
        await btn.click();
        await new Promise(resolve => setTimeout(resolve, 500 + Math.random() * 800));
        console.log("[INFO] Cookies aceptadas.");
        break;
      }
    }
  } catch (e) {
    console.warn("[WARN] No se pudieron aceptar cookies automáticamente:", e?.message);
  }
}

// --- Helper universal de espera (usa sleep de utils.js) ---
const wait = sleep;

// --- Helper de clic seguro compatible con SPA y shadow DOM ---
async function safeClick(page, selector, options = {}) {
  const maxAttempts = options.maxAttempts || 3;
  const timeout = options.timeout || 8000;
  const waitAfterClick = options.waitAfterClick || 1200 + Math.random() * 800;
  const checkActive = options.checkActive !== false; // Default true
  const activeAttribute = options.activeAttribute || 'aria-selected';
  const activeValue = options.activeValue || 'true';

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const elHandle = await page.waitForSelector(selector, { timeout });
      if (!elHandle) throw new Error("Elemento no encontrado");
      console.log(`[INFO] Intento ${attempt}: simulando clic en ${selector}`);

      // Verificar si ya está activa la pestaña (opcional, configurable)
      if (checkActive) {
        const isActive = await page.evaluate(
          (el, attr, val) => el.getAttribute(attr) === val,
          elHandle, activeAttribute, activeValue
        );
        if (isActive) {
          console.log(`[INFO] ${selector} ya está activo.`);
          return true;
        }
      }

      // Simular clic DOM nativo sin forzar navegación
      await page.evaluate(el => {
        const evt = new MouseEvent("click", {
          bubbles: true,
          cancelable: true,
          view: window,
        });
        el.dispatchEvent(evt);
      }, elHandle);

      // Esperar a que el panel cambie sin destruir el contexto (configurable)
      const waitCondition = options.waitCondition || (() =>
        !!document.querySelector('div[jscontroller][data-review-id]') ||
        document.querySelector('div.section-layout.section-scrollbox.scrollable-y')
      );
      await page.waitForFunction(waitCondition, { timeout: 15000 });

      console.log(`[INFO] Clic procesado correctamente en ${selector}`);
      await new Promise(r => setTimeout(r, waitAfterClick));
      return true;

    } catch (err) {
      if (err.message.includes("Execution context was destroyed")) {
        console.warn(`⚠️ Contexto destruido (${attempt}/${maxAttempts}), reintentando...`);
        await new Promise(r => setTimeout(r, 2500 + Math.random() * 1000));
        continue;
      }
      if (attempt === maxAttempts) {
        console.error(`[ERROR] Fallo persistente en ${selector}: ${err.message}`);
        throw err;
      }
    }
  }
  return false;
}

// 🧩 Función robusta para abrir la pestaña de reseñas (integración google-review-scraper-1)
export async function openReviewsPanel(page) {
  const reviewSelectors = [
    // Pestañas modernas (2025)
    'div[role="tab"][aria-label*="Reseñas"]',
    'div[role="tab"][aria-label*="Opiniones"]',
    'span[class*="hh2c6"][aria-label*="Reseñas"]',
    'span[class*="hh2c6"][aria-label*="Opiniones"]',
    'button[aria-label*="Reseñas"]',
    'button[aria-label*="Opiniones"]',
    // Compatibilidad con layouts antiguos
    'button[jsaction*="pane.reviewChart"]',
    'a[href*="=reviews"]',
    'div[role="tab"]'
  ];

  // ⏱️ Esperar a que el tab de reseñas esté disponible
  try {
    await page.waitForSelector(
      'div[role="tab"], button[aria-label*="Reseñas"], button[aria-label*="Opiniones"]',
      { timeout: 15000 }
    );
    console.log("[INFO] Elemento de pestaña detectado");
  } catch (e) {
    console.warn("[WARN] Timeout esperando selector de pestaña");
  }

  for (const sel of reviewSelectors) {
    try {
      console.log(`[INFO] Buscando selector: ${sel}`);
      const el = await page.$(sel);
      if (!el) continue;
      
      // Verificar si ya está activo
      const isActive = await page.evaluate((s) => {
        const elem = document.querySelector(s);
        return elem?.getAttribute('aria-selected') === 'true' || 
               elem?.classList?.contains('active') ||
               false;
      }, sel);
      
      if (isActive) {
        console.log(`[INFO] ${sel} ya está activo.`);
        return true;
      }

      // Realizar clic
      const opened = await safeClick(page, sel, {
        waitAfterClick: 2000 + Math.random() * 1000
      });
      
      if (opened) {
        console.log("[INFO] ✅ Pestaña de reseñas abierta correctamente.");
        await sleep(2000);
        return true;
      }
    } catch (err) {
      console.warn(`[WARN] Fallo con ${sel}: ${err.message}`);
    }
  }

  // Fallback: verificar si ya estamos dentro del panel
  try {
    const alreadyIn = await page.$('div[data-review-id], div[jscontroller][data-review-id]');
    if (alreadyIn) {
      console.log("[INFO] Panel de reseñas ya visible sin interacción directa.");
      return true;
    }
  } catch (e) {
    console.warn("[WARN] Error verificando panel existente");
  }

  // Recuperación: recarga si todos los selectores fallan
  console.warn("⚠️ No se pudo abrir la pestaña de reseñas. Recargando página...");
  try {
    await page.reload({ waitUntil: "domcontentloaded", timeout: 30000 });
    await sleep(3000 + Math.random() * 2000);
  } catch (e) {
    console.warn(`[WARN] Error durante recarga: ${e.message}`);
  }

  // Reintento post recarga
  for (const sel of reviewSelectors) {
    try {
      const opened = await safeClick(page, sel, {
        waitAfterClick: 2000 + Math.random() * 1000
      });
      if (opened) {
        console.log("[INFO] ✅ Pestaña de reseñas abierta tras recarga.");
        await sleep(2000);
        return true;
      }
    } catch (err) {
      console.warn(`[WARN] Fallo tras recarga con ${sel}: ${err.message}`);
    }
  }

  // Screenshot de diagnóstico
  try {
    await page.screenshot({ path: "error_open_reviews_tab.png", fullPage: true });
    console.log("[DEBUG] Captura guardada: error_open_reviews_tab.png");
  } catch (e) {
    console.warn(`[WARN] No se pudo tomar screenshot`);
  }

  throw new Error("❌ No se pudo abrir la pestaña de reseñas después de múltiples intentos");
}

export async function detectCaptcha(page) {
  const captcha = await page.$('#captcha-form, input[name="captcha"], iframe[src*="captcha"]');
  return !!captcha;
}

// 🧩 Extrae el nombre del negocio de la página
export async function extractBusinessName(page) {
  try {
    const businessName = await page.evaluate(() => {
      // Intentar obtener del h1 sin saltos de línea
      const h1 = document.querySelector('h1');
      if (h1) {
        let text = h1.innerText?.trim() || '';
        if (text && !text.includes('\n') && text.length > 2 && text.length < 150) {
          return text;
        }
      }
      // Fallback: usar title del documento
      if (document.title && document.title !== 'Google Maps') {
        const match = document.title.match(/^([^|—-]+)/);
        if (match) {
          const text = match[1].trim();
          if (text.length > 2 && text.length < 150) return text;
        }
      }
      return null;
    });
    if (businessName) {
      console.log(`[INFO] Nombre del negocio extraído: ${businessName}`);
      return businessName;
    }
    console.warn('[WARN] No se pudo extraer el nombre del negocio');
    return null;
  } catch (error) {
    console.warn(`[WARN] Error extrayendo nombre: ${error.message}`);
    return null;
  }
}

// 🧩 Extrae reseñas visibles
// 🧩 Extrae reseñas visibles completas con parseo mejorado
export async function extractVisibleReviews(page) {
  try {
    const items = await page.$$eval(
      'div[data-review-id], div[jscontroller][data-review-id], .section-review',
      nodes => {
        // Funciones auxiliares de parseo (dentro de $$eval para acceso en navegador)
        function parseRating(text) {
          if (!text) return 0;
          
          // Intenta parsear "4 estrellas", "4 stars", "4.5 out of 5", etc.
          const match = text.match(/(\d+(?:\.\d+)?)\s*(?:estrellas?|stars?|out of|de|\/)\s*(?:5)?/i);
          if (match) {
            const val = parseFloat(match[1]);
            return isNaN(val) ? 0 : Math.min(5, Math.max(0, val));
          }
          
          // Intenta contar caracteres de estrella ★
          const stars = (text.match(/★/g) || []).length;
          return stars > 0 ? stars : 0;
        }

        function parseRelativeDate(text) {
          if (!text) return new Date().toISOString();
          
          const patterns = [
            { regex: /(\d+)\s*(?:segundo|second)s?\s*ago/, mult: 1000 },
            { regex: /(\d+)\s*(?:minuto|minute)s?\s*ago/, mult: 60000 },
            { regex: /(\d+)\s*(?:hora|hour)s?\s*ago/, mult: 3600000 },
            { regex: /(\d+)\s*(?:día|day)s?\s*ago/, mult: 86400000 },
            { regex: /(\d+)\s*(?:semana|week)s?\s*ago/, mult: 604800000 },
            { regex: /(\d+)\s*(?:mes|month)s?\s*ago/, mult: 2592000000 },
            { regex: /(\d+)\s*(?:año|year)s?\s*ago/, mult: 31536000000 }
          ];
          
          for (const { regex, mult } of patterns) {
            const match = text.match(regex);
            if (match) {
              const ago = parseInt(match[1]) * mult;
              return new Date(Date.now() - ago).toISOString();
            }
          }
          
          return new Date().toISOString();
        }

        function parseLikes(text) {
          if (!text) return 0;
          const match = text.match(/(\d+)/);
          return match ? parseInt(match[1]) : 0;
        }

        return nodes.map((n, idx) => {
          const id = n.getAttribute('data-review-id') || (n.dataset?.reviewId) || n.id;
          if (!id) return null;
          
          // DEBUG: Mostrar estructura del elemento de reseña
          if (idx === 0) {
            console.log('[DEBUG] Estructura HTML del primer elemento encontrado:');
            console.log('[DEBUG] data-review-id:', n.getAttribute('data-review-id'));
            console.log('[DEBUG] clases:', n.className);
            console.log('[DEBUG] HTML truncado:', n.innerHTML.substring(0, 500));
            
            // Buscar todos los aria-label disponibles
            const allElements = n.querySelectorAll('[aria-label]');
            console.log('[DEBUG] Elementos con aria-label encontrados:', allElements.length);
            Array.from(allElements).slice(0, 10).forEach((el, i) => {
              console.log(`[DEBUG] aria-label ${i} (${el.tagName}):`, el.getAttribute('aria-label').substring(0, 100));
            });
          }
          
          // Extractores mejorados de google-review-scraper-1
          const authorEl = n.querySelector('[class*="d4r55"], [class*="fontBodyMedium"]:first-child');
          const author = authorEl?.innerText?.trim() || "Unknown";
          
          // Intenta múltiples formas de obtener rating
          let ratingEl = n.querySelector('[aria-label*="estrellas"], [aria-label*="stars"]');
          if (!ratingEl) {
            // Busca rating en svg o g-rating
            ratingEl = n.querySelector('svg g[role="img"], g-rating, svg[aria-label*="estrellas"], svg[aria-label*="stars"]');
          }
          if (!ratingEl) {
            // Busca cualquier elemento con aria-label que mention estrellas
            const allAriaElements = n.querySelectorAll('[aria-label]');
            ratingEl = Array.from(allAriaElements).find(e => {
              const label = e.getAttribute('aria-label') || '';
              return label.match(/(\d+)\s*(?:estrellas?|stars?|de|out of)/i);
            });
          }
          
          const ratingText = ratingEl?.getAttribute('aria-label') || ratingEl?.innerText || "";
          if (idx === 0) {
            console.log('[DEBUG] Rating encontrado:', ratingText ? ratingText.substring(0, 50) : '❌ NO ENCONTRADO');
          }
          const rating = parseRating(ratingText);
          
          const textEl = n.querySelector('.wiI7pd, [class*="review-text"], .section-review-content');
          const text = textEl?.innerText?.trim() || n.innerText?.split('\n')[1]?.trim() || "";
          
          const dateEl = n.querySelector('.rsqaWe, [class*="review-date"], span[class*="fontBodySmall"]');
          const dateText = dateEl?.innerText?.trim() || "";
          const date = parseRelativeDate(dateText);
          
          const likesEl = n.querySelector('.RfnDt span, [class*="likes"]');
          const likesText = likesEl?.innerText || "0";
          const likes = parseLikes(likesText);
          
          // === NUEVO BLOQUE: extracción de respuesta del propietario ===
          let ownerResponse = null;
          try {
            const ownerBlock = n.querySelector('div.CDe7pd, div.ODSEW-ShBeI-text, div[class*="reply"]');
            if (ownerBlock) {
              const ownerLabel =
                n.querySelector('div.CDe7pd')?.innerText ||
                n.querySelector('span[class*="owner"]')?.innerText ||
                "Respuesta del propietario";

              const ownerText =
                n.querySelector('div.ODSEW-ShBeI-text')?.innerText ||
                n.querySelector('span[class*="reply-text"]')?.innerText ||
                "";

              if (ownerText.trim()) {
                ownerResponse = {
                  label: ownerLabel,
                  text: ownerText.trim().substring(0, 5000)
                };
              }
            }
          } catch (e) {
            // Silenciar errores en extracción de respuesta del propietario
          }
          
          return { 
            id, 
            author, 
            rating,
            text: text.substring(0, 5000),
            date,
            dateRaw: dateText,
            likes,
            ownerResponse,
            timestamp: new Date().toISOString()
          };
        }).filter(r => r !== null);
      }
    );
    
    return items.filter(r => !!r.id && !!r.text);
  } catch (error) {
    console.warn(`[WARN] Error extrayendo reseñas: ${error.message}`);
    return [];
  }
}


// 🌀 Scroll humano con delays dinámicos y jitter (integración google-review-scraper-1)
export async function humanScrollLoop(page, targetReviews = 1000, onProgress = () => {}) {
  const maxNoNew = 25;  // Aumentado a 25 para permitir más intentos sin nuevas reseñas (modo unlimited)
  let noNew = 0;
  let seen = new Set();
  let totalReviews = [];
  let scrolls = 0;
  const minDelay = FAST_MODE ? 200 : 800;
  const maxDelay = FAST_MODE ? 500 : 1500;

  console.log(`[INFO] Iniciando scroll humano hacia ${targetReviews} reseñas...`);

  while (totalReviews.length < targetReviews && noNew < maxNoNew) {
    // 🌀 Scroll con cantidad aleatoria
    const scrollAmount = 300 + Math.floor(Math.random() * 450);
    
    // Scroll en elemento específico del panel
    const scrollInfo = await page.evaluate((s) => {
      // Buscar el contenedor correcto de reseñas - intenta múltiples estrategias
      let scrollable = document.querySelector('[role="region"] > div:nth-child(2)') ||
                       document.querySelector('div[role="main"] > div:last-child') ||
                       document.querySelector('.section-layout.section-scrollbox') || 
                       document.querySelector('[role="main"]');
      
      // Si no encontró, intenta buscar el padre del primer review
      if (!scrollable) {
        const firstReview = document.querySelector('[data-review-id]');
        if (firstReview) {
          let parent = firstReview.parentElement;
          for (let i = 0; i < 5 && parent; i++) {
            const style = window.getComputedStyle(parent);
            if (style.overflowY === 'auto' || style.overflowY === 'scroll') {
              scrollable = parent;
              break;
            }
            parent = parent.parentElement;
          }
        }
      }
      
      if (!scrollable) scrollable = window;
      
      const before = scrollable instanceof Element ? scrollable.scrollTop : window.scrollY;
      
      if (scrollable instanceof Element) {
        scrollable.scrollBy(0, s);
      } else {
        window.scrollBy(0, s);
      }
      
      const after = scrollable instanceof Element ? scrollable.scrollTop : window.scrollY;
      const selectorInfo = scrollable instanceof Element ? 
        `${scrollable.tagName}.${scrollable.className.split(' ')[0]}` : 
        'window';
      
      return {
        scrollable: selectorInfo,
        before,
        after,
        moved: after - before
      };
    }, scrollAmount);
    
    if (scrolls === 1) {
      console.log(`[INFO] Contenedor scrollable: ${scrollInfo.scrollable}`);
      console.log(`[INFO] Scroll movement: antes=${scrollInfo.before}, después=${scrollInfo.after}, movido=${scrollInfo.moved}px`);
    }
    
    scrolls++;

    // ⏱️ Delay con jitter (±10%)
    const baseDelay = minDelay + Math.floor(Math.random() * (maxDelay - minDelay));
    const jitter = baseDelay * (0.9 + Math.random() * 0.2);
    await sleep(jitter);
    
    // ⏳ Esperar a que se carguen nuevas reviews (máximo 5 segundos)
    const waitForNewReviews = async () => {
      let attempts = 0;
      while (attempts < 50) {
        const count = await page.evaluate(() => 
          document.querySelectorAll('[data-review-id]').length
        );
        if (count > totalReviews.length || attempts > 30) {
          break;
        }
        await sleep(100);
        attempts++;
      }
    };
    await waitForNewReviews();
    
    if (scrolls % 3 === 0) {
      console.log(`[INFO] Scroll #${scrolls} — delay: ${Math.round(jitter)}ms, reseñas encontradas: ${totalReviews.length}`);
    }

    // Extraer reseñas visibles
    const vis = await extractVisibleReviews(page);
    let newly = 0;
    
    for (const r of vis) {
      if (!seen.has(r.id)) { 
        seen.add(r.id); 
        totalReviews.push(r);
        newly++; 
      }
    }
    
    if (newly === 0) {
      noNew++;
      console.warn(`⚠️ Sin nuevas reseñas (${noNew}/${maxNoNew})`);
    } else { 
      noNew = 0;
    }

    await onProgress({ scrolls, totalFound: totalReviews.length, newly });
  }

  console.log(`[INFO] Scroll finalizado — scrolls=${scrolls}, total=${totalReviews.length}, únicas=${seen.size}`);
  return { 
    scrolls, 
    total: totalReviews.length, 
    reviews: totalReviews,
    ids: Array.from(seen) 
  };
}

// Funciones auxiliares inline
const getRandomUserAgent = () => {
  const agents = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36'
  ];
  return agents[Math.floor(Math.random() * agents.length)];
};

const getRandomViewport = () => {
  const viewports = [
    { width: 1920, height: 1080 },
    { width: 1366, height: 768 },
    { width: 1536, height: 864 }
  ];
  return viewports[Math.floor(Math.random() * viewports.length)];
};

const validatePlaceId = (placeId) => {
  return placeId && placeId.length === 27 && /^[A-Za-z0-9_-]+$/.test(placeId);
};

const validateMaxReviews = (maxReviews) => {
  return maxReviews >= 1 && maxReviews <= MASS_SCRAPER_CONFIG.MAX_REVIEWS;
};

const cleanBusinessName = (name) => {
  return name ? name.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_") : "PLACE_UNKNOWN";
};

const createUniqueKey = (user, date, text) => {
  return `${user}_${date}_${text.substring(0, 50)}`.replace(/[^a-zA-Z0-9_]/g, '');
};

// Clase monitor simplificada
class ScrapingMonitor {
  constructor(businessName, placeId) {
    this.businessName = businessName;
    this.placeId = placeId;
    this.startTime = Date.now();
    this.errors = 0;
    this.captchaCount = 0;
    this.rateLimitCount = 0;
    this.proxyRotations = 0;
  }

  updateProgress(reviewsCount, batchNumber) {
    console.log(`📊 Progreso: ${reviewsCount} reseñas, Lote: ${batchNumber}`);
  }

  incrementCaptchaCount() { this.captchaCount++; }
  incrementRateLimitCount() { this.rateLimitCount++; }
  incrementProxyRotations() { this.proxyRotations++; }
  addError(error) { this.errors++; }

  calculateStats() {
    const elapsed = Math.round((Date.now() - this.startTime) / 60000);
    return {
      elapsed,
      reviewsPerMinute: 0,
      proxyRotations: this.proxyRotations,
      errors: this.errors,
      captchaCount: this.captchaCount,
      rateLimitCount: this.rateLimitCount
    };
  }
}

// Funciones auxiliares inline removidas - ahora importadas de utils.js

// loadProxies y selectRandomProxy importadas de utils.js

const clickWithRetry = async (page, selector, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      const element = await page.waitForSelector(selector, { timeout: 5000 });
      await element.click();
      return true;
    } catch (e) {
      if (i === retries - 1) return false;
      await sleep(randomDelay(1000, 3000));
    }
  }
  return false;
};


// Concurrencia controlada
async function runWithConcurrency(items, workerFn, concurrency=2) {
  const pool = [];
  let idx = 0;
  const results = [];
  async function next() {
    if (idx >= items.length) return Promise.resolve();
    const i = idx++;
    try {
      const r = await workerFn(items[i]);
      results[i] = { status: "fulfilled", value: r };
    } catch (e) {
      results[i] = { status: "rejected", reason: e };
    }
    return next();
  }
  for (let i=0;i<Math.min(concurrency, items.length);i++) pool.push(next());
  await Promise.all(pool);
  return results;
}

const gotoWithRetry = async (page, url, options = {}, retries = 3) => {
  for (let i = 0; i < retries; i++) {
    try {
      await page.goto(url, { ...options, timeout: 30000 });
      return true;
    } catch (e) {
      if (i === retries - 1) return false;
      await sleep(randomDelay(2000, 5000));
    }
  }
  return false;
};

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Configurar Puppeteer
puppeteer.use(StealthPlugin());
puppeteer.use(AnonymizeUAPlugin());

export async function massScrapeReviews() {
  let browser = null;
  let dataDir = null;
  
  try {
    // 📋 Lee parámetros desde flags
    const placeId = flags["place-id"] || flags.placeId || flags.pid;
    let maxReviews = flags["max-reviews"] ?? flags.maxReviews ?? flags.max ?? 1000;
    
    // 🎯 Soporte para "unlimited" o "all" para extraer todas las reviews disponibles
    if (typeof maxReviews === 'string') {
      if (maxReviews.toLowerCase() === 'unlimited' || maxReviews.toLowerCase() === 'all') {
        maxReviews = MASS_SCRAPER_CONFIG.MAX_REVIEWS;
        console.log("🔓 Modo UNLIMITED activado - intentará extraer hasta", MASS_SCRAPER_CONFIG.MAX_REVIEWS, "reviews");
      } else {
        maxReviews = Number(maxReviews);
      }
    }
    maxReviews = Number(maxReviews) || 1000;

    if (!placeId || !isValidPlaceId(placeId)) {
      console.error("❌ Debes proporcionar un --place-id válido (27 caracteres)");
      process.exit(1);
    }

    // 📋 Validar maxReviews
    if (maxReviews < 1 || maxReviews > MASS_SCRAPER_CONFIG.MAX_REVIEWS) {
      console.error(`❌ maxReviews debe estar entre 1 y ${MASS_SCRAPER_CONFIG.MAX_REVIEWS}`);
      process.exit(1);
    }

    // 🚀 Construye URL de Maps por PlaceID
    const url = `https://www.google.com/maps/place/?q=place_id:${placeId}`;
    console.log("🚀 === INICIANDO SCRAPING MASIVO ===");
    console.log("📍 Place ID:", placeId);
    console.log("🎯 Objetivo de reseñas:", maxReviews);
    console.log("🌍 URL:", url);
    if (FAST_MODE) console.log("⚡ FAST MODE: ON (delays reducidos)");

    // 🎮 Lanza Puppeteer con configuración mejorada
    browser = await puppeteer.launch({
      headless: false,
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--disable-gpu"
      ],
      defaultViewport: null
    });

    let page = await browser.newPage();
    console.log("✅ Puppeteer lanzado correctamente");

    // 🐛 Listener para capturar console.log del navegador
    page.on('console', msg => {
      if (msg.text().includes('[DEBUG]')) {
        console.log('[BROWSER]', msg.text());
      }
    });

  await applyHumanHeaders(page);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 });

  // 🔄 Espera adicional para evitar destrucción temprana del contexto
  await new Promise(r => setTimeout(r, 3500 + Math.random() * 1500));

  // 🧩 Reintentar inyección de cookies y UA sin evaluar directamente si falla
  try {
    await page.evaluateOnNewDocument(() => {
      Object.defineProperty(navigator, "webdriver", { get: () => false });
    });
  } catch (e) {
    console.warn("[WARN] No se pudo establecer webdriver=false (ignorable)");
  }

  // ⚙️ Asegurar estabilidad de contexto antes de operar con el DOM
  let contextOK = false;
  for (let i = 0; i < 5; i++) {
    try {
      await page.evaluate(() => document.readyState);
      contextOK = true;
      break;
    } catch {
      console.warn(`[WARN] Contexto inestable, esperando reintento ${i + 1}/5...`);
      await new Promise(r => setTimeout(r, 1200));
    }
  }
  if (!contextOK) console.warn("⚠️ Contexto potencialmente inestable, continuando con precaución");

  // Cookies
  await acceptCookiesIfPresent(page);

  // 🔄 Espera adicional tras aceptar cookies para evitar destrucción por navegación interna
  await new Promise(r => setTimeout(r, 2000 + Math.random() * 1000));

  // ⚙️ Verificar estabilidad de contexto tras cookies
  let contextOKAfterCookies = false;
  for (let i = 0; i < 3; i++) {
    try {
      await page.evaluate(() => document.readyState);
      contextOKAfterCookies = true;
      break;
    } catch {
      console.warn(`[WARN] Contexto inestable tras cookies, esperando reintento ${i + 1}/3...`);
      await new Promise(r => setTimeout(r, 1000));
    }
  }
  if (!contextOKAfterCookies) {
    console.warn("⚠️ Contexto inestable tras aceptar cookies, recargando página...");
    await page.reload({ waitUntil: "domcontentloaded" });
    await new Promise(r => setTimeout(r, 3000 + Math.random() * 1500));
  }

  // CAPTCHA?
  if (await detectCaptcha(page)) {
    console.warn("[BLOCK] CAPTCHA detectado al inicio. Cierra y reintenta con otro proxy/UA.");
    await browser.close();
    process.exit(1);
  }

  // Abre panel de reseñas
  await new Promise(resolve => setTimeout(resolve, 2000));

  let retries = 0;
  const maxRetries = 3;
  while (retries < maxRetries) {
    try {
      await openReviewsPanel(page);
      break; // si se abre correctamente, salir del bucle
    } catch (err) {
      if (err.message.includes("Execution context was destroyed")) {
        retries++;
        console.warn(`⚠️ Contexto destruido (${retries}/${maxRetries}), reintentando...`);
        await page.reload({ waitUntil: "domcontentloaded" });
        await page.waitForTimeout(2000 + Math.random() * 1500);
        continue;
      } else {
        throw err; // error real, salir
      }
    }
  }
  if (retries >= maxRetries) throw new Error("❌ Fallo persistente: no se pudo abrir el panel de reseñas.");

  // 🧩 Extraer nombre del negocio y crear directorio con la estructura correcta
  const apiKey = process.env.GOOGLE_MAPS_API_KEY;
  let businessName = await extractBusinessName(page, placeId, apiKey);
  if (!businessName) {
    businessName = `Lugar_${placeId.substring(0, 8)}`;
    console.log(`[INFO] Se usará nombre por defecto: ${businessName}`);
  }
  
  dataDir = createDataDirectory(businessName, placeId);
  console.log(`📁 Directorio de datos: ${dataDir}`);

  // Ordenar por "Más recientes" si es posible (tolerante a fallos)
  try {
    console.log("[INFO] 🔄 Intentando ordenar reseñas por 'Más recientes'...");
    
    const orderSelectors = [
      'button[aria-label*="Ordenar"]',
      'button[aria-label*="Sort"]',
      'button[jsaction*="pane.reviewChart"]',
      'button[data-tooltip*="Ordenar"]'
    ];

    let orderBtnClicked = false;
    for (const selector of orderSelectors) {
      const orderBtn = await page.$(selector);
      if (orderBtn) {
        await orderBtn.click();
        console.log(`[INFO] ✓ Botón ordenar clickeado: ${selector}`);
        orderBtnClicked = true;
        await new Promise(resolve => setTimeout(resolve, 800 + Math.random() * 800));
        break;
      }
    }

    if (orderBtnClicked) {
      const menuItems = await page.evaluate(() => {
        return Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], .goog-menuitem, li'))
          .filter(el => {
            const text = (el.textContent || '').toLowerCase();
            return /más recientes|recientes|newest|recent/i.test(text) && el.offsetParent !== null;
          })
          .map(el => ({
            text: el.textContent?.trim() || '',
            visible: el.offsetParent !== null
          }));
      });

      if (menuItems.length > 0) {
        const recentOption = menuItems[0];
        console.log(`[INFO] Encontrada opción: "${recentOption.text}"`);
        
        const clicked = await page.evaluate(() => {
          const items = Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], .goog-menuitem, li'));
          for (const el of items) {
            const text = (el.textContent || '').toLowerCase();
            if (/más recientes|recientes|newest|recent/i.test(text) && el.offsetParent !== null) {
              el.click();
              return true;
            }
          }
          return false;
        });

        if (clicked) {
          console.log("[INFO] ✅ Orden aplicado: Más recientes");
          await new Promise(resolve => setTimeout(resolve, 1000 + Math.random() * 1000));
        }
      } else {
        console.log("[WARN] ⚠️ No se encontró opción 'Más recientes' en el menú");
      }
    } else {
      console.log("[WARN] ⚠️ No se encontró botón de ordenamiento");
    }
  } catch (e) {
    console.warn(`[WARN] Error al ordenar reseñas: ${e.message}`);
  }

    // 🌀 Bucle de scroll humano hasta alcanzar maxReviews
    const scrollResult = await humanScrollLoop(page, maxReviews, async ({ totalFound, newly, scrolls }) => {
      // Mostrar progreso
      if (scrolls % 5 === 0) {
        console.log(`📊 Progreso: ${totalFound} reseñas encontradas (batch ${scrolls})`);
      }
    });

    // 📊 Procesar y validar reseñas
    let reviews = scrollResult.reviews || [];
    reviews = reviews.slice(0, maxReviews);

    const totalOut = reviews.length;
    console.log(`\n📦 Reseñas recopiladas: ${totalOut}/${maxReviews}`);
    console.log(`📊 Scrolls realizados: ${scrollResult.scrolls}`);

    if (totalOut === 0) {
      console.warn("⚠️ No se extrajeron reseñas. Verifique que el Place ID es válido.");
      await browser.close();
      process.exit(1);
    }

    // === NUEVO BLOQUE: mostrar resumen de respuestas del propietario ===
    const reviewsWithOwnerResponse = reviews.filter(r => r.ownerResponse && r.ownerResponse.text);
    if (reviewsWithOwnerResponse.length > 0) {
      console.log(`\n💬 Respuestas del propietario encontradas: ${reviewsWithOwnerResponse.length}/${totalOut}`);
      // Mostrar las primeras 3 como preview
      reviewsWithOwnerResponse.slice(0, 3).forEach((r, idx) => {
        console.log(`\n  ⭐ Reseña ${idx + 1}: ${r.author} - ${r.rating} estrellas`);
        console.log(`     📝 "${r.text.substring(0, 80)}${r.text.length > 80 ? '...' : ''}"`);
        console.log(`     💬 Respuesta: "${r.ownerResponse.text.substring(0, 80)}${r.ownerResponse.text.length > 80 ? '...' : ''}"`);
      });
      if (reviewsWithOwnerResponse.length > 3) {
        console.log(`     ... y ${reviewsWithOwnerResponse.length - 3} respuestas más`);
      }
    } else {
      console.log(`\n💬 No se encontraron respuestas del propietario en esta búsqueda.`);
    }

    // 💾 Guardado usando el módulo storage.js mejorado
    console.log("[INFO] Guardando reseñas en directorio de datos...");
    const reviewsPath = saveReviews(reviews, placeId, { dataDir, businessName });
    
    // 💾 Guardar metadatos
    const metadata = {
      businessName,
      placeId,
      totalReviews: totalOut,
      targetReviews: maxReviews,
      scrollsPerformed: scrollResult.scrolls,
      extractedAt: new Date().toISOString(),
      reviewsFile: reviewsPath
    };
    saveMetadata(metadata, placeId, { dataDir, businessName });

    // 📊 Crear checkpoint final
    saveCheckpoint({
      placeId,
      businessName,
      totalReviews: totalOut,
      status: 'completed'
    }, 0, { dataDir });

    // 📋 Exportar como CSV también
    let csvPath = null;
    try {
      const csvResult = exportAsCSV(reviews, placeId, { dataDir, businessName });
      csvPath = csvResult.absolutePath;
    } catch (e) {
      console.warn(`⚠️ CSV export falló: ${e.message}`);
    }

    console.log(`\n${'='.repeat(80)}`);
    console.log(`✅ SCRAPING COMPLETADO CON ÉXITO`);
    console.log(`${'='.repeat(80)}`);
    console.log(`📊 Total de reseñas: ${totalOut}`);
    console.log(`📁 Directorio de datos: ${path.resolve(dataDir)}`);
    if (csvPath) {
      console.log(`📋 CSV generado: ${csvPath}`);
      console.log(`\n💡 Puedes copiar esta ruta directamente:`);
      console.log(`   ${csvPath}`);
    }
    console.log(`${'='.repeat(80)}`);
  } catch (error) {
    console.error(`\n❌ Error durante scraping: ${error.message}`);
    console.error(error.stack);
    if (dataDir) {
      try {
        saveCheckpoint({
          status: 'error',
          error: error.message
        }, -1, { dataDir });
      } catch (e) {
        console.warn(`⚠️ No se pudo guardar checkpoint de error`);
      }
    }
  } finally {
    // Cierre seguro del navegador
    if (browser) {
      try {
        await browser.close();
        console.log("🔒 Navegador cerrado correctamente");
      } catch (e) {
        console.warn(`⚠️ Error cerrando navegador: ${e.message}`);
      }
    }
  }
}

// --- 🧱 Manejo robusto de errores a nivel de proceso ---
process.on("unhandledRejection", err => {
  console.error("\n⚠️ Promesa rechazada no manejada:");
  console.error("  Mensaje:", err?.message || err);
  console.error("  Stack:", err?.stack);
  console.log("🔄 Manteniendo proceso en ejecución para diagnóstico...");
  // No salir del proceso aquí - dejar que continúe
});

process.on("uncaughtException", err => {
  console.error("\n💥 Excepción no capturada en el proceso:");
  console.error("  Mensaje:", err?.message || err);
  console.error("  Stack:", err?.stack);
  console.log("🔄 Manteniendo navegador abierto para diagnóstico...");
  // Para excepciones no capturadas, salir después de log
  process.exit(1);
});

// === EJECUCIÓN ===
const __filenameExec = fileURLToPath(import.meta.url);
const __normalizedArg = path.resolve(process.argv[1] || "");

if (__filenameExec === __normalizedArg) {
  await massScrapeReviews();
}




