# 06 — Auditoría de dependencias: libxmp, pygame-ce y voz

> Estado: **PROPUESTA / PENDIENTE DE REVISIÓN**. Ningún cambio de código ha sido realizado.
> Fecha: 2026-10-15
> Alcance: análisis y propuesta. Cada acción descrita aquí requiere aprobación explícita y su propio corte de trabajo.

---

## 0. Pregunta de partida

¿Debe ToroidAMP prescindir de librerías externas y sustituirlas por código propio?

**Conclusión corta:** no como estrategia general. La infraestructura (Qt, numpy, libsndfile, PortAudio, libxmp) resuelve problemas maduros y caros; reescribirla contradice *"Playback must remain boring enough to be reliable"*. El código propio debe ir donde está la identidad del producto (análisis, visualizadores, shaders).

Sí existen **tres puntos concretos** donde una dependencia está mal ubicada o no se justifica:

| # | Dependencia | Problema | Severidad |
|---|-------------|----------|-----------|
| A | libxmp (vía pygame-ce) | Reproducción de trackers acoplada al empaquetado interno de una librería de gráficos | **Alta** (riesgo de rotura silenciosa) |
| B | pygame-ce | Forma parte del contrato `Visualizer`; dos frameworks gráficos conviviendo | Media (deuda arquitectónica) |
| C | pyttsx3 + pywin32 + comtypes | Tres dependencias para una frase de arranque; no funciona en Linux | Baja (higiene) |

Hallazgo adicional no relacionado con dependencias:

| # | Ubicación | Problema | Severidad |
|---|-----------|----------|-----------|
| D | `ui/modules/visualizer_module.py` | Excepciones de render tragadas con `pass`, sin log | Baja, pero arreglo trivial |

---

## 1. Evidencia

### A. libxmp depende de pygame-ce

`src/toroidamp/audio/decoders/tracker.py`

- `_discover_libxmp()` hace `import pygame` y busca `libxmp.dll / libxmp-4.dll / libxmp.so.4 / libxmp.so` **dentro de la carpeta del paquete pygame**. Fallback: `ctypes.util.find_library("xmp")`.
- El mensaje de error dice literalmente: *"Ensure pygame-ce is installed — it bundles libxmp on Windows."*
- Offsets de `xmp_frame_info` **derivados empíricamente contra libxmp 4.6.3**:
  - `_FRAME_INFO_TIME_OFFSET = 28`
  - `_FRAME_INFO_TOTAL_TIME_OFFSET = 32`

`packaging/toroidamp.spec`

- `binaries = collect_dynamic_libs("pygame")` — libxmp entra en el build únicamente como "efecto secundario" de empaquetar pygame.

**Riesgos:**

1. **Versión no controlada.** ToroidAMP carga la libxmp que pygame-ce decida incluir. Si pygame-ce actualiza libxmp y el layout de `xmp_frame_info` cambia, los offsets 28/32 leerían datos erróneos **sin lanzar ningún error** (tiempo/duración incorrectos, posible lógica de EOF/seek afectada).
2. **Disponibilidad no garantizada.** Si pygame-ce deja de incluir libxmp (o la renombra), se rompe la reproducción de MOD/XM/IT/S3M — una funcionalidad de V1 — por un cambio en una librería de *visualización*.
3. **Linux (PROBABLE, NO VERIFICADO).** Los wheels Linux de pygame-ce suelen ubicar las librerías nativas en `pygame_ce.libs/` con nombres con hash. La búsqueda solo mira en `pygame/`, por lo que en Linux probablemente funciona gracias a una `libxmp` del sistema.

   Verificación sugerida en Ubuntu:
   ```bash
   python -c "from toroidamp.audio.decoders.tracker import TrackerDecoder as T; print(T._discover_libxmp())"
   ```
   - Ruta dentro de `site-packages/pygame/` → la hipótesis es falsa.
   - `libxmp.so.4` (resultado de `find_library`) → se está usando la del sistema.
   - `None` → trackers rotos en esa máquina.

