# Arquitectura del Sistema

## Visión General

El gateway Meshtastic → OSM Notes es un sistema de procesamiento de mensajes que convierte reportes de campo en notas de OpenStreetMap. Está diseñado para operar de forma autónoma en una Raspberry Pi con conexión serial USB a un dispositivo Meshtastic.

## Componentes Principales

### 1. MeshtasticSerial (`meshtastic_serial.py`)

**Responsabilidad**: Comunicación serial con dispositivo Meshtastic.

- **Conexión**: Maneja conexión/reconexión automática al puerto USB
- **Lectura**: Thread separado para leer mensajes entrantes
- **Escritura**: Envío de DMs y broadcasts
- **Parser**: Convierte mensajes serial a formato interno (JSON o pipe-separated)

**Flujo**:
```
Serial Port → Buffer → Parser → Message Callback → Gateway._handle_message()
```

### 2. PositionCache (`position_cache.py`)

**Responsabilidad**: Cache en memoria de posiciones GPS por nodo.

- Almacena última posición conocida de cada nodo
- Calcula edad de posición para validación
- Mantiene contador de actualizaciones

**Estructura**:
```python
{
    "node_id": Position(lat, lon, received_at, seen_count)
}
```

### 3. CommandProcessor (`commands.py`)

**Responsabilidad**: Procesamiento de comandos y hashtags.

- **Comandos soportados**: #osmhelp, #osmstatus, #osmcount, #osmlist, #osmqueue
- **Reportes**: #osmnote con variantes (#osm-note, #osm_note)
- **Validación GPS**: Verifica edad de posición (POS_GOOD=15s, POS_MAX=60s)
- **Deduplicación**: Verifica duplicados antes de crear nota
- **Normalización**: Normaliza texto para comparación

**Flujo de #osmnote**:
```
Mensaje → Extraer hashtag → Validar GPS → Verificar duplicado → Crear nota → Retornar queue_id
```

### 4. Database (`database.py`)

**Responsabilidad**: Persistencia SQLite con store-and-forward.

- **Tabla principal**: `notes` con todos los campos necesarios
- **Índices**: Optimizados para consultas por node_id, status, created_at
- **Operaciones**: CRUD completo + estadísticas + deduplicación

**Esquema**:
```sql
notes (
    id, local_queue_id, node_id, created_at,
    lat, lon, text_original, text_normalized,
    status, osm_note_id, osm_note_url, sent_at,
    last_error, notified_sent
)
```

### 5. OSMWorker (`osm_worker.py`)

**Responsabilidad**: Envío de notas a OSM Notes API.

- **Rate Limiting**: Mínimo 3 segundos entre envíos
- **Manejo de errores**: Timeouts, conexión, errores HTTP
- **Dry Run**: Modo de prueba sin enviar realmente
- **Procesamiento batch**: Procesa múltiples notas pendientes

**Flujo**:
```
Pending Notes → Rate Limit Check → POST to OSM API → Update Status
```

### 6. NotificationManager (`notifications.py`)

**Responsabilidad**: Sistema de notificaciones DM con anti-spam.

- **ACKs**: Envía confirmaciones de éxito, cola, rechazo, duplicado
- **Anti-spam**: Máximo 3 notificaciones por minuto por nodo
- **Notificaciones proactivas**: Q→Note cuando se envía desde cola
- **Resúmenes**: Envía resumen cuando se excede límite anti-spam

**Tipos de ACK**:
- `success`: Nota creada en OSM (incluye ID y URL)
- `queued`: Nota en cola (incluye queue_id)
- `reject`: Rechazo (falta GPS, texto, etc.)
- `duplicate`: Duplicado detectado

### 7. Gateway (`main.py`)

**Responsabilidad**: Orquestación y ciclo principal.

- **Inicialización**: Crea todos los componentes
- **Message Handler**: Procesa mensajes entrantes
- **Worker Thread**: Procesa cola cada 30 segundos
- **Signal Handling**: Manejo graceful de shutdown

**Flujo Principal**:
```
Start → Initialize Components → Start Serial → Start Worker Thread → Main Loop
```

## Flujo de Datos

### Creación de Nota

