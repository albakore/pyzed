---
title: Bienvenida y ejemplos
description: "La ventana de bienvenida de Pyzed Design: empieza o abre un proyecto, vuelve a uno reciente o crea un proyecto desde uno de los ejemplos incluidos, cada uno con miniatura, título y descripción."
sidebar:
  order: 1
---

Cuando Pyzed Design se inicia sin un archivo, se abre la **ventana de bienvenida**. A la izquierda puedes empezar un
proyecto nuevo, abrir uno, crear un formulario o leer la documentación, y volver a un proyecto reciente. A la derecha
está la **galería de proyectos de ejemplo**: cada ejemplo tiene una miniatura, un título y una descripción.

![La ventana de bienvenida con la galería de proyectos de ejemplo](../../../../assets/editor/welcome.png)

Ábrela de nuevo cuando quieras desde **Ayuda → Bienvenida**, o **Ayuda → Proyectos de ejemplo…** para ver todos los
ejemplos. Desmarca **Mostrar al iniciar** (o desactiva **Ventana de bienvenida** en
[Ajustes](/pyzed/es/editor/settings/)) para empezar directamente con un formulario vacío.

## La galería

Los botones de encima de la galería filtran los ejemplos por categoría (cada uno dice cuántos tiene) y el buscador
los filtra por título y descripción. **Todos** muestra cada categoría bajo su propio título:

| Categoría | Ejemplos |
| --- | --- |
| **Apps** | Contador, Lista de tareas, Tareas (Iced), Pomodoro, Visor de Markdown, Juego de la vida, Reloj analógico, Cronómetro, Código QR, Selector de color, Visor de imágenes, Varias ventanas, Marco de ventana propio, Galería de componentes, Mini editor, Editor estilo Zed. |
| **Tutorial** | Los cinco pasos del tutorial (Hola, Estado, Diseño, Trabajo asíncrono, App de notas), Diseño básico, Listas y tablas, Navegación, Hablar con el usuario, Selector de tema, Contactos con SQLite. |
| **Audio** | Sintetizador, Caja de ritmos, Rack modular, Visualizador de música, Controlador MIDI, Webcam. |
| **Juegos** | Snake, Breakout, Neon Invaders, Rock Storm, Pixel Run, 2048, Coin Chase, Jump Lab, Walker, Orb Rush, Target Rush, Dodge. |
| **Animación** | Animaciones, Efectos, Línea de tiempo. |
| **Estilo** | Estilos, Diseño estilo web, Laboratorio de temas y los temas De marca, Oscuro de cristal, Pastel, Terminal retro, Alto contraste y Dos temas. |
| **Shading** | Galería de shaders, Shader de aurora. |
| **Vitrina** | Panel de cristal, HUD de juego, Menú principal de juego, Inventario. |
| **Bloques** | Panel de control, Tablero Kanban, Reproductor de música, Chat, Ajustes, Tabla de datos, Diseño de IDE, Pantalla de inicio de sesión, Asistente de bienvenida. |
| **Patrones** | Servicios (temporizador, trabajo en segundo plano, proceso, portapapeles, ajustes), Componentes propios, Paneles y cuadrículas, Paneles redimensionables, Menú contextual, Diálogos e idiomas, Trabajo en segundo plano, Progreso de descargas, Datos en vivo. |
| **IA** | Agente de Pyzed (un agente que usa herramientas, con un modelo de demostración que no necesita clave), Chat de IA. |
| **Diseñador** | Formularios hechos en Pyzed Design: Inicio de sesión, Lanzador de tareas (los componentes no visuales), Explorador de proyecto (árbol, ruta de navegación, pestañas, tabla ordenable y otros controles de la caja de herramientas), Mini IDE (un Dock con paneles en cada lado), Tarjetas de componentes, Registro con datos enlazados, Formulario sobre un shader. |
| **Integraciones** | Héroes con SQLModel, Inventario con SQLModel, Registro con Pydantic, PyPI con httpx, Descargas con httpx, Contactos con SQLAlchemy, Inicio rápido de SQLAlchemy, Diario con SQLite asíncrono, Héroes con FastAPI. |

![La categoría Audio de la galería: el sintetizador, la caja de ritmos, el rack modular, el visualizador, el controlador MIDI y la webcam](../../../../assets/editor/welcome-audio.png)

![La categoría Juegos de la galería](../../../../assets/editor/welcome-games.png)

![La categoría Vitrina de la galería: el panel de cristal, el HUD de juego, el menú principal y el inventario](../../../../assets/editor/welcome-showcase.png)

## Crear un proyecto desde un ejemplo

Haz clic en un ejemplo para darle nombre al proyecto nuevo y elegir dónde va (por defecto
`~/Pyzed Projects/<nombre>`; **Examinar…** elige otra carpeta). **Crear proyecto** entonces:

1. copia el ejemplo en la carpeta como un [proyecto de uv](/pyzed/es/editor/projects/) normal, con `pyzed-ui` y los
   paquetes que el ejemplo necesita en `pyproject.toml`;
2. lo abre en el panel Proyecto, con su script (o, en el ejemplo del Diseñador, su formulario principal) delante;
3. instala sus paquetes con `uv sync` en segundo plano.

![Dar nombre al proyecto creado desde un ejemplo](../../../../assets/editor/welcome-create.png)

La copia es tuya: cámbiala a tu gusto, el ejemplo original no se toca.

## Ejecutarlo

Los proyectos creados desde un ejemplo de código tienen un `script` en `[tool.pyzed]`:

```toml
[tool.pyzed]
ui = "ui"
script = "snake.py"
```

Cuando no hay un formulario abierto, **Ejecutar** (<kbd>F5</kbd>) inicia ese script con `uv run` y su salida va a la
[consola](/pyzed/es/editor/console-and-running/). **Ejecutar → Ejecutar el script del proyecto** hace lo mismo en
cualquier momento. Los archivos del proyecto abiertos con cambios sin guardar se guardan antes.

## De dónde salen los ejemplos

La app independiente **Pyzed Design** lleva dentro todos los ejemplos y sus miniaturas (unos 5 MB), así que la
galería funciona sin conexión. Un diseñador instalado con pip no los incluye: la galería ofrece **Descargar
ejemplos**, que los baja una vez desde la release de la versión instalada. Crear el entorno del proyecto con
`uv sync` necesita conexión la primera vez, para descargar Python y los paquetes.
