# OSM Mesh Notes Gateway

**Offline field reports via LoRa mesh → OpenStreetMap Notes**

---

## ¿Qué es?

El **OSM Mesh Notes Gateway** es un sistema que permite a personas en terreno (sin conexión a Internet) enviar reportes de mapeo usando dispositivos LoRa mesh (Meshtastic) que se convierten automáticamente en notas de OpenStreetMap.

Cuando un usuario en campo envía un mensaje con el comando `#osmnote` desde su dispositivo Meshtastic (como un T-Echo), el gateway lo recibe por radio LoRa, valida su ubicación GPS, y lo convierte en una nota pública de OSM. Si no hay Internet disponible, el reporte se guarda en una cola local y se envía automáticamente cuando la conexión se restaura.

Este sistema está diseñado para funcionar de forma autónoma en una Raspberry Pi con un dispositivo Meshtastic conectado por USB, operando 24/7 sin intervención manual.

---

## ¿Por qué existe?

Este proyecto nace de la necesidad de permitir reportes de mapeo en situaciones donde:

- **No hay Internet disponible**: Zonas remotas, áreas afectadas por desastres naturales, o lugares donde la infraestructura de telecomunicaciones está caída o es inexistente.
- **Se requiere mapeo colaborativo**: Comunidades que necesitan documentar cambios en el territorio, daños por desastres, o mejoras necesarias en infraestructura.
- **Conectividad intermitente**: El gateway funciona como un "puente" entre la red LoRa mesh local (que no requiere Internet) y OpenStreetMap (que sí lo requiere), almacenando reportes localmente cuando no hay conexión.

El sistema prioriza **robustez** y **simplicidad de despliegue**, permitiendo que comunidades locales puedan desplegar su propio gateway con hardware accesible y software de código abierto.

---

## ¿Cómo funciona?

El flujo básico es el siguiente:

1. **Usuario en campo**: Envía un reporte desde su dispositivo Meshtastic (T-Echo) usando el comando `#osmnote <mensaje>`. El dispositivo debe tener GPS activo y estar al aire libre para obtener ubicación.

2. **Red LoRa mesh**: El mensaje viaja por radio LoRa hasta llegar al gateway, sin necesidad de Internet.

3. **Gateway**: 
   - Recibe el mensaje por USB desde el dispositivo Meshtastic conectado
   - Valida que haya GPS reciente (últimos 60 segundos)
   - Verifica que no sea un duplicado
   - Guarda el reporte en una base de datos local (SQLite)

4. **Envío a OSM**:
   - Si hay Internet: Envía inmediatamente a la API de OSM Notes
   - Si no hay Internet: Guarda en cola y envía automáticamente cuando se restaura la conexión

5. **Confirmación**: El usuario recibe una confirmación por mensaje directo (DM) con el ID de la nota creada o el ID de cola si quedó pendiente.

```
┌─────────────┐      LoRa      ┌──────────┐      USB      ┌─────────────┐
│   T-Echo    │ ──────────────> │ Heltec   │ ────────────> │ Raspberry   │
│  (Campo)    │    (Radio)     │   V3     │   (Serial)    │     Pi      │
└─────────────┘                └──────────┘               └─────────────┘
                                                                   │
                                                                   │ Internet
                                                                   ▼
                                                            ┌─────────────┐
                                                            │ OSM Notes   │
                                                            │    API      │
                                                            └─────────────┘
```

---

## Quick Start

### Requisitos

- **Raspberry Pi 3** (o superior) con Raspberry Pi OS
- **Dispositivo Meshtastic** (Heltec V3) conectado por USB
- Conexión a Internet (para envío a OSM, puede ser intermitente)
- Python 3.8+

### Instalación rápida

```bash
# Clonar repositorio
git clone https://github.com/OSM-Notes/osm-mesh-notes-gateway.git
cd osm-mesh-notes-gateway

# Instalar (requiere sudo)
sudo bash scripts/install_pi.sh
```

El script de instalación configura todo automáticamente:
- Instala dependencias del sistema
- Crea entorno virtual Python
- Configura servicio systemd
- Agrega usuario al grupo `dialout` para acceso serial

### Configuración inicial

1. **Detectar puerto serial**:
```bash
# Usar el script de detección automática (recomendado)
bash scripts/detect_serial.sh

# O manualmente
ls -l /dev/ttyACM* /dev/ttyUSB*
```

2. **Editar configuración** (`/var/lib/lora-osmnotes/.env`):
```bash
SERIAL_PORT=/dev/ttyACM0  # Ajustar según tu dispositivo
DRY_RUN=false
TZ=America/Bogota
```

3. **Iniciar servicio**:
```bash
sudo systemctl start lora-osmnotes
sudo systemctl enable lora-osmnotes  # Iniciar al arrancar
```

4. **Verificar funcionamiento**:
```bash
sudo journalctl -u lora-osmnotes -f
```

### Uso básico

Desde la app Meshtastic en tu teléfono (conectado por Bluetooth al T-Echo):

