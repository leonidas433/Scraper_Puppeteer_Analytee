import { Config } from './config.js';
import { httpsGetJson, retryWithExponentialBackoff } from './utils.js';
import { CacheManager } from './cacheManager.js';
import { Logger } from './logger.js';

// NUEVO: helpers para foto principal
import { getPrimaryPhotoFromDOM } from './scraper.js';
import { savePhotoFromUrl } from './photo.js';

/**
 * Cache con control de memoria para evitar fugas
 */
class MemoryAwareCache {
  constructor(maxMemoryMB = 50) {
    this.cache = new Map();
    this.maxMemory = maxMemoryMB * 1024 * 1024;
    this.currentMemory = 0;
    this.accessTimes = new Map();
  }

  estimateSize(obj) {
    const str = JSON.stringify(obj);
    return str.length * 2; // Aproximación conservadora para UTF-16
  }

  evictIfNeeded(requiredSize) {
    if (requiredSize > this.maxMemory) {
      throw new Error(`Value too large: ${requiredSize} bytes, max allowed: ${this.maxMemory}`);
    }

    while (this.currentMemory + requiredSize > this.maxMemory && this.cache.size > 0) {
      let oldestKey = null;
      let oldestTime = Date.now();

      for (const [key, accessTime] of this.accessTimes) {
        if (accessTime < oldestTime) {
          oldestTime = accessTime;
          oldestKey = key;
        }
      }

      if (oldestKey) {
        const removed = this.cache.get(oldestKey);
        const removedSize = this.estimateSize(removed);
        this.cache.delete(oldestKey);
        this.accessTimes.delete(oldestKey);
        this.currentMemory -= removedSize;
      } else {
        break;
      }
    }
  }

  async set(key, value, ttl = 3600) {
    const size = this.estimateSize(value);
    this.evictIfNeeded(size);

    this.cache.set(key, {
      value,
      expiresAt: Date.now() + ttl * 1000,
    });
    this.accessTimes.set(key, Date.now());
    this.currentMemory += size;
  }

  async get(key) {
    const entry = this.cache.get(key);
    if (!entry) return null;

    if (Date.now() > entry.expiresAt) {
      const size = this.estimateSize(entry.value);
      this.cache.delete(key);
      this.accessTimes.delete(key);
      this.currentMemory -= size;
      return null;
    }

    this.accessTimes.set(key, Date.now());
    return entry.value;
  }

  clear() {
    this.cache.clear();
    this.accessTimes.clear();
    this.currentMemory = 0;
  }

  getStats() {
    return {
      size: this.cache.size,
      memory: this.currentMemory,
      maxMemory: this.maxMemory,
      utilizationPercent: (this.currentMemory / this.maxMemory) * 100,
    };
  }
}

export class GooglePlacesAPI {
  constructor() {
    this.config = new Config();
    this.apiKey = this.config.get('googleMapsApiKey');
    this.memoryCache = new MemoryAwareCache(25); // 25MB límite
    this.cache = new CacheManager();
    this.logger = new Logger();
  }

  /**
   * Procesa múltiples requests en paralelo para mejor rendimiento
   */
  async batchGetPlaceDetails(placeIds) {
    const cacheKey = `batch:${placeIds.sort().join(',')}`;

    const cached = await this.memoryCache.get(cacheKey);
    if (cached) {
      this.logger.info(`Cache HIT: batch ${placeIds.length} places`);
      return cached;
    }

    const promises = placeIds.map(async (placeId) => {
      try {
        const result = await this.getPlaceDetails(placeId);
        return { placeId, success: true, data: result };
      } catch (error) {
        this.logger.warn(`Error fetching place ${placeId}: ${error.message}`);
        return { placeId, success: false, error: error.message };
      }
    });

    const results = await Promise.all(promises);

    await this.memoryCache.set(cacheKey, results, 1800); // 30 min TTL

    return results;
  }

  async getPlaceDetails(placeId) {
    const fields = [
      'place_id',
      'name',
      'formatted_address',
      'geometry',
      'url',
      'formatted_phone_number',
      'international_phone_number',
      'opening_hours',
      'current_opening_hours',
      'secondary_opening_hours',
      'price_level',
      'rating',
      'user_ratings_total',
      'website',
      'types',
      'business_status',
      'address_components',
      'plus_code',
      'vicinity',
      'utc_offset',
      'reviews',
      'photos',
      'editorial_summary',
    ].join(',');

    const url = `https://maps.googleapis.com/maps/api/place/details/json?place_id=${encodeURIComponent(
      placeId
    )}&fields=${encodeURIComponent(fields)}&key=${encodeURIComponent(this.apiKey)}`;

    const cacheKey = `place:${placeId}`;
    const cached = await this.memoryCache.get(cacheKey);
    if (cached) {
      this.logger.debug(`Cache HIT: metadata ${placeId}`);
      return cached;
    }

    const json = await retryWithExponentialBackoff(
      async () => httpsGetJson(url),
      3,
      1000,
      this.logger
    );

    if (!json || json.status !== 'OK' || !json.result) {
      throw new Error(
        `Places Details error: ${json?.status || 'NO_STATUS'} ${json?.error_message || ''}`
      );
    }

    try {
      await this.memoryCache.set(cacheKey, json.result, 3600); // 1 hora
      this.logger.debug(`Cache SET: metadata ${placeId}`);
    } catch (error) {
      this.logger.warn(`Cache SET failed for ${placeId}: ${error.message}`);
    }

    return json.result;
  }

