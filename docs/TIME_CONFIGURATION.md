# Configuración de Tiempo y Sincronización

Este documento describe las consideraciones y recomendaciones para configurar el tiempo del sistema en el gateway, especialmente para despliegues sin conexión a Internet constante.

---

## Problema: Raspberry Pi NO tiene pila interna

**Los Raspberry Pi NO tienen pila CMOS/batería interna** como las PCs tradicionales. Esto significa que:

- Al apagarse, el tiempo se pierde
- Al encenderse sin Internet, el tiempo puede estar incorrecto (fecha de compilación del kernel o fecha por defecto)
- Sin Internet y sin RTC hardware, el sistema no puede saber la hora real

### Consecuencias para el sistema

Si el tiempo del sistema es incorrecto:

- **Validación GPS fallará**: El sistema calcula la edad de posiciones usando `time.time()`. Si el tiempo está mal, posiciones recientes pueden ser rechazadas como "muy viejas" o viceversa.
- **Deduplicación puede fallar**: Usa buckets temporales de 120s. Con tiempo incorrecto, mensajes duplicados pueden no ser detectados.
- **`#osmcount` mostrará conteos incorrectos**: Calcula "hoy" usando la zona horaria del servidor. Si el tiempo está mal, los conteos serán incorrectos.
- **Las notas se guardarán con timestamps incorrectos**: Las notas en la base de datos y en OSM tendrán fechas/horas incorrectas.

---

## Soluciones Recomendadas

### 1. NTP (Network Time Protocol) - Cuando hay Internet

**Raspberry Pi OS incluye NTP por defecto** usando `systemd-timesyncd`. El servicio se sincroniza automáticamente con servidores NTP cuando hay conexión a Internet.

**Verificar estado de NTP:**
```bash
timedatectl status
```

**Si no está sincronizado:**
```bash
sudo timedatectl set-ntp true
```

**Limitaciones:**
- Requiere conexión a Internet al menos ocasionalmente
- Si el sistema arranca sin Internet, el tiempo puede estar incorrecto hasta que se conecte

---

### 2. RTC Hardware (Recomendado para despliegues sin Internet)

Si el Raspberry Pi puede operar sin Internet (o con Internet intermitente), se **recomienda fuertemente** instalar un **módulo RTC (Real-Time Clock) hardware**.

#### Opciones comunes

- **DS1307**: RTC básico, I2C, requiere batería externa
- **DS3231**: Más preciso, I2C, incluye compensación de temperatura, requiere batería externa
- **PCF8523**: Bajo consumo, I2C, requiere batería externa

#### Instalación básica (DS3231)

1. **Conectar módulo RTC** al bus I2C del Raspberry Pi (SDA/SCL)
2. **Habilitar I2C**: 
   ```bash
   sudo raspi-config
   # Interface Options → I2C → Enable
   ```
3. **Instalar herramientas**:
   ```bash
   sudo apt-get update
   sudo apt-get install -y i2c-tools
   ```
4. **Verificar detección**:
   ```bash
   sudo i2cdetect -y 1
   # Debería mostrar la dirección del RTC (típicamente 0x68 para DS3231)
   ```
5. **Configurar kernel para usar RTC**:
   ```bash
   # Agregar al /boot/config.txt (para DS3231):
   dtoverlay=i2c-rtc,ds3231
   
   # Reiniciar
   sudo reboot
   ```
6. **Verificar que funciona**:
   ```bash
   # Ver tiempo del RTC
   sudo hwclock -r
   
   # Sincronizar tiempo del sistema con RTC
   sudo hwclock -s
   
   # Verificar que el tiempo es correcto
   date
   ```

#### Configuración automática

El sistema debe leer del RTC al arrancar y escribir al RTC periódicamente. Con la configuración correcta del kernel (`dtoverlay=i2c-rtc,ds3231`), esto debería funcionar automáticamente.

**Verificar configuración:**
```bash
# Ver si el RTC está siendo usado
ls -l /dev/rtc*

# Ver tiempo del RTC
sudo hwclock -r

# Ver estado de sincronización
timedatectl status
```

---

## Propuesta: Ajuste Automático de Timestamps

### Idea