- `#osmnote Árbol caído bloquea la calle` - Crea una nota de OSM
- `#osmhelp` - Muestra ayuda básica
- `#osmmorehelp` - Muestra ayuda adicional detallada
- `#osmstatus` - Verifica estado del gateway
- `#osmlist` - Lista tus notas recientes

---

## Documentación

Para más información, consulta la documentación técnica:

- **[docs/spec.md](docs/spec.md)** - Especificación canónica del MVP (fuente de verdad)
- **[docs/architecture.md](docs/architecture.md)** - Arquitectura del sistema y diseño
- **[docs/message-format.md](docs/message-format.md)** - Formato de mensajes Meshtastic
- **[docs/API.md](docs/API.md)** - Referencia de API interna
- **[docs/SECURITY.md](docs/SECURITY.md)** - Guía de seguridad
- **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Solución de problemas
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Guía para contribuidores

---

## Privacidad y Alcance

### ⚠️ **NO es un sistema de emergencias**

Este sistema **NO debe usarse** para:
- Emergencias médicas o situaciones que requieran atención inmediata
- Reportes que requieran respuesta de autoridades
- Comunicación crítica que dependa de disponibilidad garantizada

### 🔒 **Privacidad**

- **Canal público**: Los mensajes viajan por un canal LoRa público, cualquier nodo en el mismo canal puede leerlos
- **Datos personales**: NO envíes información personal identificable (nombres, números de teléfono, direcciones específicas)
- **Notas públicas**: Las notas creadas en OSM son públicas y visibles para cualquiera
- **Advertencias automáticas**: Todos los mensajes del sistema incluyen advertencias de privacidad

### 📍 **Alcance del sistema**

El gateway procesa **solo** mensajes que contengan comandos específicos (hashtags como `#osmnote`, `#osmhelp`, `#osmmorehelp`, etc.). Los mensajes de texto libre sin comandos son ignorados y no se responde a ellos.

---

## Comandos Disponibles

Los usuarios pueden enviar comandos desde la app Meshtastic:

| Comando | Descripción |
|---------|-------------|
| `#osmnote <mensaje>` | Crea una nota de OSM. Requiere GPS reciente (≤60s) |
| `#osmhelp` | Muestra instrucciones de uso básicas |
| `#osmmorehelp` | Muestra ayuda adicional detallada |
| `#osmstatus` | Estado del gateway (activo, Internet, colas) |
| `#osmcount` | Conteo de notas creadas (hoy + total) |
| `#osmlist [n]` | Lista últimas `n` notas (default: 5, max: 20) |
| `#osmqueue` | Tamaño de cola total y del nodo |
| `#osmnodes` | Lista todos los nodos conocidos en la red mesh |

Variantes aceptadas para `#osmnote`: `#osm-note`, `#osm_note`

---

## Créditos

Este proyecto fue desarrollado como parte del esfuerzo de mapeo colaborativo para comunidades en zonas con conectividad limitada.

**Desarrollado por**: OSM-Notes Project Team

**Con el apoyo de**:
- **AC3** - Apoyo técnico y validación en campo
- **NASA Lifelines** - Financiamiento y contexto de aplicación en respuesta a desastres

**Autores**: Ver [AUTHORS](AUTHORS) para la lista completa de contribuidores.

### Publicaciones