  makePhotoUrl(photoReference, maxWidth = 1600) {
    return `https://maps.googleapis.com/maps/api/place/photo?maxwidth=${maxWidth}&photoreference=${encodeURIComponent(
      photoReference
    )}&key=${encodeURIComponent(this.apiKey)}`;
  }

  async downloadPhoto(photoReference, destPath, maxWidth = 1600) {
    const photoUrl = this.makePhotoUrl(photoReference, maxWidth);
    const { downloadToFile } = await import('./utils.js');
    return downloadToFile(photoUrl, destPath);
  }

  async searchNearby(location, radius = 5000, type = 'restaurant', keyword = '') {
    const fields = 'place_id,name,vicinity,types,rating,user_ratings_total,price_level';
    let url = `https://maps.googleapis.com/maps/api/place/nearbysearch/json?location=${location}&radius=${radius}&type=${type}&fields=${fields}&key=${this.apiKey}`;

    if (keyword) {
      url += `&keyword=${encodeURIComponent(keyword)}`;
    }

    const json = await retryWithExponentialBackoff(
      async () => httpsGetJson(url),
      3,
      1000,
      this.logger
    );

    if (!json || json.status !== 'OK') {
      throw new Error(`Nearby search error: ${json?.status || 'NO_STATUS'}`);
    }

    return json.results || [];
  }

  async getPlacePhoto(photoReference, maxWidth = 1600) {
    const photoUrl = this.makePhotoUrl(photoReference, maxWidth);
    return photoUrl;
  }

  validateApiKey() {
    if (!this.apiKey) {
      throw new Error('Google Maps API key no configurada');
    }
    if (!this.apiKey.startsWith('AIza')) {
      throw new Error('API key inválida. Debe comenzar con "AIza"');
    }
    return true;
  }

  async testConnection() {
    try {
      this.validateApiKey();
      await this.getPlaceDetails('ChIJd8srQ6nYMzURyN2affsY2ro'); // ejemplo
      return { success: true, message: 'API connection successful' };
    } catch (error) {
      return { success: false, message: error.message };
    }
  }

  // =====================================================
  // NUEVO BLOQUE: FOTO PRINCIPAL "PRO"
  // =====================================================

  /**
   * Devuelve la mejor URL de foto disponible para un place:
   * 1) API -> photo_reference
   * 2) Fallback -> DOM con Puppeteer (imagen de perfil real)
   */
  async getBestPhotoUrl(placeData, placeId, maxWidth = 1600) {
    try {
      // 1) API: si hay photos, usar photo_reference
      if (placeData?.photos?.length) {
        const ref = placeData.photos[0].photo_reference;
        if (ref) {
          this.logger.debug(`Usando photo_reference de API para ${placeId}`);
          return this.makePhotoUrl(ref, maxWidth);
        }
      }

      // 2) Fallback: scraping DOM
      this.logger.debug(`Buscando foto principal en DOM para ${placeId}`);
      const domUrl = await getPrimaryPhotoFromDOM(placeId, this.logger);
      if (domUrl) {
        this.logger.debug(`Foto DOM encontrada para ${placeId}`);
        return domUrl;
      }

      this.logger.warn(`No se encontró foto para ${placeId}`);
      return null;
    } catch (err) {
      this.logger.warn(`getBestPhotoUrl error ${placeId}: ${err.message}`);
      return null;
    }
  }

  /**
   * Guarda la foto principal del negocio en destPath.
   * Devuelve objeto { success, path?, reason? }
   */
  async savePrimaryPhoto(placeId, destPath, placeData, maxWidth = 1600) {
    const url = await this.getBestPhotoUrl(placeData, placeId, maxWidth);
    if (!url) {
      return { success: false, reason: 'NO_PHOTO_URL' };
    }

    const ok = await savePhotoFromUrl(url, destPath, this.logger);
    if (!ok) {
      return { success: false, reason: 'DOWNLOAD_FAILED' };
    }

    return { success: true, path: destPath };
  }
}
