// autos: Leox433
// Metodo: AI
// Version: V1.0 - Mass Scraper Configuration
// Fecha de última modificación: 2025-01-27
// Descripción: Configuración y monitoreo para scraping masivo

const fs = require("fs");
const path = require("path");

// === CONFIGURACIÓN PRINCIPAL ===
const MASS_SCRAPER_CONFIG = {
  // Límites y objetivos
  MAX_REVIEWS: 150000,           // Máximo de reseñas por negocio
  TARGET_REVIEWS: 120000,        // Objetivo recomendado
  BATCH_SIZE: 2000,              // Reseñas por lote
  MAX_BATCHES: 75,               // Máximo de lotes (150k / 2k)
  
  // Intervalos de guardado
  CHECKPOINT_INTERVAL: 1000,     // Guardar cada X reseñas
  BACKUP_INTERVAL: 5000,         // Backup cada X reseñas
  PROGRESS_INTERVAL: 500,        // Mostrar progreso cada X reseñas
  
  // Rotación y anti-detección
  PROXY_ROTATION_INTERVAL: 5000, // Cambiar proxy cada X reseñas
  USER_AGENT_ROTATION: 1000,     // Cambiar UA cada X reseñas
  VIEWPORT_ROTATION: 2000,       // Cambiar viewport cada X reseñas
  
  // Delays y timeouts
  SCROLL_DELAY_MIN: 800,         // Delay mínimo entre scrolls
  SCROLL_DELAY_MAX: 2500,        // Delay máximo entre scrolls
  BATCH_DELAY_MIN: 30000,        // Delay mínimo entre lotes
  BATCH_DELAY_MAX: 60000,        // Delay máximo entre lotes
  ERROR_DELAY: 10000,            // Delay después de error
  
  // Límites de scroll
  MAX_SCROLLS_PER_BATCH: 200,    // Máximo scrolls por lote
  SCROLL_TIMEOUT: 30000,         // Timeout de scroll
  UNCHANGED_LIMIT: 15,           // Límite de iteraciones sin cambios
  
  // Reintentos
  MAX_RETRIES: 5,                // Máximo reintentos por error
  RETRY_DELAY: 2000,             // Delay entre reintentos
  CAPTCHA_DELAY: 30000,          // Delay después de CAPTCHA
  RATE_LIMIT_DELAY: 60000,       // Delay después de rate limit
  
  // Archivos y rutas
  CHECKPOINT_PREFIX: "checkpoint_batch_",
  BACKUP_PREFIX: "backup_",
  LOG_FILE: "mass_scraper.log",
  PROGRESS_FILE: "scraping_progress.json"
};

// === CONFIGURACIÓN DE SELECTORES ===
const SELECTOR_CONFIG = {
  // Contenedores de reseñas
  REVIEW_CONTAINERS: [
    "div.m6QErb.DxyBCb.kA9KIf.dS8AEf",
    "div.m6QErb",
    "div[role='main']",
    "div[jsname='bN97Pc']",
    "div[data-value*='review']"
  ],
  
  // Elementos de reseñas
  REVIEW_ELEMENTS: [
    "div.jftiEf",
    "div[data-review-id]",
    "div[jsaction*='review']",
    "div.review-item",
    "div[role='listitem']",
    "div[data-value*='review']",
    "div.jftiEf.fontBodyMedium"
  ],
  
  // Controles de paginación
  PAGINATION_CONTROLS: [
    "button[aria-label*='más']",
    "button[aria-label*='more']",
    "button[jsname*='more']",
    "div[role='button'][aria-label*='cargar']",
    "button[data-value*='more']",
    "div[jsname='HiaYvf']",
    "button[jsname='HiaYvf']"
  ],
  
  // Indicadores de carga
  LOADING_INDICATORS: [
    "div[role='progressbar']",
    "div[aria-label*='cargando']",
    "div[aria-label*='loading']",
    "div.spinner",
    "div.loading",
    "div[jsname='HiaYvf'][aria-label*='cargando']"
  ],
  
  // Detección de CAPTCHA
  CAPTCHA_INDICATORS: [
    "form[action*='recaptcha']",
    "div[id*='captcha']",
    "iframe[src*='recaptcha']",
    "div[class*='captcha']"
  ],
  
  // Detección de rate limit
  RATE_LIMIT_INDICATORS: [
    "text*='demasiadas solicitudes'",
    "text*='too many requests'",
    "text*='rate limit'",
    "text*='temporalmente bloqueado'"
  ]
};