- **[OSM Diary](https://www.openstreetmap.org/user/AngocA/diary/408194)** (inglés, alto nivel) - Overview del proyecto y casos de uso
- **[osm.lat Blog](https://www.osm.lat/reportes-en-terreno-sin-internet-lora-mesh-meshtastic-%e2%86%92-notas-osm-con-gateway-en-raspberry-pi/)** (español, técnico) - Detalles técnicos y guía de despliegue

---

## Licencia

Este proyecto está licenciado bajo **GPL-3.0**. Ver archivo [LICENSE](LICENSE).

Para información sobre cómo citar este software, ver [CITATION.cff](CITATION.cff).

---

## Contribuciones

Las contribuciones son bienvenidas. Por favor:

1. Fork el proyecto: https://github.com/OSM-Notes/osm-mesh-notes-gateway
2. Crea una rama para tu feature
3. Commit tus cambios
4. Push a la rama
5. Abre un Pull Request

Ver **[CONTRIBUTING.md](CONTRIBUTING.md)** para más detalles.

---

## Soporte

Para reportar problemas o solicitar features, abre un issue en GitHub:
https://github.com/OSM-Notes/osm-mesh-notes-gateway/issues

Para problemas comunes, consulta **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)**.

---

## Troubleshooting Rápido

### El servicio no inicia o no se conecta al dispositivo

**1. Verificar logs del servicio:**
```bash
# Ver logs en tiempo real
sudo journalctl -u lora-osmnotes -f

# Ver últimos 50 líneas
sudo journalctl -u lora-osmnotes -n 50

# Ver logs desde hoy
sudo journalctl -u lora-osmnotes --since today
```

**2. Verificar permisos del puerto serial:**
```bash
# Detectar dispositivo automáticamente
bash scripts/detect_serial.sh

# Verificar permisos manualmente
ls -l /dev/ttyACM0  # o /dev/ttyUSB0 según tu dispositivo

# Si no tienes permisos, agregar usuario a grupo dialout
sudo usermod -a -G dialout $USER
# IMPORTANTE: Cerrar sesión y volver a iniciar para aplicar cambios
```

**3. Verificar que el dispositivo está conectado:**
```bash
# Ver dispositivos USB conectados
lsusb | grep -i meshtastic

# Ver dispositivos seriales disponibles
ls -l /dev/ttyACM* /dev/ttyUSB*

# Verificar que el puerto configurado existe
cat /var/lib/lora-osmnotes/.env | grep SERIAL_PORT
```

**4. Verificar estado del servicio:**
```bash
# Estado del servicio
sudo systemctl status lora-osmnotes

# Reiniciar servicio
sudo systemctl restart lora-osmnotes

# Ver si está habilitado para iniciar al arrancar
sudo systemctl is-enabled lora-osmnotes
```

### Error: "Permission denied" o "No such file or directory"

**Problema de permisos del puerto serial:**
```bash
# Verificar grupo del usuario actual
groups

# Si no está en dialout, agregarlo
sudo usermod -a -G dialout $USER

# CERRAR SESIÓN Y VOLVER A INICIAR (requerido)
# Luego verificar:
groups | grep dialout
```

**Problema de permisos del directorio de datos:**
```bash
# Verificar permisos
ls -l /var/lib/lora-osmnotes

# Corregir permisos (ajustar usuario según tu sistema)
sudo chown -R $USER:$USER /var/lib/lora-osmnotes
# O si es para el servicio:
sudo chown -R pi:pi /var/lib/lora-osmnotes  # Ajustar según tu usuario
```

### No se reciben mensajes desde Meshtastic

**Verificar conexión serial:**
```bash
# Usar script de detección
bash scripts/detect_serial.sh

# Probar conexión directa (requiere permisos)
sudo screen /dev/ttyACM0 9600
# Presionar Ctrl+A luego K para salir
```

**Verificar configuración:**
```bash
# Ver puerto configurado
cat /var/lib/lora-osmnotes/.env | grep SERIAL_PORT

# Ver logs para errores de conexión
sudo journalctl -u lora-osmnotes | grep -i "serial\|connection\|error"
```

### No se envían notas a OSM

**Verificar conexión a Internet:**
```bash
ping -c 3 api.openstreetmap.org
curl -I https://api.openstreetmap.org/api/0.6/notes.json
```

**Verificar logs:**
```bash
# Buscar errores relacionados con OSM
sudo journalctl -u lora-osmnotes | grep -i "osm\|error\|failed"

# Ver estado de notas en la base de datos
sudo sqlite3 /var/lib/lora-osmnotes/gateway.db "SELECT local_queue_id, status, last_error FROM notes WHERE status='pending' LIMIT 10;"
```

**Nota:** El sistema respeta un mínimo de 3 segundos entre envíos. Si hay muchas notas pendientes, puede tardar.

### Más ayuda

Para problemas más complejos o detallados, consulta la **[guía completa de troubleshooting](docs/TROUBLESHOOTING.md)**.

---

## Notas Técnicas

### Validación GPS

El sistema valida la posición GPS antes de crear notas:
- **Sin GPS**: Rechaza si no hay posición en cache
- **GPS viejo (>60s)**: Rechaza con mensaje de error
- **GPS aproximado (15-60s)**: Acepta pero marca como "posición aproximada"
- **GPS reciente (≤15s)**: Acepta normalmente

### Deduplicación

El sistema evita crear notas duplicadas si coinciden:
- Mismo `node_id` emisor
- Texto normalizado idéntico
- Ubicación muy cercana (redondeada a 4 decimales ≈ 11m)
- Mismo bucket temporal de 120 segundos

### Store-and-Forward

El sistema usa SQLite para almacenar reportes localmente cuando no hay Internet, garantizando que ningún reporte se pierda. Los reportes pendientes se envían automáticamente cuando se restaura la conexión.

---

## Estructura del Proyecto

```
.
├── src/gateway/          # Código fuente principal
├── tests/                # Tests con pytest
├── scripts/              # Scripts de instalación y utilidades
│   ├── install_pi.sh    # Instalación automática
│   └── detect_serial.sh # Detección de dispositivos seriales
├── systemd/              # Archivos systemd
├── docs/                 # Documentación técnica
├── README.md             # Este archivo
├── CONTRIBUTING.md       # Guía de contribución
├── CHANGELOG.md          # Historial de cambios
├── CITATION.cff          # Información de citación
└── AUTHORS               # Autores y contribuidores
```

---

## Testing

```bash
# Instalar dependencias de desarrollo
pip install -e ".[dev]"

# Ejecutar tests
pytest

# Con cobertura
pytest --cov=gateway --cov-report=html
```
