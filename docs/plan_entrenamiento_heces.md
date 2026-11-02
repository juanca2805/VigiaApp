# Plan de entrenamiento — modelo de heces (Vigía de aseo)

> Lo marcado **[SUPUESTO]** hay que verificarlo antes de depender de ello.

## 1. Objetivo y criterio de éxito

Detectar `heces` (y luego `basura`, `derrame`) en cámaras fijas del conjunto, con pocas falsas alarmas.

| Métrica | Meta MVP | Por qué |
|---|---|---|
| Recall de heces (objeto visible ≥ 2 min) | ≥ 80 % | Se persigue el objeto en el tiempo, no el cuadro suelto |
| Falsos positivos por cámara y día (tras regla de persistencia) | ≤ 2 | Más que eso y el personal de aseo deja de confiar |
| Precisión a umbral de producción | ≥ 70 % | Siempre hay revisión humana antes de multar |
| Latencia en celular | ≤ 300 ms/cuadro | 3 fps basta para objetos quietos |

La métrica clave no es mAP sino **recall por evento y falsos positivos por cámara-día**, medidos en video real del conjunto.

## 2. Elección de modelo y licencia

| Opción | Licencia | Exporta a | Comentario |
|---|---|---|---|
| **RF-DETR (Nano/Small)** | Apache 2.0 | ONNX | Recomendada: sin problema comercial |
| YOLOv8/11 (Ultralytics) | AGPL-3.0 | TFLite, TF.js, ONNX | Más fácil de exportar, pero un producto cerrado exige licencia comercial |
| YOLOX | Apache 2.0 | ONNX, TFLite | Alternativa libre y madura |

**Recomendación:** prototipar rápido con YOLO (solo para validar datos y flujo), y la versión de producción con RF-DETR o YOLOX. **[SUPUESTO]** La licencia de cada repositorio y de los pesos preentrenados debe revisarse el día que se clone.

## 3. Datos

### 3.1 Fuentes
1. **ScatSpotter** (dataset público de heces de perro en exteriores): punto de partida, miles de imágenes **[SUPUESTO: cantidad y licencia exactas por verificar en su página]**.
2. **Imágenes propias del conjunto** (lo más valioso): las cámaras reales, sus ángulos, su luz y su pasto. El dataset público solo da la base.
3. **Negativos difíciles** (obligatorio): hojas secas, sombras, barro, piedras, tierra, charcos, colillas, bolsas oscuras, mascotas sin heces.

### 3.2 Recolección propia (semanas 1–2)
- Grabar clips de cada cámara en mañana, mediodía, tarde, noche y lluvia.
- **Escenificar** heces falsas (plastilina marrón, o heces reales con permiso y guantes) en distintos puntos, distancias y luz. Meta: 300–500 imágenes positivas propias.
- Guardar también 1 000+ fotos **sin heces** de las mismas cámaras (negativos de fondo).
- Muestrear 1 cuadro cada 2–5 s para evitar miles de imágenes casi idénticas.
- Privacidad: avisar a la administración, no grabar rostros innecesariamente, y pixelar personas antes de subir datos a cualquier servicio externo (Ley 1581).

### 3.3 Etiquetado
- Herramienta: Roboflow, CVAT o Label Studio.
- Clases iniciales: `heces`, `basura`, `derrame`. Empezar solo con `heces` mejora la calidad.
- Una caja ajustada por objeto; reglas escritas de qué cuenta (heces parcialmente tapadas por pasto sí, manchas secas viejas no).
- Revisión cruzada del 10 % por una segunda persona.
- **[SUPUESTO]** 1 minuto por imagen → 1 500 imágenes ≈ 25 horas. Usar un modelo preentrenado para pre-etiquetar y solo corregir acelera esto.

### 3.4 División (el error más común)
- **No partir al azar** cuadro por cuadro: cuadros vecinos casi iguales caen en entrenamiento y prueba y inflan la métrica.
- Dividir **por cámara y por día**: p. ej. entrenar con 3 cámaras, validar con otra, y probar con una semana nueva.
- Proporción: 70 % entrenamiento, 15 % validación, 15 % prueba (esta última se toca una sola vez).

