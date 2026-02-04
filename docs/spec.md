# LoRa Mesh → OSM Notes Gateway (MVP)

**Propósito**: permitir que personas en terreno (sin Internet) envíen *reportes de texto* desde una red LoRa mesh (Meshtastic) y que un **gateway en Raspberry Pi** (con Internet intermitente) los convierta en **OSM Notes**. El sistema prioriza **simplicidad de despliegue**, **robustez store-and-forward**, y **privacidad** (no usarlo como canal de emergencias).

> **Estado**: Documento de especificación MVP (con decisiones cerradas) + prompt final para implementar en Cursor IDE.

---

## 1. Hardware objetivo

- **Terreno (reporter)**: **T‑Echo** con **GNSS** (GPS) habilitado.
- **Gateway LoRa**: **Heltec V3** (sin GPS), conectado por **USB** a la Raspberry Pi.
- **Gateway compute**: **Raspberry Pi 3** con Raspberry Pi OS (u otro Linux compatible).

**Conexiones**
- Usuarios en terreno: teléfono ↔ (BLE) ↔ T‑Echo, usando app Meshtastic.
- Gateway: Heltec V3 ↔ (USB serial) ↔ Raspberry Pi.

---

## 2. Stack recomendado (MVP)

- **Meshtastic** (sobre LoRa) por facilidad de despliegue y app móvil existente.
- Gateway en **Python** con conexión **USB serial** a Meshtastic (sin MQTT en MVP).
- Persistencia local con **SQLite** (cola offline y auditoría).
- Servicio **systemd** para ejecución 24/7.

---

## 3. Alcance y principios

### 3.1 Qué hace el sistema
- Recibe mensajes Meshtastic desde la mesh.
- Filtra y procesa **solo** mensajes con comandos/hashtags definidos.
- Para reportes `#osmnote`, asocia ubicación GNSS del **nodo emisor** (T‑Echo) y crea una **OSM Note**.
- Si no hay Internet, **encola** el reporte y lo envía después (store-and-forward).
- Siempre responde por **DM** con *ACK + aviso de privacidad*.

### 3.2 Qué NO hace el sistema (MVP)
- No es un sistema de emergencias (ni promete atención).
- No usa brújula/orientación de celular.
- No requiere que el usuario escriba etiquetas OSM ni tecnicismos.
- No procesa texto libre sin comandos.
- No integra Ushahidi/uMap en MVP (queda como extensión futura).

---

## 4. Configuración de radio y canal

- **Región**: **US915** (Colombia) en *todos* los nodos.
- **Canal**: **público** (sin PSK) para el MVP.

> Nota: canal público implica que cualquier nodo en el mismo canal puede leer/escribir mensajes. El gateway solo automatiza cuando detecta comandos.

---

## 5. Experiencia de usuario (terreno)

1. Encender T‑Echo.
2. Esperar **30–60 s al aire libre** para GNSS (primer fix).
3. Conectar teléfono por Bluetooth (app Meshtastic).
4. Enviar reportes como texto libre con el prefijo:

```
#osmnote <tu mensaje>
```

Ejemplos:
- `#osmnote Árbol caído bloquea media calzada frente al colegio.`
- `#osmnote Derrumbe grande, vía cerrada.`

El usuario recibe un DM con confirmación y recordatorio de privacidad.

---

## 6. Reglas de ubicación (movilidad)

**Problema**: posición GNSS y mensaje de texto no siempre viajan en el mismo paquete; en mesh pueden llegar con distintos retrasos. En movilidad (a pie/moto/carro) una posición vieja puede desplazar la nota.

**Solución**: el gateway mantiene un cache `last_position[node_id]` y evalúa la edad del último fix recibido.

### Umbrales cerrados (MVP)
- `POS_GOOD = 15 s`
- `POS_MAX  = 60 s`

Decisión:
- Si **no hay** posición reciente en cache → **rechazar** (no crear nota).
- Si `pos_age > 60 s` → **rechazar**.
- Si `15 < pos_age ≤ 60` → **aceptar** pero marcar "posición aproximada".
- Si `pos_age ≤ 15` → **aceptar** normal.

---

## 7. Dedupe (anti reintentos, sin perder eventos reales)

**Objetivo del dedupe**: evitar duplicados por reenvío/reintento (at-least-once delivery), **no** colapsar reportes reales repetidos (p.ej., "Casa derrumbada" puede ser otra casa).

