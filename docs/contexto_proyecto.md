# Vigía de aseo — contexto y prompt para otra IA

## Prompt (copiar y pegar)

Eres un diseñador de producto y arquitecto de software. Quiero que diseñes **"Vigía de aseo"**, una herramienta de visión por computador para un **conjunto residencial en Colombia (Bogotá)**. Usa el contexto de este documento. Si algo no está claro, pregunta antes de asumir; si no, propón y justifica.

**Lo que necesito de ti:** diseño funcional completo (pantallas, flujos, reglas, modelo de datos y arquitectura), con una primera versión realista (MVP) y una hoja de ruta.

---

## 1. Idea en una frase

Cámaras de vigilancia que **detectan movimiento y reconocen basura, heces de perro, derrames y piso sucio** en zonas comunes, y **generan una alerta o notificación** al administrador y al personal de aseo, para limpiar más rápido y, cuando corresponda, **dar soporte a un proceso de multas** con revisión humana.

## 2. Problema que resuelve

- Los dueños de perros no siempre recogen las heces en parques, pasillos y zonas verdes.
- Hay basura, derrames y suciedad que nadie reporta a tiempo.
- La administración no tiene evidencia ordenada ni tiempos de respuesta medibles.
- Las multas por incumplimiento del reglamento carecen de soporte objetivo.

## 3. Usuarios

| Rol | Qué necesita |
|---|---|
| Administrador | Ver alertas, asignar aseo, revisar evidencia, decidir sobre sanciones |
| Personal de aseo | Recibir aviso con foto y ubicación, marcar "atendida" |
| Consejo / comité | Reportes de zonas críticas, tiempos de respuesta, tendencias |
| Residentes | Información sobre cámaras y tratamiento de datos (aviso visible) |

## 4. Funcionalidad

### 4.1 Vista de cámara (en vivo)
- Imagen de la cámara con **detección de movimiento** (cajas sobre las zonas con cambio).
- **Detección de objetos** con cajas, clase y porcentaje de confianza (ej. `HECES 87%`).
- Sello de fecha y hora, nombre de la cámara (ej. "Parque infantil", "Portería", "Pasillo torre 2").
- Controles: pausar, mostrar/ocultar movimiento, mostrar/ocultar detecciones, sonido.

### 4.2 Qué detecta
| Clase | Descripción | Observación |
|---|---|---|
| `heces` | Excremento de perro | Requiere modelo entrenado con imágenes del conjunto |
| `basura` | Bolsas, envases, residuos | |
| `derrame` | Líquidos o manchas en el piso | Confianza más baja |
| `persona` | Para evitar falsas alertas y para privacidad | No se identifica a nadie |
| Señuelos | Hojas, sombras, charcos de lluvia | Deben descartarse |

### 4.3 Regla de alerta (persistencia)
Un objeto genera alerta solo si:
1. Su confianza supera el umbral configurado (ej. 50 %).
2. Lleva **quieto** más de N segundos (en pruebas 10 s; en producción 120 s o más, para no alertar mientras el dueño está recogiendo).
3. **No hay una persona cerca** (distancia configurable, ej. 5–50 % del encuadre).

Cuando el objeto desaparece por unos segundos, la alerta se **cierra** y se registra el tiempo de respuesta.

### 4.4 Alertas
- Notificación en el teléfono (push), vibración y sonido opcional.
- Foto de evidencia con **personas en mosaico** (pixelado).
- Estado: abierta → atendida / descartada (falso positivo).
- Acciones: **"Enviar aseo"** y **"Descartar"**.
- Historial filtrable por cámara, clase, fecha y estado.
- Exportación (JSONL/CSV) y envío por **webhook** (n8n, WhatsApp, correo).

### 4.5 Seguimiento del aseo
- Al pulsar "Enviar aseo" se registra quién, cuándo y cuánto tardó (`respuesta_s`).
- El sistema verifica el cierre cuando el objeto ya no aparece en la cámara.

### 4.6 Ajustes
Confianza mínima, persistencia, distancia de "persona cerca", cuadros por segundo analizados, nombre de la cámara, URL de webhook, enviar foto en el webhook, modo prueba (modelo general que detecta botella/vaso/mochila para validar el flujo sin modelo propio).

### 4.7 Reportes (fase 2)
Mapa de calor de zonas críticas, horarios con más incidentes, tiempo medio de respuesta, tasa de falsos positivos, reincidencias por zona.

## 5. Arquitectura propuesta

```
Cámara (IP/RTSP o celular)
   → Detector en el borde (YOLO / RF-DETR)
   → Tracker + regla de persistencia
   → Alerta (JSON) → App móvil / panel web / webhook
   → Almacenamiento corto de evidencia (con mosaico a personas)
```

- **Borde:** inferencia local (CPU/GPU/NPU) para no enviar video continuo a la nube.
- **Una sola estructura JSON** en todos los componentes (script Python, app Flutter, app Kotlin, simulador web).

```json
{
  "id": "A-1761750000000",
  "evento": "alerta",
  "camara": "Parque infantil",
  "clase": "heces",
  "hora": "2026-10-29T08:15:00",
  "persistio_s": 120,
  "respuesta_s": null,
  "confianza": 0.87,
  "caja": [0.41, 0.62, 0.47, 0.68],
  "imagen": "ruta/o/url.jpg"
}
```
Eventos: `alerta` y `cerrada` (con `respuesta_s`).

## 6. Lo que ya existe (para no repetir trabajo)

- Informe de investigación y mockup de la herramienta.
- Simulador web interactivo (`vigia-en-vivo.html`): cámara simulada con detección de movimiento, objetos, alertas y notificación al teléfono.
- Detector en Python (`detector_aseo.py`).
- App móvil en **Flutter** y en **Kotlin** (CameraX + TensorFlow Lite), sin compilar ni probar todavía.
- Video grabado del simulador.

## 7. Privacidad y legal (Colombia)

- **No hay reconocimiento facial.** Personas en mosaico en fotos guardadas y enviadas.
- Imágenes = datos personales: **Ley 1581 de 2012** (aviso visible, finalidad clara, conservación corta).
- **Ley 675 de 2001** (propiedad horizontal) y reglamento interno: la multa exige debido proceso.
- **Código de Policía (Ley 1801 de 2016)** como referencia sobre heces y espacio público.
- **Una alerta automática no es una multa:** siempre revisión humana antes de sancionar.

## 8. Restricciones y riesgos

- No existe un modelo público listo para heces; hay que entrenar con imágenes propias (ScatSpotter sirve de punto de partida).
- **Licencias:** Ultralytics YOLO es AGPL-3.0 (producto cerrado requiere licencia comercial); RF-DETR es Apache 2.0.
- Falsos positivos por hojas, sombras, charcos, luz nocturna y lluvia.
- Teléfono fijo: necesita energía continua y pantalla encendida; para varias cámaras IP, usar un servidor.

## 9. Qué quiero que entregues

1. **Flujos de usuario** (administrador, aseo) y mapa de pantallas.
2. **Reglas de negocio** completas (alertas, cierre, descarte, reincidencia, multas con revisión humana).
3. **Modelo de datos** y API (incluye webhook).
4. **Arquitectura** para 1 cámara (MVP) y para 10+ cámaras.
5. **Plan de entrenamiento y evaluación** del modelo (datos, métricas, umbrales).
6. **Plan de pruebas de campo** en el conjunto residencial.
7. **MVP en 4 semanas** y hoja de ruta posterior, con costos aproximados.

Responde en **español**, con tablas y diagramas simples, y marca claramente qué es supuesto.
