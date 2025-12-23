// autos: Leox433
// Metodo: AI
// Version: V4.6
// Fecha de última modificación: 2025-10-18
// Descripción: Scrapea metadatos de Google Maps usando Places API con fallback a Puppeteer

import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import fs from 'fs';
import puppeteer from 'puppeteer-extra';
import StealthPlugin from 'puppeteer-extra-plugin-stealth';
import AnonymizeUAPlugin from 'puppeteer-extra-plugin-anonymize-ua';
import { createDataDirectory, saveMetadata } from './storage/storage.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

dotenv.config({ path: "./config/.env" });

puppeteer.use(StealthPlugin());
puppeteer.use(AnonymizeUAPlugin());

// === Utilidades ===
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const randomDelay = (min, max) => Math.floor(Math.random() * (max - min + 1)) + min;

// === User-Agents rotativos ===
const USER_AGENTS = [
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
  'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0',
];

// === Viewports rotativos ===
const VIEWPORTS = [
  { width: 1920, height: 1080 },
  { width: 1366, height: 768 },
  { width: 1440, height: 900 },
];

// === Cargar proxies ===
function loadProxies() {
  const proxyFile = path.join(__dirname, '..', '..', 'config', 'Webshare_10_proxies.txt');
  if (!fs.existsSync(proxyFile)) {
    console.error('❌ Archivo config/Webshare_10_proxies.txt no encontrado');
    return [];
  }
  const content = fs.readFileSync(proxyFile, 'utf-8');
  return content
    .split('\n')
    .filter((line) => line.trim())
    .map((line) => {
      const [host, port, username, password] = line.trim().split(':');
      return { host, port, username, password };
    });
}

