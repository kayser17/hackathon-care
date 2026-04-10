# Documentacion Del Postproceso

## Objetivo

Este modulo es la ultima capa del pipeline y sirve para tomar una decision determinista a partir de tres fuentes de evidencia:

- metricas cuantitativas del chunk actual
- analisis historico y de tendencia
- probabilidades y contexto del LLM

La salida final responde a estas preguntas:

- que tipo de riesgo catalogamos: `bullying`, `grooming` o `distress`
- que gravedad tiene el caso en una escala `0-100`
- que decision operativa tomamos:
  - `discarded`
  - `follow_up`
  - `notify_guardian`


## Entradas

El modelo usa tres entradas principales:

### 1. `current_metrics`

Metricas del chunk actual:

- `toxicity`
- `insult_score`
- `manipulation_similarity`
- `targeting_intensity`
- `dominance_ratio`
- `emotion.anger`
- `emotion.sadness`
- `emotion.fear`
- `activity_anomaly`
- `distress_signal`
- `confidence`
- `risk_trend`

### 2. `historical_metrics`

Lista de chunks historicos de la misma conversacion. Para cada chunk se recalculan intensidades por tipo y se mide la evolucion temporal.

### 3. `llm_result`

Salida del LLM:

- `risk_types`
- `severity`
- `confidence`
- `key_evidence`
- `risk_detected`


## Flujo General

El flujo del modelo es:

1. calcular un `metric_score` para cada tipo
2. calcular un `llm_type_score` para cada tipo
3. calcular un `trend_type_score` para cada tipo
4. fusionar esos tres scores y elegir el tipo final
5. calcular intensidad actual y gravedad final
6. convertir la gravedad a:
   - `severity_score` de `0-100`
   - `severity_band`
   - `postprocess_decision`


## 1. Score Por Metricas

Funcion: `compute_type_scores(...)`

Estas formulas salen de ponderar las metricas del chunk actual. Cada tipo usa pesos distintos.

### Bullying

```text
metric_score_bullying =
  0.25 * toxicity +
  0.25 * insult_score +
  0.19 * targeting_intensity +
  0.12 * dominance_ratio +
  0.10 * anger +
  0.05 * activity_anomaly +
  0.04 * distress_signal
```

### Grooming

```text
metric_score_grooming =
  0.31 * manipulation_similarity +
  0.18 * targeting_intensity +
  0.16 * dominance_ratio +
  0.12 * fear +
  0.09 * activity_anomaly +
  0.08 * distress_signal +
  0.06 * confidence
```

### Distress

```text
metric_score_distress =
  0.30 * distress_signal +
  0.23 * sadness +
  0.16 * fear +
  0.12 * activity_anomaly +
  0.08 * anger +
  0.06 * toxicity +
  0.05 * insult_score
```

Despues se aplica:

```text
clamp(score, 0, 1)
```

Interpretacion:

- este score mide cuanto apuntan las metricas actuales a cada tipo
- no incluye ni LLM ni historico


## 2. Score Del LLM Por Tipo

Funcion: `compute_llm_type_scores(...)`

Mapeo:

- `cyberbullying -> bullying`
- `grooming -> grooming`
- `self_harm -> distress`

Formula:

```text
llm_type_score[type] = probabilidad del LLM para ese tipo
```

Interpretacion:

- este score incorpora el contexto semantico
- es importante porque el LLM es el unico que entiende la conversacion completa


## 3. Score De Tendencia Por Tipo

Funciones:

- `compute_historical_escalation(...)`
- `compute_trend_type_score(...)`

Primero se recalcula la intensidad historica para cada tipo usando los chunks previos.

### Variables historicas

```text
recent_mean = media de la ventana corta
baseline_mean = media de la ventana base
delta_vs_baseline = recent_mean - baseline_mean
sustained_ratio = porcentaje de chunks recientes con intensidad >= 0.75
consecutive_high = numero de chunks altos consecutivos al final
slope = pendiente de la ventana reciente
```

### Score De Escalada Historica

```text
historical_escalation_score =
  0.30 * recent_mean +
  0.22 * clamp(delta_vs_baseline + 0.5) +
  0.22 * sustained_ratio +
  0.16 * clamp(consecutive_high / 4.0) +
  0.10 * clamp((slope + 0.2) / 0.4)
```

### Ajuste Por Direccion Temporal

```text
trend_direction_bonus =
  +0.08 si risk_trend == increasing
   0.00 si risk_trend == stable
  -0.08 si risk_trend == decreasing
```

### Score Final De Tendencia Por Tipo

```text
trend_type_score =
  0.75 * historical_escalation_score +
  trend_direction_bonus
```

Interpretacion:

- si el caso empeora, este score sube
- si el caso baja, este score baja
- no decide solo, pero si sube o baja probabilidades


## 4. Score Final Del Tipo

Funcion: `compute_final_type_scores(...)`

Para cada tipo se fusionan las tres fuentes:

```text
final_type_score =
  0.45 * metric_score +
  0.35 * llm_type_score +
  0.20 * trend_type_score
```

Interpretacion:

- las metricas mandan ligeramente mas
- el LLM tiene mucho peso
- la tendencia ajusta

El tipo final es el que tenga mayor `final_type_score`.

### Umbral minimo para catalogar

```text
TYPE_CLASSIFICATION_THRESHOLD = 0.42
```

Si el mejor tipo no supera `0.42`, el caso se descarta y no se clasifica.


## 5. Intensidad Actual

Funcion: `compute_current_intensity(...)`

Se calcula asi:

```text
current_intensity =
  metric_score_del_tipo +
  trend_adjustment
```

Donde:

- `increasing -> +0.06`
- `stable -> 0.00`
- `decreasing -> -0.06`

Interpretacion:

- mide la fuerza actual del caso en el chunk presente
- no es la gravedad final


## 6. Soporte Del LLM Para La Gravedad

Funcion: `compute_llm_support_score(...)`

Formula:

```text
llm_support_score =
  0.62 * selected_type_probability +
  0.17 * llm_confidence +
  agreement_bonus +
  evidence_bonus +
  severity_bonus +
  detected_bonus
```

### Componentes

`selected_type_probability`

- probabilidad del LLM para el tipo final elegido

`agreement_bonus`

- `+0.10` si el tipo dominante del LLM coincide con el tipo final
- `-0.08` si contradice

`evidence_bonus`

```text
min(len(key_evidence) / 5.0, 0.10)
```

`severity_bonus`

- `low -> 0.00`
- `medium -> 0.04`
- `high -> 0.08`

`detected_bonus`

- `+0.03` si `risk_detected == true`

Interpretacion:

- este score no elige el tipo
- sirve para apoyar o enfriar la gravedad final


## 7. Gravedad Final

Funcion: `compute_final_alert_score(...)`

Primero:

```text
combined_confidence =
  0.55 * llm_confidence +
  0.45 * preprocessing_confidence
```

Despues:

```text
final_score =
  0.45 * current_intensity +
  0.20 * historical_escalation_score +
  0.25 * llm_support_score +
  0.10 * combined_confidence
```

Luego:

```text
severity_score = round(final_score * 100)
```

Interpretacion:

- esta es la nota final de peligro
- es la mezcla de presente, historico, LLM y confianza


## 8. Banda De Gravedad

Funcion: `_severity_band_from_score(...)`

Reglas:

```text
< 0.45   -> none
0.45-0.69 -> medium
0.70-0.89 -> high
>= 0.90 -> critical
```

En porcentaje:

```text
0-44   -> none
45-69  -> medium
70-89  -> high
90-100 -> critical
```


## 9. Decision Operativa

Funcion: `_decision_level_from_score(...)`

Reglas:

```text
< 0.45   -> discarded
0.45-0.69 -> follow_up
>= 0.70 -> notify_guardian
```

En porcentaje:

```text
0-44   -> discarded
45-69  -> follow_up
70-100 -> notify_guardian
```

Interpretacion:

- la gravedad se usa para decidir que hacer
- el corte de aviso a padres esta a partir de `70`


## 10. Reglas Especificas Por Tipo

En `decide_alert_level(...)` hay reglas de negocio adicionales.

### Grooming

Si la intensidad actual es muy alta y el soporte es fuerte, el caso escala con mas facilidad.

### Distress

La tendencia historica pesa mucho mas para decidir si basta con seguimiento o si se acerca a un caso serio.

### Bullying

La repeticion y los patrones sostenidos elevan la probabilidad de escalar.


## 11. Cooldown De Padres

Si ya hay una alerta reciente del mismo tipo, se evita repetir la notificacion al guardian dentro del cooldown salvo que el caso sea critico.

Valor actual:

```text
PARENT_NOTIFICATION_COOLDOWN_HOURS = 12
```


## 12. Salida JSON

La salida esta pensada para serializarse facilmente a JSON.

Ejemplo:

```json
{
  "validated_risk": true,
  "risk_type": "grooming",
  "severity_score": 85,
  "severity_band": "high",
  "postprocess_decision": "notify_guardian",
  "notify_guardian": true,
  "notify_counselor": true,
  "create_new_alert": true,
  "update_existing_alert": false,
  "trend_status": "isolated_spike",
  "score_breakdown": {
    "metric_type_score": 0.8354,
    "llm_type_score": 0.94,
    "trend_type_score": 0.4717,
    "final_type_score": 0.7993,
    "current_intensity": 0.8954,
    "historical_escalation_score": 0.5222,
    "llm_support_score": 1.0,
    "llm_confidence": 0.93,
    "preprocessing_confidence": 0.87,
    "combined_confidence": 0.903,
    "final_score": 0.8477,
    "recent_mean": 0.5284,
    "baseline_mean": 0.3448,
    "delta_vs_baseline": 0.1835,
    "sustained_ratio": 0.3333,
    "consecutive_high": 1,
    "slope": 0.2835
  }
}
```