**Contradice:** VISION §5 — *"dependency isolation"*, *"replaceable subsystems"*.

### B. pygame-ce está dentro del contrato de visualizadores

`src/toroidamp/visualizers/base.py`

```python
def render(self, surface: pygame.Surface, frame: AudioFrame, dt: float) -> None
```

- El contrato que debería ser neutral (`AudioFrame` → dibujar) **impone pygame** a todo visualizador de CPU.
- Visualizadores afectados (CPU): toroid, ribbon, deep_field, floor, geometric, matrix_rain, xwing_squadron, spectrum*, metalwar_credits, etc.
- Puente pygame → Qt **duplicado** en dos sitios:
  - `ui/modules/visualizer_module.py` (~L282)
  - `ui/fullscreen.py` (~L1788)

  Ambos: `pygame.image.tobytes(surface, "RGBA")` → `QImage` → `QPixmap` → `QLabel.setPixmap` en cada frame.

**Consecuencia:** eliminar pygame **no es un cambio de librería, es un cambio de contrato**. Decisión arquitectónica, no refactor.

### C. Voz de arranque

`src/toroidamp/audio/voice.py`

- pyttsx3 (+ pywin32 + comtypes en Windows) para sintetizar una frase fija.
- En Linux está deshabilitada (LINUX-TTS-001) por problemas de ciclo de vida de eSpeak.
- Ya existe una ruta que decodifica WAV con `soundfile` y lo reproduce por el pipeline normal.

**Observación:** si la frase es siempre la misma, sintetizarla en cada arranque no aporta nada. Un `.ogg`/`.wav` pregrabado ofrece el mismo resultado en Windows y Linux con cero dependencias nuevas.

### D. Errores de render silenciados

`ui/modules/visualizer_module.py`

```python
except Exception as e:
    # Failure isolation: render bug must never crash playback
    pass
```

El aislamiento es correcto; la falta de diagnóstico no. Un visualizador roto produce imagen congelada/negra sin rastro en logs. Revisar si `fullscreen.py` tiene el mismo patrón.

---

## 2. Propuestas (cada una = un corte independiente)

### P-D — Log de fallos de render *(trivial, recomendado primero)*

- Sustituir `pass` por `logger.exception(...)` con limitación (p. ej. primer fallo por visualizador + contador, o como máximo 1 log/segundo) para no inundar el log a 60 fps.
- No cambia comportamiento visible. No toca contratos.

### P-A — Desacoplar libxmp de pygame-ce *(recomendado)*

1. Crear `vendor/libxmp/` con binarios propios por plataforma (`win64/libxmp.dll`, `linux-x86_64/libxmp.so.4`) y un `VERSION.txt` + licencia (libxmp ya figura en `licenses/`).
2. Orden de descubrimiento en `_discover_libxmp()`:
   1. `vendor/libxmp/<plataforma>/` (vía `resources`/`paths` existentes)
   2. librería del sistema (`find_library("xmp")`)
   3. *(opcional, transitorio)* carpeta de pygame, con warning de deprecación
3. `.spec`: añadir la libxmp de vendor explícitamente en `binaries`, independiente de `collect_dynamic_libs("pygame")`.
4. **Test de versión:** leer `xmp_vercode` (export de DATOS, ya identificado en RC-069-002B) y fallar/avisar si no coincide con la versión para la que se verificaron los offsets 28/32.
5. Actualizar mensaje de error y `THIRD_PARTY_NOTICES.md`.

**Decisiones abiertas para Metal:**
- ¿Compilar libxmp o usar binarios oficiales de release?
- ¿Mantener el fallback a pygame durante una versión o cortarlo directamente?
- ¿Fijar a 4.6.3 o actualizar y re-verificar offsets?

