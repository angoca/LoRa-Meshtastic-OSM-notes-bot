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

# Instalar dependencias (pyproject.toml es la fuente de verdad)
pip install -e ".[dev]"  # Incluye todas las dependencias + herramientas de desarrollo

# O si prefieres usar requirements.txt (solo dependencias principales)
# pip install -r requirements.txt
# pip install pytest pytest-cov black ruff  # Herramientas de desarrollo manualmente
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

### Formateo y Linting

El proyecto usa **Black** para formateo automático y **Ruff** para linting rápido.

#### Instalación de herramientas

```bash
# Las herramientas ya están incluidas en [dev] dependencies
pip install -e ".[dev]"
```

#### Formateo con Black

```bash
# Formatear todos los archivos
black src/ tests/

# Ver qué cambios haría sin aplicarlos
black --check src/ tests/

# Formatear un archivo específico
black src/gateway/commands.py
```

**Configuración**: Black está configurado en `pyproject.toml` con:
- Longitud de línea: 100 caracteres
- Versiones objetivo: Python 3.8+

#### Linting con Ruff

```bash
# Verificar todos los archivos
ruff check src/ tests/

# Auto-fix problemas que se pueden corregir automáticamente
ruff check --fix src/ tests/

# Verificar un archivo específico
ruff check src/gateway/commands.py
```

**Configuración**: Ruff está configurado en `pyproject.toml` con reglas que cubren:
- Errores de estilo (pycodestyle E, W)
- Problemas comunes (pyflakes F)
- Orden de imports (isort I)
- Mejores prácticas (flake8-bugbear B)
- Sugerencias de modernización (pyupgrade UP)

#### Workflow recomendado

Antes de hacer commit:

```bash
# 1. Formatear código
black src/ tests/

# 2. Verificar y corregir linting
ruff check --fix src/ tests/

# 3. Ejecutar tests
pytest

# 4. Si todo está bien, hacer commit
git add .
git commit -m "feat: descripción del cambio"
```

#### Integración con editores

**VS Code / Cursor**:
- Instalar extensiones: "Black Formatter" y "Ruff"
- Configurar formato automático al guardar

**Pre-commit hooks** (recomendado):

El proyecto incluye un archivo `.pre-commit-config.yaml` con hooks configurados para:
- Formateo automático con Black
- Linting con Ruff
- Verificación de archivos (YAML, JSON, TOML)
- Detección de conflictos de merge
- Verificaciones de seguridad con Bandit

Para instalar y usar:

```bash
# Instalar pre-commit
pip install pre-commit

# Instalar los hooks en tu repositorio local
pre-commit install

# (Opcional) Ejecutar manualmente en todos los archivos
pre-commit run --all-files
```

Los hooks se ejecutarán automáticamente antes de cada commit. Si algún hook falla, el commit será rechazado hasta que corrijas los problemas.

### Gestión de Dependencias

**Fuente de verdad**: `pyproject.toml` es la fuente canónica de dependencias.

- **Dependencias principales**: Definidas en `[project.dependencies]`
- **Dependencias de desarrollo**: Definidas en `[project.optional-dependencies.dev]`
- **requirements.txt**: Se mantiene por compatibilidad, pero `pyproject.toml` tiene prioridad

**Instalación recomendada**:
```bash
# Usar pyproject.toml (recomendado)
pip install -e ".[dev]"

# O solo dependencias principales
pip install -e .
```

**Actualizar requirements.txt** (si es necesario):
```bash
# Generar desde pyproject.toml (manual)
pip-compile pyproject.toml  # Requiere pip-tools
```

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

- [ ] Código formateado con Black (`black src/ tests/`)
- [ ] Linting pasa sin errores (`ruff check src/ tests/`)
- [ ] Tests pasan (`pytest`)
- [ ] Tests nuevos agregados para nueva funcionalidad
- [ ] Documentación actualizada
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
