import fs from 'fs';
import path from 'path';
import https from 'https';
import { URL } from 'url';
import { Config } from './config.js';

export const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const randomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

export const randomScrollAmount = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

export const cleanText = (text) => {
  if (typeof text !== 'string') return '';
  return text
    .replace(/[\u{1F300}-\u{1FAFF}\u{1F1E6}-\u{1F1FF}\u{2600}-\u{27BF}]/gu, '')
    .replace(/\s+/g, ' ')
    .trim();
};

export const ensureDir = (dirPath) => {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    return true;
  }
  return false;
};

export const writeFileSafe = (filePath, content) => {
  ensureDir(path.dirname(filePath));
  fs.writeFileSync(filePath, content, 'utf-8');
};

export const downloadToFile = async (url, destPath) => {
  return new Promise((resolve, reject) => {
    try {
      const u = new URL(url);
      const req = https.get(
        {
          hostname: u.hostname,
          path: u.pathname + (u.search || ''),
          headers: { 'User-Agent': 'Mozilla/5.0' },
        },
        (res) => {
          if (res.statusCode !== 200) {
            reject(new Error(`HTTP ${res.statusCode}`));
            return;
          }
          ensureDir(path.dirname(destPath));
          const file = fs.createWriteStream(destPath);
          res.pipe(file);
          file.on('finish', () => file.close(() => resolve(destPath)));
          file.on('error', (e) => reject(e));
        }
      );
      req.on('error', reject);
      req.setTimeout(15000, () => {
        req.destroy(new Error('timeout descarga'));
      });
    } catch (e) {
      reject(e);
    }
  });
};

export const isValidPlaceId = (pid) => {
  if (!pid || typeof pid !== 'string') return false;
  // Google Place IDs: 27 caracteres, pueden contener letras, números, guiones y guiones bajos
  // Algunos IDs reales pueden tener letras mayúsculas, minúsculas, números y guiones bajos
  return (
    typeof pid === 'string' &&
    (/^[A-Za-z0-9_-]{27}$/.test(pid) || // 27 chars, alfanumérico + _-
      /^[A-Za-z0-9]{27}$/.test(pid)) // 27 chars, solo alfanumérico
  );
};

export const isValidUrl = (url) => {
  if (!url || typeof url !== 'string') return false;
  try {
    const parsedUrl = new URL(url);
    return ['http:', 'https:'].includes(parsedUrl.protocol);
  } catch {
    return false;
  }
};

export const isValidNumber = (num, min = 0, max = Infinity) => {
  if (typeof num !== 'number' && typeof num !== 'string') return false;
  const parsed = parseFloat(num);
  if (isNaN(parsed)) return false;
  // Permitir Infinity y -Infinity si están dentro del rango permitido
  if (!isFinite(parsed)) {
    return parsed === Infinity
      ? max === Infinity
      : parsed === -Infinity
        ? min === -Infinity
        : false;
  }
  return parsed >= min && parsed <= max;
};

export const isValidEmail = (email) => {
  if (!email || typeof email !== 'string') return false;
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
};

