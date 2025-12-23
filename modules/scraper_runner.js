#!/usr/bin/env node

/**
 * scraper_runner.js
 *
 * ✅ Runner directo para ReviewsScraper
 *
 * Uso:
 *   node scraper_runner.js <PLACE_ID> [maxReviews]
 *
 * Ejemplos:
 *   node scraper_runner.js ChIJPVJmXkS9pBIRMq2hlz01j4s
 *   node scraper_runner.js ChIJPVJmXkS9pBIRMq2hlz01j4s 5000
 */

import { ReviewsScraper } from './reviews_scraper.js';

const PLACE_ID = process.argv[2];
const MAX_REVIEWS = parseInt(process.argv[3] || '5000', 10);

if (!PLACE_ID) {
  console.error('❌ Error: Se requiere PLACE_ID\n');
  console.error('Uso: node scraper_runner.js <PLACE_ID> [maxReviews]\n');
  console.error('Ejemplo: node scraper_runner.js ChIJPVJmXkS9pBIRMq2hlz01j4s 5000\n');
  process.exit(1);
}

(async () => {
  try {
    const scraper = new ReviewsScraper();
    console.log(`\n🚀 Iniciando scraper para Place ID: ${PLACE_ID}`);
    console.log(`📊 Máximo de reseñas: ${MAX_REVIEWS}`);
    console.log('⏳ Por favor espera...\n');

    const result = await scraper.scrape(PLACE_ID, MAX_REVIEWS);

    console.log('\n✅ Scraping completado exitosamente.\n');
    console.log('📁 Resultado:', JSON.stringify(result, null, 2));

    process.exit(0);
  } catch (err) {
    console.error('\n❌ Error en scraping:', err.message);
    console.error('\n📋 Stack:', err.stack);
    process.exit(1);
  }
})();
