// ============================================================================
// db_integration.js - Integración con base de datos
// Importar y usar estas funciones en analysis_runner.js
// ============================================================================

import { spawn } from 'child_process';
import chalk from 'chalk';
import fs from 'fs';
import path from 'path';

/**
 * Guardar análisis en base de datos
 */
export async function saveAnalysisToDatabase(csvPath, clientName, csvDir) {
  return new Promise((resolve) => {
    try {
      const analysisJsonPath = path.join(csvDir, clientName + '_analysis.json');
      
      if (!fs.existsSync(analysisJsonPath)) {
        console.log(chalk.yellow('⚠️  Archivo de análisis JSON no encontrado'));
        resolve(false);
        return;
      }
      
      const analysisResults = JSON.parse(fs.readFileSync(analysisJsonPath, 'utf-8'));
      
      const payload = JSON.stringify({
        results: analysisResults,
        csv_path: csvPath,
        csv_row_count: analysisResults.csv_row_count || 0,
        execution_time: 0
      });
      
      console.log(chalk.cyan('💾 Guardando análisis en base de datos...'));
      
      const python = spawn('python', [
        'analisis/save_to_db.py',
        clientName,
        payload
      ], {
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8'
      });
      
      let output = '';
      let errorOutput = '';
      
      python.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      python.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });
      
      python.on('close', (code) => {
        if (code === 0 && output) {
          try {
            const result = JSON.parse(output);
            if (result.status === 'success') {
              console.log(chalk.green('✅ Análisis guardado en BD (ID: ' + result.analysis_id + ')'));
            } else {
              console.log(chalk.yellow('⚠️  ' + result.message));
            }
          } catch (e) {
            console.log(chalk.yellow('⚠️  No se pudo parsear respuesta de BD'));
          }
        } else if (code !== 0) {
          console.log(chalk.yellow('⚠️  No se guardó en BD: ' + (errorOutput || 'Error desconocido')));
        }
        resolve(true);
      });
    } catch (error) {
      console.log(chalk.yellow('⚠️  Error guardando en BD: ' + error.message));
      resolve(true);
    }
  });
}

/**
 * Generar comparación automática
 */
export async function generateComparison(clientName) {
  return new Promise((resolve) => {
    try {
      console.log(chalk.cyan('📊 Generando comparación con análisis anterior...'));
      
      const python = spawn('python', [
        'analisis/generate_comparison.py',
        clientName
      ], {
        stdio: ['pipe', 'pipe', 'pipe'],
        encoding: 'utf-8'
      });
      
      let output = '';
      let errorOutput = '';
      
      python.stdout.on('data', (data) => {
        output += data.toString();
      });
      
      python.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });
      
      python.on('close', (code) => {
        if (code === 0 && output) {
          try {
            const result = JSON.parse(output);
            if (result.status === 'success' && result.has_comparison) {
              console.log(chalk.green('✅ Comparación generada:'));
              const ratingStr = result.rating_change >= 0 ? '+' : '';
              const satStr = result.satisfaction_improvement >= 0 ? '+' : '';
              console.log(chalk.cyan('   📈 Rating: ' + ratingStr + result.rating_change.toFixed(1)));
              console.log(chalk.cyan('   ⚠️  Riesgo: ' + result.risk_change));
              console.log(chalk.cyan('   😊 Satisfacción: ' + satStr + result.satisfaction_improvement.toFixed(1) + '%'));
            } else if (result.status === 'no_comparison') {
              console.log(chalk.cyan('ℹ️  ' + result.message));
            }
          } catch (e) {
            console.log(chalk.yellow('⚠️  No se pudo parsear comparación'));
          }
        } else if (code !== 0) {
          console.log(chalk.yellow('⚠️  Error generando comparación: ' + (errorOutput || 'Error desconocido')));
        }
        resolve(true);
      });
    } catch (error) {
      console.log(chalk.yellow('⚠️  Error en comparación: ' + error.message));
      resolve(true);
    }
  });
}
