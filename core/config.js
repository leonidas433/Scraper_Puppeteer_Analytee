import dotenv from 'dotenv';
import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// Compatibilidad Jest/Babel: fallback para __filename/__dirname en entorno de test
let __filename, __dirname;
try {
  __filename = fileURLToPath(import.meta.url);
  __dirname = path.dirname(__filename);
} catch (e) {
  // Entorno de test (CommonJS transformado por Babel)
  __filename = typeof __filename !== 'undefined' ? __filename : '';
  __dirname = typeof __dirname !== 'undefined' ? __dirname : process.cwd();
}

// Para Jest, necesitamos definir __filename y __dirname globalmente
if (typeof global !== 'undefined') {
  global.__filename = __filename;
  global.__dirname = __dirname;
}

export class Config {
  constructor() {
    // Cargar variables de entorno con configuración silenciosa
    dotenv.config({ silent: true });

    // Configuraciones con fallbacks robustos
    this.config = this.buildConfiguration();

    // Validar y establecer configuración
    this.initializeConfiguration();
  }

  buildConfiguration() {
    return {
      // 🔑 API Keys (Críticas)
      googleMapsApiKey: this.getEnvVar('GOOGLE_MAPS_API_KEY', { required: true, pattern: /^AIza/ }),
      openaiApiKey: this.getEnvVar('OPENAI_API_KEY', { required: false }),

      // 📁 Directorios y Rutas
      baseDir: this.getEnvVar('BASE_DIR', {
        default: path.join(__dirname, '..', '..'),
        type: 'path',
      }),
      logsDir: path.join(__dirname, '..', 'logs'),
      dataDir: path.join(__dirname, '..', 'data'),

      // 🔍 Configuración de Scraping (Críticas)
      maxReviews: this.getEnvVar('MAX_REVIEWS', {
        default: 150000,
        type: 'integer',
        min: 1,
        max: 150000,
      }),
      batchSize: this.getEnvVar('BATCH_SIZE', {
        default: 500,
        type: 'integer',
        min: 1,
        max: 1000,
      }),
      checkpointInterval: this.getEnvVar('CHECKPOINT_INTERVAL', {
        default: 200,
        type: 'integer',
        min: 1,
        max: 1000,
      }),
      proxyRotationInterval: this.getEnvVar('PROXY_ROTATION_INTERVAL', {
        default: 2000,
        type: 'integer',
        min: 1000,
        max: 60000,
      }),

      // 🌍 Configuración de Proxies
      proxyFile: this.getEnvVar('PROXY_FILE', { required: false }),

      // 🌐 Configuración de Puppeteer
      puppeteerHeadless: this.getEnvVar('PUPPETEER_HEADLESS', {
        default: 'true',
        type: 'boolean',
      }),
      chromePath: this.getEnvVar('CHROME_PATH', {
        default: this.getDefaultChromePath(),
        type: 'path',
      }),

      // 📊 Configuración de Scraping Avanzado
      maxScrollsPerBatch: this.getEnvVar('MAX_SCROLLS_PER_BATCH', {
        default: 50,
        type: 'integer',
        min: 1,
        max: 100,
      }),
      scrollTimeout: this.getEnvVar('SCROLL_TIMEOUT', {
        default: 15000,
        type: 'integer',
        min: 5000,
        max: 30000,
      }),
      retryAttempts: this.getEnvVar('RETRY_ATTEMPTS', {
        default: 3,
        type: 'integer',
        min: 1,
        max: 10,
      }),
      humanDelayMin: this.getEnvVar('HUMAN_DELAY_MIN', {
        default: 300,
        type: 'integer',
        min: 100,
        max: 2000,
      }),
      humanDelayMax: this.getEnvVar('HUMAN_DELAY_MAX', {
        default: 800,
        type: 'integer',
        min: 500,
        max: 5000,
      }),
      batchDelayMin: this.getEnvVar('BATCH_DELAY_MIN', {
        default: 5000,
        type: 'integer',
        min: 1000,
        max: 15000,
      }),
      batchDelayMax: this.getEnvVar('BATCH_DELAY_MAX', {
        default: 10000,
        type: 'integer',
        min: 2000,
        max: 30000,
      }),
      extractionTimeout: this.getEnvVar('EXTRACTION_TIMEOUT', {
        default: 10000,
        type: 'integer',
        min: 5000,
        max: 30000,
      }),
      maxExtractionAttempts: this.getEnvVar('MAX_EXTRACTION_ATTEMPTS', {
        default: 3,
        type: 'integer',
        min: 1,
        max: 10,
      }),

      // 📝 Configuración de Logging
      logLevel: this.getEnvVar('LOG_LEVEL', {
        default: 'info',
        type: 'enum',
        values: ['error', 'warn', 'info', 'debug'],
      }),

      // 💾 Configuración de Redis
      redis: {
        enabled: this.getEnvVar('REDIS_ENABLED', {
          default: 'false',
          type: 'boolean',
        }),
        host: this.getEnvVar('REDIS_HOST', { default: 'localhost' }),
        port: this.getEnvVar('REDIS_PORT', {
          default: 6379,
          type: 'integer',
          min: 1,
          max: 65535,
        }),
        password: this.getEnvVar('REDIS_PASSWORD', { required: false }),
        db: this.getEnvVar('REDIS_DB', {
          default: 0,
          type: 'integer',
          min: 0,
          max: 15,
        }),
      },

      // 🌐 Configuración del Servidor Web
      webPort: this.getEnvVar('WEB_PORT', {
        default: 3000,
        type: 'integer',
        min: 1024,
        max: 65535,
      }),

      // 🔧 Configuración de Desarrollo
      environment: this.getEnvVar('NODE_ENV', { default: 'development' }),
      scrapingDebug: this.getEnvVar('SCRAPING_DEBUG', {
        default: 'false',
        type: 'boolean',
      }),
      globalTimeout: this.getEnvVar('GLOBAL_TIMEOUT', {
        default: 60,
        type: 'integer',
        min: 30,
        max: 300,
      }),

      // 📈 Configuración de Métricas
      enableMetrics: this.getEnvVar('ENABLE_METRICS', {
        default: 'true',
        type: 'boolean',
      }),
      metricsInterval: this.getEnvVar('METRICS_INTERVAL', {
        default: 300,
        type: 'integer',
        min: 60,
        max: 3600,
      }),

      // 🚨 Configuración de Seguridad
      rateLimitPerMinute: this.getEnvVar('RATE_LIMIT_PER_MINUTE', {
        default: 100,
        type: 'integer',
        min: 60,
        max: 1000,
      }),
      rateLimitPerHour: this.getEnvVar('RATE_LIMIT_PER_HOUR', {
        default: 5000,
        type: 'integer',
        min: 1000,
        max: 10000,
      }),
      customUserAgent: this.getEnvVar('CUSTOM_USER_AGENT', { required: false }),
    };
  }

