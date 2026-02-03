# API Reference

Documentación de la API interna del gateway.

## Módulos Principales

### gateway.config

Configuración centralizada del sistema.

**Constantes**:
- `DATA_DIR`: Directorio de datos (default: `/var/lib/lora-osmnotes`)
- `DB_PATH`: Ruta a la base de datos SQLite
- `SERIAL_PORT`: Puerto serial (default: `/dev/ttyACM0`)
- `DRY_RUN`: Modo de prueba (default: `False`)
- `POS_GOOD`: Umbral GPS bueno en segundos (15)
- `POS_MAX`: Umbral GPS máximo en segundos (60)
- `OSM_RATE_LIMIT_SECONDS`: Rate limit OSM (3)
- `WORKER_INTERVAL`: Intervalo worker en segundos (30)

### gateway.database.Database

Gestión de base de datos SQLite.

#### Métodos Principales

**`create_note(node_id, lat, lon, text_original, text_normalized)`**
- Crea nueva nota con status 'pending'
- Retorna: `local_queue_id` (str) o None

**`get_pending_notes(limit=100)`**
- Obtiene notas pendientes ordenadas por fecha
- Retorna: Lista de dicts con datos de notas

**`update_note_sent(local_queue_id, osm_note_id, osm_note_url)`**
- Marca nota como enviada
- Actualiza OSM ID y URL

**`check_duplicate(node_id, text_normalized, lat, lon, time_bucket)`**
- Verifica si existe nota duplicada
- Retorna: `True` si es duplicado, `False` si no

**`get_node_stats(node_id)`**
- Obtiene estadísticas de un nodo
- Retorna: Dict con 'total', 'today', 'queue'

### gateway.commands.CommandProcessor

Procesamiento de comandos y mensajes.

#### Métodos Principales

**`process_message(node_id, text, lat=None, lon=None, timestamp=None)`**
- Procesa mensaje entrante
- Retorna: `(command_type, response_message)`

**`normalize_text(text)`**
- Normaliza texto para deduplicación
- Retorna: Texto normalizado (trim + collapse whitespace)

**`extract_osmnote(text)`**
- Extrae comando #osmnote y retorna texto restante
- Retorna: Texto sin hashtag o None

### gateway.meshtastic_serial.MeshtasticSerial

Comunicación serial con dispositivo Meshtastic.

#### Métodos Principales

**`connect()`**
- Conecta al puerto serial
- Retorna: `True` si éxito, `False` si falla

**`start()`**
- Inicia thread de lectura
- Configura callback para mensajes

**`send_dm(node_id, message)`**
- Envía mensaje directo a nodo
- Retorna: `True` si éxito

**`send_broadcast(message)`**
- Envía mensaje broadcast
- Retorna: `True` si éxito

**`set_message_callback(callback)`**
- Configura callback para mensajes entrantes
- Callback recibe: `dict` con 'node_id', 'text', 'lat', 'lon', 'timestamp'

### gateway.osm_worker.OSMWorker

Worker para envío a OSM Notes API.

#### Métodos Principales

**`send_note(lat, lon, text)`**
- Envía nota a OSM API con rate limiting
- Retorna: `{'id': note_id, 'url': note_url}` o None

**`process_pending(limit=10)`**
- Procesa notas pendientes
- Retorna: Número de notas enviadas exitosamente

### gateway.notifications.NotificationManager

Sistema de notificaciones DM.

#### Métodos Principales

**`send_ack(node_id, status, ...)`**
- Envía ACK al nodo
- Status: 'success', 'queued', 'duplicate'

**`send_reject(node_id, message)`**
- Envía mensaje de rechazo

**`send_command_response(node_id, message)`**
- Envía respuesta a comando

**`process_sent_notifications()`**
- Procesa notificaciones Q→Note pendientes
- Respeta anti-spam

### gateway.position_cache.PositionCache

Cache de posiciones GPS.

#### Métodos Principales

**`update(node_id, lat, lon)`**
- Actualiza posición de nodo

**`get(node_id)`**
- Obtiene posición de nodo
- Retorna: `Position` object o None

**`get_age(node_id)`**
- Obtiene edad de posición en segundos
- Retorna: `float` o None

### gateway.main.Gateway

Aplicación principal.

#### Métodos Principales

**`start()`**
- Inicia gateway y todos los componentes
- Bloquea hasta shutdown

**`stop()`**
- Detiene gateway gracefulmente

**`_handle_message(msg)`**
- Handler interno para mensajes entrantes
- Procesa y envía respuestas

## Tipos de Datos

### Position

```python
@dataclass
class Position:
    lat: float
    lon: float
    received_at: float  # Unix timestamp
    seen_count: int
```

### Message Dict

```python
{
    "node_id": str,
    "text": str,
    "lat": Optional[float],
    "lon": Optional[float],
    "timestamp": float
}
```

### Note Dict

```python
{
    "id": int,
    "local_queue_id": str,
    "node_id": str,
    "created_at": str,  # ISO format
    "lat": float,
    "lon": float,
    "text_original": str,
    "text_normalized": str,
    "status": str,  # 'pending' or 'sent'
    "osm_note_id": Optional[int],
    "osm_note_url": Optional[str],
    "sent_at": Optional[str],
    "last_error": Optional[str],
    "notified_sent": int  # 0 or 1
}
```

## Flujos de Ejecución

### Creación de Nota

```
Message → MeshtasticSerial → Gateway._handle_message()
  → CommandProcessor.process_message()
    → PositionCache.get() [GPS validation]
    → Database.check_duplicate()
    → Database.create_note() [status: 'pending']
    → OSMWorker.send_note() [try immediate]
      → Database.update_note_sent() [if success]
    → NotificationManager.send_ack()
```

### Procesamiento de Cola

```
Worker Thread (every 30s)
  → OSMWorker.process_pending()
    → Database.get_pending_notes()
    → OSMWorker.send_note() [for each]
      → Database.update_note_sent()
  → NotificationManager.process_sent_notifications()
    → NotificationManager.send_ack() [Q→Note]
```

## Manejo de Errores

### Excepciones Comunes

- **`serial.SerialException`**: Error de conexión serial → Auto-reconnect
- **`sqlite3.Error`**: Error de base de datos → Rollback y log
- **`requests.exceptions.Timeout`**: Timeout OSM API → Mantener pending
- **`requests.exceptions.ConnectionError`**: Sin Internet → Mantener pending

### Valores de Retorno

- **`None`**: Error o no disponible
- **`False`**: Operación falló
- **`True`**: Operación exitosa
- **Dict/List**: Datos retornados

## Configuración Avanzada

### Variables de Entorno

Todas las configuraciones pueden sobrescribirse con variables de entorno:

```bash
export SERIAL_PORT=/dev/ttyUSB0
export DRY_RUN=true
export DATA_DIR=/custom/path
export LOG_LEVEL=DEBUG
export TZ=America/Bogota
```

### Modo Dry-Run

Cuando `DRY_RUN=true`:
- No se envían DMs reales
- No se hacen llamadas a OSM API
- Se retornan datos mock
- Todo se loggea normalmente