export const sanitizeInput = (input, maxLength = 1000) => {
  if (!input || typeof input !== 'string') return '';
  return input
    .replace(/[<>"'&]/g, '') // Remover caracteres peligrosos
    .replace(/\s+/g, ' ') // Normalizar espacios
    .trim()
    .substring(0, maxLength);
};

export const loadProxies = () => {
  const config = new Config();
  const proxyFile = config.get('proxyFile');

  if (!proxyFile || !fs.existsSync(proxyFile)) {
    return [];
  }

  try {
    const content = fs.readFileSync(proxyFile, 'utf-8');
    const lines = content.split('\n').filter((line) => line.trim() && !line.startsWith('#'));
    const failedProxy = '84.247.60.125:6095';
    const proxies = lines
      .filter((line) => !line.includes(failedProxy))
      .map((line) => {
        const [host, port, username, password] = line.trim().split(':');
        return {
          host,
          port,
          username,
          password,
          full: `http://${username}:${password}@${host}:${port}`,
          working: true,
          failures: 0,
          lastTested: null,
        };
      });
    return proxies;
  } catch (error) {
    return [];
  }
};

export const selectRandomProxy = (proxies) => {
  if (proxies.length === 0) return null;

  // Filtrar solo proxies que funcionen
  const workingProxies = proxies.filter((proxy) => proxy.working);

  let selectedProxy;
  if (workingProxies.length === 0) {
    // Si no hay proxies funcionando, usar el primero disponible
    selectedProxy = proxies[Math.floor(Math.random() * proxies.length)];
    console.log(`[PROXY] ⚠️ Ningún proxy funcionando. Usando proxy: ${selectedProxy.host}:${selectedProxy.port}`);
  } else {
    selectedProxy = workingProxies[Math.floor(Math.random() * workingProxies.length)];
    console.log(`[PROXY] ✅ Proxy seleccionado: ${selectedProxy.host}:${selectedProxy.port} (${workingProxies.length}/${proxies.length} activos)`);
  }

  return selectedProxy;
};

export const testProxy = async (proxy) => {
  return new Promise((resolve) => {
    const url = new URL('https://www.google.com');
    const req = https.request({
      hostname: url.hostname,
      path: url.pathname,
      method: 'HEAD',
      timeout: 10000,
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
      },
    });

    req.on('response', (res) => {
      resolve({
        success: true,
        statusCode: res.statusCode,
        proxy: proxy,
      });
    });

    req.on('timeout', () => {
      req.destroy();
      resolve({
        success: false,
        error: 'timeout',
        proxy: proxy,
      });
    });

    req.on('error', (error) => {
      resolve({
        success: false,
        error: error.message,
        proxy: proxy,
      });
    });

    req.end();
  });
};

export const testAllProxies = async (proxies, logger = null) => {
  if (proxies.length === 0) return proxies;

  console.log(`[PROXY-TEST] 🧪 Iniciando pruebas de ${proxies.length} proxies...`);

  const testPromises = proxies.map(async (proxy, index) => {
    try {
      const testStartTime = Date.now();
      const result = await testProxy(proxy);
      const testDuration = Date.now() - testStartTime;
      
      proxy.working = result.success;
      proxy.lastTested = new Date();
      proxy.failures = result.success ? 0 : (proxy.failures || 0) + 1;
      proxy.responseTime = testDuration;

      if (!result.success) {
        const msg = `[PROXY-TEST] ❌ Proxy ${index + 1}/${proxies.length} FALLÓ: ${proxy.host}:${proxy.port} - Error: ${result.error}`;
        console.log(msg);
        if (logger) logger.warn(msg);
      } else {
        const msg = `[PROXY-TEST] ✅ Proxy ${index + 1}/${proxies.length} OK: ${proxy.host}:${proxy.port} (${testDuration}ms)`;
        console.log(msg);
        if (logger) logger.info(msg);
      }

      return proxy;
    } catch (error) {
      proxy.working = false;
      proxy.failures = (proxy.failures || 0) + 1;
      proxy.lastTested = new Date();
      const msg = `[PROXY-TEST] ❌ Excepción en proxy ${index + 1}/${proxies.length}: ${proxy.host}:${proxy.port} - ${error.message}`;
      console.log(msg);
      if (logger) logger.warn(msg);
      return proxy;
    }
  });

  const testedProxies = await Promise.all(testPromises);
  const workingCount = testedProxies.filter((p) => p.working).length;

  const summaryMsg = `[PROXY-TEST] 📊 Pruebas completadas: ${workingCount}/${testedProxies.length} proxies funcionando`;
  console.log(summaryMsg);
  if (logger) {
    logger.info(summaryMsg);
  }

  return testedProxies;
};

export const markProxyAsFailed = (proxies, failedProxy) => {
  const proxy = proxies.find((p) => p.host === failedProxy.host && p.port === failedProxy.port);
  if (proxy) {
    proxy.working = false;
    proxy.failures = (proxy.failures || 0) + 1;
    proxy.lastTested = new Date();
  }
  return proxies;
};

export const detectLanguageSimple = (text) => {
  if (!text || text.length < 3) return 'unknown';

  const textLower = text.toLowerCase();

  // Palabras clave por idioma (detección básica)
  const langPatterns = {
    es: [
      'el',
      'la',
      'los',
      'las',
      'un',
      'una',
      'y',
      'de',
      'que',
      'en',
      'muy',
      'pero',
      'por',
      'con',
      'sin',
      'sobre',
      'entre',
      'desde',
      'hasta',
      'durante',
      'aunque',
      'siempre',
      'nunca',
      'también',
      'tampoco',
      'quizá',
      'acá',
      'ahí',
      'allá',
      'aquí',
      'bueno',
      'buena',
      'buenos',
      'buenas',
      'malo',
      'mala',
      'malos',
      'malas',
      'excelente',
      'perfecto',
      'horrible',
      'terrible',
      'delicioso',
      'rico',
      'fresco',
      'caliente',
      'frío',
      'rápido',
      'lento',
      'amable',
      'atento',
      'servicio',
      'comida',
      'bebida',
      'restaurante',
      'precio',
      'calidad',
      'ambiente',
      'ubicación',
    ],
    en: [
      'the',
      'and',
      'or',
      'but',
      'in',
      'on',
      'at',
      'to',
      'for',
      'of',
      'with',
      'by',
      'an',
      'a',
      'is',
      'are',
      'was',
      'were',
      'be',
      'been',
      'being',
      'have',
      'has',
      'had',
      'do',
      'does',
      'did',
      'will',
      'would',
      'could',
      'should',
      'may',
      'might',
      'must',
      'can',
      'good',
      'bad',
      'great',
      'excellent',
      'terrible',
      'amazing',
      'wonderful',
      'delicious',
      'fresh',
      'hot',
      'cold',
      'fast',
      'slow',
      'friendly',
      'service',
      'food',
      'drink',
      'restaurant',
      'price',
      'quality',
      'atmosphere',
      'location',
    ],
    fr: [
      'le',
      'la',
      'les',
      'un',
      'une',
      'et',
      'de',
      'que',
      'en',
      'à',
      'pour',
      'avec',
      'par',
      'sur',
      'dans',
      'du',
      'des',
      'au',
      'aux',
      'ce',
      'cette',
      'ces',
      'il',
      'elle',
      'nous',
      'vous',
      'ils',
      'elles',
      'bon',
      'bonne',
      'bons',
      'bonnes',
      'mauvais',
      'mauvaise',
      'excellent',
      'parfait',
      'horrible',
      'terrible',
      'délicieux',
      'frais',
      'chaud',
      'froid',
      'rapide',
      'lent',
      'aimable',
      'service',
      'nourriture',
      'boisson',
      'restaurant',
      'prix',
      'qualité',
      'ambiance',
      'emplacement',
    ],
    ca: [
      'el',
      'la',
      'els',
      'les',
      'un',
      'una',
      'uns',
      'unes',
      'i',
      'de',
      'que',
      'en',
      'a',
      'per',
      'amb',
      'amb',
      'sobre',
      'entre',
      'des',
      'fins',
      'tot',
      'tota',
      'tots',
      'totes',
      'bé',
      'bona',
      'bons',
      'bones',
      'dolent',
      'dolenta',
      'excel·lent',
      'perfecte',
      'horrible',
      'terrible',
      'deliciós',
      'fresc',
      'calent',
      'fred',
      'ràpid',
      'lent',
      'amable',
      'servei',
      'menjar',
      'beguda',
      'restaurant',
      'preu',
      'qualitat',
      'ambient',
      'ubicació',
    ],
    pt: [
      'o',
      'a',
      'os',
      'as',
      'um',
      'uma',
      'uns',
      'umas',
      'e',
      'de',
      'que',
      'em',
      'para',
      'com',
      'por',
      'sobre',
      'entre',
      'desde',
      'até',
      'durante',
      'embora',
      'sempre',
      'nunca',
      'também',
      'tampouco',
      'talvez',
      'aqui',
      'aí',
      'lá',
      'bom',
      'boa',
      'bons',
      'boas',
      'mau',
      'má',
      'maus',
      'más',
      'excelente',
      'perfeito',
      'horrível',
      'terrível',
      'delicioso',
      'fresco',
      'quente',
      'frio',
      'rápido',
      'lento',
      'amável',
      'serviço',
      'comida',
      'bebida',
      'restaurante',
      'preço',
      'qualidade',
      'ambiente',
      'localização',
    ],
  };

  // Contar ocurrencias de palabras clave por idioma
  const scores = {};
  for (const [lang, words] of Object.entries(langPatterns)) {
    scores[lang] = 0;
    for (const word of words) {
      const regex = new RegExp(`\\b${word}\\b`, 'gi');
      const matches = textLower.match(regex);
      if (matches) {
        scores[lang] += matches.length;
      }
    }
  }

  // Encontrar el idioma con más coincidencias
  let maxScore = 0;
  let detectedLang = 'es'; // Default español

  for (const [lang, score] of Object.entries(scores)) {
    if (score > maxScore) {
      maxScore = score;
      detectedLang = lang;
    }
  }

  // Si no hay suficientes coincidencias, devolver unknown
  return maxScore >= 2 ? detectedLang : 'unknown';
};

export const createUniqueKey = (user, date, text) => {
  return `${user}_${date}_${text.slice(0, 50)}`.replace(/[^a-zA-Z0-9_-]/g, '');
};

export const getRandomElement = (array) => {
  if (!Array.isArray(array) || array.length === 0) {
    return undefined;
  }
  return array[Math.floor(Math.random() * array.length)];
};

export const httpsGetJson = (url) => {
  return new Promise((resolve, reject) => {
    https
      .get(url, (res) => {
        let data = '';
        res.on('data', (d) => (data += d));
        res.on('end', () => {
          try {
            resolve(JSON.parse(data));
          } catch (e) {
            reject(e);
          }
        });
      })
      .on('error', reject)
      .setTimeout(15000, function () {
        this.destroy(new Error('timeout api'));
      });
  });
};

export const savePartialResults = (allReviews, cleanBusinessName, placeId, type = 'reviews') => {
  const config = new Config();
  const dir = config.getPath(`${cleanBusinessName}_${placeId}`);

  ensureDir(dir);

  let filename;
  let header;
  let csvContent = '';

  if (type === 'reviews') {
    filename = `${cleanBusinessName}_${placeId}_partial.csv`;
    header =
      'user,rating date,text,lang,owner_response,' +
      'owner_response_date,review_likes,review_photos,review_response_time\n';
    for (const r of allReviews.values()) {
      const row =
        `"${r.user}","${r.rating}","${r.date}","${r.text.replace(/"/g, '""')}",` +
        `"${r.lang || 'unknown'}","${r.ownerResponse || ''}",` +
        `"${r.ownerResponseDate || ''}","${r.reviewLikes || '0'}",` +
        `"${r.reviewPhotos || '0'}","${r.reviewResponseTime || ''}"\n`;
      csvContent += row;
    }
  } else {
    // Para otros tipos de datos
    filename = `${cleanBusinessName}_${placeId}_partial.json`;
    header = '';
    csvContent = JSON.stringify(Array.from(allReviews.entries()), null, 2);
  }

  const filePath = path.join(dir, filename);
  fs.writeFileSync(filePath, header + csvContent, 'utf-8');
};

export const anonymizeText = (text, maxLength = 50) => {
  if (!text) return '[vacío]';

  // Remover datos sensibles
  let anonymized = text
    .replace(/\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b/g, '[TARJETA]')
    .replace(/\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b/g, '[EMAIL]')
    .replace(/\b\d{3}[-.]?\d{3}[-.]?\d{4}\b/g, '[TELÉFONO]');

  if (anonymized.length > maxLength) {
    anonymized = anonymized.substring(0, maxLength) + '...';
  }

  return anonymized;
};

// Directory management functions integrated
export class DirectoryManager {
  constructor(logger = null) {
    this.logger = logger;
    this.config = new Config();
    this.baseDir = this.config.get('baseDir');
    this.ensureBaseStructure();
  }

  ensureBaseStructure() {
    const dirs = [this.baseDir, this.config.get('logsDir'), this.config.get('dataDir')];
    dirs.forEach((dir) => ensureDir(dir));
  }

  getPlaceDirectory(placeId, businessName = '') {
    if (!placeId || typeof placeId !== 'string') {
      throw new Error('Place ID is required and must be a string');
    }
    const folderName = businessName
      ? `${this.cleanBusinessName(businessName)}_${placeId}`
      : placeId;
    // ✅ CORREGIDO: Usar subdirectorio 'clientes/' para consistencia
    return path.join(this.baseDir, 'clientes', folderName);
  }

  getMetadataDirectory(placeId, businessName = '') {
    return this.getPlaceDirectory(placeId, businessName);
  }

  getReviewsDirectory(placeId, businessName = '') {
    return this.getPlaceDirectory(placeId, businessName);
  }

  getImagesDirectory(placeId, businessName = '') {
    return this.getPlaceDirectory(placeId, businessName);
  }

  cleanBusinessName(name) {
    return cleanText(name)
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '') // Eliminar acentos
      .replace(/[<>:"/\\|?*]/g, '')
      .replace(/\s+/g, '_')
      .replace(/_{2,}/g, '_')
      .substring(0, 50);
  }

  ensureDirectory(dirPath) {
    return ensureDir(dirPath);
  }

  getPlaceInfo(placeId, businessName = '') {
    const placeDir = this.getPlaceDirectory(placeId, businessName);

    return {
      placeId,
      businessName: this.cleanBusinessName(businessName),
      placeDirectory: placeDir,
      metadataDirectory: placeDir,
      reviewsDirectory: placeDir,
      imagesDirectory: placeDir,
      exists: fs.existsSync(placeDir),
      files: this.getDirectoryFiles(placeDir),
    };
  }

  getDirectoryFiles(dirPath) {
    if (!fs.existsSync(dirPath)) {
      return [];
    }

    try {
      return fs.readdirSync(dirPath).map((file) => ({
        name: file,
        path: path.join(dirPath, file),
        size: fs.statSync(path.join(dirPath, file)).size,
        modified: fs.statSync(path.join(dirPath, file)).mtime,
      }));
    } catch (error) {
      return [];
    }
  }

  findExistingPlace(placeId) {
    if (!fs.existsSync(this.baseDir)) return null;

    const items = fs.readdirSync(this.baseDir);
    const placeDir = items.find((item) => item.includes(placeId));

    if (placeDir) {
      return path.join(this.baseDir, placeDir);
    }

    return null;
  }

  detectBusinessName(placeId) {
    try {
      const baseDir = path.join(this.baseDir, 'clientes');
      if (!fs.existsSync(baseDir)) {
        if (this.logger) {
          this.logger.warn(`Directorio base de clientes no encontrado: ${baseDir}`);
        }
        return '';
      }

      const folders = fs.readdirSync(baseDir);
      // ✅ MEJORADO: Búsqueda más robusta de carpetas
      const candidates = folders.filter((f) => {
        // Incluir carpetas que terminan con el placeId
        return f.endsWith(`_${placeId}`) || f.includes(placeId);
      });

      if (candidates.length === 0) {
        if (this.logger) {
          this.logger.warn(`No se encontraron carpetas para Place ID: ${placeId}`);
        }
        return '';
      }

      // ✅ NUEVO: Si hay múltiples candidatos, elegir el más reciente
      let selectedFolder = candidates[0];
      if (candidates.length > 1) {
        const folderStats = candidates.map((folder) => {
          const folderPath = path.join(baseDir, folder);
          try {
            const stats = fs.statSync(folderPath);
            return { folder, mtime: stats.mtime };
          } catch (e) {
            return { folder, mtime: new Date(0) };
          }
        });

        // Ordenar por fecha de modificación (más reciente primero)
        folderStats.sort((a, b) => b.mtime - a.mtime);
        selectedFolder = folderStats[0].folder;

        if (this.logger) {
          this.logger.info(
            `Múltiples carpetas encontradas, seleccionando más reciente: ${selectedFolder}`
          );
        }
      }

      // ✅ MEJORADO: Extracción más robusta del nombre del negocio
      const regex = new RegExp(`^(.+)_${placeId}$`);
      const match = selectedFolder.match(regex);

      let businessName = '';
      if (match) {
        businessName = match[1];
      } else {
        // Fallback: quitar el placeId del final
        businessName = selectedFolder.replace(new RegExp(`_${placeId}$`), '');
      }

      // Limpiar nombre
      businessName = businessName.replace(/_+$/, '').trim();

      if (!businessName || businessName === '') {
        businessName = 'PLACE_UNKNOWN';
      }

      // ✅ NUEVO: Validar que el nombre no sea solo números o caracteres especiales
      if (/^[\d\W_]+$/.test(businessName)) {
        businessName = 'PLACE_UNKNOWN';
      }

      if (this.logger) {
        this.logger.info(
          `BusinessName detectado: "${businessName}" para Place ID: ${placeId} (carpeta: ${selectedFolder})`
        );
      }

      return businessName;
    } catch (error) {
      if (this.logger) {
        this.logger.error('Error detectando businessName', error);
      }
      return '';
    }
  }

  getStorageStats() {
    const stats = {
      totalDirectories: 0,
      totalFiles: 0,
      totalSize: 0,
      filesByType: {
        txt: 0,
        csv: 0,
        json: 0,
        jpg: 0,
        png: 0,
        other: 0,
      },
    };

    if (!fs.existsSync(this.baseDir)) return stats;

    const items = fs.readdirSync(this.baseDir);

    items.forEach((item) => {
      const itemPath = path.join(this.baseDir, item);
      const stat = fs.statSync(itemPath);

      if (stat.isDirectory()) {
        stats.totalDirectories++;

        const placeItems = fs.readdirSync(itemPath);
        placeItems.forEach((file) => {
          const filePath = path.join(itemPath, file);
          const fileStat = fs.statSync(filePath);

          if (fileStat.isFile()) {
            stats.totalFiles++;
            stats.totalSize += fileStat.size;

            const ext = path.extname(file).toLowerCase().substring(1);
            if (ext in stats.filesByType) {
              stats.filesByType[ext]++;
            } else {
              stats.filesByType.other++;
            }
          }
        });
      }
    });

    return stats;
  }

  createPlaceIndex(placeDir, placeId, businessName, data = {}) {
    const dir = placeDir; // ya viene con ...\clientes\<nombre>_<id>
    ensureDir(dir);
    const indexFile = path.join(dir, 'index.json');

    const indexData = {
      placeId,
      businessName: this.cleanBusinessName(businessName),
      createdAt: new Date(),
      lastModified: new Date(),
      files: this.getDirectoryFiles(dir),
      metadata: {
        hasMetadata: true,
        hasReviews: true,
        hasImages: false,
      },
      ...data,
    };

    writeFileSafe(indexFile, JSON.stringify(indexData, null, 2));
    return indexData;
  }

  getPlaceIndex(placeId, businessName = '') {
    const placeDir = path.join(
      this.config.get('baseDir'),
      'clientes',
      `${this.cleanBusinessName(businessName)}_${placeId}`
    );
    const indexFile = path.join(placeDir, 'index.json');

    if (fs.existsSync(indexFile)) {
      try {
        return JSON.parse(fs.readFileSync(indexFile, 'utf8'));
      } catch (error) {
        // Silently handle errors in place index reading
      }
    }

    return null;
  }

  listAllPlaces() {
    const places = [];

    const clientesDir = path.join(this.baseDir, 'clientes');
    if (!fs.existsSync(clientesDir)) return places;

    const items = fs.readdirSync(clientesDir);

    items.forEach((item) => {
      const itemPath = path.join(clientesDir, item);

      if (fs.statSync(itemPath).isDirectory()) {
        const regex = new RegExp(`^(.+)_([A-Za-z0-9_-]{27})$`);
        const match = item.match(regex);
        if (match) {
          const businessName = match[1].replace(/_+$/, '').trim();
          const placeId = match[2];
          let finalBusinessName = businessName || 'PLACE_UNKNOWN';

          places.push({
            placeId,
            businessName: finalBusinessName,
            directory: itemPath,
            index: this.getPlaceIndex(placeId, finalBusinessName),
          });
        }
      }
    });

    return places.sort((a, b) => b.index?.lastModified - a.index?.lastModified);
  }

  cleanupTempFiles(maxAge = 86400000) {
    const tempDir = path.join(this.baseDir, 'temp');
    if (!fs.existsSync(tempDir)) return 0;

    const files = fs.readdirSync(tempDir);
    let cleanedCount = 0;

    files.forEach((file) => {
      const filePath = path.join(tempDir, file);
      const stat = fs.statSync(filePath);

      if (Date.now() - stat.mtime.getTime() > maxAge) {
        fs.unlinkSync(filePath);
        cleanedCount++;
      }
    });

    return cleanedCount;
  }

  saveCheckpoint(data, businessName, placeId, batchNumber = 0) {
    const dir = this.getPlaceDirectory(placeId, businessName);
    ensureDir(dir);

    const checkpointFile = path.join(dir, `checkpoint_batch_${batchNumber}.json`);
    const checkpointData = {
      batchNumber,
      totalReviews: data.size || 0,
      timestamp: new Date().toISOString(),
      reviews: Array.from(data.entries() || []),
    };

    fs.writeFileSync(checkpointFile, JSON.stringify(checkpointData, null, 2));
    return checkpointFile;
  }

  loadCheckpoint(placeId, businessName) {
    const dir = this.getPlaceDirectory(placeId, businessName);

    if (!fs.existsSync(dir)) return { allReviews: new Map(), lastBatch: -1 };

    try {
      const files = fs.readdirSync(dir).filter((f) => f.startsWith('checkpoint_batch_'));
      if (files.length === 0) return { allReviews: new Map(), lastBatch: -1 };

      const latestFile = files.sort().pop();
      const data = JSON.parse(fs.readFileSync(path.join(dir, latestFile), 'utf-8'));

      return {
        allReviews: new Map(data.reviews || []),
        lastBatch: typeof data.batchNumber === 'number' ? data.batchNumber : -1,
      };
    } catch (e) {
      return { allReviews: new Map(), lastBatch: -1 };
    }

  }
}

// ✅ Exponential backoff retry mechanism
export const retryWithExponentialBackoff = async (
  fn,
  maxAttempts = 3,
  initialDelay = 1000,
  logger = null
) => {
  let lastError;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;

      if (attempt === maxAttempts) {
        break;
      }

      const delay = initialDelay * Math.pow(2, attempt - 1);
      if (logger) {
        logger.warn(`Intento ${attempt}/${maxAttempts} falló. Reintentando en ${delay}ms...`, {
          error: error.message,
        });
      }

      await sleep(delay);
    }
  }

  throw lastError;
};

// ✅ Get business name from Google Places API
export const getBusinessNameFromApi = async (placeId, apiKey) => {
  if (!placeId || !apiKey) return null;
  
  try {
    const encodedPlaceId = encodeURIComponent(placeId);
    const encodedKey = encodeURIComponent(apiKey);
    const url = `https://maps.googleapis.com/maps/api/place/details/json?place_id=${encodedPlaceId}&fields=name&key=${encodedKey}`;
    
    const response = await fetch(url);
    const data = await response.json();
    
    if (data.status === 'OK' && data.result?.name) {
      console.log('[API] Business Name:', data.result.name);
      return data.result.name;
    }
    
    return null;
  } catch (error) {
    console.error('[ERROR] Failed to fetch business name from API:', error.message);
    return null;
  }
};
