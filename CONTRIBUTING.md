# Guía de Contribución

Gracias por tu interés en contribuir al proyecto [osm-mesh-notes-gateway](https://github.com/OSM-Notes/osm-mesh-notes-gateway).

## Estructura del Proyecto

```
.
├── src/gateway/          # Código fuente principal
│   ├── main.py          # Aplicación principal
│   ├── config.py        # Configuración
│   ├── database.py      # SQLite database
│   ├── meshtastic_serial.py  # Comunicación serial
│   ├── position_cache.py # Cache GPS
│   ├── commands.py      # Procesamiento comandos
│   ├── osm_worker.py    # Worker OSM
│   └── notifications.py # Notificaciones
├── tests/               # Tests unitarios
├── scripts/             # Scripts de utilidad
├── systemd/            # Archivos systemd
└── docs/               # Documentación adicional
```

## Configuración del Entorno de Desarrollo

### Requisitos

- Python 3.8+
- Git
- SQLite3

### Setup

```bash
# Clonar repositorio
git clone https://github.com/OSM-Notes/osm-mesh-notes-gateway.git
cd osm-mesh-notes-gateway

# Crear entorno virtual
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
pip install -e ".[dev]"  # Incluye pytest y herramientas de desarrollo
```

## Estándares de Código

### Estilo

- **PEP 8**: Seguir guía de estilo Python
- **Type Hints**: Usar type hints en funciones públicas
- **Docstrings**: Docstrings en formato Google style

### Ejemplo de Docstring

```python
def process_message(
    self,
    node_id: str,
    text: str,
    lat: Optional[float] = None,
    lon: Optional[float] = None,
) -> Tuple[str, Optional[str]]:
    """
    Process incoming message and return command type and response.
    
    Args:
        node_id: Meshtastic node ID
        text: Message text content
        lat: Optional latitude
        lon: Optional longitude
        
    Returns:
        Tuple of (command_type, response_message)
        command_type: 'osmnote', 'osmhelp', 'ignore', etc.
        response_message: Response text or None
    """
```

### Convenciones de Nombres

- **Clases**: `PascalCase` (ej: `CommandProcessor`)
- **Funciones/Métodos**: `snake_case` (ej: `process_message`)
- **Constantes**: `UPPER_SNAKE_CASE` (ej: `POS_GOOD`)
- **Variables privadas**: Prefijo `_` (ej: `_init_db`)

## Testing

### Ejecutar Tests

```bash
# Todos los tests
pytest

# Con verbose
pytest -v

# Test específico
pytest tests/test_commands.py::test_osmnote_success

# Con cobertura
pytest --cov=gateway --cov-report=html
```

### Escribir Tests

- Usar `pytest` fixtures para setup/teardown
- Mockear dependencias externas (serial, requests)
- Tests independientes y reproducibles
- Nombre descriptivo: `test_<functionality>_<scenario>`

### Ejemplo de Test

```python
def test_osmnote_success(processor, db, position_cache):
    """Test successful osmnote creation."""
    node_id = "test_node"
    position_cache.update(node_id, 1.0, 2.0)
    
    cmd_type, response = processor.process_message(node_id, "#osmnote test")
    
    assert cmd_type == "osmnote_queued"
    assert response.startswith("Q-")
```

## Proceso de Contribución

### 1. Crear Issue

Antes de hacer cambios grandes, crear un issue para discutir:
- Bug reports con pasos para reproducir
- Feature requests con casos de uso
- Mejoras de documentación

### 2. Crear Branch

```bash
git checkout -b feature/nombre-de-la-feature
# o
git checkout -b fix/nombre-del-bug
```

### 3. Hacer Cambios

- Escribir código siguiendo estándares
- Agregar tests para nueva funcionalidad
- Actualizar documentación si es necesario
- Asegurar que todos los tests pasen

### 4. Commit

```bash
git add .
git commit -m "feat: agregar nueva funcionalidad X"
```

**Formato de commits**:
- `feat:` Nueva funcionalidad
- `fix:` Corrección de bug
- `docs:` Cambios en documentación
- `test:` Agregar/modificar tests
- `refactor:` Refactorización de código
- `chore:` Tareas de mantenimiento

### 5. Push y Pull Request

```bash
git push origin feature/nombre-de-la-feature
```

Crear Pull Request en [GitHub](https://github.com/OSM-Notes/osm-mesh-notes-gateway) con:
- Descripción clara de cambios
- Referencia a issues relacionados
- Screenshots si aplica
- Checklist de verificación

### Checklist de PR

- [ ] Código sigue estándares PEP 8
- [ ] Tests pasan (`pytest`)
- [ ] Tests nuevos agregados para nueva funcionalidad
- [ ] Documentación actualizada
- [ ] No hay warnings de linter
- [ ] Commits con mensajes descriptivos

## Áreas de Contribución

### Código

- Mejoras de rendimiento
- Nuevas funcionalidades
- Corrección de bugs
- Refactorización

### Documentación

- Mejorar docstrings
- Agregar ejemplos de uso
- Traducir documentación
- Crear tutoriales

### Testing

- Aumentar cobertura de tests
- Agregar tests de integración
- Tests de rendimiento
- Tests de carga

### Infraestructura

- Mejorar scripts de instalación
- CI/CD pipelines
- Dockerización
- Monitoreo y métricas

## Preguntas Frecuentes

### ¿Cómo agrego un nuevo comando?

1. Agregar handler en `CommandProcessor`
2. Agregar caso en `process_message()`
3. Agregar tests
4. Actualizar documentación

### ¿Cómo manejo errores?

- Usar logging para errores
- No silenciar excepciones sin log
- Retornar valores apropiados (None, False, etc.)
- Mantener estado consistente

### ¿Cómo pruebo cambios localmente?

```bash
# Modo dry-run
export DRY_RUN=true
python -m gateway.main

# Con datos de prueba
export DATA_DIR=/tmp/test-data
python -m gateway.main
```

## Contacto

Para preguntas o dudas:
- Abrir issue en [GitHub](https://github.com/OSM-Notes/osm-mesh-notes-gateway/issues)
- Revisar documentación existente
- Consultar código de ejemplos

## Licencia

Al contribuir, aceptas que tus contribuciones serán licenciadas bajo la misma licencia del proyecto (GPL-3.0).
