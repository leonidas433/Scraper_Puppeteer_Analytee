import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import AnonymizeUAPlugin from 'puppeteer-extra-plugin-anonymize-ua';
import fs from 'fs';
import path from 'path';
import { DirectoryManager } from '../core/utils.js';
import { Logger } from '../core/logger.js';
import { Config } from '../core/config.js';
import { CacheManager } from '../core/cacheManager.js';
import { GooglePlacesAPI } from '../core/api.js';
import {
  sleep,
  randomDelay,
  ensureDir,
  detectLanguageSimple,
  loadProxies,
  selectRandomProxy,
  getRandomElement,
  testAllProxies,
  testProxy,
  markProxyAsFailed,
  cleanText,
} from '../core/utils.js';

export class ReviewsScraper {
  constructor() {
    this.config = new Config();
    this.logger = new Logger();
    this.directory = new DirectoryManager(this.logger);
    this.cache = new CacheManager();
    this.api = new GooglePlacesAPI();
    this.setupPuppeteer();
    this.setupSelectors();
    this.setupUserAgents();
  }

  cleanupTempFiles(placeDir) {
    try {
      // Limpiar archivos temporales y checkpoints antiguos
      const files = fs.readdirSync(placeDir);
      let cleanedCount = 0;

      files.forEach((file) => {
        const filePath = path.join(placeDir, file);

        // Eliminar archivos temporales y checkpoints antiguos (excepto el último)
        if (
          file.startsWith('checkpoint_batch_') ||
          file.includes('_partial.') ||
          file.endsWith('.tmp') ||
          file.endsWith('.temp')
        ) {
          try {
            fs.unlinkSync(filePath);
            cleanedCount++;
            this.logger.debug(`Archivo temporal eliminado: ${file}`);
          } catch (error) {
            this.logger.warn(`No se pudo eliminar archivo temporal: ${file}`, error);
          }
        }
      });

      if (cleanedCount > 0) {
        this.logger.info(`🧹 Limpieza completada: ${cleanedCount} archivos temporales eliminados`);
      }
    } catch (error) {
      this.logger.warn('Error durante limpieza de archivos temporales', error);
    }
  }

  setupPuppeteer() {
    puppeteer.use(StealthPlugin());
    puppeteer.use(AnonymizeUAPlugin());
  }

  async detectPageError(page) {
    const errorText = await page.evaluate(() => {
      const errorElements = document.querySelectorAll('body');
      for (const el of errorElements) {
        const text = el.innerText || '';
        if (
          text.includes('Esta página no funciona') ||
          text.includes("This page isn't working") ||
          text.includes('No se puede acceder') ||
          text.includes('Cannot access') ||
          text.includes('Error 429') ||
          text.includes('Too Many Requests')
        ) {
          return text;
        }
      }
      return null;
    });

    if (errorText) {
      throw new Error(`Error de página detectado: ${errorText}`);
    }
  }

