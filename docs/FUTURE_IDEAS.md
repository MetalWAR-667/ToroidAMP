# ToroidAMP — Future Ideas & Improvement Roadmap

> **"Playback must remain boring enough to be reliable. Visualization may be as ridiculous as necessary."**

Este documento recopila las propuestas de mejoras y siguientes cortes de trabajo planificados para evolucionar ToroidAMP paso a paso, complementando el `ROADMAP.md` y la arquitectura general del proyecto.

---

## 🚀 Bloque 1: UX & Daily-Use Fixes (`UX-005`) ** COMPLETED **
*Objetivo: Perfeccionar la experiencia de uso diario para que el reproductor sea ágil, táctil y fluido.*

- [ ] **Atajos de Teclado Globales / Media Keys**:
  - Soporte de teclas multimedia del teclado (`Play/Pause`, `Next`, `Prev`, `Stop`, `Mute`) funcionando en segundo plano y con la app minimizada.
  - Atajos rápidos en foco:
    - `Espacio`: Play / Pause.
    - `Flechas Izq / Der`: Seek $\pm 5$ segundos.
    - `Flechas Arriba / Abajo`: Volumen $\pm 5\%$.
    - `F11`: Entrar / Salir de **RETINA MELT** (pantalla completa).
    - `F10`: Cambiar modo de visualizador.
- [ ] **Arrastrar y Soltar Mejorado (Drag & Drop)**:
- Arrastrar carpetas completas o múltiples archivos de audio directamente sobre la ventana principal, el chasis o la playlist para encolar o reproducir al instante de forma recursiva.
- [ ] **Búsqueda / Filtrado Rápido en Playlist**:
  - Barra de búsqueda incremental (`Ctrl+F` en módulo de Playlist) para saltar rápidamente a una pista o módulo tracker en listas extensas.
- [ ] **Notificaciones OSD / Tray al cambiar de pista**:
  - Mini notificación OSD compacta o tooltip enriquecido en el System Tray con el título del tema, artista y formato (ej. `XM / 32ch`).

02-09-2026 ** COMPLETED **
---

## 🎛️ Bloque 2: DSP & Audio Foundation (`DSP-001`) **COMPLETED **
*Objetivo: Audio continuo, dinámico y profesional sin clics digitales ni saltos bruscos de volumen.*

- [ ] **Normalización Automática (Peak / RMS Limiter / ReplayGain)**:
  - Nivelación suave opcional para evitar descompensaciones de volumen entre pistas MP3 masterizadas modernas y módulos tracker clásicos (MOD/XM).
- [ ] **Crossfade y Gapless Playback**:
  - Transiciones suaves y configurables entre canciones consecutivas (fundido encadenado configurable de 0.5s a 2.0s).
- [ ] **Micro-Fades en Stop / Pausa / Seek**:
  - Rampa suave de 25ms para evitar cualquier "pop" o clic digital al pausar, detener o hacer saltos en la línea de tiempo.
02-09-2026 **COMPLETED **
---

## 🌌 Bloque 3: Expansión Gráfica y GLSL (`EXP-GL-002` / `EXP-GL-003`)
*Objetivo: Elevar la potencia del motor de shaders hacia técnicas avanzadas de la demoscene.*

- [ ] **Soporte de Texturas `iChannel0..3` (`EXP-GL-002`)**:
  - Inyección de texturas procedurales (Blue Noise, RGBA noise de alta frecuencia).
  - Mapeo de buffers de audio y espectro como texturas 1D/2D para muestreo directo en shaders.
  - Carga de imágenes/assets estáticos en canales secundarios.
- [ ] **Multipass / Feedback FBO (`EXP-GL-003`)**:
  - Soporte de renderizado multipaso con buffer de persistencia/framebuffer anterior.
  - Efectos de retroalimentación analógica de vídeo, estelas de movimiento reales (motion blur por persistencia) y eco óptico.

---

## 🎨 Bloque 4: Visualizadores y Demoscene (`VIS-COMP-001` & Creatividad)
*Objetivo: "Make Future Crew cry" — efectos únicos con alta identidad retrofuturista.*

- [ ] **FastTracker II / Matrix Tracker Channel Visualizer**:
  - Visualizador estilo reproductor FT2 / Impulse Tracker clásico: columnas independientes donde se ve el volumen, frecuencia y notas activas de cada canal del módulo tracker en tiempo real.
- [ ] **Wing Commander / Space Combat HUD**:
  - Cabina de nave espacial retro con radar vectorial reactivo al espectro, miras holográficas y wireframes espaciales táctiles.
- [ ] **Soporte de Letras Sincronizadas (LRC Lyrics Overlay)**:
  - Detección automática y visualización flotante de archivos `.lrc` sobre el visualizador con tipografía cyberpunk / retro-scroller.