**Regla final**: un reporte es **duplicado SOLO si coinciden TODAS**:
1. **Mismo `node_id` emisor** (dedupe solo intra-nodo)
2. **Texto normalizado idéntico** (trim + colapsar espacios)
3. **Ubicación muy cercana**: lat/lon redondeados a **4 decimales** (~11 m)
4. **Mismo bucket temporal** de **120 s** (`floor(recv_time/120)`)

**Explícito**:
- **NO** deduplicar entre nodos distintos.
- **NO** deduplicar si cambia la ubicación, aunque el texto sea igual.

---

## 8. Comandos soportados

### 8.1 Reportes OSM
- `#osmnote <texto>`: crea (o encola) una nota OSM.
- Variantes aceptadas (para reducir fricción humana): `#osmnote`, `#osm-note`, `#osm_note`.

**Regla**: si el mensaje trae solo el hashtag sin texto → rechazo "falta texto".

### 8.2 Comandos informativos (siempre por DM)
- `#osmhelp`: instrucciones de uso.
- `#osmstatus`: estado del gateway (activo, internet OK/NO, colas).
- `#osmcount`: conteo de notas creadas por ese nodo (hoy + total).
- `#osmlist [n]`: últimas `n` notas del nodo, incluyendo **pending + sent** (default 5, max 20).
- `#osmqueue`: tamaño de cola total y del nodo.

### 8.3 Mensajes sin comandos
- Texto libre sin hashtags: **no se responde** (no intervención del gateway).

---

## 9. Mensajes (plantillas exactas)

> **Todos los ACK de `#osmnote` se envían por DM** e incluyen privacidad.

### 9.1 Falta texto
```
❌ Falta el texto del reporte.
Usa: #osmnote <tu mensaje>
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.2 Éxito (nota creada)
```
✅ Reporte recibido y nota creada en OSM.
📝 Nota: #<id>
<url>
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.3 En cola (sin Internet)
```
✅ Reporte recibido. Quedó en cola para enviar cuando haya Internet.
📦 En cola: Q-<id>
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.4 Rechazo sin GPS
```
❌ Reporte recibido, pero no hay GPS reciente del dispositivo.
Mantén el T‑Echo encendido al aire libre 30–60 s y reenvía.
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.5 Rechazo GPS viejo
```
❌ Reporte recibido, pero la última posición es muy vieja (>60 s).
Espera a que el GPS se actualice y reenvía.
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.6 Duplicado
```
✅ Reporte recibido (ya estaba registrado).
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.7 Notificación de cola enviada (solo pending→sent)
> **Solo** cuando un ítem estaba `pending` y pasó a `sent`.

```
✅ Enviado desde cola: Q-<id> → Nota OSM #<note_id>
<url>
```

### 9.8 Help
```
ℹ️ Para crear una nota de mapeo escribe:
#osmnote <tu mensaje>

Usa #osmstatus para ver estado.
⚠️ No envíes datos personales ni emergencias médicas.
```

### 9.9 Broadcast diario (opcional, 1 vez/24h)
```
ℹ️ Gateway de notas OSM activo.
Usa:
#osmnote <mensaje>
#osmhelp
```

---

## 10. Persistencia y colas

### 10.1 SQLite (mínimo)
Tabla `notes` con:
- `id` AUTOINCREMENT
- `local_queue_id` UNIQUE (`Q-0001`)
- `node_id`
- `created_at`
- `lat`, `lon`
- `text_original`, `text_normalized`
- `status` (`pending|sent`)
- `osm_note_id` (nullable)
- `osm_note_url` (nullable)
- `sent_at` (nullable)
- `last_error` (nullable)
- `notified_sent` (0/1)

### 10.2 Worker
- Flush de pendientes cada **30 s**.
- Rate limit global al enviar a OSM: **≥ 3 s** entre notas.
- Cuando un pendiente se envía con éxito:
  - Guardar `osm_note_id`/`url`
  - Marcar `sent`
  - Si `notified_sent==0`: DM "Q→Note", luego `notified_sent=1`
- Anti-spam de notificaciones: máx **3/minuto/nodo**; si excede, enviar resumen.

---

## 11. Confiabilidad y privacidad

- Canal público: cualquiera en el canal puede leer/escribir.
- Automatismos solo con comandos (`#osmnote`, `#osmhelp`, etc.).
- `#osmlist`, `#osmcount`, `#osmqueue`, `#osmstatus` deben responder **solo por DM**.
- El gateway debe tener identidad clara (nombre tipo **osm-notes-bot**) para que se entienda que es un sistema automatizado.

