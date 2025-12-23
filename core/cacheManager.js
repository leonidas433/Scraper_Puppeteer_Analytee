import { Logger } from './logger.js';
import { Config } from './config.js';

export class CacheManager {
  constructor() {
    this.config = new Config();
    this.logger = new Logger();
    this.redis = null;
    this.isConnected = false;

    // Redis deshabilitado por defecto para simplificar dependencias
    this.logger.info('Cache Manager inicializado (Redis deshabilitado)');
  }

  // Redis deshabilitado para simplificar dependencias
  // Todas las operaciones de cache retornan null/false

  // Métodos simplificados sin Redis
  async connect() {
    return false;
  }

  async disconnect() {
    return;
  }

  generateKey(type, identifier, params = {}) {
    const keyParts = [type, identifier, ...Object.values(params).sort()];
    return `scrapersuite:${keyParts.join(':')}`;
  }

  async get(key) {
    return null; // Sin cache
  }

  async set(key, data, ttl = null) {
    return false; // Sin cache
  }

  async delete(key) {
    return false; // Sin cache
  }

  async getOrSet(key, factoryFunction, ttl = null) {
    return await factoryFunction(); // Ejecutar siempre
  }

  // Métodos específicos simplificados
  async getPlaceMetadata(placeId) {
    return null;
  }

  async setPlaceMetadata(placeId, data, ttl = 3600) {
    return false;
  }

  async getPlaceReviews(placeId, maxReviews) {
    return null;
  }

  async setPlaceReviews(placeId, data, maxReviews, ttl = 7200) {
    return false;
  }

  async getAnalytics(placeId, businessName) {
    return null;
  }

  async setAnalytics(placeId, data, businessName, ttl = 14400) {
    return false;
  }

  async invalidatePlace(placeId) {
    return false;
  }

  async getStats() {
    return { enabled: false };
  }

  async cleanup() {
    return 0;
  }
}