- [ ] **Dembow / Glitch Overdrive Mode 👹**:
  - Modo reactivo de sobrecarga: distorsión cromática agresiva, temblor de pantalla (CRT jitter) y shockwaves térmicos cuando la pista tiene un ritmo continuo muy alto (`taStrongBeat` + `taBass` saturado).
- [ ] **Skin / Tema Estilo Cyberpunk Clásico (John Pondsmith tribute)**:
  - Tema cromático oscuro con acentos ámbar/neón de terminal militar retro.

---

## 🖥️ Bloque 5: Soporte Multipantalla (`MULTI-SCREEN`)
*Objetivo: que RETINA MELT sepa en qué pantalla vive, y más adelante, separar salida visual y controles.*

> Estado actual (2026-10-15): `ui/fullscreen.py::show_fullscreen_experience()` usa siempre `QGuiApplication.primaryScreen()`.

- [ ] **Nivel 1 — Elegir pantalla** *(barato, recomendado primero)*:
  - RETINA MELT se abre en la pantalla donde está el reproductor (`self.screen()` / `QGuiApplication.screenAt(...)`), no en la principal.
  - Submenú opcional "Abrir en pantalla: 1, 2…" persistido en sesión.
  - Persistir por `QScreen.name()` / `serialNumber()`, nunca por índice (Windows reordena al desconectar monitores).
- [ ] **Nivel 2 — Modo VJ** *(requiere documento de diseño previo)*:
  - Visual limpio fullscreen en monitor 2 (proyector/TV); HUD, TUNE y LAB en monitor 1.
  - Ideal para editar shaders en el Lab viendo el resultado en otra pantalla.
  - Implica separar `fullscreen.py` en **ventana de salida** (consumidor puro: `AudioFrame` + parámetros → pinta) y **panel de control**. Aplicación directa de "el renderer es un consumidor de datos".
- [ ] **Nivel 3 — Varias salidas simultáneas** *(cada variante es una decisión aparte)*:
  - Espejo: mismo visual en todas las pantallas.
  - Uno por pantalla: visualizador distinto en cada monitor.
  - Lienzo extendido: un único visual repartido entre monitores.
  - Prerrequisito: **un solo análisis de audio, N consumidores** (verificar que `AudioFrame` no se calcula por ventana).

**Riesgos técnicos a tener en cuenta:**
- **DPI / escalado (posible bug actual, sin verificar):** `geometry()` devuelve píxeles lógicos; con escalado 150 % la superficie se crea a resolución lógica y se escala → visual borroso. Multiplicar por `devicePixelRatio()`.
- **Desconexión en caliente:** escuchar `screenRemoved` y recolocar RETINA MELT en una pantalla existente.
- **Tasas de refresco distintas** (60 / 144 Hz): el timer de render no debe atarse a una pantalla concreta.
- **Wayland:** el compositor decide la colocación; el fullscreen en pantalla concreta suele funcionar, las ventanas libres no.
- **Coste CPU:** la vía pygame a fullscreen en varias pantallas 4K multiplica la copia por frame (relacionado con decisión P-B de `investigations/06_dependency_audit.md`).

---

## ✨ Bloque 6: Ideas Sueltas (semillas)

- [ ] **Transiciones sincronizadas al beat**: cambio de visualizador en un strong beat, no a mitad de compás. Depende de la futura Rhythm Analysis Foundation.
- [ ] **Playlists de visuales / Modo Fiesta**: lista de presets que rota por pista o cada N compases, sin intervención.
- [ ] **Grabación a vídeo de RETINA MELT**: frames + audio vía `ffmpeg` como ejecutable externo opcional (sin dependencia Python nueva). Útil para material de YouTube.
- [ ] **HUD de información tracker en tiempo real**: patrón, fila y BPM actuales. libxmp ya los expone en `xmp_frame_info` (`pos`, `row`, `bpm`) — requiere verificar sus offsets igual que `time`/`total_time`.
- [ ] **Shader/preset por canción**: asociar un preset a cada pista y guardarlo junto a la playlist.

---

## 🌐 Bloque 7: RETINA MELT Web (semilla lejana, fuera de V1)

*No es "ToroidAMP en WebAssembly": portar la app Python/PySide6 tal cual sería casi reescribirla (PortAudio, `ctypes`/libxmp, tray, modo MINI, media keys y pyttsx3 no existen en navegador).*

- [ ] **Producto independiente**: TypeScript + Web Audio + WebGL2 + reproductor tracker en WASM (libxmp o libopenmpt), cargando los mismos `.frag` y presets JSON. Escaparate: arrastrar un `.xm` y derretir la retina.
- **Higiene que ya conviene mantener (sin cambiar scope):**
  - Shaders oficiales compatibles con GLSL ES 3.0 (sin extensiones exclusivas de OpenGL de escritorio).
  - `AudioFrame` y formato de presets como datos puros y documentados: son el contrato que compartirían ambos productos.
  - Cuanto más visual viva en GLSL y menos en pygame, más portable (relacionado con P-B).
