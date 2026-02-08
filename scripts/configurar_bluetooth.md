# Configurar Bluetooth en Heltec V3 desde Raspberry Pi

## Problema

Si deshabilitaste el Bluetooth en el Heltec V3 y no puedes accederlo desde el celular, puedes habilitarlo nuevamente desde el Raspberry Pi usando la línea de comandos.

## Solución Rápida

### Opción 1: Usar el script automático (Recomendado)

```bash
# Conectarte al Raspberry Pi
ssh usuario@192.168.2.121

# Ejecutar el script (detecta automáticamente el puerto)
cd /ruta/al/proyecto/LoRa-Meshtastic-OSM-notes-bot
sudo bash scripts/habilitar_bluetooth.sh

# El script detecta automáticamente:
# - Primero busca en /var/lib/lora-osmnotes/.env (SERIAL_PORT)
# - Luego busca /dev/ttyUSB* (Heltec V3 generalmente usa este)
# - Finalmente busca /dev/ttyACM* (otros dispositivos)

# O especificar el puerto manualmente si es necesario
sudo bash scripts/habilitar_bluetooth.sh /dev/ttyUSB0
```

El script:
1. ✅ Detiene el servicio `lora-osmnotes` temporalmente
2. ✅ Habilita Bluetooth en el Heltec V3
3. ✅ Verifica que se haya habilitado
4. ✅ Reinicia el servicio automáticamente

### Opción 2: Comandos manuales

Si prefieres hacerlo manualmente:

```bash
# 1. Detener el servicio
sudo systemctl stop lora-osmnotes

# 2. Esperar un momento para que libere el puerto
sleep 2

# 3. Habilitar Bluetooth (Heltec V3 generalmente usa /dev/ttyUSB0)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.enabled true
# Si tu dispositivo usa otro puerto, ajusta según corresponda:
# sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyACM0 --set bluetooth.enabled true

# 4. Esperar a que el dispositivo reinicie (5 segundos)
sleep 5

# 5. Reiniciar el servicio
sudo systemctl start lora-osmnotes
```

## Verificar que funcionó

1. **Desde el Raspberry Pi:**
   ```bash
   # Para Heltec V3 (generalmente /dev/ttyUSB0)
   sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --info | grep -i bluetooth
   
   # O si usa otro puerto:
   sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyACM0 --info | grep -i bluetooth
   ```

2. **Desde el celular:**
   - Abre la app Meshtastic
   - Busca dispositivos Bluetooth cercanos
   - Deberías ver el Heltec V3 listado como "Meshtastic" o con un nombre similar
   - Conecta desde la app

## Deshabilitar Bluetooth nuevamente

Si necesitas deshabilitarlo otra vez:

```bash
sudo bash scripts/deshabilitar_bluetooth.sh
```

O manualmente:
```bash
sudo systemctl stop lora-osmnotes
# Para Heltec V3 (generalmente /dev/ttyUSB0)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.enabled false
sudo systemctl start lora-osmnotes
```

## Configuración adicional de Bluetooth

### Cambiar modo de emparejamiento

```bash
# Modo PIN aleatorio (por defecto)
# Para Heltec V3 (generalmente /dev/ttyUSB0)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.mode RANDOM_PIN

# Modo PIN fijo
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.mode FIXED_PIN

# Sin PIN (menos seguro)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.mode NO_PIN
```

### Configurar PIN fijo

```bash
# Establecer PIN fijo (ejemplo: 111111)
# Para Heltec V3 (generalmente /dev/ttyUSB0)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 --set bluetooth.fixed_pin 111111
```

### Configurar múltiples opciones a la vez

```bash
# Para Heltec V3 (generalmente /dev/ttyUSB0)
sudo /opt/lora-osmnotes/bin/meshtastic --port /dev/ttyUSB0 \
  --set bluetooth.enabled true \
  --set bluetooth.mode FIXED_PIN \
  --set bluetooth.fixed_pin 123456
```

**Nota:** El dispositivo se reinicia después de cada comando `--set`, así que es mejor combinarlos en un solo comando.

## Troubleshooting

### Error: "Device not found"

```bash
# Verificar qué dispositivos están disponibles
# Heltec V3 generalmente aparece como /dev/ttyUSB0 o /dev/ttyUSB1
ls -l /dev/ttyUSB* /dev/ttyACM*

# Usar el script de detección automática
bash scripts/detect_serial.sh

# Ver qué puerto está configurado en el servicio
cat /var/lib/lora-osmnotes/.env | grep SERIAL_PORT
```

### Error: "Permission denied"

```bash
# Verificar permisos
ls -l /dev/ttyACM0

# Agregar usuario al grupo dialout (si es necesario)
sudo usermod -a -G dialout $USER
# Cerrar sesión y volver a iniciar
```

### El servicio no se reinicia

```bash
# Verificar estado
sudo systemctl status lora-osmnotes

# Ver logs
sudo journalctl -u lora-osmnotes -n 50

# Reiniciar manualmente
sudo systemctl restart lora-osmnotes
```

### No aparece en el celular

1. Verificar que Bluetooth esté habilitado en el celular
2. Verificar que el Heltec V3 esté encendido
3. Intentar desconectar y reconectar el dispositivo USB
4. Reiniciar el Heltec V3 (desconectar y volver a conectar USB)

## Notas importantes

- ⚠️ El dispositivo se **reinicia automáticamente** después de cambiar la configuración de Bluetooth
- ⚠️ El servicio `lora-osmnotes` debe estar **detenido** mientras cambias la configuración
- ✅ El script maneja esto automáticamente
- ✅ Puedes usar Bluetooth y USB simultáneamente (no hay conflicto)