Los payloads derivados tambien usan la misma semantica:

```json
{
  "risk_assessment_payload": {
    "chunk_id": "chunk-123",
    "risk_type": "grooming",
    "severity_band": "high",
    "severity_score": 85,
    "confidence_score": 0.903,
    "rationale": "...",
    "model_name": "postprocess-v1"
  },
  "alert_payload": {
    "child_user_id": "child-1",
    "conversation_id": "conv-1",
    "chunk_id": "chunk-123",
    "alert_type": "grooming",
    "severity_band": "high",
    "title": "Grooming risk high",
    "summary": "...",
    "status": "open"
  }
}
```


## 13. Estado Actual: Funciona O No

Ahora mismo si funciona en estos sentidos:

- el modulo ejecuta bien
- el flujo es consistente con el diseno
- la salida es JSON friendly
- el sistema mezcla metricas, historico y LLM de forma determinista

### Verificacion actual

Se ha ejecutado:

```text
python test_postproceso.py
```

Resultado:

- pasan `31 tests`

Los tests cubren:

- acuerdo entre metricas y LLM
- desacuerdo entre metricas y LLM
- casos debiles descartados
- casos cercanos donde el LLM empuja la catalogacion
- casos donde las metricas corrigen al LLM
- subida y bajada de tendencia
- grooming fuerte
- distress con historial
- bullying sostenido
- cooldown de notificacion a padres
- alertas ya existentes
- fronteras entre `follow_up` y `notify_guardian`
- casos con tendencia decreciente
- casos ambiguos donde el LLM gana
- casos donde las metricas corrigen un LLM moderado


## 14. Estructura Esperada De Entrada

La funcion principal espera:

```text
child_user_id: str
conversation_id: str
chunk_id: str
llm_result: LLMResult
current_metrics: PreprocessingMetrics
historical_metrics: list[HistoricalChunkMetrics]
existing_open_alerts: list[dict] | None
```

### Ejemplo De `llm_result`

```json
{
  "risk_detected": true,
  "risk_types": {
    "cyberbullying": 0.72,
    "grooming": 0.18,
    "self_harm": 0.10
  },
  "severity": "high",
  "confidence": 0.91,
  "key_evidence": ["...", "..."],
  "reasoning": "...",
  "conversation_summary": "..."
}
```

### Ejemplo De `current_metrics`

```json
{
  "toxicity": 0.81,
  "insult_score": 0.77,
  "emotion": {
    "anger": 0.69,
    "sadness": 0.22,
    "fear": 0.14
  },
  "manipulation_similarity": 0.18,
  "targeting_intensity": 0.84,
  "dominance_ratio": 0.73,
  "risk_trend": "increasing",
  "activity_anomaly": 0.41,
  "distress_signal": 0.35,
  "confidence": 0.86
}
```

### Ejemplo De `historical_metrics`

```json
[
  {
    "chunk_id": "chunk-1",
    "conversation_id": "conv-123",
    "created_at": "2026-04-10T10:00:00+00:00",
    "toxicity": 0.44,
    "insult_score": 0.40,
    "manipulation_similarity": 0.12,
    "targeting_intensity": 0.39,
    "dominance_ratio": 0.31,
    "activity_anomaly": 0.20,
    "distress_signal": 0.18,
    "confidence": 0.71,
    "risk_trend": "stable",
    "emotion_anger": 0.32,
    "emotion_sadness": 0.15,
    "emotion_fear": 0.11
  }
]
```

## 15. Que Significa "Funciona"

Significa que:

- la implementacion corre
- produce un tipo final y una nota de gravedad razonables
- la logica es trazable
- las formulas se pueden auditar

No significa todavia que:

- los pesos sean los definitivos
- los thresholds esten calibrados con datos reales de produccion
- la sensibilidad sea perfecta para todos los casos


## 16. Riesgos Y Ajustes Futuros

Lo mas probable a futuro es ajustar:

- pesos entre metricas y LLM
- umbral de catalogacion `0.42`
- umbral de notificacion a padres `70`
- reglas especificas de `distress`

La arquitectura ya esta bien para hacer esa calibracion sin rehacer el sistema.


## 17. Resumen Final

El modelo actual:

- usa tus ponderaciones de metricas para generar probabilidades por tipo
- usa el LLM para aportar contexto semantico real
- usa el historico para subir o bajar probabilidades
- elige el tipo final con una fusion simple y trazable
- calcula una gravedad `0-100`
- toma una decision operativa simple

La idea central es:

```text
catalogacion_final = metricas + llm + tendencia
gravedad_final = intensidad_actual + historico + soporte_llm + confianza
```

Con eso el postproceso deja de ser una capa arbitraria y pasa a ser una capa determinista, auditable y facil de explicar.
