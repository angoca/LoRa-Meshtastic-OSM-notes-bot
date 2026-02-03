# LoRa-Meshtastic-OSM-notes-bot

Gateway MVP para convertir mensajes Meshtastic en notas de OpenStreetMap (OSM). Diseñado para Raspberry Pi 3 con dispositivo Meshtastic Heltec V3 conectado por USB.

## Descripción

Este gateway permite a usuarios en campo enviar reportes de mapeo usando dispositivos Meshtastic (como T-Echo) que se convierten automáticamente en notas de OSM. El sistema incluye:

- **Recepción de mensajes** desde dispositivos Meshtastic vía USB serial
- **Cache de posiciones GPS** para validación de ubicación
- **Procesamiento de comandos** mediante hashtags (#osmnote, #osmhelp, etc.)
- **Deduplicación inteligente** para evitar reportes duplicados
- **Store-and-forward** con SQLite para garantizar entrega
- **Envío a OSM Notes API** con rate limiting
- **Notificaciones por DM** con anti-spam

## Requisitos

- Raspberry Pi 3 (o superior) con Raspberry Pi OS
- Dispositivo Meshtastic (Heltec V3) conectado por USB
- Conexión a Internet (para envío a OSM)
- Python 3.8+

## Instalación

### Instalación automática (recomendada)

```bash
git clone https://github.com/tu-usuario/LoRa-Meshtastic-OSM-notes-bot.git
cd LoRa-Meshtastic-OSM-notes-bot
sudo bash scripts/install_pi.sh
```

El script de instalación:
1. Instala dependencias del sistema
2. Crea entorno virtual en `/opt/lora-osmnotes`
3. Instala dependencias de Python
4. Crea directorio de datos en `/var/lib/lora-osmnotes`
5. Configura servicio systemd
6. Agrega usuario al grupo `dialout` para acceso serial

### Instalación manual

1. **Instalar dependencias del sistema:**
```bash
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv python3-dev gcc git sqlite3
```

2. **Crear entorno virtual:**
```bash
python3 -m venv /opt/lora-osmnotes
source /opt/lora-osmnotes/bin/activate
```

3. **Instalar dependencias:**
```bash
pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
```

4. **Crear directorio de datos:**
```bash
sudo mkdir -p /var/lib/lora-osmnotes
sudo chown $USER:$USER /var/lib/lora-osmnotes
```

5. **Configurar variables de entorno:**
```bash
cp .env.example /var/lib/lora-osmnotes/.env
# Editar /var/lib/lora-osmnotes/.env según necesidad
```

6. **Agregar usuario a dialout:**
```bash
sudo usermod -a -G dialout $USER
# Cerrar sesión y volver a iniciar para aplicar cambios
```

7. **Instalar servicio systemd:**
Copiar el contenido de `systemd/lora-osmnotes.service` a `/etc/systemd/system/` y ajustar rutas.

## Configuración

### Variables de entorno

Editar `/var/lib/lora-osmnotes/.env`:

```bash
# Puerto serial del dispositivo Meshtastic
SERIAL_PORT=/dev/ttyACM0

# Modo dry-run (no envía DMs ni llama a OSM)
DRY_RUN=false

# Zona horaria
TZ=America/Bogota

# Nivel de logging
LOG_LEVEL=INFO

# Broadcast diario opcional
DAILY_BROADCAST_ENABLED=false
```

### Detectar puerto serial

```bash
# Listar dispositivos seriales
ls -l /dev/ttyACM* /dev/ttyUSB*

# Verificar permisos
ls -l /dev/ttyACM0

# Probar conexión (requiere permisos)
sudo chmod 666 /dev/ttyACM0
```

## Uso

### Iniciar servicio

```bash
sudo systemctl start lora-osmnotes
sudo systemctl enable lora-osmnotes  # Iniciar al arrancar
```

### Ver logs

```bash
# Ver logs en tiempo real
sudo journalctl -u lora-osmnotes -f

# Ver últimos 100 líneas
sudo journalctl -u lora-osmnotes -n 100

# Ver logs desde hoy
sudo journalctl -u lora-osmnotes --since today
```

### Detener servicio

```bash
sudo systemctl stop lora-osmnotes
```

## Comandos disponibles

Los usuarios pueden enviar comandos desde la app Meshtastic:

### `#osmnote <mensaje>`
Crea una nota de OSM con el mensaje proporcionado. Requiere GPS reciente (últimos 60 segundos).

Variantes aceptadas: `#osmnote`, `#osm-note`, `#osm_note`

### `#osmhelp`
Muestra instrucciones de uso.

### `#osmstatus`
Muestra estado del gateway:
- Gateway activo/inactivo
- Estado de Internet
- Tamaño de cola total
- Tamaño de cola del nodo

### `#osmcount`
Muestra conteo de notas creadas:
- Notas creadas hoy
- Total de notas

### `#osmlist [n]`
Lista las últimas `n` notas del nodo (default: 5, máximo: 20).

### `#osmqueue`
Muestra tamaño de cola:
- Cola total
- Cola del nodo

## Validación GPS

El sistema valida la posición GPS antes de crear notas:

- **Sin GPS**: Rechaza si no hay posición en cache
- **GPS viejo (>60s)**: Rechaza con mensaje de error
- **GPS aproximado (15-60s)**: Acepta pero marca como "posición aproximada"
- **GPS reciente (≤15s)**: Acepta normalmente

## Deduplicación

El sistema evita crear notas duplicadas si coinciden:
- Mismo `node_id`
- Texto normalizado idéntico
- Ubicación muy cercana (redondeada a 4 decimales ≈ 11m)
- Mismo bucket temporal de 120 segundos

## Documentación

- **[README.md](README.md)** - Esta guía de inicio rápido
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Arquitectura del sistema y diseño
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guía para contribuidores
- **[MESSAGE_FORMAT.md](MESSAGE_FORMAT.md)** - Formato de mensajes Meshtastic

## Estructura del proyecto

```
.
├── src/
│   └── gateway/
│       ├── __init__.py
│       ├── main.py           # Aplicación principal
│       ├── config.py         # Configuración
│       ├── database.py       # SQLite database
│       ├── meshtastic_serial.py  # Comunicación serial
│       ├── position_cache.py # Cache de posiciones GPS
│       ├── commands.py       # Procesamiento de comandos
│       ├── osm_worker.py     # Worker de envío a OSM
│       └── notifications.py  # Sistema de notificaciones
├── tests/                    # Tests con pytest
├── scripts/
│   └── install_pi.sh        # Script de instalación
├── systemd/                  # Archivos systemd
├── requirements.txt         # Dependencias Python
├── setup.py                 # Setup package
├── README.md                # Documentación principal
├── ARCHITECTURE.md          # Arquitectura del sistema
├── CONTRIBUTING.md          # Guía de contribución
└── MESSAGE_FORMAT.md        # Formato de mensajes
```

## Testing

Ejecutar tests:

```bash
# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Con cobertura
pytest --cov=gateway --cov-report=html
```

## Troubleshooting

### El servicio no inicia

1. Verificar logs:
```bash
sudo journalctl -u lora-osmnotes -n 50
```

2. Verificar permisos del puerto serial:
```bash
ls -l /dev/ttyACM0
sudo chmod 666 /dev/ttyACM0  # Temporal para pruebas
```

3. Verificar que el usuario esté en grupo `dialout`:
```bash
groups
```

### No se reciben mensajes

1. Verificar conexión serial:
```bash
# Verificar dispositivo
lsusb | grep -i meshtastic

# Probar conexión directa
sudo screen /dev/ttyACM0 9600
```

2. Verificar configuración de puerto en `.env`

3. Verificar logs del gateway:
```bash
sudo journalctl -u lora-osmnotes -f
```

### No se envían notas a OSM

1. Verificar conexión a Internet:
```bash
ping -c 3 api.openstreetmap.org
```

2. Verificar rate limiting (mínimo 3s entre envíos)

3. Verificar logs para errores de API:
```bash
sudo journalctl -u lora-osmnotes | grep -i "osm\|error"
```

### Modo Dry-Run

Para probar sin enviar DMs ni crear notas en OSM:

```bash
# Editar .env
echo "DRY_RUN=true" >> /var/lib/lora-osmnotes/.env

# Reiniciar servicio
sudo systemctl restart lora-osmnotes
```

## Desarrollo

### Estructura de base de datos

Tabla `notes`:
- `id`: ID autoincremental
- `local_queue_id`: ID único de cola (Q-0001, Q-0002, ...)
- `node_id`: ID del nodo Meshtastic
- `created_at`: Timestamp de creación
- `lat`, `lon`: Coordenadas GPS
- `text_original`: Texto original del mensaje
- `text_normalized`: Texto normalizado para deduplicación
- `status`: 'pending' o 'sent'
- `osm_note_id`: ID de la nota en OSM (nullable)
- `osm_note_url`: URL de la nota en OSM (nullable)
- `sent_at`: Timestamp de envío (nullable)
- `last_error`: Último error (nullable)
- `notified_sent`: Flag de notificación enviada (0/1)

### Flujo de procesamiento

1. **Recepción**: Mensaje llega por serial USB
2. **Cache GPS**: Actualiza posición si hay datos GPS
3. **Procesamiento**: Comando procesado según hashtag
4. **Validación**: Valida GPS y texto para `#osmnote`
5. **Deduplicación**: Verifica duplicados
6. **Almacenamiento**: Guarda en SQLite con status 'pending'
7. **Envío**: Worker intenta enviar a OSM API
8. **Notificación**: Envía DM con ACK al usuario

## Licencia

Ver archivo LICENSE.

## Contribuciones

Las contribuciones son bienvenidas. Por favor:
1. Fork el proyecto
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

## Notas importantes

⚠️ **Privacidad**: El sistema incluye advertencias sobre no enviar datos personales ni emergencias médicas en todos los mensajes.

⚠️ **Rate Limiting**: OSM API tiene límites de rate. El sistema respeta mínimo 3 segundos entre envíos.

⚠️ **GPS**: Los dispositivos T-Echo necesitan estar al aire libre 30-60 segundos para obtener GPS válido.

## Soporte

Para reportar problemas o solicitar features, abre un issue en GitHub.
