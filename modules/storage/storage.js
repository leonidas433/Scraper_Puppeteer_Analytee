// storage.js - Módulo unificado de almacenamiento de reseñas y metadatos
// Integración: google-review-scraper-1 + Scraper_final

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

/**
 * Limpia nombre de negocio para usar en ruta de carpeta
 * @param {string} name - Nombre del negocio
 * @returns {string} Nombre limpio
 */
function cleanFolderName(name) {
  if (!name || typeof name !== 'string') return 'unknown';
  
  let cleaned = name
    .replace(/[<>:"/\\|?*]/g, '') // Caracteres inválidos en Windows
    .replace(/\s+/g, '_') // Espacios a guiones bajos
    .trim();
  
  // Limita a máximo 100 caracteres para evitar rutas demasiado largas
  if (cleaned.length > 100) {
    cleaned = cleaned.substring(0, 100);
  }
  
  // Si después de la limpieza queda vacío, usa valor por defecto
  return cleaned || 'unknown';
}

/**
 * Crea directorio de datos con nombre del negocio y PlaceID
 * @param {string} businessName - Nombre del negocio
 * @param {string} placeId - ID del lugar
 * @returns {string} Ruta del directorio creado
 */
export function createDataDirectory(businessName = null, placeId = null) {
  let dirName;

  if (placeId) {
    // Siempre usar PlaceID como base para consistencia
    // Si hay businessName, lo agregamos pero limpiamos para evitar duplicados
    if (businessName) {
      const cleanName = cleanFolderName(businessName);
      dirName = `${cleanName}_${placeId}`;
    } else {
      // Solo PlaceID si no hay nombre de negocio
      dirName = placeId;
    }
  } else {
    // Formato antiguo: timestamp (para compatibilidad)
    const timestamp = new Date();
    const dateStr = timestamp.toISOString().split('T')[0].replace(/-/g, '');
    const timeStr = timestamp.toTimeString().split(' ')[0].replace(/:/g, '');
    dirName = `${dateStr}-${timeStr}`;
  }

  const dataDir = path.join(__dirname, '../../data', dirName);

  // Verificar si ya existe un directorio con el mismo PlaceID
  const dataRoot = path.join(__dirname, '../../data');
  if (fs.existsSync(dataRoot)) {
    const existingDirs = fs.readdirSync(dataRoot, { withFileTypes: true })
      .filter(dirent => dirent.isDirectory())
      .map(dirent => dirent.name)
      .filter(name => name.includes(placeId));

    if (existingDirs.length > 0) {
      // Usar el directorio existente en lugar de crear uno nuevo
      const existingDir = path.join(dataRoot, existingDirs[0]);
      console.log(`📁 Usando directorio existente para PlaceID ${placeId}: ${existingDirs[0]}`);
      return existingDir;
    }
  }

  if (!fs.existsSync(dataDir)) {
    fs.mkdirSync(dataDir, { recursive: true });
  }

  return dataDir;
}

/**
 * Guarda reseñas en archivo JSON
 * @param {Array} reviews - Array de objetos de reseñas
 * @param {string} placeId - ID del lugar
 * @param {Object} options - Opciones adicionales (dataDir, businessName, fileName)
 * @returns {string} Ruta del archivo guardado
 */
export function saveReviews(reviews, placeId, options = {}) {
  const dataDir = options.dataDir || createDataDirectory();
  // Si se proporciona businessName, usarlo en el nombre del archivo; si no, usar placeId
  const fileBaseName = options.businessName 
    ? cleanFolderName(options.businessName) 
    : `reviews_${placeId}`;
  const fileName = options.fileName || `${fileBaseName}.json`;
  const filePath = path.join(dataDir, fileName);
  
  const output = {
    placeId,
    total: reviews.length,
    scrapedAt: new Date().toISOString(),
    reviews: reviews
  };
  
  try {
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    fs.writeFileSync(filePath, JSON.stringify(output, null, 2), 'utf-8');
    console.log(`💾 Guardadas ${reviews.length} reseñas en ${filePath}`);
    
    return filePath;
  } catch (error) {
    console.error(`❌ Error guardando reseñas: ${error.message}`);
    throw error;
  }
}

/**
 * Guarda metadatos del lugar
 * @param {Object} metadata - Objeto con información del lugar
 * @param {string} placeId - ID del lugar
 * @param {Object} options - Opciones adicionales (dataDir, businessName, fileName)
 * @returns {string} Ruta del archivo guardado
 */
export function saveMetadata(metadata, placeId, options = {}) {
  const dataDir = options.dataDir || createDataDirectory();
  // Construir nombre de archivo basado en businessName o placeId
  const fileBaseName = options.businessName 
    ? cleanFolderName(options.businessName)
    : `metadata_${placeId}`;
  const fileName = options.fileName || `${fileBaseName}_metadata.json`;
  const filePath = path.join(dataDir, fileName);
  
  const output = {
    placeId,
    scrapedAt: new Date().toISOString(),
    ...metadata
  };
  
  try {
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    fs.writeFileSync(filePath, JSON.stringify(output, null, 2), 'utf-8');
    console.log(`💾 Metadatos guardados en ${filePath}`);
    
    return filePath;
  } catch (error) {
    console.error(`❌ Error guardando metadatos: ${error.message}`);
    throw error;
  }
}

/**
 * Carga reseñas desde archivo JSON
 * @param {string} filePath - Ruta del archivo
 * @returns {Array} Array de reseñas
 */
export function loadReviews(filePath) {
  try {
    if (!fs.existsSync(filePath)) {
      console.warn(`⚠️ Archivo no encontrado: ${filePath}`);
      return [];
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    const data = JSON.parse(content);
    
    return Array.isArray(data.reviews) ? data.reviews : data;
  } catch (error) {
    console.error(`❌ Error cargando reseñas: ${error.message}`);
    return [];
  }
}

/**
 * Crea archivo de checkpoint para recuperación ante fallos
 * @param {Object} checkpoint - Datos del checkpoint
 * @param {string} batchNumber - Número de lote
 * @param {Object} options - Opciones adicionales
 * @returns {string} Ruta del archivo checkpoint
 */
export function saveCheckpoint(checkpoint, batchNumber, options = {}) {
  const dataDir = options.dataDir || createDataDirectory();
  const fileName = `checkpoint_batch_${batchNumber}.json`;
  const filePath = path.join(dataDir, fileName);
  
  const output = {
    batchNumber,
    timestamp: new Date().toISOString(),
    ...checkpoint
  };
  
  try {
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    fs.writeFileSync(filePath, JSON.stringify(output, null, 2), 'utf-8');
    console.log(`✅ Checkpoint ${batchNumber} guardado`);
    
    return filePath;
  } catch (error) {
    console.error(`❌ Error guardando checkpoint: ${error.message}`);
    throw error;
  }
}

/**
 * Carga checkpoint para recuperación
 * @param {string} filePath - Ruta del checkpoint
 * @returns {Object} Datos del checkpoint
 */
export function loadCheckpoint(filePath) {
  try {
    if (!fs.existsSync(filePath)) {
      return null;
    }
    
    const content = fs.readFileSync(filePath, 'utf-8');
    return JSON.parse(content);
  } catch (error) {
    console.error(`❌ Error cargando checkpoint: ${error.message}`);
    return null;
  }
}

/**
 * Exporta reseñas en formato CSV
 * @param {Array} reviews - Array de reseñas
 * @param {string} placeId - ID del lugar
 * @param {Object} options - Opciones adicionales (dataDir, businessName, fileName)
 * @returns {string} Ruta del archivo CSV
 */
export function exportAsCSV(reviews, placeId, options = {}) {
  const dataDir = options.dataDir || createDataDirectory();
  // Usar businessName si está disponible; si no, usar placeId
  const fileBaseName = options.businessName 
    ? cleanFolderName(options.businessName)
    : `reviews_${placeId}`;
  // Incluir PlaceID en el nombre del archivo CSV
  const fileName = options.fileName || `${fileBaseName}_${placeId}.csv`;
  const filePath = path.join(dataDir, fileName);
  
  try {
    if (!fs.existsSync(dataDir)) {
      fs.mkdirSync(dataDir, { recursive: true });
    }
    
    // === NUEVO BLOQUE: aplanar ownerResponse para CSV ===
    const flatReviews = reviews.map(r => ({
      ...r,
      ownerResponse: r.ownerResponse?.text || ""
    }));
    
    // Obtener headers
    const headers = Array.from(
      new Set(flatReviews.flatMap(r => Object.keys(r)))
    );
    
    // Crear CSV
    const rows = [
      headers.join(','),
      ...flatReviews.map(review =>
        headers.map(h => {
          const val = review[h];
          // Escapar comillas y entrecomillar si contiene comas, comillas o newlines
          const escaped = String(val || '').replace(/"/g, '""');
          return escaped.includes(',') || escaped.includes('"') || escaped.includes('\n') || escaped.includes('\r')
            ? `"${escaped}"` 
            : escaped;
        }).join(',')
      )
    ];
    
    fs.writeFileSync(filePath, rows.join('\n'), 'utf-8');
    const absolutePath = path.resolve(filePath);
    console.log(`📊 CSV exportado a ${absolutePath}`);
    
    return { path: filePath, absolutePath: absolutePath };
  } catch (error) {
    console.error(`❌ Error exportando CSV: ${error.message}`);
    throw error;
  }
}

/**
 * Obtiene información de archivos en directorio de datos
 * @param {string} dataDir - Directorio de datos
 * @returns {Object} Información de archivos
 */
export function getDataDirInfo(dataDir = null) {
  const dir = dataDir || path.join(__dirname, '../../data');
  
  try {
    if (!fs.existsSync(dir)) {
      return { exists: false, files: [] };
    }
    
    const files = fs.readdirSync(dir, { withFileTypes: true });
    const fileInfo = files.map(f => ({
      name: f.name,
      isDirectory: f.isDirectory(),
      path: path.join(dir, f.name)
    }));
    
    return {
      exists: true,
      path: dir,
      files: fileInfo,
      totalFiles: fileInfo.length
    };
  } catch (error) {
    console.error(`❌ Error leyendo directorio: ${error.message}`);
    return { exists: false, files: [], error: error.message };
  }
}