// === Obtener metadatos desde API ===
async function fetchMetadataFromApi(placeId, apiKey) {
  console.log('\n🔍 Obteniendo metadatos directamente de Google Places API...');
  const encodedPlaceId = encodeURIComponent(placeId);
  const encodedKey = encodeURIComponent(apiKey);
  const url = `https://maps.googleapis.com/maps/api/place/details/json?place_id=${encodedPlaceId}&fields=name,formatted_address,formatted_phone_number,website,opening_hours,rating,user_ratings_total,types,price_level,business_status,geometry,url,photos,international_phone_number,adr_address,address_components,current_opening_hours,icon_background_color,icon_mask_base_uri&key=${encodedKey}`;

  try {
    const res = await fetch(url);
    const result = await res.json();

    if (!result || result.status !== 'OK' || !result.result) {
      throw new Error(
        `API status: ${result?.status || 'NO_RESPONSE'} - ${result?.error_message || 'Unknown error'}`
      );
    }

    const businessName = result.result.name || `PLACE_${placeId}`;
    const address = result.result.formatted_address || 'NO_ADDRESS';
    const coords = result.result.geometry?.location || null;
    const latText = coords ? coords.lat : 'NO_LAT_LNG';
    const lngText = coords ? coords.lng : 'NO_LAT_LNG';

    let cid = 'NO_CID';
    if (result.result.url) {
      const m = result.result.url.match(/cid=(\d+)/);
      if (m) cid = m[1];
    }

    const phone = result.result.formatted_phone_number || 'NO_PHONE';
    const website = result.result.website || 'NO_WEBSITE';
    const rating = result.result.rating || 'NO_RATING';
    const reviewCount = result.result.user_ratings_total || 'NO_REVIEWS';
    const openingHours = result.result.opening_hours?.weekday_text
      ? result.result.opening_hours.weekday_text.join('; ')
      : 'NO_HOURS';
    const businessStatus = result.result.business_status || 'UNKNOWN';
    const types = result.result.types ? result.result.types.join(', ') : 'NO_TYPES';

    const category =
      result.result.types && result.result.types.length > 0
        ? result.result.types[0]
        : 'NO_CATEGORY';

    const price =
      typeof result.result.price_level === 'number'
        ? result.result.price_level.toString()
        : 'NO_PRICE';

    let photoReference = null;
    let allPhotos = [];
    if (result.result.photos && result.result.photos.length > 0) {
      photoReference = result.result.photos[0].photo_reference;
      // Capturar todas las referencias de fotos
      allPhotos = result.result.photos.map(p => ({
        reference: p.photo_reference,
        width: p.width,
        height: p.height,
        attribution: p.html_attributions ? p.html_attributions[0] : null
      }));
    }

    // === NUEVO BLOQUE: Extraer campos adicionales de API ===
    const internationalPhone = result.result.international_phone_number || phone;
    const formattedAddr = result.result.formatted_address || address;
    const adrAddress = result.result.adr_address || null;
    
    // Address components desglosados
    const addressComponents = {};
    if (result.result.address_components && Array.isArray(result.result.address_components)) {
      result.result.address_components.forEach(comp => {
        const types = comp.types || [];
        if (types.includes('street_number')) addressComponents.streetNumber = comp.long_name;
        if (types.includes('route')) addressComponents.street = comp.long_name;
        if (types.includes('locality')) addressComponents.city = comp.long_name;
        if (types.includes('administrative_area_level_2')) addressComponents.province = comp.long_name;
        if (types.includes('administrative_area_level_1')) addressComponents.state = comp.long_name;
        if (types.includes('postal_code')) addressComponents.zipCode = comp.long_name;
        if (types.includes('country')) addressComponents.country = comp.long_name;
      });
    }

    // Horarios actuales detallados
    let currentOpeningHours = null;
    if (result.result.current_opening_hours) {
      const coh = result.result.current_opening_hours;
      currentOpeningHours = {
        openNow: coh.open_now || false,
        weekdayText: coh.weekday_text || [],
        periods: coh.periods ? coh.periods.map(p => ({
          open: p.open || null,
          close: p.close || null
        })) : []
      };
    }

    // Viewport (área visible del mapa)
    let viewport = null;
    if (result.result.geometry && result.result.geometry.viewport) {
      const vp = result.result.geometry.viewport;
      viewport = {
        northeast: {
          lat: vp.northeast?.lat,
          lng: vp.northeast?.lng
        },
        southwest: {
          lat: vp.southwest?.lat,
          lng: vp.southwest?.lng
        }
      };
    }

    // Datos de iconografía
    const iconBackgroundColor = result.result.icon_background_color || null;
    const iconMaskUri = result.result.icon_mask_base_uri || null;

    console.log(
      `✅ Metadatos completos de API: Nombre=${businessName}, Dirección=${address}, Teléfono=${phone}, Rating=${rating}, Reviews=${reviewCount}, Estado=${businessStatus}, Precio=${price}`
    );
    return {
      businessName,
      address,
      phone,
      website,
      rating,
      reviewCount,
      openingHours,
      businessStatus,
      types,
      category,
      price,
      cid,
      latText,
      lngText,
      photoReference,
      // === NUEVOS CAMPOS ===
      internationalPhone,
      formattedAddress: formattedAddr,
      adrAddress,
      addressComponents,
      currentOpeningHours,
      viewport,
      iconBackgroundColor,
      iconMaskUri,
      allPhotos
    };
  } catch (err) {
    console.error('❌ Error en API de Places:', err.message);
    return null;
  }
}

// === Validar formato de Place ID ===
function isValidPlaceId(placeId) {
  return /^[A-Za-z0-9_-]{27}$/.test(placeId);
}

