# Despliegue

## Local (para probar en el celular)

La cámara del navegador solo funciona con **HTTPS** (o `localhost`), por eso `servidor.js` usa un certificado
autofirmado.

```bash
cd vigia-app
openssl req -x509 -newkey rsa:2048 -nodes -keyout key.pem -out cert.pem -days 365 -subj "/CN=vigia"
node servidor.js
```

1. Celular y PC en la misma WiFi. Abre `https://<IP-de-tu-PC>:8443` (el mensaje de `servidor.js` muestra una IP fija; cámbiala por la tuya).
2. El navegador avisa que el certificado no es de confianza: acepta continuar.
3. Si no conecta, Windows probablemente bloquea el puerto 8443. Permítelo en el Firewall (regla de entrada TCP 8443).
4. `key.pem` y `cert.pem` están en `.gitignore`: **no los subas**.

## Google Cloud Run

Servicio `vigia-aseo`, región `us-east1`. Cloud Run da HTTPS válido, así que no hace falta certificado propio.

```bash
cd vigia-app
gcloud run deploy vigia-aseo --source . --region us-east1 --allow-unauthenticated
```

Qué hace cada pieza:

- `Dockerfile`: imagen nginx que copia solo `index.html`, `app.js`, `detector.js`, `manifest.json` y `modelo/`.
- `nginx.conf`: escucha en el puerto 8080, revalida siempre `modelo/` y la página (`no-cache`), y limita la cámara a la propia página.
- `.gcloudignore`: excluye `datos/`, `entrenamiento/`, `docs/` y los secretos, para no subir gigas a Cloud Build.

### Detalles que costaron

- **Límite de 32 MiB:** Cloud Run falla (error 500) con respuestas HTTP/1 con `Content-Length` mayores a 32 MiB, y el
  `.onnx` pesa ~120 MB. Se resuelve con `gzip on` en nginx, que responde por trozos (chunked). Los navegadores
  descomprimen solos.
- **Tipos MIME:** el bloque `types { ... }` de nginx reemplaza la tabla completa; por eso se incluye `mime.types`
  y se añade `onnx` aparte.
- **Modelo nuevo:** copia `modelo.json` y el `.onnx` a `modelo/`, vuelve a ejecutar el comando de arriba y
  verifica con `curl --compressed` que lo servido sea idéntico al archivo local.

El `.onnx` no está en git; hay que tenerlo en `modelo/` antes de desplegar (ver [README](../README.md#el-modelo-no-está-en-git)).