  getEnvVar(key, options = {}) {
    const {
      required = false,
      default: defaultValue = null,
      type = 'string',
      pattern = null,
      min = null,
      max = null,
      values = null,
    } = options;

    let value = process.env[key];

    // Si no está definida y es requerida
    if (!value && required) {
      throw new Error(`Variable de entorno requerida faltante: ${key}`);
    }

    // Si no está definida y no es requerida, usar default
    if (!value && !required && defaultValue !== null) {
      value = defaultValue;
    }

    // Si sigue sin estar definida y no tiene default
    if (!value && defaultValue === null) {
      return null;
    }

    // Transformar valor según tipo
    try {
      switch (type) {
        case 'integer': {
          const intValue = parseInt(value, 10);
          if (isNaN(intValue)) {
            throw new Error(`Invalid integer value for ${key}: ${value}`);
          }

          if (min !== null && intValue < min) {
            throw new Error(`Value ${intValue} for ${key} is below minimum ${min}`);
          }

          if (max !== null && intValue > max) {
            throw new Error(`Value ${intValue} for ${key} exceeds maximum ${max}`);
          }

          return intValue;
        }

        case 'boolean':
          return ['true', '1', 'yes', 'on'].includes(value.toLowerCase());

        case 'enum': {
          if (!values.includes(value)) {
            throw new Error(
              `Invalid value for ${key}: ${value}. Valid options: ${values.join(', ')}`
            );
          }
          return value;
        }

        case 'path': {
          // Validar que el path existe (para archivos) o crear directorio (para carpetas)
          if (value && !fs.existsSync(value)) {
            try {
              fs.mkdirSync(value, { recursive: true });
            } catch (error) {
              console.warn(`No se pudo crear el directorio ${value}: ${error.message}`);
            }
          }
          return value;
        }

        default: {
          // Validar pattern si está definido
          if (pattern && !pattern.test(value)) {
            throw new Error(`Value for ${key} doesn't match required pattern`);
          }
          return value;
        }
      }
    } catch (error) {
      if (required) {
        throw new Error(`Error validando ${key}: ${error.message}`);
      }
      console.warn(`Error en configuración ${key}, usando valor por defecto: ${error.message}`);
      return defaultValue;
    }
  }