## 4. Entrenamiento

1. **Entorno:** Google Colab (GPU T4 gratuita) o una GPU propia. **[SUPUESTO]** ~1–3 horas por corrida con ~3 000 imágenes.
2. **Base:** pesos preentrenados en COCO, afinar (fine-tuning) con ScatSpotter, y luego con datos propios.
3. **Resolución:** 640 px; probar 960 px si las heces se ven pequeñas (cámaras lejanas).
4. **Aumentos:** brillo/contraste, ruido, desenfoque, rotación leve, recorte, volteo horizontal, simulación de lluvia/niebla. Evitar cambios de tono fuertes (el color café es una pista).
5. **Mezcla de datos:** 20–30 % de negativos difíciles para reducir falsos positivos.
6. **Iteración:** entrenar → correr sobre video propio → recopilar falsos positivos → etiquetarlos como negativos → reentrenar. Dos o tres rondas suelen bastar.

## 5. Evaluación

| Nivel | Qué se mide |
|---|---|
| Por imagen | Precisión/recall y curva PR en el conjunto de prueba |
| Por evento (la que importa) | ¿Se alertó sobre cada objeto real que estuvo ≥ N segundos? ¿Cuántas alertas sin objeto real? |
| Por cámara | Falsos positivos/día y causas (sombras, hojas, charcos) |
| Por franja | Día, noche, lluvia |

**Umbral de confianza:** elegirlo en validación como el punto con precisión ≥ 70 % y el mayor recall posible; guardar un umbral distinto por cámara si hace falta. Combinarlo con persistencia (10 s en pruebas, 120 s o más en producción) filtra casi todo el ruido de un cuadro.

## 6. Exportación e integración con la app

| Destino | Ruta |
|---|---|
| PWA actual (navegador) | Modelo → **ONNX** → `onnxruntime-web` (reemplaza COCO-SSD en `app.js`; las reglas de persistencia, persona cerca y alertas no cambian) |
| Android nativo | ONNX o TFLite con cuantización a INT8 para ganar velocidad |
| Varias cámaras IP | Servidor local con GPU/CPU y el mismo modelo ONNX |

Cambios en `app.js`: sustituir `modelo.detect(...)` por la inferencia ONNX y mapear la clase `heces` en `CLASES`. El resto del código se mantiene.

## 7. Cronograma (4 semanas)

| Semana | Entregable |
|---|---|
| 1 | Verificar licencias, descargar ScatSpotter, montar entorno de entrenamiento, grabar clips de las cámaras |
| 2 | Etiquetar datos propios + negativos difíciles; primer entrenamiento (línea base) |
| 3 | Rondas de reentrenamiento con falsos positivos; elegir umbral; exportar a ONNX y probar en el celular |
| 4 | Prueba de campo 5–7 días con revisión humana; informe de recall, falsos positivos por cámara y ajuste de umbrales |

## 8. Riesgos principales

| Riesgo | Mitigación |
|---|---|
| Pocas heces reales en las cámaras | Datos escenificados + ScatSpotter |
| Falsos positivos por sombras, hojas, charcos | Negativos difíciles y persistencia larga |
| Visión nocturna / infrarrojo | Recolectar datos nocturnos aparte; posible modelo por modo |
| Heces pequeñas o lejanas | Mayor resolución, recorte por zonas, cámaras más cerca |
| Licencia AGPL | Usar RF-DETR o YOLOX en producción |
| Privacidad | Mosaico a personas, retención corta, aviso visible |

## 9. Costos aproximados **[SUPUESTO]**

| Concepto | Estimado |
|---|---|
| Colab Pro o GPU en la nube | 0–50 USD |
| Etiquetado (horas propias o apoyo) | 25–40 h |
| Herramienta de etiquetado | 0 (CVAT/Label Studio) a ~50 USD (plan de pago) |

## 10. Decisiones pendientes

1. ¿Cuántas cámaras y de qué tipo (IP, celular)? Define la resolución y el hardware.
2. ¿Se pueden escenificar heces (falsas o reales) para recolectar datos?
3. ¿Producto interno del conjunto o comercial? Define la licencia (YOLO frente a RF-DETR/YOLOX).
