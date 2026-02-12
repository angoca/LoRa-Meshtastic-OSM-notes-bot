# Ejemplos de Uso y Casos de Uso Reales

Este documento proporciona ejemplos prácticos de cómo usar el gateway OSM Mesh Notes en situaciones reales.

---

## Casos de Uso Reales

### 1. Mapeo Post-Desastre

**Situación**: Después de un terremoto o inundación, la infraestructura de telecomunicaciones está caída. Los equipos de respuesta necesitan documentar daños en edificios e infraestructura.

**Solución**:
- Desplegar gateway en un punto estratégico con acceso a Internet (cuando esté disponible)
- Equipos en campo con dispositivos Meshtastic (T-Echo) pueden enviar reportes sin Internet
- Los reportes se almacenan localmente y se envían a OSM cuando hay conexión

**Ejemplo de mensaje**:
```
#osmnote Edificio colapsado en esquina Calle Principal y Avenida Central. 
Peligro de derrumbe. Evacuar área.
```

**Resultado**: Nota creada en OSM con ubicación GPS del dispositivo, visible para equipos de respuesta y mapeadores.

---

### 2. Mapeo Comunitario en Zonas Rurales

**Situación**: Comunidad rural sin cobertura de Internet estable quiere mapear mejoras necesarias en infraestructura (caminos, puentes, puntos de agua).

**Solución**:
- Gateway instalado en un punto con acceso intermitente a Internet (ej: escuela con WiFi)
- Vecinos con dispositivos Meshtastic pueden reportar problemas desde cualquier punto del área de cobertura LoRa
- Los reportes se sincronizan cuando el gateway tiene Internet

**Ejemplo de mensaje**:
```
#osmnote Puente sobre quebrada necesita reparación. 
Viga principal agrietada. Tránsito peligroso.
```

**Resultado**: Nota en OSM que puede ser vista por autoridades locales y organizaciones de desarrollo.

---

### 3. Documentación de Cambios en el Territorio

**Situación**: Organización ambiental quiere documentar cambios en uso de suelo, deforestación, o construcción no autorizada en áreas remotas.

**Solución**:
- Gateway móvil o fijo en área de interés
- Observadores en campo documentan cambios usando dispositivos Meshtastic
- Reportes automáticos a OSM para seguimiento a largo plazo

**Ejemplo de mensaje**:
```
#osmnote Nueva construcción en zona protegida. 
Coordenadas: 4.1234, -73.5678. Sin permisos visibles.
```

**Resultado**: Historial de cambios documentado en OSM con timestamps precisos.

---

### 4. Mapeo de Infraestructura Pública

**Situación**: Municipalidad quiere inventariar el estado de infraestructura pública (parques, alumbrado, señalización) con participación ciudadana.

**Solución**:
- Gateway en oficina municipal con Internet estable
- Ciudadanos con dispositivos Meshtastic reportan problemas durante sus recorridos
- Reportes automáticos a OSM para seguimiento y planificación

**Ejemplo de mensaje**:
```
#osmnote Poste de alumbrado caído en Parque Central. 
Cableado expuesto. Peligro eléctrico.
```

**Resultado**: Base de datos pública de problemas de infraestructura visible para todos.

---

## Ejemplos de Comandos

### Comandos Básicos

#### Ver estado del gateway
```
#osmstatus
```
**Respuesta esperada**:
```
✅ Gateway activo
🌐 Internet: Conectado
📊 Cola: 0 notas pendientes
📡 Nodos: 5 conocidos
```

#### Crear una nota
```
#osmnote Bache grande en carretera principal. 
Necesita reparación urgente.
```
**Respuesta esperada**:
```
✅ Nota creada: Q-12345
📍 Ubicación: Barrio Centro
🌐 Ver en OSM: https://www.openstreetmap.org/note/456789
```

#### Ver ayuda
```
#osmhelp
```
**Respuesta**: Mensaje con todos los comandos disponibles.

#### Ver ayuda extendida
```
#osmmorehelp
```
**Respuesta**: Información detallada sobre configuración y uso avanzado.

---

## Ejemplos de Flujos Completos

### Flujo 1: Reporte Simple con Internet

1. **Usuario en campo** envía desde T-Echo:
   ```
   #osmnote Fuente de agua contaminada en vereda La Esperanza
   ```

2. **Gateway recibe** el mensaje por LoRa

3. **Gateway valida**:
   - ✅ Comando `#osmnote` detectado
   - ✅ GPS válido (posición reciente del dispositivo)
   - ✅ Texto normalizado

4. **Gateway crea nota** en OSM inmediatamente (hay Internet)

5. **Gateway responde** al usuario:
   ```
   ✅ Nota creada: Q-12345
   📍 Ubicación: Vereda La Esperanza
   🌐 Ver en OSM: https://www.openstreetmap.org/note/456789
   ```

---

### Flujo 2: Reporte sin Internet (Store-and-Forward)

1. **Usuario en campo** envía desde T-Echo:
   ```
   #osmnote Árbol caído bloqueando camino rural
   ```

2. **Gateway recibe** el mensaje por LoRa

