# Formato de Mensajes Meshtastic

## Nota sobre el MVP

Este gateway MVP usa un formato simplificado de mensajes para facilitar la implementación inicial. En producción, Meshtastic usa protocolo protobuf, pero para el MVP se aceptan formatos de texto simples.

## Formatos Soportados

### Formato JSON (recomendado)

```json
{
  "from": "node_id",
  "lat": 4.6097,
  "lon": -74.0817,
  "text": "#osmnote Mensaje de prueba"
}
```

### Formato Pipe-separated

```
node_id|lat|lon|mensaje
```

Ejemplo:
```
!12345678|4.6097|-74.0817|#osmnote Mensaje de prueba
```

Si no hay GPS disponible:
```
!12345678|||#osmnote Mensaje sin GPS
```

## Integración con Meshtastic Real

Para integrar con el protocolo real de Meshtastic, se recomienda usar la biblioteca `meshtastic-python`:

```python
import meshtastic.serial_interface

interface = meshtastic.serial_interface.SerialInterface()
def onReceive(packet, interface):
    node_id = packet['from']
    text = packet.get('decoded', {}).get('text', '')
    # Extract GPS from telemetry or position packets
    # ...
    
interface.subscribe(onReceive)
```

## Comandos de Envío

### Enviar DM

Formato de comando:
```
DM|node_id|mensaje
```

Ejemplo:
```
DM|!12345678|✅ Reporte recibido
```

### Enviar Broadcast

Formato de comando:
```
BC|mensaje
```

Ejemplo:
```
BC|ℹ️ Gateway de notas OSM activo
```

## Notas de Implementación

- El parser actual es simplificado y espera mensajes terminados en `\n`
- Los mensajes se leen línea por línea desde el buffer serial
- El baudrate por defecto es 9600
- Se requiere reconexión automática en caso de desconexión

## Migración a Protobuf

Para migrar a protobuf real:

1. Instalar `meshtastic-python`:
```bash
pip install meshtastic
```

2. Modificar `meshtastic_serial.py` para usar `SerialInterface` de meshtastic
3. Implementar handlers para diferentes tipos de paquetes (text, position, telemetry)
4. Extraer GPS de paquetes de posición/telemetría