---

## 12. Prueba de demo (real field)

1. T‑Echo encendido al aire libre 30–60 s.
2. App Meshtastic conectada por BLE.
3. `#osmstatus` (debe responder; mostrar Internet OK/NO).
4. `#osmnote Prueba en campo` → DM con ID/URL si Internet.
5. Cortar Internet en la Pi → `#osmnote ...` → DM con `Q-XXXX`.
6. Restaurar Internet → recibir DM `Q-XXXX → Nota #YYYY`.
7. `#osmlist` → debe mostrar PEND y SENT.

---

## 13. Prompt final para Cursor IDE

> Copiar y pegar tal cual en Cursor.

```text
Necesito implementar un gateway MVP "Meshtastic USB → OSM Notes" para Raspberry Pi 3, en Python.

Contexto:
- Nodos en campo: T-Echo con GNSS. Usuarios escriben mensajes desde la app Meshtastic (Bluetooth).
- Gateway: Heltec V3 conectado por USB a Raspberry Pi.
- Canal público, sin PSK.
- El gateway convierte reportes en OSM Notes usando la ubicación GNSS del nodo emisor.

Enfoque: robustez y demos en campo (real field). NO usar MQTT.

REQUISITOS FUNCIONALES

1) Entrada Meshtastic (USB serial)
- Conectar al puerto SERIAL_PORT (env var) con reconexión automática.
- Escuchar paquetes entrantes de:
  a) mensajes de texto
  b) posiciones/telemetría (lat/lon)
- Mantener un cache en memoria: last_position[node_id] = (lat, lon, last_pos_received_at, pos_seen_count).
- El timestamp que manda el gateway para decisiones es el momento de recepción en el gateway.
- Debe existir una función para enviar DM al node_id y otra para broadcast.

2) Procesar SOLO comandos/hashtags. Ignorar texto libre sin responder.
Comandos soportados (responder SIEMPRE por DM):
- #osmhelp: instrucciones.
- #osmstatus: gateway activo, internet OK/NO, cola total y cola del nodo.
- #osmcount: conteo de notas creadas por ese nodo (hoy y total).
- #osmlist [n]: últimas n notas de ese nodo, incluyendo pending+sent, ordenadas por created_at desc. Default 5, máximo 20.
- #osmqueue: tamaño de cola total y tamaño de cola del nodo.

3) Reportes de notas: hashtag #osmnote
- Un reporte es un mensaje que contiene el comando de nota.
- Aceptar variantes del hashtag (para reducir fricción humana): "#osmnote", "#osm-note", "#osm_note" y tratarlas como equivalentes.
- Si el mensaje contiene solo el hashtag sin texto adicional (ej. "#osmnote" o "#osm-note" con espacios):
  -> RECHAZAR con DM "Falta texto".
- Si hay texto:
  -> Validar GPS por edad de la última posición en cache:
     POS_GOOD=15s, POS_MAX=60s.
     - Si NO hay posición en cache para el node_id, RECHAZAR (no GPS reciente).
     - Si pos_age > 60s, RECHAZAR (GPS viejo).
     - Si 15s < pos_age <= 60s, ACEPTAR pero marcar en el texto final "posición aproximada".
     - Si pos_age <= 15s, ACEPTAR normal.

4) DEDUPLICACIÓN (crítica para no perder reportes reales)
- El objetivo del dedupe es SOLO evitar reintentos accidentales (doble envío), no colapsar eventos reales repetidos.
- Un reporte se considera duplicado SOLO si coinciden TODAS:
  a) mismo node_id emisor
  b) texto normalizado idéntico (trim y colapsar espacios)
  c) ubicación muy cercana: lat/lon redondeados a 4 decimales (≈ 11m)
  d) mismo bucket temporal de 120s (time_bucket = floor(recv_time/120))
- NO deduplicar entre nodos distintos.
- NO deduplicar si cambia la ubicación (aunque el texto sea igual).
- Si es duplicado: NO crear nota, pero SÍ enviar ACK de duplicado.

5) Persistencia local (SQLite) y colas
- Usar SQLite para garantizar store-and-forward.
- Tabla notes con campos mínimos:
  id AUTOINCREMENT,
  local_queue_id UNIQUE (formato Q-0001),
  node_id,
  created_at,
  lat, lon,
  text_original,
  text_normalized,
  status ('pending','sent'),
  osm_note_id (nullable),
  osm_note_url (nullable),
  sent_at (nullable),
  last_error (nullable),
  notified_sent (0/1).
- Al aceptar un reporte (normal o aproximado): encolar (pending) con local_queue_id y guardar.
- Intentar envío inmediato a OSM si hay Internet; si falla mantener pending.

6) Envío a OSM Notes
- POST a: https://api.openstreetmap.org/api/0.6/notes.json con lat, lon, text.
- Rate limit global: mínimo 3s entre envíos.
- Worker periódico cada 30s intenta flush de pending.
- Manejo de errores: timeouts, rate limit, desconexión; no bloquear el proceso.

7) Notificaciones y ACK (DM)
- Para cualquier #osmnote (incluyendo duplicado y rechazado) enviar SIEMPRE un DM con ACK + aviso de privacidad.
- Si éxito online: incluir osm_note_id y URL.
- Si quedó pending: incluir Q-XXXX.
- Notificación proactiva SOLO para pending→sent:
  - Cuando un item pase de pending a sent y notified_sent==0: enviar DM "Q→Note" y marcar notified_sent=1.
  - Anti-spam: máximo 3 notificaciones por minuto por nodo; si excede, enviar resumen: "✅ Se enviaron N reportes en cola. Usa #osmlist."

8) Mensajes exactos (plantillas)
Implementar EXACTAMENTE estos textos:

FALTA TEXTO:
"❌ Falta el texto del reporte.\nUsa: #osmnote <tu mensaje>\n⚠️ No envíes datos personales ni emergencias médicas."

ACK SUCCESS:
"✅ Reporte recibido y nota creada en OSM.\n📝 Nota: #<id>\n<url>\n⚠️ No envíes datos personales ni emergencias médicas."

ACK QUEUED:
"✅ Reporte recibido. Quedó en cola para enviar cuando haya Internet.\n📦 En cola: Q-<id>\n⚠️ No envíes datos personales ni emergencias médicas."

REJECT NO GPS:
"❌ Reporte recibido, pero no hay GPS reciente del dispositivo.\nMantén el T‑Echo encendido al aire libre 30–60 s y reenvía.\n⚠️ No envíes datos personales ni emergencias médicas."

REJECT STALE GPS:
"❌ Reporte recibido, pero la última posición es muy vieja (>60 s).\nEspera a que el GPS se actualice y reenvía.\n⚠️ No envíes datos personales ni emergencias médicas."

DUPLICATE:
"✅ Reporte recibido (ya estaba registrado).\n⚠️ No envíes datos personales ni emergencias médicas."

HELP:
"ℹ️ Para crear una nota de mapeo escribe:\n#osmnote <tu mensaje>\n\nUsa #osmstatus para ver estado.\n⚠️ No envíes datos personales ni emergencias médicas."

Q→NOTE:
"✅ Enviado desde cola: Q-<id> → Nota OSM #<note_id>\n<url>"

DAILY BROADCAST (opcional 1 vez/24h):
"ℹ️ Gateway de notas OSM activo.\nUsa:\n#osmnote <mensaje>\n#osmhelp"

STATUS:
Debe incluir: gateway activo, internet OK/NO, cola total, cola del nodo.

9) Entregables del repo
- Estructura con src/gateway/*
- README.md con instalación en Raspberry Pi OS:
  - dependencias, venv, permisos dialout, detección /dev/ttyACM0
  - systemd service + logs con journalctl
  - troubleshooting
- scripts/install_pi.sh: instala deps, crea venv, configura /var/lib/lora-osmnotes, instala unit systemd y habilita el servicio.
- systemd unit file robusto (Restart=always, After=network-online.target).
- tests con pytest: parser, dedupe, store.
- logging claro.
- Config por variables de entorno y .env.example.
- Timezone America/Bogota.
- DRY_RUN=true para no enviar DMs ni llamar a OSM (solo logs).

No usar MQTT. Implementar reconexión serial, manejo de excepciones, y mantener el servicio estable.
Genera el código completo y coherente.
```

---

## 14. Notas de implementación sugeridas (no bloqueantes)

- Usar nombre de nodo gateway tipo `osm-notes-bot`.
- Mantener los comandos (`#osmhelp`, `#osmstatus`, etc.) como DM para privacidad.
- Mantener el redondeo de 4 decimales para dedupe (evita colapsar casas distintas).