3. **Gateway valida** y crea entrada en base de datos local
   - Estado: `pending` (pendiente de envío)
   - ID local: `Q-12346`

4. **Gateway responde** al usuario:
   ```
   ⏳ Nota en cola: Q-12346
   Se enviará cuando haya Internet
   ```

5. **Más tarde**, cuando el gateway tiene Internet:
   - Worker procesa cola de notas pendientes
   - Envía nota a OSM
   - Actualiza estado a `sent`
   - Nota visible en OSM

---

### Flujo 3: Múltiples Reportes del Mismo Evento

**Escenario**: Varios usuarios reportan el mismo problema desde diferentes ubicaciones.

1. **Usuario A** envía:
   ```
   #osmnote Accidente de tránsito en intersección principal
   ```

2. **Usuario B** envía (5 minutos después, desde otra ubicación):
   ```
   #osmnote Accidente de tránsito en intersección principal
   ```

3. **Gateway detecta duplicado**:
   - Texto normalizado idéntico
   - Ubicaciones cercanas (dentro del radio de deduplicación)
   - Mismo bucket temporal (120 segundos)

4. **Gateway responde** al Usuario B:
   ```
   ⚠️ Nota duplicada detectada
   Ya existe: Q-12345
   ```

5. **Solo una nota** se crea en OSM (evita spam)

---

## Ejemplos de Mensajes Válidos

### ✅ Mensajes que funcionan

```
#osmnote Bache en carretera
```

```
#osmnote Poste de luz caído en esquina
```

```
#osmnote Fuente de agua sin funcionar
```

```
#osmnote Nueva construcción sin permisos
```

```
#osmnote Árbol caído bloqueando vía
```

```
#osmnote Señal de tránsito dañada
```

```
#osmnote Punto de reciclaje necesita mantenimiento
```

---

## Ejemplos de Mensajes Inválidos

### ❌ Mensajes que NO funcionan

**Sin comando**:
```
Bache en carretera
```
→ El gateway ignora mensajes sin comandos

**Comando incorrecto**:
```
#osm Bache en carretera
```
→ Debe ser `#osmnote`, no `#osm`

**Sin GPS válido**:
```
#osmnote Bache en carretera
```
→ Si el dispositivo no tiene GPS reciente, el gateway rechaza:
```
⚠️ No hay GPS válido reciente
Asegúrate de que tu dispositivo tenga señal GPS
```

**Texto demasiado largo**:
```
#osmnote [texto de más de 200 caracteres...]
```
→ El gateway rechaza:
```
⚠️ Mensaje demasiado largo
Máximo 200 caracteres
```

---

## Ejemplos de Uso con Quick Chat

### Usando "Append to message" en Meshtastic

En la app Meshtastic, puedes usar "Quick Chat" para agregar texto a un mensaje existente:

1. **Primer mensaje**:
   ```
   #osmnote Problema en
   ```

2. **Segundo mensaje** (usando "Append to message"):
   ```
   intersección principal
   ```

3. **Resultado**: El gateway recibe el mensaje completo:
   ```
   #osmnote Problema en intersección principal
   ```

**Nota**: Esto es útil para mensajes largos que exceden el límite de un solo mensaje Meshtastic.

---

## Ejemplos de Configuración para Diferentes Escenarios

### Escenario 1: Gateway con Internet Estable

**Configuración recomendada**:
- `DRY_RUN=false` (modo producción)
- `GPS_VALIDATION_DISABLED=false` (validación GPS activa)
- `DAILY_BROADCAST_ENABLED=true` (broadcast diario activo)
- `LOG_LEVEL=INFO` (logs informativos)

**Uso**: Oficina municipal, centro comunitario con WiFi estable.

---

### Escenario 2: Gateway con Internet Intermitente

**Configuración recomendada**:
- `DRY_RUN=false`
- `GPS_VALIDATION_DISABLED=false`
- `DAILY_BROADCAST_ENABLED=false` (evitar spam en reinicios)
- `LOG_LEVEL=INFO`
- RTC hardware recomendado (ver `TIME_CONFIGURATION.md`)

**Uso**: Zona rural con conexión intermitente, gateway móvil.

---

### Escenario 3: Gateway de Prueba/Desarrollo

**Configuración recomendada**:
- `DRY_RUN=true` (no crea notas reales en OSM)
- `LOG_LEVEL=DEBUG` (logs detallados)
- `GPS_VALIDATION_DISABLED=false`

**Uso**: Desarrollo, pruebas, demostraciones.

---

## Ejemplos de Troubleshooting

### Problema: "No hay GPS válido reciente"

**Causa**: El dispositivo Meshtastic no ha recibido posición GPS reciente.

**Soluciones**:
1. Asegúrate de estar al aire libre con vista al cielo
2. Espera unos segundos para que el GPS se sincronice
3. Verifica que el dispositivo tiene GPS habilitado
4. Intenta enviar el mensaje nuevamente

**Ejemplo**:
```
Usuario: #osmnote Bache en carretera
Gateway: ⚠️ No hay GPS válido reciente
         Asegúrate de que tu dispositivo tenga señal GPS
         Intenta nuevamente en unos segundos
```

