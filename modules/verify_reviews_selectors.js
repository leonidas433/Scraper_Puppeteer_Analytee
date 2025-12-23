import puppeteer from "puppeteer-extra";
import StealthPlugin from "puppeteer-extra-plugin-stealth";
import dotenv from "dotenv";

dotenv.config({ path: "./config/.env" });
puppeteer.use(StealthPlugin());

const PLACE_ID = "ChIJO4Ff4qa9pBIR1IdVPci5FCo";

(async () => {
  console.log("🧪 Iniciando verificación visual de selectores de reseñas...");

  const browser = await puppeteer.launch({
    headless: false, // Muestra Chrome para inspección visual
    executablePath: "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
  });

  const page = await browser.newPage();
  const url = `https://www.google.com/maps/place/?q=place_id:${PLACE_ID}`;
  console.log(`🌍 Cargando URL: ${url}`);
  await page.goto(url, { waitUntil: "domcontentloaded" });

  // Aceptar cookies si el banner aparece
  try {
    await page.waitForSelector('button[aria-label*="Aceptar todo"]', { timeout: 5000 });
    await page.click('button[aria-label*="Aceptar todo"]');
    console.log("🍪 Cookies aceptadas automáticamente.");
    await new Promise(resolve => setTimeout(resolve, 2000));
  } catch {
    console.log("✅ No se mostró banner de cookies.");
  }

  console.log("⌛ Esperando a que se cargue el panel de reseñas...");
  await new Promise(resolve => setTimeout(resolve, 6000));

  // Intentar abrir la pestaña de reseñas
  try {
    console.log("🧭 Buscando pestaña de reseñas...");
    // Busca un botón o enlace con texto 'Reseñas' o 'Reviews'
    const [reviewsTab] = await page.$x("//button[contains(., 'Reseñas')] | //button[contains(., 'Reviews')]");
    if (reviewsTab) {
      await reviewsTab.click();
      console.log("✅ Pestaña de reseñas abierta correctamente.");
      await new Promise(resolve => setTimeout(resolve, 4000));
    } else {
      console.log("⚠️ No se encontró pestaña de reseñas. Posible interfaz alternativa.");
    }
  } catch (error) {
    console.log("⚠️ Error al intentar abrir la pestaña de reseñas:", error.message);
  }

  // Selector actualizado
  const selector = 'div[jscontroller][data-review-id]';
  const reviews = await page.$$(selector);

  console.log(`📋 Reseñas detectadas con el nuevo selector: ${reviews.length}`);

  if (reviews.length > 0) {
    console.log("✅ Selector funcional. Se encontraron reseñas visibles en el DOM.");
  } else {
    console.log("⚠️ No se encontraron reseñas. Posible UI alternativa o delay de carga.");
  }

  console.log("🔎 Mantén la ventana abierta para inspeccionar manualmente los elementos.");
  console.log("Presiona Ctrl+C para cerrar cuando termines.");

  // No cierres automáticamente para poder inspeccionar el DOM
})();