Cuando el servidor se conecta a Internet por primera vez después de arrancar sin tiempo correcto:

1. **Detectar desfase**: Al sincronizar con NTP, detectar si el tiempo del sistema estaba muy desfasado
2. **Calcular corrección**: Calcular el desfase entre el tiempo incorrecto usado y el tiempo real
3. **Ajustar timestamps**: Aplicar el mismo desfase a todas las notas en la base de datos que fueron creadas antes de la sincronización

### Consideraciones

**Ventajas:**
- Corrige timestamps históricos automáticamente
- No requiere hardware adicional (RTC)
- Útil para despliegues con Internet intermitente

**Desventajas y limitaciones:**
- **Notas ya enviadas a OSM**: No se pueden corregir timestamps de notas que ya fueron enviadas a OSM (las notas en OSM tienen sus propios timestamps)
- **Detección de desfase**: ¿Cómo saber si el tiempo estaba mal? Podría detectarse cuando NTP sincroniza por primera vez después del arranque
- **Desfases grandes**: Si el tiempo estaba muy desfasado (años), podría causar problemas
- **Complejidad**: Requiere lógica adicional para detectar y aplicar correcciones
- **Riesgo de corrupción**: Modificar timestamps históricos puede afectar deduplicación y otros cálculos

### Implementación

Esta funcionalidad **está implementada** en el sistema. El gateway automáticamente:

1. **Guarda timestamp de arranque**: Al iniciar el servicio, guarda `time.time()` en la tabla `system_state`
2. **Detecta primera sincronización NTP**: En cada ciclo del worker thread, verifica si NTP está sincronizado usando `timedatectl`
3. **Calcula desfase**: Compara el tiempo actual (correcto después de NTP) con el timestamp de arranque guardado
4. **Aplica corrección solo a notas pendientes**: Solo ajusta timestamps de notas con `status='pending'` que fueron creadas antes de la sincronización
5. **No toca notas enviadas**: No modifica `created_at` de notas con `status='sent'` (ya están en OSM con su timestamp original)

**Características:**
- Solo corrige si el desfase es significativo (> 60 segundos)
- Solo se aplica una vez por sesión (usa bandera `time_correction_applied`)
- Ignora offsets muy pequeños (< 1 segundo)
- Funciona automáticamente sin configuración adicional

**Nota**: Aunque esta funcionalidad está disponible, se recomienda usar RTC hardware como solución principal para despliegues sin Internet constante, ya que evita el problema desde el inicio.

---

## Configuración de Zona Horaria

La zona horaria se configura en `/var/lib/lora-osmnotes/.env`:

```bash
TZ=America/Bogota
```

O a nivel del sistema:

```bash
sudo timedatectl set-timezone America/Bogota
```

**Importante**: La zona horaria solo afecta la visualización y cálculos locales. Las notas siempre se almacenan en UTC en la base de datos, igual que en OSM.

---

## Manejo del Tiempo en el Sistema

### Almacenamiento

- Las notas se guardan en **UTC** (`datetime.utcnow()`) en la base de datos
- Esto coincide con cómo OSM almacena los timestamps de las notas

### Visualización

- **`#osmlist`**: Muestra la hora convertida a la zona horaria del servidor con indicador de zona horaria (ej: `2026-02-09 14:30 (COT)`)
- **`#osmcount`**: Muestra conteos calculados usando la zona horaria del servidor para determinar "hoy"

### Sincronización de mensajes

- Los mensajes Meshtastic pueden incluir timestamps, pero el sistema usa `time.time()` del servidor para crear las notas
- **No hay sincronización automática** con timestamps de Meshtastic
- El tiempo del servidor debe estar sincronizado vía NTP o RTC para que los cálculos funcionen correctamente

---

## Recomendación Final

Para despliegues en producción, especialmente aquellos que pueden operar sin Internet:

1. **Instalar RTC hardware** (DS3231 recomendado por precisión)
2. **Configurar NTP** para sincronización cuando hay Internet disponible
3. **Verificar periódicamente** que el tiempo está correcto: `timedatectl status`

Esto garantiza que el sistema tenga tiempo preciso incluso después de reinicios sin Internet, evitando problemas con validación GPS, deduplicación y timestamps incorrectos.
