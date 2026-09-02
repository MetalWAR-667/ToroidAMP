# ToroidAMP — Future Ideas & Improvement Roadmap

> **"Playback must remain boring enough to be reliable. Visualization may be as ridiculous as necessary."**

Este documento recopila las propuestas de mejoras y siguientes cortes de trabajo planificados para evolucionar ToroidAMP paso a paso, complementando el `ROADMAP.md` y la arquitectura general del proyecto.

---

## 🚀 Bloque 1: UX & Daily-Use Fixes (`UX-005`)
*Objetivo: Perfeccionar la experiencia de uso diario para que el reproductor sea ágil, táctil y fluido.*

- [ ] **Atajos de Teclado Globales / Media Keys**:
  - Soporte de teclas multimedia del teclado (`Play/Pause`, `Next`, `Prev`, `Stop`, `Mute`) funcionando en segundo plano y con la app minimizada.
  - Atajos rápidos en foco:
    - `Espacio`: Play / Pause.
    - `Flechas Izq / Der`: Seek $\pm 5$ segundos.
    - `Flechas Arriba / Abajo`: Volumen $\pm 5\%$.
    - `M`: Mute / Unmute.
    - `F` / `F11`: Entrar / Salir de **RETINA MELT** (pantalla completa).
    - `V` / `Tab`: Cambiar modo de visualizador.
- [ ] **Arrastrar y Soltar Mejorado (Drag & Drop)**:
  - Arrastrar carpetas completas o múltiples archivos de audio directamente sobre la ventana principal, el chasis o la playlist para encolar o reproducir al instante de forma recursiva.
- [ ] **Búsqueda / Filtrado Rápido en Playlist**:
  - Barra de búsqueda incremental (`Ctrl+F` en módulo de Playlist) para saltar rápidamente a una pista o módulo tracker en listas extensas.
- [ ] **Notificaciones OSD / Tray al cambiar de pista**:
  - Mini notificación OSD compacta o tooltip enriquecido en el System Tray con el título del tema, artista y formato (ej. `XM / 32ch`).

---

## 🎛️ Bloque 2: DSP & Audio Foundation (`DSP-001`)
*Objetivo: Audio continuo, dinámico y profesional sin clics digitales ni saltos bruscos de volumen.*

- [ ] **Normalización Automática (Peak / RMS Limiter / ReplayGain)**:
  - Nivelación suave opcional para evitar descompensaciones de volumen entre pistas MP3 masterizadas modernas y módulos tracker clásicos (MOD/XM).
- [ ] **Crossfade y Gapless Playback**:
  - Transiciones suaves y configurables entre canciones consecutivas (fundido encadenado configurable de 0.5s a 2.0s).
- [ ] **Micro-Fades en Stop / Pausa / Seek**:
  - Rampa suave de 25ms para evitar cualquier "pop" o clic digital al pausar, detener o hacer saltos en la línea de tiempo.

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