// === CONFIGURACIÓN DE USER AGENTS ===
const USER_AGENT_CONFIG = {
  CHROME_WINDOWS: [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7390.102 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.7390.99 Safari/537.36"
  ],
  
  CHROME_MAC: [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7390.102 Safari/537.36"
  ],
  
  CHROME_LINUX: [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.7390.108 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.7390.102 Safari/537.36"
  ],
  
  FIREFOX: [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0"
  ]
};

// === CONFIGURACIÓN DE VIEWPORTS ===
const VIEWPORT_CONFIG = {
  DESKTOP: [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1366, height: 768 },
    { width: 1536, height: 864 }
  ],
  
  LAPTOP: [
    { width: 1280, height: 720 },
    { width: 1366, height: 768 },
    { width: 1440, height: 900 }
  ]
};

// === FUNCIONES DE CONFIGURACIÓN ===
function getRandomUserAgent() {
  const allAgents = [
    ...USER_AGENT_CONFIG.CHROME_WINDOWS,
    ...USER_AGENT_CONFIG.CHROME_MAC,
    ...USER_AGENT_CONFIG.CHROME_LINUX,
    ...USER_AGENT_CONFIG.FIREFOX
  ];
  return allAgents[Math.floor(Math.random() * allAgents.length)];
}

function getRandomViewport() {
  const allViewports = [
    ...VIEWPORT_CONFIG.DESKTOP,
    ...VIEWPORT_CONFIG.LAPTOP
  ];
  return allViewports[Math.floor(Math.random() * allViewports.length)];
}

function getChromeArgs(proxy = null) {
  const baseArgs = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",
    "--disable-infobars",
    "--disable-gpu",
    "--lang=es-ES",
    "--accept-lang=es-ES,es",
    "--disable-web-security",
    "--disable-features=VizDisplayCompositor",
    "--disable-background-timer-throttling",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-field-trial-config",
    "--disable-back-forward-cache",
    "--disable-ipc-flooding-protection"
  ];
  
  if (proxy) {
    baseArgs.push(`--proxy-server=${proxy.host}:${proxy.port}`);
  }
  
  return baseArgs;
}

// === FUNCIONES DE MONITOREO ===
class ScrapingMonitor {
  constructor(businessName, placeId) {
    this.businessName = businessName;
    this.placeId = placeId;
    this.startTime = Date.now();
    this.lastCheckpoint = 0;
    this.totalReviews = 0;
    this.batchNumber = 0;
    this.errors = [];
    this.proxyRotations = 0;
    this.captchaCount = 0;
    this.rateLimitCount = 0;
  }
  
  updateProgress(reviewCount, batchNumber) {
    this.totalReviews = reviewCount;
    this.batchNumber = batchNumber;
    
    const stats = this.calculateStats();
    this.logProgress(stats);
    
    if (reviewCount - this.lastCheckpoint >= MASS_SCRAPER_CONFIG.PROGRESS_INTERVAL) {
      this.saveProgress();
      this.lastCheckpoint = reviewCount;
    }
  }
  
  calculateStats() {
    const elapsed = Date.now() - this.startTime;
    const minutes = elapsed / 60000;
    const reviewsPerMinute = Math.round(this.totalReviews / minutes);
    const estimatedTimeRemaining = (MASS_SCRAPER_CONFIG.TARGET_REVIEWS - this.totalReviews) / reviewsPerMinute;
    const progress = (this.totalReviews / MASS_SCRAPER_CONFIG.TARGET_REVIEWS) * 100;
    
    return {
      elapsed: Math.round(minutes * 100) / 100,
      reviewsPerMinute,
      estimatedTimeRemaining: Math.round(estimatedTimeRemaining * 100) / 100,
      progress: Math.round(progress * 100) / 100,
      batchNumber: this.batchNumber,
      errors: this.errors.length,
      proxyRotations: this.proxyRotations,
      captchaCount: this.captchaCount,
      rateLimitCount: this.rateLimitCount
    };
  }
  
