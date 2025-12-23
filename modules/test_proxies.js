// autos: Leox433
// Script para probar proxies desde config/Webshare_10_proxies.txt
// Uso: node test_proxies.js

import fs from 'fs';
import path from 'path';
import https from 'https';
import http from 'http';
import { fileURLToPath } from 'url';
import { dirname } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Función para leer proxies
function loadProxies() {
  const proxyFile = path.join(__dirname, '..', 'config', 'Webshare_10_proxies.txt');

  if (!fs.existsSync(proxyFile)) {
    console.error('❌ Archivo config/Webshare_10_proxies.txt no encontrado');
    process.exit(1);
  }

  const content = fs.readFileSync(proxyFile, 'utf-8');
  const lines = content.split('\n').filter((line) => line.trim());

  return lines.map((line) => {
    const [host, port, username, password] = line.trim().split(':');
    return { host, port, username, password };
  });
}

// Función para probar un proxy
function testProxy(proxy, index) {
  return new Promise((resolve) => {
    const startTime = Date.now();

    const options = {
      host: proxy.host,
      port: proxy.port,
      method: 'GET',
      path: 'https://api.ipify.org?format=json',
      headers: {
        'Proxy-Authorization':
          'Basic ' + Buffer.from(`${proxy.username}:${proxy.password}`).toString('base64'),
      },
    };

    const req = http.request(options, (res) => {
      let data = '';

      res.on('data', (chunk) => {
        data += chunk;
      });

      res.on('end', () => {
        const endTime = Date.now();
        const responseTime = endTime - startTime;

        try {
          const json = JSON.parse(data);
          resolve({
            index: index + 1,
            proxy: `${proxy.host}:${proxy.port}`,
            status: '✅ OK',
            ip: json.ip || 'N/A',
            responseTime: `${responseTime}ms`,
            error: null,
          });
        } catch (e) {
          resolve({
            index: index + 1,
            proxy: `${proxy.host}:${proxy.port}`,
            status: '❌ ERROR',
            ip: 'N/A',
            responseTime: `${responseTime}ms`,
            error: 'Respuesta inválida',
          });
        }
      });
    });

    req.on('error', (err) => {
      const endTime = Date.now();
      const responseTime = endTime - startTime;

      resolve({
        index: index + 1,
        proxy: `${proxy.host}:${proxy.port}`,
        status: '❌ ERROR',
        ip: 'N/A',
        responseTime: `${responseTime}ms`,
        error: err.message,
      });
    });

    req.setTimeout(10000, () => {
      req.destroy();
      resolve({
        index: index + 1,
        proxy: `${proxy.host}:${proxy.port}`,
        status: '⏱️ TIMEOUT',
        ip: 'N/A',
        responseTime: '10000ms+',
        error: 'Timeout después de 10s',
      });
    });

    req.end();
  });
}

// Función principal
async function main() {
  console.log('🔍 Probando proxies desde config/Webshare_10_proxies.txt\n');

  const proxies = loadProxies();
  console.log(`📋 Total de proxies a probar: ${proxies.length}\n`);

  const results = [];

  for (let i = 0; i < proxies.length; i++) {
    const proxy = proxies[i];
    console.log(`🔄 Probando proxy ${i + 1}/${proxies.length}: ${proxy.host}:${proxy.port}`);

    const result = await testProxy(proxy, i);
    results.push(result);

    console.log(`   ${result.status} | IP: ${result.ip} | Tiempo: ${result.responseTime}`);
    if (result.error) {
      console.log(`   ⚠️  Error: ${result.error}`);
    }
    console.log('');
  }

  // Resumen final
  console.log('\n' + '='.repeat(60));
  console.log('📊 RESUMEN DE RESULTADOS');
  console.log('='.repeat(60) + '\n');

  const working = results.filter((r) => r.status === '✅ OK').length;
  const errors = results.filter((r) => r.status === '❌ ERROR').length;
  const timeouts = results.filter((r) => r.status === '⏱️ TIMEOUT').length;

  console.log(`✅ Proxies funcionando: ${working}/${proxies.length}`);
  console.log(`❌ Proxies con error: ${errors}/${proxies.length}`);
  console.log(`⏱️  Proxies con timeout: ${timeouts}/${proxies.length}`);

  console.log('\n📋 Detalle de proxies funcionando:\n');
  results.forEach((r) => {
    if (r.status === '✅ OK') {
      console.log(`   ${r.index}. ${r.proxy} → IP: ${r.ip} (${r.responseTime})`);
    }
  });

  if (errors > 0 || timeouts > 0) {
    console.log('\n⚠️  Proxies con problemas:\n');
    results.forEach((r) => {
      if (r.status !== '✅ OK') {
        console.log(`   ${r.index}. ${r.proxy} → ${r.status} - ${r.error || 'N/A'}`);
      }
    });
  }

  console.log('\n' + '='.repeat(60));
}

main();