---

### Problema: "Mensaje duplicado"

**Causa**: Ya existe una nota similar creada recientemente.

**Solución**: El gateway ya procesó este reporte. No es necesario enviarlo nuevamente.

**Ejemplo**:
```
Usuario: #osmnote Bache en carretera
Gateway: ⚠️ Nota duplicada detectada
         Ya existe: Q-12345
         Ver en OSM: https://www.openstreetmap.org/note/456789
```

---

### Problema: "Mensaje demasiado largo"

**Causa**: El mensaje excede el límite de caracteres.

**Solución**: Acorta el mensaje o usa múltiples mensajes con "Append to message".

**Ejemplo**:
```
Usuario: #osmnote [texto muy largo de más de 200 caracteres...]
Gateway: ⚠️ Mensaje demasiado largo
         Máximo 200 caracteres
         Usa mensajes más cortos o divide en partes
```

---

## Ejemplos de Integración con OSM

### Ver notas creadas

Una vez que una nota es creada, puedes verla en:

1. **OpenStreetMap web**:
   - URL proporcionada en la respuesta del gateway
   - Ejemplo: `https://www.openstreetmap.org/note/456789`

2. **Usando comandos del gateway**:
   ```
   #osmlist
   ```
   Muestra las últimas notas con sus URLs.

3. **Consultando la base de datos**:
   ```bash
   sqlite3 /var/lib/lora-osmnotes/gateway.db \
     "SELECT osm_note_url FROM notes WHERE status='sent' LIMIT 10;"
   ```

---

## Casos de Uso por Tipo de Organización

### Organizaciones de Respuesta a Desastres

**Uso**: Documentación rápida de daños y necesidades post-desastre.

**Ejemplo**:
```
#osmnote Edificio colapsado. 10 familias afectadas. 
Necesitan refugio y alimentos.
```

**Beneficio**: Reportes inmediatos sin depender de infraestructura de telecomunicaciones.

---

### Organizaciones Ambientales

**Uso**: Monitoreo de cambios en ecosistemas, deforestación, contaminación.

**Ejemplo**:
```
#osmnote Área deforestada ilegalmente. 
Coordenadas: 4.1234, -73.5678. Evidencia fotográfica disponible.
```

**Beneficio**: Documentación con timestamps precisos para seguimiento legal.

---

### Municipalidades

**Uso**: Participación ciudadana en mantenimiento de infraestructura pública.

**Ejemplo**:
```
#osmnote Semáforo no funciona en intersección peligrosa. 
Necesita reparación urgente.
```

**Beneficio**: Sistema de reportes ciudadanos sin necesidad de apps móviles complejas.

---

### Comunidades Rurales

**Uso**: Mapeo colaborativo de necesidades comunitarias.

**Ejemplo**:
```
#osmnote Necesitamos punto de recarga para celulares. 
Zona sin cobertura eléctrica estable.
```

**Beneficio**: Documentación de necesidades para solicitar recursos a autoridades.

---

## Mejores Prácticas

### ✅ Hacer

- **Sé específico**: Incluye detalles útiles (ubicación, tipo de problema, urgencia)
- **Usa GPS válido**: Asegúrate de tener señal GPS antes de enviar
- **Mensajes concisos**: Respeta el límite de caracteres
- **Verifica duplicados**: Usa `#osmlist` para ver notas recientes antes de reportar

### ❌ Evitar

- **No enviar datos personales**: El sistema es público
- **No usar para emergencias médicas**: Usa servicios de emergencia oficiales
- **No spam**: El sistema detecta duplicados, pero evita enviar el mismo mensaje múltiples veces
- **No coordenadas manuales**: El sistema usa GPS automático del dispositivo

---

## Ejemplos de Respuestas del Sistema

### Respuesta de Éxito

```
✅ Nota creada: Q-12345
📍 Ubicación: Barrio Centro, Calle Principal
🌐 Ver en OSM: https://www.openstreetmap.org/note/456789

⚠️ No envíes datos personales ni información sensible.
Este sistema es público y abierto.
```

### Respuesta de Cola (sin Internet)

```
⏳ Nota en cola: Q-12346
Se enviará cuando haya Internet
📍 Ubicación: Vereda La Esperanza
```

### Respuesta de Duplicado

```
⚠️ Nota duplicada detectada
Ya existe: Q-12345
🌐 Ver nota existente: https://www.openstreetmap.org/note/456789
```

### Respuesta de Error

```
❌ Error: No hay GPS válido reciente
Asegúrate de que tu dispositivo tenga señal GPS
Intenta nuevamente en unos segundos
```

---

## Recursos Adicionales

- **[README.md](../README.md)** - Guía de inicio rápido
- **[FIELD_DEPLOYMENT_GUIDE.md](FIELD_DEPLOYMENT_GUIDE.md)** - Guía de despliegue en terreno
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Solución de problemas comunes
- **[spec.md](spec.md)** - Especificación técnica completa

---

¿Tienes un caso de uso que quieras compartir? ¡Abre un issue o pull request!
