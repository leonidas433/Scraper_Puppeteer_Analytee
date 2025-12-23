// photo.js
import { downloadToFile } from './utils.js';

export async function savePhotoFromUrl(url, destPath, logger = null) {
  try {
    if (!url) {
      logger?.warn && logger.warn('savePhotoFromUrl: URL vacía');
      return false;
    }

    await downloadToFile(url, destPath);

    logger?.info && logger.info(`Foto guardada en ${destPath}`);
    return true;
  } catch (err) {
    logger?.warn && logger.warn(`savePhotoFromUrl error: ${err.message}`);
    return false;
  }
}