```
1. Mensaje llega por Serial
   ↓
2. MeshtasticSerial._parse_message()
   ↓
3. Gateway._handle_message()
   ↓
4. CommandProcessor.process_message()
   ↓
5. Validación GPS (PositionCache)
   ↓
6. Verificación Duplicado (Database.check_duplicate)
   ↓
7. Crear Nota (Database.create_note) → Status: 'pending'
   ↓
8. Intentar Envío Inmediato (OSMWorker.send_note)
   ↓
9a. Si éxito → Update Status: 'sent' → ACK success
9b. Si falla → Mantener 'pending' → ACK queued
```

### Procesamiento de Cola

```
Worker Thread (cada 30s):
   ↓
1. OSMWorker.process_pending() → Obtener notas 'pending'
   ↓
2. Para cada nota:
   - Rate Limit Check
   - POST to OSM API
   - Update Status: 'sent' o 'error'
   ↓
3. NotificationManager.process_sent_notifications()
   ↓
4. Enviar DM Q→Note (con anti-spam)
```

## Deduplicación

**Reglas**:
1. Mismo `node_id`
2. Texto normalizado idéntico (trim + collapse whitespace)
3. Ubicación cercana (redondeada a 4 decimales ≈ 11m)
4. Mismo bucket temporal (120 segundos)

**Implementación**:
- `Database.check_duplicate()`: Query SQL con condiciones
- `CommandProcessor.normalize_text()`: Normalización de texto
- Bucket temporal: `floor(timestamp / 120)`

## Validación GPS

**Umbrales**:
- `POS_GOOD = 15s`: Posición fresca (normal)
- `POS_MAX = 60s`: Posición máxima aceptable

**Comportamiento**:
- Sin GPS: Rechazar
- > 60s: Rechazar
- 15-60s: Aceptar con marca "[posición aproximada]"
- ≤ 15s: Aceptar normal

## Manejo de Errores

### Serial
- **Desconexión**: Auto-reconexión cada 5 segundos
- **Errores de lectura**: Log y continuar
- **Errores de escritura**: Log y retornar False

### OSM API
- **Timeout**: Marcar error, mantener pending
- **Connection Error**: Marcar error, mantener pending
- **HTTP Error**: Marcar error con código, mantener pending
- **Rate Limit**: Respetar delay, reintentar en siguiente ciclo

### Base de Datos
- **Errores SQL**: Rollback y log
- **Integrity Errors**: Retry con nuevo queue_id
- **Connection Timeout**: Retry con timeout de 10s

## Threading

**Threads**:
1. **Main Thread**: Loop principal, signal handling
2. **Serial Read Thread**: Lectura continua de serial (daemon)
3. **Worker Thread**: Procesamiento periódico de cola (daemon)

**Sincronización**:
- SQLite maneja concurrencia internamente
- PositionCache: Acceso desde múltiples threads (simple dict)
- No hay locks explícitos (SQLite es thread-safe)

## Configuración

**Fuentes**:
1. Variables de entorno (`.env`)
2. Valores por defecto en `config.py`
3. Fallback a temp directory si no hay permisos

**Parámetros clave**:
- `SERIAL_PORT`: Puerto serial del dispositivo
- `DRY_RUN`: Modo de prueba
- `POS_GOOD`, `POS_MAX`: Umbrales GPS
- `OSM_RATE_LIMIT_SECONDS`: Rate limiting OSM
- `WORKER_INTERVAL`: Intervalo de worker

## Escalabilidad

**Limitaciones actuales**:
- Cache GPS: En memoria (se pierde al reiniciar)
- Base de datos: SQLite (single-writer)
- Rate limiting: Global (no por nodo)

**Mejoras futuras**:
- Persistir cache GPS en DB
- Migrar a PostgreSQL para múltiples writers
- Rate limiting por nodo
- Métricas y monitoreo

## Seguridad

**Consideraciones**:
- Validación de entrada (texto, coordenadas)
- Sanitización de mensajes antes de enviar a OSM
- Advertencias de privacidad en todos los mensajes
- No almacenar datos personales
- Logs sin información sensible

**Mejoras futuras**:
- Autenticación de nodos
- Cifrado de mensajes
- Rate limiting por nodo más estricto