// === Scraping con Puppeteer (fallback) ===
async function scrapeMetadataWithPuppeteer(placeId, proxies) {
  console.log('\n🔄 Fallback a scraping con Puppeteer...');
  let browser;
  try {
    const proxy = proxies.length ? proxies[Math.floor(Math.random() * proxies.length)] : null;
    const args = proxy ? [`--proxy-server=${proxy.host}:${proxy.port}`] : [];

    // Ruta configurable desde .env
    const chromePath =
      process.env.CHROME_PATH || 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';

    browser = await puppeteer.launch({
      headless: true,
      executablePath: chromePath,
      args: args.filter((arg) => !arg.includes('proxy-server')), // Remover proxy args por ahora
    });

    const page = await browser.newPage();
    // establecer User-Agent y viewport
    await page.setUserAgent(USER_AGENTS[Math.floor(Math.random() * USER_AGENTS.length)]);
    await page.setViewport(VIEWPORTS[Math.floor(Math.random() * VIEWPORTS.length)]);

    if (proxy && proxy.username && proxy.password) {
      try {
        await page.authenticate({ username: proxy.username, password: proxy.password });
      } catch (e) {
        console.warn('⚠️ No se pudo autenticar proxy (puede que no lo requiera):', e.message);
      }
    }

    const url = `https://www.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
    await page.goto(url, { waitUntil: 'networkidle2', timeout: 20000 });
    await sleep(randomDelay(800, 1800));

    // obtener nombre, dirección y datos adicionales de forma robusta
    const businessData = await page.evaluate(() => {
      // Nombre del negocio
      const h1 = document.querySelector('h1');
      const businessName =
        h1 && h1.innerText
          ? h1.innerText.trim()
          : document.querySelector('[data-testid="entity-title"]')?.innerText?.trim() ||
            document.querySelector('[aria-labelledby]')?.innerText?.trim() ||
            null;

      // Dirección
      const address =
        document.querySelector('[data-item-id="address"]')?.innerText?.trim() ||
        document.querySelector('[data-testid="address"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Dirección"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Address"]')?.innerText?.trim() ||
        'NO_ADDRESS';

      // Teléfono - múltiples selectores más específicos
      const phone =
        document.querySelector('[data-item-id*="phone"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Teléfono"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Phone"]')?.innerText?.trim() ||
        document.querySelector('[data-tooltip*="phone"]')?.innerText?.trim() ||
        document.querySelector('a[href*="tel:"]')?.innerText?.trim() ||
        document.querySelector('a[href*="tel:"]')?.href?.replace('tel:', '') ||
        document.querySelector('.section-info-phone')?.innerText?.trim() ||
        'NO_PHONE';

      // Sitio web - múltiples estrategias
      const website =
        document.querySelector('a[data-item-id*="website"]')?.href ||
        document.querySelector('a[aria-label*="Sitio web"]')?.href ||
        document.querySelector('a[aria-label*="Website"]')?.href ||
        document.querySelector('a[data-tooltip*="website"]')?.href ||
        document.querySelector('a[href*="http"]')?.href ||
        document.querySelector('.section-info-website a')?.href ||
        'NO_WEBSITE';

      // Horarios - más selectores específicos
      const hours =
        document.querySelector('[data-item-id="hours"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Horario"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Hours"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Horarios"]')?.innerText?.trim() ||
        document.querySelector('.section-info-hours')?.innerText?.trim() ||
        document.querySelector('.opening-hours')?.innerText?.trim() ||
        document.querySelector('[data-section-id*="hours"]')?.innerText?.trim() ||
        'NO_HOURS';

      // Calificación general - más robusta
      const ratingElement =
        document.querySelector('[aria-label*="estrellas"]') ||
        document.querySelector('[aria-label*="stars"]') ||
        document.querySelector('[data-rating]') ||
        document.querySelector('.kvMYJc') ||
        document.querySelector('.section-rating') ||
        document.querySelector('[aria-label*="valoración"]');

      let rating = 'NO_RATING';
      if (ratingElement) {
        const ariaLabel = ratingElement.getAttribute('aria-label');
        const dataRating = ratingElement.getAttribute('data-rating');
        const innerText = ratingElement.innerText?.trim();

        if (ariaLabel) rating = ariaLabel;
        else if (dataRating) rating = dataRating;
        else if (innerText) rating = innerText;
      }

      // Número de reseñas - más selectores
      const reviewCount =
        document.querySelector('[aria-label*="reseñas"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="reviews"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="opiniones"]')?.innerText?.trim() ||
        document.querySelector('.UY7F9')?.innerText?.trim() ||
        document.querySelector('.section-rating-line .section-rating-term')?.innerText?.trim() ||
        document.querySelector('[data-review-count]')?.innerText?.trim() ||
        'NO_REVIEWS';

      // Categoría del negocio - más robusta
      const category =
        document.querySelector('[data-item-id="category"]')?.innerText?.trim() ||
        document.querySelector('.DkEaL')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Categoría"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Category"]')?.innerText?.trim() ||
        document.querySelector('.section-info-category')?.innerText?.trim() ||
        document.querySelector('[data-section-id*="category"]')?.innerText?.trim() ||
        'NO_CATEGORY';

      // Precio (indicador de €/$/$$/$$$ y rangos de precios más detallados)
      const price =
        document.querySelector('[aria-label*="Precio"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="Price"]')?.innerText?.trim() ||
        document.querySelector('.mgr77e')?.innerText?.trim() ||
        document.querySelector('[data-item-id*="price"]')?.innerText?.trim() ||
        document.querySelector('.section-info-price')?.innerText?.trim() ||
        document.querySelector('[aria-label*="rango de precios"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="price range"]')?.innerText?.trim() ||
        // Selectores adicionales para rangos de precios más específicos
        document.querySelector('[data-section-id*="price"]')?.innerText?.trim() ||
        document.querySelector('.section-price-range')?.innerText?.trim() ||
        document.querySelector('[aria-label*="€"]')?.innerText?.trim() ||
        document.querySelector('[aria-label*="$"]')?.innerText?.trim() ||
        document.querySelector('.price-range')?.innerText?.trim() ||
        document.querySelector('.cost')?.innerText?.trim() ||
        document.querySelector('[data-tooltip*="price"]')?.innerText?.trim() ||
        document.querySelector('[data-tooltip*="cost"]')?.innerText?.trim() ||
        'NO_PRICE';

      return {
        businessName: businessName || `PLACE_${placeId}`,
        address,
        phone,
        website,
        hours,
        rating,
        reviewCount,
        category,
        price,
      };
    });

    let cid = 'NO_CID';
    const pageUrl = page.url();
    const cidMatch = pageUrl.match(/cid=(\d+)/);
    if (cidMatch) cid = cidMatch[1];

    let latText = 'NO_LAT_LNG';
    let lngText = 'NO_LAT_LNG';
    const coordsMatch = pageUrl.match(/@(-?\d+\.\d+),(-?\d+\.\d+)/);
    if (coordsMatch) {
      latText = coordsMatch[1];
      lngText = coordsMatch[2];
    }

    console.log(
      `✅ Metadatos de scraping: Nombre=${businessData.businessName}, Dirección=${businessData.address}, Teléfono=${businessData.phone}, Sitio Web=${businessData.website}, Horarios=${businessData.hours}, Rating=${businessData.rating}, Reviews=${businessData.reviewCount}, Categoría=${businessData.category}, Precio=${businessData.price}, CID=${cid}, Lat=${latText}, Lng=${lngText}`
    );
    return {
      businessName: businessData.businessName,
      address: businessData.address,
      phone: businessData.phone,
      website: businessData.website,
      hours: businessData.hours,
      rating: businessData.rating,
      reviewCount: businessData.reviewCount,
      category: businessData.category,
      price: businessData.price,
      cid,
      latText,
      lngText,
    };
  } catch (error) {
    console.error('❌ Error en fallback de scraping:', error.message);
    return null;
  } finally {
    if (browser) {
      try {
        await browser.close();
      } catch (e) {
        /* ignorar */
      }
    }
  }
}

// === Función Principal ===
async function scrapeMetadata(placeId) {
  console.log(`🚀 Iniciando scraping de metadata para: ${placeId}`);
  console.log(`📅 Timestamp: ${new Date().toISOString()}`);

  if (!placeId) {
    console.error('⚠️ Debes pasar un Place ID como argumento');
    process.exit(1);
  }

  if (!isValidPlaceId(placeId)) {
    console.error(
      '⚠️ Formato de Place ID inválido. Debe tener 27 caracteres alfanuméricos con _ o -'
    );
    process.exit(1);
  }

  console.log('✅ Validación de Place ID correcta');

  const apiKey = process.env.GOOGLE_MAPS_API_KEY;
  console.log(`🔑 API Key configurada: ${apiKey ? 'SÍ' : 'NO'}`);

  const proxies = loadProxies();
  console.log(`🌐 Proxies cargados: ${proxies.length}`);

  let metadata = null;
  let apiMetadata = null;

  // Primero intentar API para datos básicos
  if (apiKey) {
    console.log('🔍 Intentando obtener datos básicos desde Google Places API...');
    apiMetadata = await fetchMetadataFromApi(placeId, apiKey);
    if (apiMetadata) {
      console.log('✅ Datos de API obtenidos correctamente');
    } else {
      console.log('⚠️ No se pudieron obtener datos de API, continuando con scraping');
    }
  } else {
    console.log('⚠️ No hay API key configurada, usando solo scraping con Puppeteer');
  }

  // SIEMPRE hacer scraping con Puppeteer para datos completos
  console.log('🔄 Realizando scraping completo con Puppeteer para obtener todos los datos...');
  metadata = await scrapeMetadataWithPuppeteer(placeId, proxies);

  if (metadata) {
    console.log('✅ Datos de scraping obtenidos correctamente');
  } else {
    console.log('❌ Error: No se pudieron obtener datos de scraping');
  }

  // Combinar datos: PRIORIZAR datos de API sobre scraping
  if (metadata && apiMetadata) {
    console.log('🔄 Combinando datos - Priorizando API sobre scraping...');

    // API tiene prioridad porque es más confiable y completa
    metadata.businessName = apiMetadata.businessName || metadata.businessName;
    metadata.address = apiMetadata.address || metadata.address;
    metadata.phone = apiMetadata.phone || metadata.phone;
    metadata.website = apiMetadata.website || metadata.website;
    metadata.rating = apiMetadata.rating || metadata.rating;
    metadata.reviewCount = apiMetadata.reviewCount || metadata.reviewCount;
    metadata.hours = apiMetadata.openingHours || metadata.hours;
    metadata.category = apiMetadata.category || metadata.category;
    metadata.price = apiMetadata.price || metadata.price;
    metadata.cid = apiMetadata.cid || metadata.cid;
    metadata.latText = apiMetadata.latText || metadata.latText;
    metadata.lngText = apiMetadata.lngText || metadata.lngText;
    metadata.photoReference = apiMetadata.photoReference || metadata.photoReference;
    
    // === NUEVO BLOQUE: Agregar campos extendidos de API ===
    metadata.internationalPhone = apiMetadata.internationalPhone || metadata.phone;
    metadata.formattedAddress = apiMetadata.formattedAddress || metadata.address;
    metadata.adrAddress = apiMetadata.adrAddress || null;
    metadata.addressComponents = apiMetadata.addressComponents || {};
    metadata.currentOpeningHours = apiMetadata.currentOpeningHours || null;
    metadata.viewport = apiMetadata.viewport || null;
    metadata.iconBackgroundColor = apiMetadata.iconBackgroundColor || null;
    metadata.iconMaskUri = apiMetadata.iconMaskUri || null;
    metadata.allPhotos = apiMetadata.allPhotos || [];
    metadata.businessStatus = apiMetadata.businessStatus || metadata.businessStatus;
    metadata.types = apiMetadata.types || metadata.types;

    console.log(
      `✅ Datos finales: Nombre=${metadata.businessName}, Dirección=${metadata.address}, Teléfono=${metadata.phone}, Rating=${metadata.rating}`
    );
  } else if (apiMetadata && !metadata) {
    console.log('⚠️ Usando solo datos de API (scraping falló)');
    metadata = apiMetadata;
  } else if (metadata && !apiMetadata) {
    console.log('⚠️ Usando solo datos de scraping (API falló)');
  }

  if (!metadata) {
    console.error('❌ No se pudieron obtener metadatos.');
    process.exit(1);
  }

  console.log(`📁 Preparando guardado de metadatos...`);

  // Crear directorio de datos con la nueva estructura: data/NombreNegocio_PlaceID/
  const dataDir = createDataDirectory(metadata.businessName, placeId);
  console.log(`📂 Directorio de salida: ${dataDir}`);

  // === NUEVO BLOQUE: Preparar objeto de metadatos COMPLETO con campos extendidos ===
  const metadataToSave = {
    // Campos básicos
    businessName: metadata.businessName,
    address: metadata.address,
    phone: metadata.phone,
    website: metadata.website,
    hours: metadata.hours,
    rating: metadata.rating,
    reviewCount: metadata.reviewCount,
    category: metadata.category,
    price: metadata.price,
    cid: metadata.cid,
    latitude: metadata.latText,
    longitude: metadata.lngText,
    photoReference: metadata.photoReference || null,
    mapsUrl: `https://www.google.com/maps?cid=${metadata.cid}`,
    reviewsUrl: `https://search.google.com/local/reviews?placeid=${placeId}`,
    
    // Campos extendidos de API
    internationalPhone: metadata.internationalPhone || null,
    formattedAddress: metadata.formattedAddress || null,
    businessStatus: metadata.businessStatus || null,
    businessTypes: metadata.types || []
  };

  // Guardar usando la función de storage
  const metadataPath = saveMetadata(metadataToSave, placeId, { dataDir, businessName: metadata.businessName });
  console.log(`✅ Metadatos guardados exitosamente en ${metadataPath}`);
  
  // === NUEVO BLOQUE: Guardar datos extendidos en archivo separado ===
  const extendedMetadata = {
    timestamp: new Date().toISOString(),
    placeId: placeId,
    businessName: metadata.businessName,
    
    // Información de contacto completa
    contactInfo: {
      phone: metadata.phone,
      internationalPhone: metadata.internationalPhone,
      website: metadata.website
    },
    
    // Dirección desglosada
    addressInfo: {
      fullAddress: metadata.formattedAddress,
      simpleAddress: metadata.address,
      adrAddress: metadata.adrAddress,
      components: metadata.addressComponents
    },
    
    // Ubicación geográfica
    locationInfo: {
      latitude: metadata.latText,
      longitude: metadata.lngText,
      viewport: metadata.viewport
    },
    
    // Información comercial
    businessInfo: {
      status: metadata.businessStatus,
      category: metadata.category,
      types: metadata.types,
      priceLevel: metadata.price,
      rating: metadata.rating,
      totalReviews: metadata.reviewCount
    },
    
    // Horarios
    scheduleInfo: {
      simpleHours: metadata.openingHours,
      currentOpeningHours: metadata.currentOpeningHours
    },
    
    // Fotos
    photosInfo: {
      primaryPhoto: metadata.photoReference,
      allPhotos: metadata.allPhotos
    },
    
    // Datos de iconografía
    uiInfo: {
      iconBackgroundColor: metadata.iconBackgroundColor,
      iconMaskUri: metadata.iconMaskUri
    },
    
    // Enlaces útiles
    links: {
      mapsUrl: `https://www.google.com/maps?cid=${metadata.cid}`,
      reviewsUrl: `https://search.google.com/local/reviews?placeid=${placeId}`,
      placeUrl: `https://www.google.com/maps/place/?q=place_id:${placeId}`
    }
  };
  
  try {
    const extendedMetadataPath = path.join(
      dataDir, 
      `${metadata.businessName}_${placeId}_extended_metadata.json`
    );
    fs.writeFileSync(
      extendedMetadataPath, 
      JSON.stringify(extendedMetadata, null, 2), 
      'utf-8'
    );
    console.log(`✅ Metadatos extendidos guardados en ${extendedMetadataPath}`);
  } catch (err) {
    console.warn(`⚠️ No se pudieron guardar metadatos extendidos: ${err.message}`);
  }

  // También mantener un archivo de texto legible como respaldo
  try {
    // === FORMATEADORES AUXILIARES ===
    const formatAddressComponents = (components) => {
      if (!components || Object.keys(components).length === 0) return 'No disponible';
      return Object.entries(components)
        .map(([key, value]) => `${key}: ${value}`)
        .join('; ');
    };

    const formatViewport = (viewport) => {
      if (!viewport) return 'No disponible';
      return `NE: (${viewport.northeast.lat}, ${viewport.northeast.lng}), SW: (${viewport.southwest.lat}, ${viewport.southwest.lng})`;
    };

    const formatHours = (hours) => {
      if (!hours || !hours.weekdayText) return 'No disponible';
      return hours.weekdayText.join('; ');
    };

    const formatPhotos = (photos) => {
      if (!photos || photos.length === 0) return 'No disponible';
      return photos.map((p, i) => `Foto ${i + 1}: ${p.width}x${p.height}px`).join('; ');
    };

    const textContent = [
      '=== INFORMACIÓN BÁSICA ===',
      'Topónimo',
      metadata.businessName,
      'DIRECCIÓN',
      metadata.address,
      'TELÉFONO',
      metadata.phone,
      'SITIO WEB',
      metadata.website,
      'HORARIOS',
      metadata.openingHours,
      'CALIFICACIÓN',
      metadata.rating,
      'NÚMERO DE RESEÑAS',
      metadata.reviewCount,
      'CATEGORÍA',
      metadata.category,
      'PRECIO',
      metadata.price,
      'ID del lugar',
      placeId,
      'CID',
      metadata.cid,
      'Latitud',
      metadata.latText,
      'Longitud',
      metadata.lngText,
      'Colocar URL',
      `https://www.google.com/maps?cid=${metadata.cid}`,
      'URL de reseñas',
      `https://search.google.com/local/reviews?placeid=${placeId}`,
      
      '',
      '=== INFORMACIÓN EXTENDIDA (API FIELDS) ===',
      'Estado del negocio',
      metadata.businessStatus || 'No disponible',
      'Tipos de negocio',
      metadata.types || 'No disponible',
      'Teléfono Internacional',
      metadata.internationalPhone || 'No disponible',
      'Dirección Formateada',
      metadata.formattedAddress || 'No disponible',
      'Dirección ADR',
      metadata.adrAddress || 'No disponible',
      'Componentes de Dirección',
      formatAddressComponents(metadata.addressComponents),
      'Horarios Actuales Detallados',
      formatHours(metadata.currentOpeningHours),
      'Viewport del Mapa',
      formatViewport(metadata.viewport),
      'Color de Icono de Fondo',
      metadata.iconBackgroundColor || 'No disponible',
      'URI Máscara de Icono',
      metadata.iconMaskUri || 'No disponible',
      'Todas las Fotos',
      formatPhotos(metadata.allPhotos),
    ].join('\n');
    
    // Nombre de archivo incluye BusinessName y PlaceID
    const cleanName = metadata.businessName.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '_');
    const textFile = path.join(dataDir, `metadatos_${cleanName}_${placeId}.txt`);
    fs.writeFileSync(textFile, textContent);
    console.log(`📝 Archivo de texto legible guardado en ${textFile}`);
  } catch (err) {
    console.warn(`⚠️ Error guardando archivo de texto: ${err.message}`);
  }

  // === Descargar imagen principal si hay referencia ===
  if (metadata.photoReference && apiKey) {
    try {
      const photoUrl = `https://maps.googleapis.com/maps/api/place/photo?maxwidth=1600&photoreference=${metadata.photoReference}&key=${apiKey}`;
      const cleanName = metadata.businessName.replace(/[<>:"/\\|?*]/g, '').replace(/\s+/g, '_');
      const photoPath = path.join(dataDir, `${cleanName}_photo.jpg`);

      console.log(`📸 Descargando imagen principal...`);
      const response = await fetch(photoUrl);
      const buffer = await response.arrayBuffer();
      fs.writeFileSync(photoPath, Buffer.from(buffer));
      console.log(`✅ Imagen guardada en ${photoPath}`);
    } catch (err) {
      console.error(`⚠️ Error al descargar la foto: ${err.message}`);
    }
  } else {
    console.log('⚠️ No hay referencia de foto disponible o falta API key.');
  }
}

// === EJECUCIÓN ===
async function mainEntry() {
  console.log('🚀 Iniciando scrape_metadata.js...');
  console.log(`📋 Argumentos: ${process.argv.slice(2).join(', ')}`);
  console.log(`📍 import.meta.url: ${import.meta.url}`);
  console.log(`📍 process.argv[1]: ${process.argv[1]}`);

  const placeId = process.argv[2];
  console.log(`🎯 Place ID: ${placeId}`);

  await scrapeMetadata(placeId).catch((err) => {
    console.error('❌ Error en mainEntry:', err);
    process.exit(1);
  });
}

// Ejecutar solo si se invoca directamente (compatibilidad Windows)
const isDirectExecution =
  import.meta.url === `file://${process.argv[1]}` ||
  import.meta.url === `file:///${process.argv[1]}` ||
  process.argv[1].includes('scrape_metadata.js') ||
  process.argv[1].endsWith('scrape_metadata.js');

console.log(`🔍 Es ejecución directa: ${isDirectExecution}`);

if (isDirectExecution) {
  console.log('✅ Ejecutando mainEntry...');
  mainEntry();
} else {
  console.log('ℹ️ Script cargado como módulo');
}

// Exportar la función para que otros módulos puedan usarla
export { scrapeMetadata };

// NOTA LEGAL: Uso permitido solo conforme a los Términos de Google Maps.
