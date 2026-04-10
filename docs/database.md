# 🧠 Database Design Overview

## 📌 Visión general del modelo

La base de datos está organizada en 5 capas lógicas:

### 1. Identidad y relaciones
- `users`
- `child_guardian_links`

### 2. Estructura de conversación
- `conversations`
- `conversation_participants`

### 3. Procesamiento por ventanas temporales
- `conversation_chunks`
- `chunk_metrics`
- `chunk_summaries`

### 4. Decisión de riesgo
- `risk_assessments`

### 5. Escalado e intervención humana
- `alerts`
- `alert_recipients`
- `alert_actions`

### 6. Configuración
- `monitoring_configs`

---

## 🔄 Flujo conceptual del sistema
flujo de mensajes en memoria
→ se agrupa por chunk temporal
→ se extraen métricas
→ se genera resumen
→ se evalúa riesgo
→ si hace falta, se crea alerta
→ una persona la recibe y actúa

---

# 🧩 Tablas del sistema

---

## 1. `users`

### Qué es
La tabla base de identidad del sistema.

### Qué representa
Cualquier actor del sistema:
- menor
- tutor/guardian
- counselor
- admin

### Por qué existe
Todo cuelga de usuarios:
- participantes en conversaciones
- relaciones entre usuarios
- destinatarios de alertas
- acciones sobre alertas

### Cómo usarla
- resolver roles
- mostrar UI según rol
- identificar actores en alertas

### Regla mental
**`users` no es solo auth. Es la entidad central del sistema.**

---

## 2. `child_guardian_links`

### Qué es
Relación entre menores y adultos responsables.

### Qué representa
Qué guardianes están asociados a qué menores.

### Por qué existe
El sistema necesita saber:
- quién recibe alertas
- quién supervisa a quién

### Cómo usarla
- resolver destinatarios de alertas
- dashboards por guardian

### Regla mental
**Determina quién recibe las alertas de un menor.**

---

## 3. `conversations`

### Qué es
Entidad que representa una conversación.

### Qué representa
Un hilo de comunicación entre usuarios.

### Por qué existe
Aunque no guardamos mensajes:
- necesitamos contexto
- agrupar análisis
- relacionar alertas

### Cómo usarla
- asociar chunks
- identificar contexto de riesgo

### Regla mental
**Contenedor lógico, no almacena contenido.**

---

## 4. `conversation_participants`

### Qué es
Relación entre usuarios y conversaciones.

### Qué representa
Quién participa en cada conversación.

### Por qué existe
Relación N:M entre usuarios y conversaciones.

### Cómo usarla
- listar participantes
- detectar menor en conversación
- lógica de permisos

### Regla mental
**Fuente de verdad de quién está en la conversación.**

---

## 5. `conversation_chunks`

### Qué es
Unidad temporal de análisis.

### Qué representa
Bloques de conversación:
- por tiempo
- por actividad
- por volumen

### Por qué existe
Permite:
- análisis incremental
- evitar procesar todo el historial
- no guardar mensajes

### Cómo usarla
- base del pipeline analítico
- referencia para métricas y resúmenes

### Regla mental
**Es la pieza central del sistema.**

---

## 6. `chunk_metrics`

### Qué es
Features derivadas del preprocesado.

### Qué representa
Señales numéricas:
- toxicidad
- insult score
- distress
- dominance
- emociones
- etc.

### Por qué existe
Permite:
- análisis estructurado
- reglas rápidas
- dashboards
- explicabilidad

### Cómo usarla
- scoring
- visualización
- auditoría

### Regla mental
**Guarda señales, no decisiones.**

---

## 7. `chunk_summaries`

### Qué es
Resumen generado por LLM.

### Qué representa
Contexto condensado del chunk.

### Por qué existe
- evita mostrar chat crudo
- mejora privacidad
- facilita comprensión

### Cómo usarla
- contexto en alertas
- revisión de casos
- input para risk_assessment

### Regla mental
**No es transcripción, es resumen.**

---

## 8. `risk_assessments`

### Qué es
Evaluación estructurada de riesgo.

### Qué representa
Conclusión del sistema:
- tipo de riesgo
- nivel
- severidad
- confianza

### Por qué existe
Transforma señales en decisiones interpretables.

### Cómo usarla
- decidir alertas
- priorizar casos
- filtrar dashboards

### Regla mental
chunk_metrics = señales
chunk_summaries = contexto
risk_assessments = decisión

---

## 9. `alerts`

### Qué es
Entidad de escalado.

### Qué representa
Eventos que requieren intervención humana.

### Por qué existe
No todo riesgo genera acción.

### Cómo usarla
- dashboards
- notificaciones
- gestión de estado

### Regla mental
**Solo contiene riesgo relevante.**

---

## 10. `alert_recipients`

### Qué es
Destinatarios de una alerta.

### Qué representa
Quién recibe la alerta:
- guardian
- counselor
- admin

### Por qué existe
Una alerta puede tener múltiples receptores.

### Cómo usarla
- notificaciones
- control de acceso
- tracking de visualización

### Regla mental
**Define quién recibe el evento.**

---

## 11. `alert_actions`

### Qué es
Trazabilidad de intervención humana.

### Qué representa
Acciones sobre una alerta:
- viewed
- acknowledged
- escalated
- dismissed
- etc.

### Por qué existe
El sistema no acaba en la detección.

### Cómo usarla
- timeline
- auditoría
- métricas operativas

### Regla mental
**Convierte el sistema en acción real.**

---

## 12. `monitoring_configs`

### Qué es
Configuración del sistema por menor.

### Qué representa
Cómo funciona el pipeline:
- tamaño de chunk
- reglas de cierre
- límites

### Por qué existe
Evita hardcodear lógica.

### Cómo usarla
- controlar comportamiento
- ajustar sensibilidad
- activar/desactivar monitorización

### Regla mental
**Controla cómo observa el sistema.**

---

# 🔗 Relaciones clave
users → conversations → conversation_chunks
→ chunk_metrics
→ chunk_summaries
→ risk_assessments
→ alerts
→ alert_recipients
→ alert_actions

---

# 🧠 Cómo debe pensar cada equipo

## Frontend
Trabaja con:
- alerts
- alert_recipients
- alert_actions
- risk_assessments
- chunk_summaries

---

## Backend realtime
Trabaja con:
- conversations
- conversation_participants
- conversation_chunks
- monitoring_configs

---

## Backend AI
Trabaja con:
- conversation_chunks
- chunk_metrics
- chunk_summaries
- risk_assessments

---

## Producto / Demo

Debe entender:
- no guardamos mensajes
- guardamos derivados
- resumimos + analizamos + escalamos
- intervención humana temprana

---

# 📌 Resumen corto

---

# 🧠 Cómo debe pensar cada equipo

## Frontend
Trabaja con:
- alerts
- alert_recipients
- alert_actions
- risk_assessments
- chunk_summaries

---

## Backend realtime
Trabaja con:
- conversations
- conversation_participants
- conversation_chunks
- monitoring_configs

---

## Backend AI
Trabaja con:
- conversation_chunks
- chunk_metrics
- chunk_summaries
- risk_assessments

---

## Producto / Demo

Debe entender:
- no guardamos mensajes
- guardamos derivados
- resumimos + analizamos + escalamos
- intervención humana temprana

---

# 📌 Resumen corto
La BBDD no almacena mensajes crudos.
Solo datos derivados y accionables.

conversation → chunk → metrics/summary → risk → alert → human action