  logProgress(stats) {
    console.log(`\n📊 === PROGRESO DEL SCRAPING ===`);
    console.log(`📍 Negocio: ${this.businessName}`);
    console.log(`📦 Lote: ${stats.batchNumber}`);
    console.log(`📈 Reseñas: ${this.totalReviews.toLocaleString()}`);
    console.log(`⏱️ Tiempo: ${stats.elapsed} min`);
    console.log(`🚀 Velocidad: ${stats.reviewsPerMinute} reseñas/min`);
    console.log(`⏳ Restante: ${stats.estimatedTimeRemaining} min`);
    console.log(`📊 Progreso: ${stats.progress}%`);
    console.log(`🔄 Proxy rotaciones: ${stats.proxyRotations}`);
    console.log(`🚨 Errores: ${stats.errors}`);
    console.log(`🤖 CAPTCHAs: ${stats.captchaCount}`);
    console.log(`⏸️ Rate limits: ${stats.rateLimitCount}`);
    console.log(`================================\n`);
  }
  
  saveProgress() {
    const cleanName = this.businessName.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_");
    const dir = path.join(process.cwd(), "clientes", `${cleanName}_${this.placeId}`);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    
    const progressFile = path.join(dir, MASS_SCRAPER_CONFIG.PROGRESS_FILE);
    const progressData = {
      businessName: this.businessName,
      placeId: this.placeId,
      startTime: this.startTime,
      lastUpdate: Date.now(),
      stats: this.calculateStats(),
      errors: this.errors,
      proxyRotations: this.proxyRotations,
      captchaCount: this.captchaCount,
      rateLimitCount: this.rateLimitCount
    };
    
    fs.writeFileSync(progressFile, JSON.stringify(progressData, null, 2));
  }
  
  addError(error) {
    this.errors.push({
      timestamp: new Date().toISOString(),
      message: error.message,
      batchNumber: this.batchNumber,
      totalReviews: this.totalReviews
    });
  }
  
  incrementProxyRotations() {
    this.proxyRotations++;
  }
  
  incrementCaptchaCount() {
    this.captchaCount++;
  }
  
  incrementRateLimitCount() {
    this.rateLimitCount++;
  }
}

// === FUNCIONES DE VALIDACIÓN ===
function validatePlaceId(placeId) {
  const pattern = /^[A-Za-z0-9_-]{27}$/;
  return pattern.test(placeId);
}

function validateMaxReviews(maxReviews) {
  return maxReviews > 0 && maxReviews <= MASS_SCRAPER_CONFIG.MAX_REVIEWS;
}

function validateProxy(proxy) {
  return proxy && proxy.host && proxy.port && proxy.username && proxy.password;
}

// === FUNCIONES DE UTILIDAD ===
function createUniqueKey(user, date, text) {
  return `${user}_${date}_${text.slice(0, 50)}`.replace(/[^a-zA-Z0-9_]/g, '');
}

function cleanBusinessName(name) {
  return name.replace(/[<>:"/\\|?*]/g, "").replace(/\s+/g, "_");
}

function formatNumber(num) {
  return num.toLocaleString();
}

function formatTime(minutes) {
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hours = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return `${hours}h ${mins}m`;
}

// === EXPORTACIONES ===
module.exports = {
  MASS_SCRAPER_CONFIG,
  SELECTOR_CONFIG,
  USER_AGENT_CONFIG,
  VIEWPORT_CONFIG,
  
  // Funciones de configuración
  getRandomUserAgent,
  getRandomViewport,
  getChromeArgs,
  
  // Monitor
  ScrapingMonitor,
  
  // Validación
  validatePlaceId,
  validateMaxReviews,
  validateProxy,
  
  // Utilidades
  createUniqueKey,
  cleanBusinessName,
  formatNumber,
  formatTime
};