**No incluye:** cambios en la API de `TrackerDecoder`, ni en reproducción, ni en visualizadores.

### P-B — Futuro del contrato `Visualizer` *(decisión de arquitectura, NO implementar aún)*

Requiere decisión explícita antes de cualquier código. Opciones:

| Opción | Descripción | Pros | Contras |
|--------|-------------|------|---------|
| **B0** | Mantener pygame | Cero trabajo; funciona | Dos stacks gráficos; copia por frame; contrato no neutral |
| **B1** | Contrato neutral sobre `QImage` + `QPainter` | Una sola stack (Qt); sin copia intermedia; contrato propio | Portar ~10 visualizadores; QPainter es más lento en primitivas masivas (partículas) |
| **B2** | Migración progresiva a GLSL; desaparece la vía CPU | Aprovecha el motor GPU existente; mayor potencia visual | Requiere GPU (pérdida de fallback); portar efectos complejos (xwing, deep_field) es mucho trabajo |
| **B3** | Contrato neutral (B1) como paso intermedio y migración GPU selectiva | Desacopla primero, migra después y solo lo que gane con GPU | Dos fases |

Nota técnica: en cualquier opción distinta de B0, el primer paso sería **extraer el puente render→Qt duplicado** a un único punto, para que el cambio de contrato toque un sitio y no dos.

**Recomendación del auditor:** B3 — pero el criterio decisivo es tuyo: ¿el modo CPU debe sobrevivir como fallback sin GPU, o no?

### P-C — Voz pregrabada *(opcional, baja prioridad)*

- Generar una vez el audio de la frase, guardarlo en `assets/` y reproducirlo por el pipeline existente.
- Eliminar pyttsx3, pywin32 y comtypes de `pyproject.toml` y sus licencias.
- Se habilita en Linux automáticamente (cierra LINUX-TTS-001).
- **Coste de identidad:** se pierde la voz "nativa" del SO (SAPI5). Decisión estética tuya.

---

## 3. Lo que NO se recomienda reemplazar

| Librería | Motivo |
|----------|--------|
| PySide6 | Es la aplicación entera |
| numpy | FFT/análisis; Python puro sería 50–100× más lento |
| soundfile / libsndfile | Decodificar MP3/FLAC/OGG es un proyecto en sí mismo |
| sounddevice / PortAudio | Salida de audio multiplataforma de baja latencia |
| libxmp | Años de afinado en efectos XM/IT; se **reubica** (P-A), no se reemplaza |

---

## 4. Orden sugerido

```
P-D  log de render            (minutos, sin riesgo)
 ↓
P-A  libxmp vendorizada       (corte pequeño, cierra el riesgo real)
 ↓
P-B  DECISIÓN de contrato     (solo documento; implementación aparte)
 ↓
P-C  voz pregrabada           (cuando apetezca)
```

## 5. Correcciones a afirmaciones previas

- Las media keys de Windows (`ui/media_keys.py`, `RegisterHotKey` + `QAbstractNativeEventFilter`) **sí están implementadas**. Las casillas `[ ]` de `docs/FUTURE_IDEAS.md` Bloque 1 son documentación desactualizada, no trabajo pendiente.

## 6. Ficheros revisados

- `src/toroidamp/audio/decoders/tracker.py`
- `src/toroidamp/audio/voice.py`
- `src/toroidamp/visualizers/base.py`, `__init__.py`, `toroid.py`
- `src/toroidamp/ui/modules/visualizer_module.py`
- `src/toroidamp/ui/fullscreen.py` (solo secciones pygame)
- `src/toroidamp/ui/media_keys.py`
- `packaging/toroidamp.spec`
- `pyproject.toml`, `docs/ARCHITECTURE.md`, `docs/VISION.md`, `docs/SCOPE.md`

No verificado: comportamiento real en Linux (§1.A.3); presencia del patrón `except: pass` en `fullscreen.py`.
