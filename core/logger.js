import fs from 'fs';
import path from 'path';
import winston from 'winston';
import { Config } from './config.js';

// ✅ Color scheme para console output
const colors = {
  reset: '\x1b[0m',
  bright: '\x1b[1m',
  dim: '\x1b[2m',
  red: '\x1b[31m',
  green: '\x1b[32m',
  yellow: '\x1b[33m',
  blue: '\x1b[34m',
  magenta: '\x1b[35m',
  cyan: '\x1b[36m',
  white: '\x1b[37m',
};

const levelColors = {
  error: colors.red + colors.bright,
  warn: colors.yellow,
  info: colors.cyan,
  debug: colors.dim + colors.blue,
};

export class Logger {
  constructor() {
    this.config = new Config();
    this.logLevel = this.config.get('logLevel');
    this.logDir = this.config.get('logsDir');
    this.ensureLogDir();

    // ✅ Formato personalizado para console con colores y timestamps
    const consoleFormat = winston.format.printf(({ level, message, timestamp, ...meta }) => {
      const color = levelColors[level] || colors.white;
      const levelUpper = level.toUpperCase().padEnd(5);
      const time = new Date(timestamp).toLocaleTimeString('es-ES');
      const metaStr =
        Object.keys(meta).length > 0 && meta.service !== 'scrapersuite'
          ? ` ${JSON.stringify(meta)}`
          : '';
      return `${color}[${time}] ${levelUpper}${colors.reset} ${message}${metaStr}`;
    });

    this.logger = winston.createLogger({
      level: this.logLevel,
      format: winston.format.combine(
        winston.format.timestamp(),
        winston.format.errors({ stack: true }),
        winston.format.json()
      ),
      defaultMeta: { service: 'scrapersuite' },
      transports: [
        new winston.transports.File({
          filename: path.join(this.logDir, 'error.log'),
          level: 'error',
        }),
        new winston.transports.File({ filename: path.join(this.logDir, 'combined.log') }),
      ],
    });

    // ✅ Agregar console logging (en desarrollo y producción con nivel INFO+)
    const consoleLevel = process.env.NODE_ENV === 'production' ? 'info' : this.logLevel;
    this.logger.add(
      new winston.transports.Console({
        level: consoleLevel,
        format: winston.format.combine(winston.format.timestamp(), consoleFormat),
      })
    );
  }

  ensureLogDir() {
    if (!fs.existsSync(this.logDir)) {
      fs.mkdirSync(this.logDir, { recursive: true });
    }
  }

  info(message, data = {}) {
    this.logger.info(message, data);
  }

  warn(message, data = {}) {
    this.logger.warn(message, data);
  }

  error(message, error = {}, data = {}) {
    this.logger.error(message, { error: error.message || error, stack: error.stack, ...data });
  }

  debug(message, data = {}) {
    this.logger.debug(message, data);
  }

  // Logging específico para scraping
  logScrapingStart(operation, data = {}) {
    this.info(`🚀 Iniciando operación de scraping: ${operation}`, data);
  }

  logScrapingEnd(operation, data = {}) {
    this.info(`✅ Operación de scraping completada: ${operation}`, data);
  }

  logScrapingProgress(operation, progress, data = {}) {
    this.debug(`📊 Progreso: ${operation} - ${progress}`, data);
  }

  // ✅ MEJORADO: Logging específico para debugging de scraping
  logElementDetection(elementsFound, strategy, data = {}) {
    if (elementsFound > 0) {
      this.debug(`🎯 Elementos encontrados con ${strategy}: ${elementsFound}`, data);
    } else {
      this.debug(`❌ Sin elementos con ${strategy}`, data);
    }
  }

  logSelectorAttempt(selector, success, data = {}) {
    const status = success ? '✅' : '❌';
    this.debug(`${status} Selector: ${selector}`, data);
  }

  logStrategyResult(strategy, success, details = {}) {
    const status = success ? '✅' : '❌';
    const detailStr = Object.keys(details).length > 0 ? ` (${JSON.stringify(details)})` : '';
    this.info(`${status} Estrategia ${strategy}${detailStr}`);
  }

  logCheckpoint(action, data = {}) {
    this.debug(`💾 Checkpoint: ${action}`, data);
  }

  logErrorWithContext(message, error, context = {}) {
    this.error(message, error, context);
  }

  // Performance logging
  logPerformance(operation, duration, data = {}) {
    this.info(`⏱️ Performance: ${operation} completado en ${duration}ms`, data);
  }

  // Batch logging
  logBatch(batchNumber, reviewsCount, data = {}) {
    this.info(`📦 Batch ${batchNumber}: ${reviewsCount} reseñas procesadas`, data);
  }

  // API logging
  logApiCall(endpoint, status, data = {}) {
    const level = status === 200 ? 'debug' : 'warn';
    this.logger.log(level, `🌐 API Call: ${endpoint} - Status: ${status}`, data);
  }

  // System health logging
  logSystemHealth(healthData) {
    this.info('💚 System Health Check', healthData);
  }

  // Generate log summary
  generateLogSummary() {
    const summary = {
      timestamp: new Date(),
      logLevel: this.logLevel,
      logDir: this.logDir,
      files: {},
    };

    try {
      const files = fs.readdirSync(this.logDir);
      files.forEach((file) => {
        if (file.endsWith('.log')) {
          const filePath = path.join(this.logDir, file);
          const stats = fs.statSync(filePath);
          summary.files[file] = {
            size: stats.size,
            modified: stats.mtime,
            lines: this.countLines(filePath),
          };
        }
      });
    } catch (error) {
      this.error('Error generating log summary', error);
    }

    return summary;
  }

  countLines(filePath) {
    try {
      const content = fs.readFileSync(filePath, 'utf-8');
      return content.split('\n').length;
    } catch (error) {
      return 0;
    }
  }

  // Clean old logs
  cleanupOldLogs(maxAge = 7 * 24 * 60 * 60 * 1000) {
    // 7 días por defecto
    try {
      const files = fs.readdirSync(this.logDir);
      let cleanedCount = 0;

      files.forEach((file) => {
        if (file.endsWith('.log')) {
          const filePath = path.join(this.logDir, file);
          const stat = fs.statSync(filePath);

          if (Date.now() - stat.mtime.getTime() > maxAge) {
            fs.unlinkSync(filePath);
            cleanedCount++;
          }
        }
      });

      this.info(`🧹 Logs limpiados: ${cleanedCount} archivos eliminados`);
      return cleanedCount;
    } catch (error) {
      this.error('Error cleaning old logs', error);
      return 0;
    }
  }
}
