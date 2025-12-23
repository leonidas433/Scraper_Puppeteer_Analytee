#!/usr/bin/env node
/**
 * Scraper Final - v3.4 (Análisis Integrado)
 * Todos los scripts unificados en /modules/
 * Compatible con Node.js >=20
 */
import { execSync, spawn } from "child_process";
import inquirer from "inquirer";
import fs from "fs";
import dotenv from "dotenv";

dotenv.config({ path: "./config/.env" });

// --- CONFIGURACIÓN ---
const MODULES = {
  metadata: "./modules/scrape_metadata.js",
  reviews: "./modules/mass_scraper_main.js",
  proxies: "./modules/test_proxies.js",
  quickAnalysis: "./modules/quick_analysis.py",
};

const ANALYTICS = {
  full: "python main.py --all",
  nlp: "python main.py --nlp",
  predictive: "python main.py --predictive",
  clustering: "python main.py --clustering",
  correlation: "python main.py --correlation",
  kpis: "python main.py --kpis",
  etl: "python main.py --etl",
};

// --- FUNCIONES AUXILIARES ---
function runScript(script, args = [], isPython = false) {
  return new Promise((resolve) => {
    try {
      if (isPython) {
        const command = `python ${script} ${args.join(" ")}`;
        console.log(`\n🚀 Ejecutando: ${command}\n`);
        const child = spawn("python", [script, ...args], { 
          stdio: "inherit",
          shell: true
        });
        child.on("close", (code) => {
          if (code !== 0) {
            console.error(`❌ Proceso terminó con código: ${code}`);
          }
          resolve();
        });
        child.on("error", (err) => {
          console.error(`❌ Error al ejecutar:`, err.message);
          resolve();
        });
      } else {
        const command = `node ${script} ${args.join(" ")}`;
        console.log(`\n🚀 Ejecutando: ${command}\n`);
        execSync(command, { stdio: "inherit" });
        resolve();
      }
    } catch (err) {
      console.error(`❌ Error al ejecutar:`, err.message);
      resolve();
    }
  });
}

function installDependencies() {
  console.log("📦 Instalando dependencias necesarias...\n");
  execSync("npm install", { stdio: "inherit" });
  console.log("\n✅ Instalación completada.\n");
}



// --- MENÚ DE ANALYTICS (Legacy) ---
async function analyticsMenu() {
  console.clear();
  console.log("=== Analytics - Análisis Avanzados ===\n");

  const { analyticsOption } = await inquirer.prompt([
    {
      type: "list",
      name: "analyticsOption",
      message: "Selecciona un análisis:",
      choices: [
        { name: "1) Análisis Completo (Full Pipeline)", value: "full" },
        { name: "2) Análisis NLP Avanzado", value: "nlp" },
        { name: "3) Análisis Predictivo", value: "predictive" },
        { name: "4) Clustering de Datos", value: "clustering" },
        { name: "5) Análisis de Correlación", value: "correlation" },
        { name: "6) Cálculo de KPIs", value: "kpis" },
        { name: "7) Pipeline ETL", value: "etl" },
        new inquirer.Separator(),
        { name: "0) Volver al menú principal", value: "back" },
      ],
    },
  ]);

  if (analyticsOption === "back") return;

  await runScript(ANALYTICS[analyticsOption], [], true);
}

// --- MENÚ PRINCIPAL ---
async function mainMenu() {
  console.clear();
  console.log("╔════════════════════════════════════════════════════════════════╗");
  console.log("║     Scraper Final - v3.4 (Scraping + Análisis Integrado)      ║");
  console.log("╚════════════════════════════════════════════════════════════════╝\n");

  const { option } = await inquirer.prompt([
    {
      type: "list",
      name: "option",
      message: "Selecciona una opción:",
      choices: [
        new inquirer.Separator("--- SCRAPING ---"),
        { name: "1) Scrape metadata", value: "metadata" },
        { name: "2) Scrape reviews (Mass Scraper)", value: "reviews" },
        { name: "3) Test proxies", value: "proxies" },
        new inquirer.Separator("--- ANÁLISIS ---"),
        { name: "4) Análisis Simple → DOCX", value: "analysis" }, // ✅ NUEVO
        { name: "5) Analytics Avanzados (Legacy)", value: "analytics" },
        new inquirer.Separator("--- MANTENIMIENTO ---"),
        { name: "6) Instalar dependencias", value: "install" },
        { name: "0) Salir", value: "exit" },
      ],
    },
  ]);

  switch (option) {
    case "metadata": {
      const { metaPlaceId } = await inquirer.prompt([
        {
          type: "input",
          name: "metaPlaceId",
          message: "Place ID:",
          validate: (input) => (input.trim() ? true : "Debes ingresar un Place ID."),
        },
      ]);
      await runScript(MODULES.metadata, [metaPlaceId]);
      break;
    }

    case "reviews": {
      const { placeId, maxReviews } = await inquirer.prompt([
        {
          type: "input",
          name: "placeId",
          message: "Place ID:",
          validate: (input) => (input.trim() ? true : "Debes ingresar un Place ID."),
        },
        {
          type: "input",
          name: "maxReviews",
          message: "maxReviews (Enter para usar valor por defecto):",
        },
      ]);

      const args = [`--place-id=${placeId}`];
      if (maxReviews) args.push(`--max-reviews=${maxReviews}`);
      await runScript(MODULES.reviews, args);
      break;
    }

    case "proxies":
      await runScript(MODULES.proxies);
      break;

    case "analysis":
      await runScript(MODULES.quickAnalysis, [], true);
      break;

    case "analytics":
      await analyticsMenu();
      break;

    case "install":
      installDependencies();
      break;

    case "exit":
      console.log("\n👋 Saliendo del Scraper Final...\n");
      process.exit(0);
  }

  await inquirer.prompt([{ type: "input", name: "cont", message: "Presiona Enter para continuar..." }]);
  await mainMenu();
}

// --- INICIO ---
(async () => {
  if (!fs.existsSync("./config/.env")) {
    console.error("❌ No se encontró el archivo ./config/.env");
    process.exit(1);
  }
  await mainMenu();
})();
