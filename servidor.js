// Servidor HTTPS estático para probar la PWA en el celular (misma red WiFi).
const https = require('https'), fs = require('fs'), path = require('path');
const tipos = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.json': 'application/json', '.onnx': 'application/octet-stream', '.wasm': 'application/wasm' };
const opciones = { key: fs.readFileSync(path.join(__dirname, 'key.pem')), cert: fs.readFileSync(path.join(__dirname, 'cert.pem')) };

https.createServer(opciones, (req, res) => {
  const f = req.url.split('?')[0] === '/' ? '/index.html' : req.url.split('?')[0];
  const ruta = path.join(__dirname, path.normalize(f));
  if (!ruta.startsWith(__dirname) || ['key.pem', 'cert.pem'].includes(path.basename(ruta)) || !fs.existsSync(ruta)) { res.writeHead(404); return res.end('no'); }
  res.writeHead(200, { 'Content-Type': tipos[path.extname(ruta)] || 'application/octet-stream' });
  fs.createReadStream(ruta).pipe(res);
}).listen(8443, '0.0.0.0', () => console.log('Vigía en https://192.168.2.11:8443'));