  setupSelectors() {
    // ✅ ACTUALIZADO: Selectores modernos para Google Maps 2024
    this.reviewSelectors = [
      // Selectores principales actuales
      'div[jscontroller][data-review-id]',
      'div.jftiEf',
      'div.fontBodyMedium',

      // Nuevos selectores basados en estructura actual
      '[data-hveid*="reviews"]',
      '[jscontroller*="reviews"]',
      '[jsaction*="reviews"]',

      // Selectores por atributos
      'div[role="listitem"]',
      'div[aria-label*="review"]',
      'div[data-value*="review"]',

      // Selectores de respaldo
      'div.review-item',
      'div.gws-localreviews__google-review',
      'div.review-full-text',
      'div.review-container',
      'div.single-review',
      'div.review-content',

      // Selectores experimentales para detectar cambios
      'div[data-test*="review"]',
      'div[data-testid*="review"]',
      'div[class*="review"]',
    ];

    // ✅ ACTUALIZADO: Estrategias modernas para pestaña de reseñas (Google Maps 2024)
    this.reviewTabSelectors = [
      // Estrategia 1: Tabs principales con aria-label (Google Maps 2024)
      {
        strategy: 'aria_tab_reviews',
        selector: '[role="tab"][aria-label*="Reseñas"], [role="tab"][aria-label*="Reviews"]',
        filter: (el) => el.offsetParent !== null,
      },
      // Estrategia 2: Tabs con data-tab
      {
        strategy: 'data_tab_reviews',
        selector: '[data-tab="reviews"], [data-tab*="review"]',
        filter: (el) => el.offsetParent !== null,
      },
      // Estrategia 3: Botones con jsaction específico
      {
        strategy: 'jsaction_reviews',
        selector: 'button[jsaction*="reviews"], button[jsaction*="pane.rating"]',
        filter: (el) => el.offsetParent !== null,
      },
      // Estrategia 4: Elementos con texto específico (más preciso)
      {
        strategy: 'text_reviews_precise',
        selector: 'button, [role="button"], [role="tab"]',
        filter: (el) => {
          const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '')
            .toLowerCase()
            .trim();
          // Más específico: solo "reseñas" o "reviews", no variaciones
          return /^reseñas?$|^reviews?$|^\(\d+\)\s*reseñas?$/i.test(text);
        },
      },
      // Estrategia 5: Elementos con data-value
      {
        strategy: 'data_value_reviews',
        selector: '[data-value*="reviews"], [data-value*="review"]',
        filter: (el) => el.offsetParent !== null,
      },
      // Estrategia 6: Búsqueda exhaustiva mejorada
      {
        strategy: 'exhaustive_improved',
        selector: 'button, a, div[role], span[role]',
        filter: (el) => {
          const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '')
            .toLowerCase()
            .trim();
          const visible =
            el.offsetParent !== null &&
            window.getComputedStyle(el).display !== 'none' &&
            window.getComputedStyle(el).visibility !== 'hidden';
          return (
            visible &&
            /^reseñas?$|^reviews?$/i.test(text) &&
            el.tagName !== 'SCRIPT' &&
            el.tagName !== 'STYLE'
          );
        },
      },
      // Estrategia 7: Fallback por posición relativa
      {
        strategy: 'position_based',
        selector: '[role="tab"], button[class*="tab"]',
        filter: (el) => {
          // Buscar tabs que estén cerca de otros tabs conocidos
          const rect = el.getBoundingClientRect();
          const nearbyTabs = Array.from(document.querySelectorAll('[role="tab"]')).filter((tab) => {
            if (tab === el) return false;
            const tabRect = tab.getBoundingClientRect();
            // Están en la misma fila (diferencia Y pequeña)
            return Math.abs(rect.top - tabRect.top) < 10;
          });
          return nearbyTabs.length > 0 && el.offsetParent !== null;
        },
      },
      // 🆕 Estrategia 8: Google Maps 2024 - Selectores específicos modernos
      {
        strategy: 'google_maps_2024_tabs',
        selector: '[role="tab"][data-tab-id="reviews"], [data-hveid*="reviews"]',
        filter: (el) => el.offsetParent !== null && window.getComputedStyle(el).display !== 'none',
      },
      // 🆕 Estrategia 9: Navegación por estructura DOM moderna
      {
        strategy: 'dom_structure_modern',
        selector:
          'div[role="tablist"] [role="tab"]:nth-child(2), .tab-container [data-tab*="review"]',
        filter: (el) => {
          const text = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
          return text.includes('reseña') || text.includes('review') || text.includes('opiniones');
        },
      },
      // 🆕 Estrategia 10: Detección por patrones de URL y navegación
      {
        strategy: 'url_pattern_detection',
        selector: 'a[href*="reviews"], button[data-url*="reviews"]',
        filter: (el) => el.offsetParent !== null,
      },
    ];

    // Selectores para ordenar reseñas
    this.sortSelectors = [
      // Estrategia 1: Botón con "Más útiles" (opción actual por defecto)
      {
        strategy: 'sort_button_default',
        selector: 'button, [role="button"]',
        filter: (el) => {
          const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '')
            .toLowerCase()
            .trim();
          return /más útiles|most helpful|útiles/i.test(text);
        },
        action: 'click',
      },
      // Estrategia 2: Botón de ordenar genérico
      {
        strategy: 'sort_button_text',
        selector: 'button, [role="button"]',
        filter: (el) => {
          const text = (el.innerText || el.textContent || el.getAttribute('aria-label') || '')
            .toLowerCase()
            .trim();
          return /ordenar|sort|filtrar|filter|^más/i.test(text);
        },
        action: 'click',
      },
      // Estrategia 3: dropdown de orden nativo
      {
        strategy: 'sort_dropdown',
        selector: 'select[data-sort], select[aria-label*="orden"], select[aria-label*="sort"]',
        filter: (el) => el.offsetParent !== null,
        action: 'select',
        value: 'Más recientes',
      },
      // Estrategia 4: menú de opciones de orden (role="menu" o "listbox")
      {
        strategy: 'sort_menu',
        selector: '[role="menu"] [role="menuitem"], [role="listbox"] [role="option"], .sort-option, .filter-option',
        filter: (el) => {
          const text = (el.innerText || el.textContent || '').toLowerCase().trim();
          return /más recientes|most recent|nuevo|new|reciente|recent/i.test(text);
        },
        action: 'click',
      },
    ];

    // ✅ ACTUALIZADO: Selectores modernos para paginación
    this.paginationSelectors = [
      // Selectores principales actuales
      "button[aria-label*='más']",
      "button[aria-label*='more']",
      "button[aria-label*='ver más']",
      "button[aria-label*='load more']",
      "button[aria-label*='show more']",

      // Nuevos selectores para Google Maps 2024
      'button[data-show-more]',
      'button[data-load-more]',
      '[role="button"][aria-label*="más"]',
      '[role="button"][aria-label*="more"]',

      // Selectores por jsaction
      "button[jsaction*='more']",
      "button[jsaction*='loadMore']",

      // Selectores específicos de reseñas
      "button[aria-label*='más reseñas']",
      "button[aria-label*='more reviews']",
      'button[data-more-reviews]',
      'button.more-reviews-btn',

      // Selectores de respaldo
      'div.more-reviews',
      'a.more-reviews-link',
      "span[role='button'][aria-label*='más']",
      "div[aria-label*='más']",
      "a[aria-label*='más']",

      // Selectores experimentales
      'button[class*="more"]',
      'div[class*="more"]',
      '[data-testid*="more"]',
    ];

    this.loadingSelectors = [
      "div[role='progressbar']",
      "div[aria-label*='cargando']",
      "div[aria-label*='loading']",
      'div.spinner',
      'div.loading',
    ];
  }

  setupUserAgents() {
    this.userAgents = [
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36',
      'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36',
      'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0',
    ];

    this.viewports = [
      { width: 1920, height: 1080 },
      { width: 1440, height: 900 },
      { width: 1366, height: 768 },
      { width: 1536, height: 864 },
    ];
  }

  /**
   * Click con reintentos - Método auxiliar del scraper original
   * @param {Page} page - Instancia de Puppeteer page
   * @param {string} selector - Selector CSS del elemento
   * @param {number} retries - Número de reintentos (default: 3)
   * @returns {Promise<boolean>} - True si el click fue exitoso
   */
  async clickWithRetry(page, selector, retries = 3) {
    for (let i = 0; i < retries; i++) {
      try {
        const element = await page.waitForSelector(selector, { timeout: 5000 });
        await element.click();
        return true;
      } catch (e) {
        this.logger.warn(`Intento ${i + 1} fallido para click en ${selector}: ${e.message}`);
        if (i === retries - 1) return false;
        await sleep(randomDelay(1000, 3000));
      }
    }
    return false;
  }

  async extractReviewsOptimized(page) {
    try {
      const allReviewsData = await page.evaluate(
        (selectors) => {
          const reviews = [];

          const findElement = (element, selectors) => {
            for (const selector of selectors) {
              const el = element.querySelector(selector);
              if (el && el.textContent?.trim()) {
                return el;
              }
            }
            return null;
          };

          for (const selector of selectors.REVIEW_SELECTORS) {
            const elements = document.querySelectorAll(selector);
            for (const element of elements) {
              try {
                const userSelectors = [
                  '.d4r55',
                  '.X43Kjb',
                  "[data-value*='user']",
                  '.section-review-author-name',
                ];
                const ratingSelectors = [
                  '.kvMYJc',
                  "[aria-label*='estrella']",
                  "[aria-label*='star']",
                  '[data-rating]',
                ];
                const dateSelectors = [
                  '.rsqaWe',
                  '.DU9Pgb',
                  "[data-value*='date']",
                  '.review-date',
                ];
                const textSelectors = [
                  '.wiI7pd',
                  '.MyEned',
                  "[data-value*='text']",
                  '.review-text',
                  '.review-full-text',
                ];

                const user = findElement(element, userSelectors)?.innerText?.trim() || 'Anónimo';
                const ratingElement = findElement(element, ratingSelectors);
                const rating =
                  ratingElement?.getAttribute('aria-label') ||
                  ratingElement?.getAttribute('data-rating') ||
                  ratingElement?.innerText?.trim() ||
                  '';
                const date = findElement(element, dateSelectors)?.innerText?.trim() || '';
                const text = findElement(element, textSelectors)?.innerText?.trim() || '';

                const reviewLikes =
                  findElement(element, [
                    '.review-like-count',
                    "[aria-label*='me gusta']",
                    "[aria-label*='likes']",
                  ])?.innerText?.trim() || '0';

                // Contar fotos/imágenes
                const photoElements = element.querySelectorAll(
                  "img[src*='review'], img[src*='photos'], .review-photo"
                );
                const reviewPhotos = photoElements.length || '0';

                // Extraer URLs de imágenes
                const imageUrls = [];
                photoElements.forEach((img) => {
                  const src = img.src || img.dataset.src;
                  if (src) imageUrls.push(src);
                });

                const reviewResponseTime =
                  findElement(element, [
                    '.review-response-time',
                    "[aria-label*='respondió']",
                  ])?.innerText?.trim() || '';

                // ⭐ NUEVOS CAMPOS - Extracción expandida
                // 1. Review ID / Link
                let reviewId = '';
                let reviewLink = '';
                const reviewLinkEl = element.querySelector('a[href*="maps"], a[href*="place"]');
                if (reviewLinkEl) {
                  reviewLink = reviewLinkEl.href || '';
                  // Extraer ID del link
                  const idMatch = reviewLink.match(/(?:review_id=|\/reviews\/)([a-zA-Z0-9]+)/);
                  reviewId = idMatch ? idMatch[1] : '';
                }

                // 2. Información del usuario extendida
                const userProfileLink = element.querySelector(
                  'a[href*="profile"], a[href*="user"]'
                );
                const contributorId = userProfileLink?.href?.match(/\/([a-zA-Z0-9]+)/)?.[1] || '';

                const userThumbnail =
                  element.querySelector('.profile-picture img, .user-avatar img')?.src || '';
                const isLocalGuide =
                  element.innerText?.includes('Local Guide') ||
                  element.querySelector('[aria-label*="Local Guide"]')
                    ? 'Yes'
                    : 'No';

                // Extraer número de reseñas y fotos del usuario
                const userStatsText =
                  element.querySelector('.user-review-count, .user-contribution-count')
                    ?.innerText || '';
                const userReviewsMatch = userStatsText.match(/(\d+)\s*(?:review|reseña)/i);
                const userPhotosMatch = userStatsText.match(/(\d+)\s*(?:photo|foto)/i);
                const userReviews = userReviewsMatch ? userReviewsMatch[1] : '';
                const userPhotos = userPhotosMatch ? userPhotosMatch[1] : '';

                // 3. Fuente de la reseña
                const source =
                  element.querySelector('[aria-label*="Google"], .review-source')?.innerText ||
                  'Google Maps';

                // 4. Respuesta del negocio (owner response)
                let ownerResponse = '';
                let ownerResponseDate = '';
                const responseElement = element.querySelector(
                  '.owner-response, [data-owner-response]'
                );
                if (responseElement) {
                  ownerResponse = responseElement.innerText?.trim() || '';
                  const responseDateEl = responseElement.querySelector(
                    '[data-response-date], .response-date'
                  );
                  ownerResponseDate = responseDateEl?.innerText?.trim() || '';
                }

                // 5. Clasificación por criterios (si disponible)
                const criteriaElements = element.querySelectorAll(
                  '.criteria-item, [data-criteria], .rating-criterion'
                );
                const criteria = [];
                criteriaElements.forEach((el) => {
                  const name = el.querySelector('.criteria-name, [data-name]')?.innerText || '';
                  const ratingValue =
                    el.querySelector('.criteria-rating, [data-rating]')?.innerText || '';
                  if (name) criteria.push({ name, rating: ratingValue });
                });

                // 6. Traducción (si aplica)
                const translatedText =
                  element.querySelector('.translated-text, [data-translated]')?.innerText || '';
                const originalLanguageEl = element.querySelector(
                  '[data-language], .language-indicator'
                );
                const originalLanguage = originalLanguageEl?.innerText?.trim() || '';

                if (text || rating) {
                  const uniqueKey = `${user}_${date}_${text.slice(0, 50)}`.replace(
                    /[^a-zA-Z0-9_]/g,
                    ''
                  );
                  reviews.push({
                    // Campos básicos (siempre)
                    user,
                    rating,
                    date,
                    text,
                    uniqueKey,
                    reviewLikes,
                    reviewPhotos,
                    reviewResponseTime,

                    // 🆕 Campos extendidos
                    reviewId,
                    reviewLink,
                    contributorId,
                    userThumbnail,
                    isLocalGuide,
                    userReviews,
                    userPhotos,
                    source,
                    ownerResponse,
                    ownerResponseDate,
                    criteria: JSON.stringify(criteria),
                    translatedText,
                    originalLanguage,
                    imageUrls: JSON.stringify(imageUrls),
                  });
                }
              } catch (e) {
                // Continuar con siguiente elemento
              }
            }
          }

          return reviews;
        },
        { REVIEW_SELECTORS: this.reviewSelectors }
      );

      // Filtrar duplicados y detectar idiomas
      const uniqueReviews = [];
      const seenKeys = new Set();

      for (const review of allReviewsData) {
        if (!seenKeys.has(review.uniqueKey)) {
          seenKeys.add(review.uniqueKey);
          review.lang = detectLanguageSimple(review.text);
          uniqueReviews.push(review);
        }
      }

      return uniqueReviews;
    } catch (e) {
      this.logger.warn(`Error en extracción optimizada: ${e.message}`);
      return [];
    }
  }

  async isEndOfContent(page) {
    // ✅ FIX: Pasar selectores como parámetros en lugar de usar this en page.evaluate()
    const hasMoreButton = await page.evaluate((selectors) => {
      for (const selector of selectors) {
        const element = document.querySelector(selector);
        if (element && element.offsetParent !== null) return true;
      }
      return false;
    }, this.paginationSelectors);

    const hasLoading = await page.evaluate((selectors) => {
      for (const selector of selectors) {
        const element = document.querySelector(selector);
        if (element && element.offsetParent !== null) return true;
      }
      return false;
    }, this.loadingSelectors);

    return !hasMoreButton && !hasLoading;
  }

  async ultraFastScroll(page) {
    try {
      const scrollResult = await page.evaluate(() => {
        const containers = [
          'div.m6QErb.DxyBCb.kA9KIf.dS8AEf',
          'div.m6QErb',
          "[role='main']",
          '.review-list',
          '.reviews-container',
          "div[role='main']",
          'div.section-layout',
          'div.section-scrollbox',
        ];

        for (const selector of containers) {
          const container = document.querySelector(selector);
          if (container) {
            const currentScroll = container.scrollTop;
            const maxScroll = container.scrollHeight - container.clientHeight;
            container.scrollTop = maxScroll;

            container.dispatchEvent(
              new WheelEvent('wheel', {
                deltaY: 1000,
                bubbles: true,
              })
            );

            return { success: true, scrolled: maxScroll - currentScroll };
          }
        }

        return { success: false };
      });

      if (scrollResult.success) {
        await sleep(randomDelay(200, 500));
        return;
      }

      await page.evaluate(() => {
        const scrollAmount = Math.floor(window.innerHeight * 0.8);
        window.scrollTo(0, document.body.scrollHeight);
        window.dispatchEvent(new KeyboardEvent('keydown', { key: 'End', bubbles: true }));
        window.scrollBy({
          top: scrollAmount,
          behavior: 'instant',
        });
        return true;
      });

      await sleep(randomDelay(this.config.get('humanDelayMin'), this.config.get('humanDelayMax')));
    } catch (e) {
      this.logger.warn(`Error en scroll optimizado: ${e.message}`);
    }
  }

  async clickMoreButton(page) {
    for (const selector of this.paginationSelectors) {
      try {
        const elements = await page.$$(selector);
        for (const element of elements) {
          try {
            const isVisible = await element.evaluate((el) => {
              const style = window.getComputedStyle(el);
              return (
                el.offsetParent !== null &&
                style.display !== 'none' &&
                style.visibility !== 'hidden' &&
                el.getBoundingClientRect().height > 0
              );
            });

            if (isVisible) {
              await element.click();
              this.logger.info(`Botón "Ver más" clickeado: ${selector}`);
              await sleep(randomDelay(3000, 5000));
              return true;
            }
          } catch (e) {
            // Continuar
          }
        }
      } catch (e) {
        // Continuar con el siguiente selector
      }
    }

    // Estrategia alternativa: buscar por texto
    try {
      const clicked = await page.evaluate(() => {
        const allElements = document.querySelectorAll(
          'button, a, div[role="button"], span[role="button"]'
        );
        for (const el of allElements) {
          const text = (el.innerText || el.getAttribute('aria-label') || '').toLowerCase();
          if (
            /más|more|ver|show|cargar|load/i.test(text) &&
            el.offsetParent !== null &&
            window.getComputedStyle(el).display !== 'none'
          ) {
            el.click();
            return true;
          }
        }
        return false;
      });

      if (clicked) {
        this.logger.info('Botón "Ver más" encontrado por texto');
        await sleep(randomDelay(3000, 5000));
        return true;
      }
    } catch (e) {
      this.logger.warn(`Error en búsqueda alternativa: ${e.message}`);
    }

    this.logger.warn('No se encontró ningún botón "Ver más"');
    return false;
  }

  async rotateProxy(page, proxies) {
    if (proxies.length === 0) return null;

    // Filtrar proxies que funcionan
    const workingProxies = proxies.filter((p) => p.working !== false);
    if (workingProxies.length === 0) {
      this.logger.warn('No hay proxies funcionales disponibles');
      return null;
    }

    // Ordenar por último uso (los menos usados primero)
    workingProxies.sort((a, b) => {
      if (!a.lastUsed) return -1;
      if (!b.lastUsed) return 1;
      return new Date(a.lastUsed) - new Date(b.lastUsed);
    });

    // Tomar el proxy menos usado recientemente
    const newProxy = workingProxies[0];
    if (!newProxy) return null;

    this.logger.info(`🔄 Rotando a proxy: ${newProxy.host}:${newProxy.port}`);

    try {
      await page.authenticate({
        username: newProxy.username,
        password: newProxy.password,
      });

      // Marcar proxy como usado exitosamente
      newProxy.lastUsed = new Date();
      newProxy.successCount = (newProxy.successCount || 0) + 1;
      return newProxy;
    } catch (e) {
      this.logger.error(`❌ Error rotando proxy ${newProxy.host}:${newProxy.port}: ${e.message}`);
      markProxyAsFailed(proxies, newProxy);
      return null;
    }
  }

  /**
   * 🔄 ✅ MEJORADO: Intenta abrir la pestaña de reseñas usando rotación inteligente
   * @param {Page} page - Instancia de Puppeteer page
   * @returns {Promise<boolean>} - True si se abrió exitosamente
   */
  async openReviewsTabWithRotation(page) {
    this.logger.info('🔄 Intentando abrir pestaña de reseñas con rotación inteligente...');

    for (let attempt = 0; attempt < this.reviewTabSelectors.length; attempt++) {
      const strategy = this.reviewTabSelectors[attempt];
      this.logger.debug(
        `Intentando estrategia ${attempt + 1}/${this.reviewTabSelectors.length}: ${strategy.strategy}`
      );

      try {
        const result = await page.evaluate((strategy) => {
          const elements = Array.from(document.querySelectorAll(strategy.selector));

          for (const element of elements) {
            try {
              if (strategy.filter(element)) {
                // ✅ MEJORADO: Verificación más robusta de clickeabilidad
                const style = window.getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                const isVisible =
                  element.offsetParent !== null &&
                  style.display !== 'none' &&
                  style.visibility !== 'hidden' &&
                  style.opacity !== '0' &&
                  rect.width > 0 &&
                  rect.height > 0 &&
                  rect.top >= 0 &&
                  rect.left >= 0;

                // ✅ NUEVO: Verificar que no esté deshabilitado
                const isDisabled =
                  element.disabled ||
                  element.getAttribute('aria-disabled') === 'true' ||
                  style.pointerEvents === 'none';

                if (isVisible && !isDisabled) {
                  // ✅ MEJORADO: Intentar scroll al elemento antes de click
                  element.scrollIntoView({ behavior: 'smooth', block: 'center' });

                  // ✅ FIX: Ejecutar click inmediatamente en lugar de setTimeout
                  // El setTimeout retornaba antes de que se ejecutara el click
                  element.click();

                  return {
                    success: true,
                    strategy: strategy.strategy,
                    text: element.innerText?.trim() || element.getAttribute('aria-label') || '',
                    tagName: element.tagName,
                    className: element.className,
                    rect: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
                  };
                }
              }
            } catch (e) {
              // Continuar con siguiente elemento
            }
          }
          // Fallback final: intentar detectar reseñas directamente en DOM principal
          const hasReviews = document.querySelectorAll('div[jscontroller*="Review"], [data-review-id]').length > 0;
          if (hasReviews) {
            return { success: true, strategy: 'direct_detection' };
          }

          return { success: false, strategy: strategy.strategy };
        }, strategy);

        if (result.success) {
          this.logger.logStrategyResult(result.strategy, true, {
            text: result.text,
            position: `${result.rect.x}, ${result.rect.y}`,
            tagName: result.tagName,
            className: result.className,
          });

          // ✅ MEJORADO: Esperar más tiempo para que cargue el contenido
          await sleep(randomDelay(3000, 5000));

          // ✅ NUEVO: Verificar que realmente se abrió la pestaña
          const tabOpened = await page.evaluate(() => {
            const reviewElements = document.querySelectorAll(
              '[data-review-id], .jftiEf, div[role="listitem"]'
            );
            const reviewsHeader =
              document.querySelector('h2, [role="heading"]')?.innerText?.toLowerCase() || '';
            return (
              reviewElements.length > 0 ||
              reviewsHeader.includes('reseña') ||
              reviewsHeader.includes('review') ||
              reviewsHeader.includes('opiniones')
            );
          });

          if (tabOpened) {
            this.logger.info('✅ Confirmada apertura de pestaña de reseñas');
            return true;
          } else {
            this.logger.warn('⚠️ Click ejecutado pero pestaña no se abrió correctamente');
            continue; // Intentar siguiente estrategia
          }
        }
      } catch (e) {
        this.logger.warn(`Error en estrategia ${strategy.strategy}: ${e.message}`);
      }
    }

    // ✅ MEJORADO: Logging de estrategias fallidas con métricas detalladas
    this.logger.logStrategyResult('todas_las_estrategias', false, {
      totalStrategies: this.reviewTabSelectors.length,
      lastAttempt: this.reviewTabSelectors[this.reviewTabSelectors.length - 1]?.strategy,
      attemptedStrategies: this.reviewTabSelectors.map((s) => s.strategy),
    });
    return false;
  }

  /**
   * 🔄 NUEVO: Método alternativo para abrir pestaña cuando las estrategias fallan
   * @param {Page} page - Instancia de Puppeteer page
   * @returns {Promise<boolean>} - True si se abrió exitosamente
   */
  async tryAlternativeTabOpening(page) {
    this.logger.info('🔄 Intentando método alternativo para abrir pestaña...');

    try {
      // Método 1: Buscar por coordenadas relativas
      const coordsResult = await page.evaluate(() => {
        const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
        if (tabs.length < 2) return false;

        // Buscar el segundo tab (usualmente reseñas)
        const reviewsTab = tabs[1];
        if (reviewsTab) {
          reviewsTab.click();
          return true;
        }
        return false;
      });

      if (coordsResult) {
        this.logger.info('✅ Pestaña abierta por posición relativa');
        await sleep(randomDelay(2000, 3000));
        return true;
      }

      // Método 2: Simular navegación por teclado
      await page.keyboard.press('Tab');
      await sleep(500);
      await page.keyboard.press('Tab');
      await sleep(500);
      await page.keyboard.press('Enter');

      await sleep(randomDelay(2000, 3000));

      const keyboardResult = await page.evaluate(() => {
        return document.querySelectorAll('[data-review-id], .jftiEf').length > 0;
      });

      if (keyboardResult) {
        this.logger.info('✅ Pestaña abierta por navegación de teclado');
        return true;
      }
    } catch (e) {
      this.logger.warn(`Error en método alternativo: ${e.message}`);
    }

    return false;
  }

  /**
   * 🆕 NUEVO: Sistema de monitoreo continuo de proxies
   * ✅ FIX: Prevenir memory leak validando si ya existe un intervalo
   * @param {Array} proxies - Lista de proxies a monitorear
   * @param {Logger} logger - Instancia del logger
   */
  startProxyHealthMonitoring(proxies, logger) {
    if (!proxies || proxies.length === 0) return;

    // ✅ FIX: Limpiar intervalo anterior si existe para prevenir memory leak
    if (this.proxyHealthInterval) {
      clearInterval(this.proxyHealthInterval);
      logger.debug('Intervalo de monitoreo de proxies anterior limpiado');
    }

    // Monitoreo cada 5 minutos
    this.proxyHealthInterval = setInterval(
      async () => {
        try {
          const workingCount = proxies.filter((p) => p.working).length;
          const totalCount = proxies.length;

          logger.debug(`📊 Estado de proxies: ${workingCount}/${totalCount} funcionando`);

          // Re-testear proxies que fallaron recientemente
          const failedProxies = proxies.filter((p) => !p.working && p.failures < 3);
          if (failedProxies.length > 0) {
            logger.info(`🔄 Re-testando ${failedProxies.length} proxies fallidos...`);
            for (const proxy of failedProxies) {
              const result = await testProxy(proxy);
              if (result.success) {
                proxy.working = true;
                proxy.failures = 0;
                logger.info(`✅ Proxy recuperado: ${proxy.host}:${proxy.port}`);
              }
            }
          }
        } catch (error) {
          logger.warn('Error en monitoreo de proxies', error);
        }
      },
      5 * 60 * 1000
    ); // 5 minutos
  }

  /**
   * 📊 Intenta ordenar reseñas por "Más recientes" usando rotación de selectores
   * @param {Page} page - Instancia de Puppeteer page
   * @returns {Promise<boolean>} - True si se ordenó exitosamente
   */
  async sortReviewsByRecent(page) {
    this.logger.info('📊 Intentando ordenar reseñas por "Más recientes"...');

    for (let attempt = 0; attempt < this.sortSelectors.length; attempt++) {
      const strategy = this.sortSelectors[attempt];
      this.logger.debug(
        `Intentando estrategia de orden ${attempt + 1}/${this.sortSelectors.length}: ${strategy.strategy}`
      );

      try {
        if (strategy.action === 'click') {
          // Estrategia de click (botón de ordenar)
          const result = await page.evaluate((strategy) => {
            const elements = Array.from(document.querySelectorAll(strategy.selector));

            for (const element of elements) {
              try {
                if (strategy.filter(element)) {
                  const style = window.getComputedStyle(element);
                  const rect = element.getBoundingClientRect();
                  const isVisible =
                    element.offsetParent !== null &&
                    style.display !== 'none' &&
                    style.visibility !== 'hidden' &&
                    rect.width > 0 &&
                    rect.height > 0;

                  if (isVisible) {
                    element.click();
                    return {
                      success: true,
                      strategy: strategy.strategy,
                      text: element.innerText?.trim() || '',
                      action: 'click',
                    };
                  }
                }
              } catch (e) {
                // Continuar
              }
            }

            return { success: false, strategy: strategy.strategy };
          }, strategy);

          if (result.success) {
            this.logger.info(
              `✅ Orden activado con estrategia: ${result.strategy} (${result.text})`
            );
            await sleep(randomDelay(1500, 2500));

            // Después de activar el menú de orden, intentar seleccionar "Más recientes"
            const selected = await this.selectMostRecentOption(page);
            if (selected) {
              return true;
            }
          }
        } else if (strategy.action === 'select') {
          // Estrategia de selección directa en dropdown
          const result = await page.evaluate((strategy) => {
            const elements = Array.from(document.querySelectorAll(strategy.selector));

            for (const element of elements) {
              try {
                if (strategy.filter(element)) {
                  element.value = strategy.value;
                  element.dispatchEvent(new Event('change', { bubbles: true }));
                  return {
                    success: true,
                    strategy: strategy.strategy,
                    value: strategy.value,
                    action: 'select',
                  };
                }
              } catch (e) {
                // Continuar
              }
            }

            return { success: false, strategy: strategy.strategy };
          }, strategy);

          if (result.success) {
            this.logger.info(`✅ Orden establecido directamente: ${result.value}`);
            await sleep(randomDelay(1500, 2500));
            return true;
          }
        }
      } catch (e) {
        this.logger.warn(`Error en estrategia de orden ${strategy.strategy}: ${e.message}`);
      }
    }

    this.logger.warn('❌ No se pudo ordenar reseñas con ninguna estrategia');
    return false;
  }

  /**
   * 🎯 Selecciona la opción "Más recientes" en el menú de orden
   * @param {Page} page - Instancia de Puppeteer page
   * @returns {Promise<boolean>} - True si se seleccionó exitosamente
   */
  async selectMostRecentOption(page) {
    try {
      await sleep(800);
      
      const result = await page.evaluate(() => {
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
        ];

        let targetElement = null;
        let foundText = '';

        for (const selector of menuSelectors) {
          const elements = Array.from(document.querySelectorAll(selector));
          
          for (const element of elements) {
            const text = (
              element.innerText ||
              element.textContent ||
              element.getAttribute('aria-label') ||
              element.getAttribute('title') ||
              ''
            ).toLowerCase().trim();
            
            const visible =
              element.offsetParent !== null &&
              window.getComputedStyle(element).display !== 'none' &&
              window.getComputedStyle(element).visibility !== 'hidden';

            if (visible && /más recientes|recientes|most recent|newest|nuevo/i.test(text)) {
              targetElement = element;
              foundText = text;
              break;
            }
          }
          
          if (targetElement) break;
        }

        if (!targetElement) {
          return { success: false, message: 'No encontrado' };
        }

        try {
          targetElement.scrollIntoView({ block: 'center' });
          
          const clickEvent = new MouseEvent('click', {
            bubbles: true,
            cancelable: true,
            view: window,
          });
          targetElement.dispatchEvent(clickEvent);
          
          return {
            success: true,
            text: foundText,
          };
        } catch (e) {
          return {
            success: false,
            message: e.message,
          };
        }
      });

      if (result.success) {
        this.logger.info(`✅ Opción "Más recientes" seleccionada: ${result.text}`);
        await sleep(randomDelay(2000, 3000));
        return true;
      } else {
        this.logger.warn(`⚠️ No se pudo seleccionar "Más recientes": ${result.message}`);
      }
    } catch (e) {
      this.logger.warn(`Error seleccionando opción "Más recientes": ${e.message}`);
    }

    return false;
  }

  /**
   * 🆕 NUEVO: Validación de contenido de reseñas extraídas
   * @param {Array} reviews - Array de reseñas extraídas
   * @param {string} placeId - ID del lugar
   * @returns {Object} - Resultado de validación
   */
  validateReviewData(reviews) {
    const validation = {
      total: reviews.length,
      valid: 0,
      invalid: 0,
      issues: [],
      quality: 'unknown',
    };

    for (const review of reviews) {
      let isValid = true;
      const issues = [];

      // Validar campos básicos
      if (!review.user || review.user.trim() === '' || review.user === 'Anónimo') {
        issues.push('usuario_vacio');
        isValid = false;
      }

      if (!review.text || review.text.trim().length < 10) {
        issues.push('texto_insuficiente');
        isValid = false;
      }

      if (!review.date || review.date.trim() === '') {
        issues.push('fecha_vacia');
        isValid = false;
      }

      // Validar rating
      const rating = parseFloat(review.rating);
      if (isNaN(rating) || rating < 1 || rating > 5) {
        issues.push('rating_invalido');
        isValid = false;
      }

      // ✅ FIX: Validación de contenido menos restrictiva para evitar falsos positivos
      // Una reseña es válida si tiene texto suficiente (>10 chars ya validado)
      // Solo marcar como no relevante si es muy corta Y sin términos comunes
      if (review.text && review.text.length > 0 && review.text.length < 30) {
        const lowerText = review.text.toLowerCase();
        // Términos generales que indican que es una reseña válida
        const validTerms = [
          'bueno',
          'malo',
          'bien',
          'mal',
          'excelente',
          'horrible',
          'recomiendo',
          'no recomiendo',
          'genial',
          'pésimo',
          'agradable',
          'desagradable',
          'calidad',
          'atención',
          'limpio',
          'sucio',
          'nuevo',
          'viejo',
          'rápido',
          'lento',
        ];
        const hasValidContent = validTerms.some((term) => lowerText.includes(term));

        // Solo rechazar si es muy corta Y sin ningún término de reseña
        if (!hasValidContent && review.text.length < 15) {
          issues.push('contenido_muy_breve');
          // No marcar como inválido - algunos negocios tienen reseñas cortas legítimas
        }
      }

      if (isValid) {
        validation.valid++;
      } else {
        validation.invalid++;
        validation.issues.push({
          review: review.uniqueKey,
          issues: issues,
        });
      }
    }

    // Calcular calidad general
    const validPercentage = (validation.valid / validation.total) * 100;
    if (validPercentage >= 90) {
      validation.quality = 'excellent';
    } else if (validPercentage >= 75) {
      validation.quality = 'good';
    } else if (validPercentage >= 50) {
      validation.quality = 'fair';
    } else {
      validation.quality = 'poor';
    }

    this.logger.info(
      `📊 Validación de reseñas: ${validation.valid}/${validation.total} válidas (${validation.quality})`
    );

    if (validation.invalid > 0) {
      this.logger.warn(`⚠️ ${validation.invalid} reseñas con problemas detectados`);
    }

    return validation;
  }

  async scrape(placeId, maxReviews = null) {
    const maxReviewsLimit = maxReviews || this.config.get('maxReviews');
    this.logger.logScrapingStart('reviews', { placeId, maxReviews: maxReviewsLimit });

    // Verificar cache primero
    const cacheKey = `reviews:${placeId}:${maxReviewsLimit}`;
    const cachedReviews = await this.cache.get(cacheKey);
    if (cachedReviews) {
      this.logger.info('Usando reseñas desde cache');
      return cachedReviews;
    }

    // ✅ OPTIMIZADO: Reemplazar Map simple con LRU Cache para evitar memory leaks
    const MAX_REVIEWS_MEMORY = 50000; // Límite de 50K reseñas para evitar saturación
    let allReviews = new Map();
    let reviewOrder = []; // Para implementar LRU eviction
    let browser;
    let currentProxy = null;
    let batchNumber = 0;
    let businessName = 'PLACE_UNKNOWN'; // Initialize to avoid undefined in catch

    try {
      let proxies = loadProxies();

      // 🆕 MEJORADO: Probar proxies con health checks mejorados
      if (proxies.length > 0) {
        this.logger.info(`🔄 Probando ${proxies.length} proxies antes de iniciar scraping`);
        proxies = await testAllProxies(proxies, this.logger);

        const workingProxies = proxies.filter((p) => p.working);
        if (workingProxies.length === 0) {
          this.logger.warn('⚠️ Ningún proxy funcionando detectado. Continuando sin proxies');
          proxies = [];
        } else {
          this.logger.info(`✅ ${workingProxies.length} proxies funcionando y listos para usar`);
          // 🆕 NUEVO: Health check continuo durante el scraping
          this.startProxyHealthMonitoring(proxies, this.logger);
        }
      }

      currentProxy = selectRandomProxy(proxies);

      const args = [
        '--no-sandbox',
        '--disable-setuid-sandbox',
        '--disable-blink-features=AutomationControlled',
        '--disable-dev-shm-usage',
        '--disable-infobars',
        '--disable-gpu',
        '--lang=es-ES',
        '--accept-lang=es-ES,es',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
      ];

      if (currentProxy) args.push(`--proxy-server=${currentProxy.host}:${currentProxy.port}`);

      const chromeSystemPath = this.config.get('chromePath');
      if (!fs.existsSync(chromeSystemPath)) {
        throw new Error('Chrome no encontrado. Verifica la ruta del sistema.');
      }

      browser = await puppeteer.launch({
        headless: this.config.get('puppeteerHeadless'),
        executablePath: chromeSystemPath,
        args: [
          ...args,
          '--disable-web-security',
          '--disable-features=VizDisplayCompositor',
          '--disable-ipc-flooding-protection',
          '--disable-background-timer-throttling',
          '--disable-renderer-backgrounding',
          '--disable-backgrounding-occluded-windows',
          '--disable-features=TranslateUI',
          '--disable-ipc-flooding-protection',
          '--no-first-run',
          '--disable-default-apps',
          '--disable-extensions',
          '--disable-plugins',
          '--disable-images',
          '--disable-javascript-harmony-shipping',
          '--memory-pressure-off',
          '--max_old_space_size=4096',
        ],
        defaultViewport: getRandomElement(this.viewports),
        ignoreDefaultArgs: ['--disable-extensions'],
        timeout: 60000,
      });

      let page = await browser.newPage();

      if (currentProxy?.username && currentProxy?.password) {
        this.logger.info(`Autenticando proxy ${currentProxy.host}:${currentProxy.port}`);
        await page.authenticate({
          username: currentProxy.username,
          password: currentProxy.password,
        });
        this.logger.info('Autenticación completada');
      }

      await page.setExtraHTTPHeaders({ 'Accept-Language': 'es-ES,es;q=0.9' });
      await page.setUserAgent(getRandomElement(this.userAgents));

      const url = `https://www.google.com/maps/place/?q=place_id:${placeId}`;
      this.logger.info(`Cargando URL: ${url}`);

      // Intentar cargar con proxy
      let loaded = false;
      let attempts = 0;
      const maxProxyAttempts = 3;

      while (!loaded && attempts < maxProxyAttempts) {
        try {
          await page.goto(url, { waitUntil: 'domcontentloaded' });

          // Detectar errores específicos en la página
          await this.detectPageError(page);

          loaded = true;
          if (currentProxy) {
            this.logger.info(
              `✅ Proxy ${currentProxy.host}:${currentProxy.port} funcionando correctamente`
            );
          }
        } catch (e) {
          attempts++;
          this.logger.warn(
            `❌ Intento ${attempts} falló con proxy ${currentProxy?.host}:${currentProxy?.port}. Error: ${e.message}`
          );

          if (currentProxy && attempts < maxProxyAttempts) {
            // Marcar proxy como fallido y rotar
            markProxyAsFailed(proxies, currentProxy);
            currentProxy = await this.rotateProxy(page, proxies);

            if (currentProxy) {
              this.logger.info(
                `🔄 Rotando a nuevo proxy: ${currentProxy.host}:${currentProxy.port}`
              );
              // Actualizar args con nuevo proxy
              const newArgs = args.filter((a) => !a.startsWith('--proxy-server'));
              if (currentProxy)
                newArgs.push(`--proxy-server=${currentProxy.host}:${currentProxy.port}`);

              await browser.close();
              browser = await puppeteer.launch({
                headless: this.config.get('puppeteerHeadless'),
                executablePath: chromeSystemPath,
                args: newArgs,
                defaultViewport: getRandomElement(this.viewports),
              });
              page = await browser.newPage();

              if (currentProxy.username && currentProxy.password) {
                await page.authenticate({
                  username: currentProxy.username,
                  password: currentProxy.password,
                });
              }
            }
          } else {
            // Si no hay más proxies o es el último intento, intentar sin proxy
            this.logger.warn('🔄 Reintentando sin proxy...');
            await browser.close();
            browser = await puppeteer.launch({
              headless: this.config.get('puppeteerHeadless'),
              executablePath: chromeSystemPath,
              args: args.filter((a) => !a.startsWith('--proxy-server')),
              defaultViewport: getRandomElement(this.viewports),
            });
            page = await browser.newPage();
            await page.setExtraHTTPHeaders({ 'Accept-Language': 'es-ES,es;q=0.9' });
            await page.setUserAgent(getRandomElement(this.userAgents));
            await page.goto(url, { waitUntil: 'networkidle2', timeout: 30000 });

            // Detectar errores específicos en la página
            await this.detectPageError(page);

            loaded = true;
          }
        }
      }

      if (!loaded) {
        throw new Error('No se pudo cargar la página');
      }

      await sleep(randomDelay(1500, 2500));

      // ✅ CRÍTICO: Aceptar políticas de cookies ANTES de buscar elementos
      try {
        const acceptButtons = [
          'button[aria-label*="Aceptar"]',
          '[role="button"][aria-label*="Aceptar"]',
          'button[jsname="d"]', // Google's accept button
        ];

        for (const selector of acceptButtons) {
          try {
            await page.waitForSelector(selector, { timeout: 2000 });
            await page.click(selector);
            this.logger.info(`✅ Cookies aceptadas usando selector: ${selector}`);
            await sleep(500); // Esperar a que el DOM se estabilice
            break;
          } catch {
            // Intentar siguiente selector
          }
        }

        // Fallback: buscar botón por texto usando evaluación JavaScript
        const cookieAccepted = await page.evaluate(() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          for (const btn of buttons) {
            if (btn.textContent && btn.textContent.includes('Aceptar')) {
              btn.click();
              return true;
            }
          }
          return false;
        });

        if (cookieAccepted) {
          this.logger.info(`✅ Cookies aceptadas usando búsqueda por texto`);
          await sleep(500);
        }
      } catch (error) {
        this.logger.debug(`ℹ️ No se encontró banner de cookies o ya fue aceptado`);
      }

      // ✅ FIX: Obtener nombre del negocio de la API de Google Places (CONSISTENTE con MetadataScraper)
      let businessName = 'PLACE_UNKNOWN';
      try {
        const apiData = await this.api.getPlaceDetails(placeId);
        if (apiData?.name) {
          businessName = cleanText(apiData.name);
          this.logger.info(`Negocio obtenido desde API: ${businessName}`);
        }
      } catch (error) {
        this.logger.warn(`No se pudo obtener nombre desde API: ${error.message}`);
      }

      // Fallback: Si API falló, obtener nombre desde la página
      if (businessName === 'PLACE_UNKNOWN') {
        const pageBusinessName = await page.evaluate(() => {
          const selectors = [
            'h1.DUwDvf',
            'h1.fontHeadlineLarge',
            '.DUwDvf',
            "[role='heading']",
            "h1[data-cy='title']",
            'h1.section-hero-header-title',
            '.hero-title',
            'h1',
            '.business-name',
            "[data-testid='business-name']",
          ];
          for (const selector of selectors) {
            const el = document.querySelector(selector);
            if (el && el.innerText && el.innerText.trim()) {
              return el.innerText.trim();
            }
          }
          return 'PLACE_UNKNOWN';
        });
        if (pageBusinessName !== 'PLACE_UNKNOWN') {
          businessName = cleanText(pageBusinessName);
          this.logger.info(`Negocio detectado desde página: ${businessName}`);
        }
      }

      // ✅ MEJORADO: Fallback con validación cruzada
      if (businessName === 'PLACE_UNKNOWN') {
        businessName = this.directory.detectBusinessName(placeId);
        if (businessName && businessName !== 'PLACE_UNKNOWN') {
          this.logger.info(`Negocio detectado automáticamente: ${businessName}`);
        } else {
          // ✅ NUEVO: Intentar obtener nombre desde la página actual
          try {
            const pageBusinessName = await page.evaluate(() => {
              const selectors = [
                'h1.DUwDvf',
                'h1.fontHeadlineLarge',
                '.DUwDvf',
                "[role='heading']",
                "h1[data-cy='title']",
                'h1.section-hero-header-title',
                '.hero-title',
                'h1',
                '.business-name',
                "[data-testid='business-name']",
              ];
              for (const selector of selectors) {
                const el = document.querySelector(selector);
                if (el && el.innerText && el.innerText.trim()) {
                  return el.innerText.trim();
                }
              }
              return 'PLACE_UNKNOWN';
            });
            if (pageBusinessName !== 'PLACE_UNKNOWN') {
              businessName = cleanText(pageBusinessName);
              this.logger.info(`Negocio detectado desde página: ${businessName}`);
            }
          } catch (pageError) {
            this.logger.warn(`Error obteniendo nombre desde página: ${pageError.message}`);
          }
        }
      }

      // Cargar checkpoint si existe
      const checkpoint = this.directory.loadCheckpoint(businessName, placeId);
      allReviews = checkpoint.allReviews;
      batchNumber = checkpoint.lastBatch + 1;

      // === ✅ INCORPORADO: Método de acceso a reseñas del scraper original ===
      const reviewsButtonSelector = 'button[jsaction*="pane.reviewChart"], button[aria-label*="Reseñas"], button[aria-label*="Reviews"]';
      if (!await this.clickWithRetry(page, reviewsButtonSelector, 15000)) {
        throw new Error("No se pudo acceder a la sección de reseñas");
      }
      await sleep(randomDelay(3000, 4500));

      // === ✅ MEJORADO: Apertura de pestaña de reseñas con estrategias modernas ===
      this.logger.info('🔍 Buscando pestaña de reseñas con estrategias mejoradas...');

      // ✅ MEJORADO: Logging detallado de elementos encontrados
      const debugElements = await page.evaluate(() => {
        const elements = document.querySelectorAll('button, [role="tab"], a, [role="button"]');
        return Array.from(elements)
          .slice(0, 30)
          .map((el) => ({
            tag: el.tagName,
            text: (el.innerText || '').substring(0, 50),
            ariaLabel: (el.getAttribute('aria-label') || '').substring(0, 50),
            className: el.className.substring(0, 50),
            role: el.getAttribute('role'),
            visible: el.offsetParent !== null,
            jsaction: el.getAttribute('jsaction') || '',
            dataValue: el.getAttribute('data-value') || '',
            dataTab: el.getAttribute('data-tab') || '',
          }));
      });
      this.logger.debug(`🔍 Elementos encontrados en página: ${debugElements.length}`);

      // ✅ MEJORADO: Logging más inteligente
      const relevantElements = debugElements.filter(
        (el) =>
          el.visible &&
          (el.text.toLowerCase().includes('reseña') ||
            el.text.toLowerCase().includes('review') ||
            el.ariaLabel.toLowerCase().includes('reseña') ||
            el.ariaLabel.toLowerCase().includes('review') ||
            el.dataValue.includes('reviews') ||
            el.dataTab.includes('reviews'))
      );

      if (relevantElements.length > 0) {
        this.logger.info(`🎯 Elementos relevantes encontrados: ${relevantElements.length}`);
        relevantElements.slice(0, 5).forEach((el, i) => {
          this.logger.debug(
            `🎯 [${i}] ${el.tag}[${el.role}] "${el.text}" aria="${el.ariaLabel}" class="${el.className}"`
          );
        });
      } else {
        this.logger.warn('⚠️ No se encontraron elementos relevantes para reseñas');
        // Mostrar algunos elementos generales para debugging
        debugElements.slice(0, 3).forEach((el, i) => {
          this.logger.debug(`🔍 [${i}] ${el.tag}[${el.role}] "${el.text}"`);
        });
      }

      // ✅ MEJORADO: Usar método de rotación inteligente
      let tabOpened = false;
      const reviewButtonFound = await this.openReviewsTabWithRotation(page);

      if (!reviewButtonFound) {
        this.logger.warn('⚠️ No se pudo abrir pestaña de reseñas con estrategias modernas');
        // Intentar método alternativo directo
        const alternativeSuccess = await this.tryAlternativeTabOpening(page);
        if (alternativeSuccess) {
          this.logger.info('✅ Pestaña abierta con método alternativo');
          tabOpened = true;
        }
      } else {
        this.logger.info('✅ Pestaña de reseñas abierta correctamente');
        tabOpened = true;
      }

      // === Cambiar orden de reseñas a "Más recientes" SOLO si la pestaña está abierta ===
      if (tabOpened) {
        try {
          this.logger.info('🔄 Intentando ordenar reseñas por "Más recientes"...');
          
          const sortResult = await this.sortReviewsByRecent(page);
          if (sortResult) {
            this.logger.info('✅ Reseñas ordenadas exitosamente');
          } else {
            this.logger.warn('⚠️ No se pudo ordenar las reseñas');
          }

          await sleep(randomDelay(2000, 3000));
        } catch (err) {
          this.logger.warn(`⚠️ No se pudo cambiar el orden de reseñas: ${err.message}`);
        }
      }
      // FALLBACK: Si no se encontró la pestaña, intentar scroll directo
      if (!tabOpened) {
        this.logger.warn('Intentando acceder directamente a reseñas por scroll...');

        for (let retries = 0; retries < 3; retries++) {
          const directReviews = await page.evaluate(() => {
            const sections = document.querySelectorAll(
              '[role="region"], [role="section"], .reviews-section, [data-review-id]'
            );
            return sections.length > 0;
          });

          if (directReviews) {
            this.logger.info('✅ Reseñas accesibles directamente (sin pestaña)');
            break;
          }

          await page.evaluate(() => {
            window.scrollBy(0, window.innerHeight * 2);
          });
          await sleep(1000);
        }

        // Si aún no hay reseñas después de 3 intentos, crear CSV vacío inmediatamente
        const reviewsExist = await page.evaluate(() => {
          return document.querySelectorAll('[data-review-id], div[role="listitem"]').length > 0;
        });

        if (!reviewsExist) {
          this.logger.warn('❌ No se encontraron reseñas en la página - creando archivos vacíos');

          const placeDir = path.join(
            this.config.get('baseDir'),
            'clientes',
            `${this.directory.cleanBusinessName(businessName)}_${placeId}`
          );
          ensureDir(placeDir);

          const cleanName = this.directory.cleanBusinessName(businessName);

          // Crear CSV RESUMEN vacío
          const csvSummaryPath = path.join(placeDir, `${cleanName}_${placeId}_SUMMARY.csv`);
          const csvSummaryEmpty =
            'user,rating,date,text,lang,review_likes,review_photos,owner_response,owner_response_date\n';
          fs.writeFileSync(csvSummaryPath, '\ufeff' + csvSummaryEmpty, 'utf-8');

          // Crear CSV DETALLADO vacío
          const csvDetailedPath = path.join(placeDir, `${cleanName}_${placeId}_DETAILED.csv`);
          const csvDetailedEmpty =
            'user,rating,date,text,lang,review_id,review_link,contributor_id,is_local_guide,user_reviews_count,user_photos_count,review_likes,review_photos,source,owner_response,owner_response_date,criteria,translated_text,original_language,image_urls\n';
          fs.writeFileSync(csvDetailedPath, '\ufeff' + csvDetailedEmpty, 'utf-8');

          // Crear JSON vacío
          const jsonPath = path.join(placeDir, `${cleanName}_${placeId}_COMPLETE.json`);
          fs.writeFileSync(jsonPath, '[]', 'utf-8');

          this.directory.createPlaceIndex(placeDir, placeId, businessName, {
            type: 'reviews',
            reviewsCount: 0,
            error: 'No reviews found or tab not accessible',
            jsonGenerated: true,
            fileTypes: ['SUMMARY.csv', 'DETAILED.csv', 'COMPLETE.json'],
          });

          this.logger.info('✅ Operación de scraping completada: reviews');
          this.logger.info('✅ Reviews scraping completado (vacío)');

          return {
            success: true,
            path: csvSummaryPath,
            reviewsCount: 0,
            warning: 'No reviews found - tab may not be available',
          };
        }
      }

      // Verificar que estamos en la vista de reseñas
      const isInReviewsSection = await page.evaluate(() => {
        const reviewElements = document.querySelectorAll(
          'div[data-review-id], div.jftiEf, div[role="listitem"]'
        );
        const reviewsHeader = document.querySelector('h2')?.innerText?.toLowerCase() || '';
        const hasReviewsTab =
          document
            .querySelector('[aria-current="page"], [aria-selected="true"]')
            ?.innerText?.toLowerCase() || '';

        return (
          reviewElements.length > 0 ||
          reviewsHeader.includes('reseña') ||
          reviewsHeader.includes('review') ||
          hasReviewsTab.includes('reseña') ||
          hasReviewsTab.includes('review')
        );
      });

      if (isInReviewsSection) {
        this.logger.info('Confirmada navegación a sección de reseñas');
      }

      // Extracción con scroll infinito
      this.logger.info(
        `Iniciando extracción con scroll infinito (objetivo: ${maxReviewsLimit} reseñas)`
      );

      let consecutiveEmptyBatches = 0;
      const MAX_EMPTY_BATCHES = 4;
      let totalScrolls = 0;
      let stuckCounter = 0;
      let moreButtonClicked = false;

      const MAX_BATCHES = 10;

      while (
        allReviews.size < maxReviewsLimit &&
        consecutiveEmptyBatches < MAX_EMPTY_BATCHES &&
        batchNumber < MAX_BATCHES
      ) {
        this.logger.debug(`Procesando lote ${batchNumber + 1}`);

        let batchStartSize = allReviews.size;
        let localScrollAttempts = 0;

        while (localScrollAttempts < 25 && allReviews.size < maxReviewsLimit) {
          totalScrolls++;
          localScrollAttempts++;

          try {
            await this.ultraFastScroll(page);
          } catch (scrollError) {
            this.logger.warn(`Error en scroll ${totalScrolls}: ${scrollError.message}`);
          }

          let newData = [];
          try {
            newData = await this.extractReviewsOptimized(page);
          } catch (extractError) {
            this.logger.warn(
              `Error extrayendo reseñas en scroll ${totalScrolls}: ${extractError.message}`
            );
            newData = [];
          }

          let added = 0;
          newData.forEach((r) => {
            if (!allReviews.has(r.uniqueKey)) {
              // ✅ LRU EVICTION: Implementar control de memoria para evitar memory leaks
              if (allReviews.size >= MAX_REVIEWS_MEMORY) {
                // Remover la reseña más antigua (LRU)
                const oldestKey = reviewOrder.shift();
                if (oldestKey) {
                  allReviews.delete(oldestKey);
                  this.logger.debug(`LRU eviction: eliminada reseña ${oldestKey}`);
                }
              }

              // Agregar nueva reseña
              allReviews.set(r.uniqueKey, r);
              reviewOrder.push(r.uniqueKey); // Registrar orden para LRU
              added++;
              stuckCounter = 0;
            }
          });

          if (added > 0) {
            this.logger.logBatch(batchNumber + 1, added, { total: allReviews.size });
            consecutiveEmptyBatches = 0;
          } else {
            stuckCounter++;
            await sleep(randomDelay(150, 400));
          }

          if (localScrollAttempts % 4 === 0) {
            this.logger.debug(
              `Esperando carga infinita (${localScrollAttempts} scrolls, ${allReviews.size} reseñas)`
            );
            await sleep(randomDelay(2000, 3500));
          }

          if (!moreButtonClicked && stuckCounter >= 8 && localScrollAttempts % 6 === 0) {
            this.logger.info(
              `Intentando botón "Ver más" después de ${stuckCounter} scrolls sin progreso`
            );
            const moreClicked = await this.clickMoreButton(page);
            if (moreClicked) {
              moreButtonClicked = true;
              await sleep(randomDelay(3000, 5000));
            }
          }

          if (stuckCounter >= 5) {
            this.logger.info(
              `Fin de contenido detectado (${stuckCounter} scrolls sin reseñas nuevas)`
            );
            break;
          }
        }

        const currentReviewCount = allReviews.size;
        const batchProgress = currentReviewCount - batchStartSize;

        if (batchProgress > 0) {
          consecutiveEmptyBatches = 0;
          this.logger.info(
            `Lote ${batchNumber + 1}: +${batchProgress} reseñas (${allReviews.size} total, ${localScrollAttempts} scrolls)`
          );
        } else {
          consecutiveEmptyBatches++;
          this.logger.warn(
            `Lote ${batchNumber + 1}: Sin progreso (${consecutiveEmptyBatches}/${MAX_EMPTY_BATCHES})`
          );
        }

        if (batchProgress > 0 && allReviews.size % this.config.get('checkpointInterval') === 0) {
          this.directory.saveCheckpoint(allReviews, businessName, placeId, batchNumber);
        }

        if (batchNumber + 1 >= MAX_BATCHES) {
          this.logger.info(`Límite de lotes alcanzado (${MAX_BATCHES})`);
          break;
        }

        if (allReviews.size >= maxReviewsLimit) {
          this.logger.info(`Objetivo alcanzado: ${allReviews.size} reseñas`);
          break;
        }

        batchNumber++;
        if (
          allReviews.size < maxReviewsLimit &&
          consecutiveEmptyBatches === 0 &&
          batchNumber < MAX_BATCHES
        ) {
          await sleep(
            randomDelay(this.config.get('batchDelayMin'), this.config.get('batchDelayMax'))
          );
        }
      }

      // Guardar resultado final
      const placeDir = path.join(
        this.config.get('baseDir'),
        'clientes',
        `${this.directory.cleanBusinessName(businessName)}_${placeId}`
      );
      ensureDir(placeDir);

      const cleanName = this.directory.cleanBusinessName(businessName);

      // ✨ GUARDAR 3 FORMATOS DIFERENTES (✅ OPTIMIZADO: I/O ASÍNCRONO CON manejo robusto):

      // 1️⃣ CSV RESUMEN (campos principales)
      const csvSummaryPath = path.join(placeDir, `${cleanName}_${placeId}_SUMMARY.csv`);
      const csvSummary = this.generateReviewsSummaryCSV(allReviews);

      // 2️⃣ CSV DETALLADO (todos los campos)
      const csvDetailedPath = path.join(placeDir, `${cleanName}_${placeId}_DETAILED.csv`);
      const csvDetailed = this.generateReviewsDetailedCSV(allReviews);

      // 3️⃣ JSON COMPLETO (estructura completa para procesamiento posterior)
      const jsonPath = path.join(placeDir, `${cleanName}_${placeId}_COMPLETE.json`);
      const jsonData = this.generateReviewsJSON(allReviews);

      // ✅ FIX: Mejorado manejo de errores en escritura de archivos
      // Usar allSettled en lugar de all para no cancelar si uno falla
      const writeResults = await Promise.allSettled([
        fs.promises.writeFile(csvSummaryPath, '\ufeff' + csvSummary, 'utf-8'),
        fs.promises.writeFile(csvDetailedPath, '\ufeff' + csvDetailed, 'utf-8'),
        fs.promises.writeFile(jsonPath, jsonData, 'utf-8'),
      ]);

      // Verificar resultados y reportar errores específicos
      const fileNames = ['CSV SUMMARY', 'CSV DETAILED', 'JSON COMPLETE'];
      for (let i = 0; i < writeResults.length; i++) {
        if (writeResults[i].status === 'rejected') {
          this.logger.error(`Error escribiendo ${fileNames[i]}: ${writeResults[i].reason.message}`);
          throw new Error(`Failed to write ${fileNames[i]}: ${writeResults[i].reason.message}`);
        } else {
          this.logger.debug(`✅ ${fileNames[i]} guardado exitosamente`);
        }
      }

      this.logger.info(`✅ Archivos finales guardados: ${allReviews.size} reseñas procesadas`);

      // 🆕 NUEVO: Validar calidad de datos extraídos
      const reviewsArray = Array.from(allReviews.values());
      const validation = this.validateReviewData(reviewsArray);
      if (validation.quality === 'poor') {
        this.logger.warn(
          `⚠️ Calidad de datos baja detectada: ${validation.invalid}/${validation.total} reseñas inválidas`
        );
      }

      // Crear índice del lugar
      this.directory.createPlaceIndex(placeDir, placeId, businessName, {
        type: 'reviews',
        reviewsCount: allReviews.size,
        jsonGenerated: true,
        fileTypes: ['SUMMARY.csv', 'DETAILED.csv', 'COMPLETE.json'],
      });

      this.logger.logScrapingEnd('reviews', {
        placeId,
        businessName,
        outputFile: csvSummaryPath,
        reviewsCount: allReviews.size,
        totalScrolls,
      });

      // ✅ I/O ASÍNCRONO: Limpiar archivos temporales sin bloquear
      await this.cleanupTempFiles(placeDir);

      const result = {
        success: true,
        path: csvSummaryPath,
        businessName,
        placeId,
        reviewsCount: allReviews.size,
      };

      // Guardar en cache solo si se obtuvieron reseñas
      if (allReviews.size > 0) {
        await this.cache.set(cacheKey, result, 1800); // TTL 30 minutos
        this.logger.info('Resultado de reseñas guardado en cache');
      }

      return result;
    } catch (err) {
      this.logger.logErrorWithContext('Error en scraping de reviews', err, { placeId });

      // Intentar guardar archivos finales incluso en caso de error
      try {
        if (allReviews.size > 0) {
          const placeDir = this.directory.getPlaceDirectory(placeId, businessName);
          ensureDir(placeDir);

          const out = path.join(placeDir, `reviews_${placeId}.json`);
          const reviewsArray = Array.from(allReviews.values());

          fs.writeFileSync(out, JSON.stringify(reviewsArray, null, 2), 'utf-8');
          this.logger.info(
            `Archivos finales guardados tras error: ${allReviews.size} reseñas en ${out}`
          );
        }
      } catch (saveError) {
        this.logger.error('Error guardando archivos tras error principal', saveError);
      }

      throw err;
    } finally {
      if (browser) {
        try {
          await browser.close();
        } catch (closeError) {
          this.logger.error(`Error cerrando navegador: ${closeError.message}`);
        }
      }

      // 🆕 NUEVO: Limpiar intervalo de monitoreo de proxies
      if (this.proxyHealthInterval) {
        clearInterval(this.proxyHealthInterval);
        this.proxyHealthInterval = null;
      }
    }
  }

  /**
   * ✅ FIX: Escapa caracteres especiales de CSV de forma robusta
   * @param {string} text - Texto a escapar
   * @returns {string} - Texto escapado y listo para CSV
   */
  escapeCSVField(text) {
    if (!text) return '';

    // Convertir a string si no lo es
    text = String(text);

    // ✅ FIX: Escapa comillas Y saltos de línea Y caracteres especiales
    // 1. Reemplazar comillas con doble comilla (estándar CSV)
    text = text.replace(/"/g, '""');

    // 2. Reemplazar saltos de línea con espacios para evitar romper estructura
    text = text.replace(/\r\n/g, ' ').replace(/\n/g, ' ').replace(/\r/g, ' ');

    // 3. Remover caracteres de control (< 0x20 excepto espacio)
    text = text.replace(/[\x00-\x08\x0B-\x0C\x0E-\x1F]/g, '');

    // 4. Remover NULL bytes
    text = text.replace(/\x00/g, '');

    return text;
  }

  /**
   * 📋 Genera CSV RESUMIDO con campos principales
   * Ideal para análisis rápido y reportes
   */
  generateReviewsSummaryCSV(allReviews) {
    let csv =
      'user,rating,date,text,lang,review_likes,review_photos,owner_response,owner_response_date\n';

    for (const r of allReviews.values()) {
      // ✅ FIX: Usar escapado robusto en lugar de solo comillas
      const escapedText = this.escapeCSVField(r.text);
      const escapedUser = this.escapeCSVField(r.user);
      const escapedOwnerResponse = this.escapeCSVField(r.ownerResponse);

      csv += `"${escapedUser}","${r.rating}","${r.date}","${escapedText}","${r.lang || 'unknown'}","${r.reviewLikes || '0'}","${r.reviewPhotos || '0'}","${escapedOwnerResponse}","${r.ownerResponseDate || ''}"\n`;
    }

    return csv;
  }

  /**
   * 🔍 Genera CSV DETALLADO con TODOS los campos extraídos
   * Incluye: IDs, links, información del usuario extendida, criterios, etc.
   */
  generateReviewsDetailedCSV(allReviews) {
    let csv =
      'user,rating,date,text,lang,review_id,review_link,contributor_id,is_local_guide,user_reviews_count,user_photos_count,review_likes,review_photos,source,owner_response,owner_response_date,criteria,translated_text,original_language,image_urls\n';

    for (const r of allReviews.values()) {
      // ✅ FIX: Usar escapado robusto para todos los campos de texto
      const escapedUser = this.escapeCSVField(r.user);
      const escapedText = this.escapeCSVField(r.text);
      const escapedOwnerResponse = this.escapeCSVField(r.ownerResponse);
      const escapedCriteria = this.escapeCSVField(r.criteria);
      const escapedTranslatedText = this.escapeCSVField(r.translatedText);
      const escapedImageUrls = this.escapeCSVField(r.imageUrls);

      csv += `"${escapedUser}","${r.rating}","${r.date}","${escapedText}","${r.lang || 'unknown'}","${r.reviewId || ''}","${r.reviewLink || ''}","${r.contributorId || ''}","${r.isLocalGuide || 'No'}","${r.userReviews || ''}","${r.userPhotos || ''}","${r.reviewLikes || '0'}","${r.reviewPhotos || '0'}","${r.source || 'Google Maps'}","${escapedOwnerResponse}","${r.ownerResponseDate || ''}","${escapedCriteria}","${escapedTranslatedText}","${r.originalLanguage || ''}","${escapedImageUrls}"\n`;
    }

    return csv;
  }

  /**
   * 💾 Genera archivo JSON completo con toda la estructura de datos
   */
  generateReviewsJSON(allReviews) {
    const reviewsArray = Array.from(allReviews.values());
    return JSON.stringify(reviewsArray, null, 2);
  }
}
// --- Bloque ejecutable ---
if (import.meta.url === `file://${process.argv[1]}`) {
  const placeId = process.argv[2];
  const maxArg = process.argv.find((a) => a.startsWith('--max-reviews='));
  const maxReviews = maxArg ? parseInt(maxArg.split('=')[1], 10) : null;

  if (!placeId) {
    console.error('❌ Debes indicar un Place ID. Ejemplo:');
    console.error(
      '   node modules/reviews_scraper.js ChIJO4Ff4qa9pBIR1IdVPci5FCo --max-reviews=500'
    );
    process.exit(1);
  }

  const scraper = new ReviewsScraper();
  scraper
    .scrape(placeId, maxReviews)
    .then(() => {
      console.log('✅ Scraping completado.');
      process.exit(0);
    })
    .catch((err) => {
      console.error('❌ Error en scraping:', err);
      process.exit(1);
    });
}

if (process.argv[1].endsWith('reviews_scraper.js')) {
  const placeId = process.argv[2];
  const maxArg = process.argv.find((a) => a.startsWith('--max-reviews='));
  const maxReviews = maxArg ? parseInt(maxArg.split('=')[1], 10) : null;

  if (!placeId) {
    console.error(
      '❌ Debes indicar un Place ID. Ejemplo: node reviews_scraper.js ChIJO4Ff4qa9pBIR1IdVPci5FCo'
    );
    process.exit(1);
  }

  const scraper = new ReviewsScraper();
  scraper
    .scrape(placeId, maxReviews)
    .then(() => {
      console.log('✅ Scraping completado.');
      process.exit(0);
    })
    .catch((err) => {
      console.error('❌ Error en scraping:', err.message);
      process.exit(1);
    });
}
