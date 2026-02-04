# Troubleshooting Guide

## Problemas Comunes y Soluciones

### Error: "Failed to determine user credentials: No such process"

**Síntoma:**
```
lora-osmnotes.service: Failed to determine user credentials: No such process
lora-osmnotes.service: Failed at step USER spawning /opt/lora-osmnotes/bin/python: No such process
```

**Causa:** El servicio systemd está configurado para ejecutarse como usuario `pi`, pero ese usuario no existe en el sistema.

**Solución:**

1. **Verificar qué usuario existe:**
```bash
id pi
id ubuntu
whoami
```

2. **Editar el servicio systemd:**
```bash
sudo systemctl edit --full lora-osmnotes.service
```

3. **Cambiar la línea `User=pi` por el usuario correcto:**
```ini
[Service]
User=tu_usuario  # Reemplazar con el usuario que existe
Group=dialout
```

4. **Recargar y reiniciar:**
```bash
sudo systemctl daemon-reload
sudo systemctl restart lora-osmnotes
```

**Alternativa:** Reinstalar usando el script que detecta automáticamente el usuario:
```bash
sudo bash scripts/install_pi.sh
```

### El servicio no inicia

**Verificar logs:**
```bash
sudo journalctl -u lora-osmnotes -n 50 --no-pager
```

**Verificar permisos del puerto serial:**
```bash
ls -l /dev/ttyACM0
# Si no tiene permisos:
sudo chmod 666 /dev/ttyACM0  # Temporal para pruebas
```

**Verificar que el usuario esté en grupo dialout:**
```bash
groups
# Si no está en dialout:
sudo usermod -a -G dialout $USER
# Cerrar sesión y volver a iniciar
```

### No se reciben mensajes

**Verificar conexión serial:**
```bash
# Verificar dispositivo
lsusb | grep -i meshtastic
ls -l /dev/ttyACM* /dev/ttyUSB*

# Probar conexión directa (requiere permisos)
sudo screen /dev/ttyACM0 9600
# Presionar Ctrl+A luego K para salir
```

**Verificar configuración:**
```bash
cat /var/lib/lora-osmnotes/.env | grep SERIAL_PORT
```

**Verificar logs:**
```bash
sudo journalctl -u lora-osmnotes -f
```

### No se envían notas a OSM

**Verificar conexión a Internet:**
```bash
ping -c 3 api.openstreetmap.org
curl -I https://api.openstreetmap.org/api/0.6/notes.json
```

**Verificar rate limiting:**
El sistema respeta un mínimo de 3 segundos entre envíos. Si hay muchas notas pendientes, puede tardar.

**Verificar logs para errores:**
```bash
sudo journalctl -u lora-osmnotes | grep -i "osm\|error\|failed"
```

**Verificar estado de notas en DB:**
```bash
sudo sqlite3 /var/lib/lora-osmnotes/gateway.db "SELECT local_queue_id, status, last_error FROM notes WHERE status='pending' LIMIT 10;"
```

### Error de permisos en /var/lib/lora-osmnotes

**Síntoma:**
```
PermissionError: [Errno 13] Permission denied: '/var/lib/lora-osmnotes'
```

**Solución:**
```bash
sudo chown -R $USER:$USER /var/lib/lora-osmnotes
# O si es para el servicio:
sudo chown -R pi:pi /var/lib/lora-osmnotes  # Ajustar usuario según corresponda
```

### El servicio se reinicia constantemente

**Verificar logs completos:**
```bash
sudo journalctl -u lora-osmnotes --since "10 minutes ago" --no-pager
```

**Verificar si es problema de usuario (ver error anterior)**

**Verificar si el puerto serial existe:**
```bash
ls -l /dev/ttyACM0
# Si no existe, verificar dispositivo USB
lsusb
```

### Modo Dry-Run

Para probar sin enviar DMs ni crear notas en OSM:

```bash
# Editar .env
sudo nano /var/lib/lora-osmnotes/.env
# Cambiar: DRY_RUN=true

# Reiniciar servicio
sudo systemctl restart lora-osmnotes

# Verificar logs
sudo journalctl -u lora-osmnotes -f
# Deberías ver [DRY_RUN] en los logs
```

### Verificar estado del servicio

```bash
# Estado del servicio
sudo systemctl status lora-osmnotes

# Ver si está activo y corriendo
sudo systemctl is-active lora-osmnotes
sudo systemctl is-enabled lora-osmnotes

# Ver procesos relacionados
ps aux | grep gateway
```

### Problemas con el entorno virtual

**Si el entorno virtual no se encuentra:**
```bash
# Verificar que existe
ls -l /opt/lora-osmnotes/bin/python

# Si no existe, reinstalar
sudo bash scripts/install_pi.sh
```

**Si hay problemas con dependencias:**
```bash
# Activar entorno virtual manualmente
source /opt/lora-osmnotes/bin/activate

# Reinstalar dependencias
pip install -r /ruta/al/proyecto/requirements.txt
```

### Verificar configuración

**Ver todas las variables de entorno:**
```bash
sudo systemctl show lora-osmnotes.service | grep Environment
```

**Ver archivo .env:**
```bash
sudo cat /var/lib/lora-osmnotes/.env
```

### Resetear base de datos

**⚠️ ADVERTENCIA: Esto eliminará todos los datos**

```bash
# Detener servicio
sudo systemctl stop lora-osmnotes

# Hacer backup (opcional)
sudo cp /var/lib/lora-osmnotes/gateway.db /var/lib/lora-osmnotes/gateway.db.backup

# Eliminar base de datos
sudo rm /var/lib/lora-osmnotes/gateway.db

# Reiniciar servicio (creará nueva DB)
sudo systemctl start lora-osmnotes
```

### Verificar mensajes en la base de datos

```bash
# Instalar sqlite3 si no está instalado
sudo apt-get install sqlite3

# Ver todas las notas
sudo sqlite3 /var/lib/lora-osmnotes/gateway.db "SELECT * FROM notes ORDER BY created_at DESC LIMIT 10;"

# Ver notas pendientes
sudo sqlite3 /var/lib/lora-osmnotes/gateway.db "SELECT local_queue_id, node_id, text_original, status, last_error FROM notes WHERE status='pending';"

# Ver estadísticas
sudo sqlite3 /var/lib/lora-osmnotes/gateway.db "SELECT node_id, COUNT(*) as total, SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending FROM notes GROUP BY node_id;"
```

### Problemas de red

**Verificar conectividad:**
```bash
# Ping a OSM API
ping -c 3 api.openstreetmap.org

# Test HTTP
curl -v https://api.openstreetmap.org/api/0.6/notes.json

# Verificar DNS
nslookup api.openstreetmap.org
```

**Si hay proxy o firewall:**
- Verificar configuración de proxy en sistema
- Verificar reglas de firewall
- El servicio necesita acceso saliente HTTPS (puerto 443)

### Logs detallados

**Activar modo DEBUG:**
```bash
# Editar .env
sudo nano /var/lib/lora-osmnotes/.env
# Cambiar: LOG_LEVEL=DEBUG

# Reiniciar
sudo systemctl restart lora-osmnotes

# Ver logs detallados
sudo journalctl -u lora-osmnotes -f
```

### Contacto y Soporte

Si el problema persiste:
1. Revisar logs completos: `sudo journalctl -u lora-osmnotes --since "1 hour ago" > logs.txt`
2. Verificar configuración: `sudo cat /var/lib/lora-osmnotes/.env`
3. Verificar estado del sistema: `sudo systemctl status lora-osmnotes`
4. Abrir issue en [GitHub](https://github.com/OSM-Notes/osm-mesh-notes-gateway/issues) con los logs y configuración (sin datos sensibles)