  getDefaultChromePath() {
    const platform = process.platform;

    // ✅ MEJORADO: Detección automática de rutas de Chrome
    const possiblePaths = {
      win32: [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        process.env.LOCALAPPDATA + '\\Google\\Chrome\\Application\\chrome.exe',
        process.env.PROGRAMFILES + '\\Google\\Chrome\\Application\\chrome.exe',
        process.env['PROGRAMFILES(X86)'] + '\\Google\\Chrome\\Application\\chrome.exe',
      ],
      darwin: [
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/Applications/Chromium.app/Contents/MacOS/Chromium',
      ],
      linux: [
        '/usr/bin/google-chrome',
        '/usr/bin/google-chrome-stable',
        '/usr/bin/chromium',
        '/usr/bin/chromium-browser',
        '/snap/bin/chromium',
      ],
    };

    const paths = possiblePaths[platform] || ['/usr/bin/google-chrome'];

    // ✅ NUEVO: Verificar existencia de archivos
    for (const path of paths) {
      try {
        if (require('fs').existsSync(path)) {
          console.log(`✅ Chrome encontrado en: ${path}`);
          return path;
        }
      } catch (error) {
        // Continuar con siguiente path
      }
    }

    // Fallback al primer path si ninguno existe
    console.warn(`⚠️ No se encontró Chrome en rutas estándar. Usando: ${paths[0]}`);
    return paths[0];
  }

  initializeConfiguration() {
    // Configurar valores derivados
    this.ensureValidDelayRanges();
    this.validateDependencies();
    this.createRequiredDirectories();
    this.logConfigurationStatus();
  }

  ensureValidDelayRanges() {
    // Asegurar que los delays estén en orden correcto
    if (this.config.humanDelayMax < this.config.humanDelayMin) {
      const temp = this.config.humanDelayMax;
      this.config.humanDelayMax = this.config.humanDelayMin;
      this.config.humanDelayMin = temp;
      console.warn('Ajustado HUMAN_DELAY_MAX para ser mayor que HUMAN_DELAY_MIN');
    }

    if (this.config.batchDelayMax < this.config.batchDelayMin) {
      const temp = this.config.batchDelayMax;
      this.config.batchDelayMax = this.config.batchDelayMin;
      this.config.batchDelayMin = temp;
      console.warn('Ajustado BATCH_DELAY_MAX para ser mayor que BATCH_DELAY_MIN');
    }
  }

  validateDependencies() {
    // Validar dependencias entre configuraciones
    const warnings = [];

    if (this.config.maxScrollsPerBatch > 100 && this.config.logLevel === 'debug') {
      warnings.push('MAX_SCROLLS_PER_BATCH > 100 puede causar timeout en modo debug');
    }

    if (this.config.proxyRotationInterval < 1000) {
      warnings.push('PROXY_ROTATION_INTERVAL muy bajo puede causar bloqueos de IP');
    }

    // Mostrar warnings si los hay
    if (warnings.length > 0) {
      console.warn('Advertencias de configuración:');
      warnings.forEach((warning) => console.warn(`  - ${warning}`));
    }
  }

  createRequiredDirectories() {
    const requiredDirs = [this.config.baseDir, this.config.logsDir, this.config.dataDir];

    requiredDirs.forEach((dir) => {
      if (!fs.existsSync(dir)) {
        try {
          fs.mkdirSync(dir, { recursive: true });
        } catch (error) {
          console.warn(`No se pudo crear directorio ${dir}: ${error.message}`);
        }
      }
    });
  }

  logConfigurationStatus() {
    const configStatus = {
      environment: this.config.environment,
      googleMapsApiKey: this.config.googleMapsApiKey ? 'Configurada' : 'No configurada',
      openaiApiKey: this.config.openaiApiKey ? 'Configurada' : 'No configurada',
      redisEnabled: this.config.redis.enabled ? 'Habilitado' : 'Deshabilitado',
      proxies: this.config.proxyFile ? `Archivo: ${this.config.proxyFile}` : 'No configurados',
      logLevel: this.config.logLevel,
    };

    console.log('📋 Estado de configuración del sistema:');
    Object.entries(configStatus).forEach(([key, value]) => {
      console.log(`  ${key}: ${value}`);
    });
  }

  get(key) {
    return this.config[key];
  }

  getAll() {
    return { ...this.config };
  }

  set(key, value) {
    this.config[key] = value;
  }

  getPath(subpath) {
    return path.join(this.config.baseDir, subpath);
  }

  getLogPath(filename) {
    return path.join(this.config.logsDir, filename);
  }

  getDataPath(filename) {
    return path.join(this.config.dataDir, filename);
  }
}
