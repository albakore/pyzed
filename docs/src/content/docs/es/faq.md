---
title: Preguntas frecuentes
description: "Preguntas frecuentes de Pyzed: qué es, cómo se compara con tkinter, Kivy, PyQt y Flet, licencia, plataformas, rendimiento, diseñador visual y agentes de IA."
---

Respuestas cortas a las preguntas más habituales sobre Pyzed. Cada una enlaza a la página que lo explica en detalle.

## ¿Qué es Pyzed?

Pyzed es un framework de código abierto para crear aplicaciones de escritorio nativas en Python. Tu código Python
describe la interfaz; [Iced](https://iced.rs), un toolkit de GUI escrito en Rust, la organiza y la dibuja con la
GPU (o con un renderizador por software si no la hay). Incluye más de 90 componentes inspirados en el editor
[Zed](https://zed.dev) (pestañas, árbol de archivos, paleta de comandos, editor de código, terminal, tablas,
gráficos, diálogos, un workspace con docks) y Pyzed Design, un diseñador visual de arrastrar y soltar. Mira la
[introducción](/pyzed/es/getting-started/introduction/).

## ¿Pyzed tiene relación con el paquete pyzed de las cámaras ZED?

No. Pyzed (`pip install pyzed-ui`, `import pyzed as pz`) es un framework de GUI de escritorio para Python, y su
nombre viene del editor [Zed](https://zed.dev), que inspira sus componentes. El módulo `pyzed` del SDK de ZED de
Stereolabs (`pyzed.sl`) es una biblioteca distinta para las cámaras estéreo ZED. Los dos se importan como
`pyzed`, así que no se pueden instalar en el mismo entorno.

## ¿Cómo instalo Pyzed?

Ejecuta `pip install pyzed-ui` o `uv add pyzed-ui` y luego `import pyzed as pz`. El paquete se llama `pyzed-ui`
en PyPI pero se importa como `pyzed`. Necesita Python 3.10 o superior, y los wheels precompilados para Windows,
macOS y Linux incluyen el motor en Rust, así que no hay nada que compilar. Mira
[Instalación](/pyzed/es/getting-started/installation/).

## ¿Pyzed es gratis y de código abierto?

Sí. Pyzed y Pyzed Design son gratuitos y se publican con licencia MIT, así que puedes usarlos en aplicaciones
comerciales y de código cerrado. El código está en [GitHub](https://github.com/albakore/pyzed).

## ¿Qué plataformas soporta Pyzed?

Windows (x64 y ARM), macOS (Intel y Apple Silicon) y Linux (x86_64 y ARM, con glibc 2.28 o superior, y musl
para Alpine). En Alpine el motor de audio solo renderiza sin dispositivos de sonido. Móviles y web todavía no son
objetivos. Mira
[Estabilidad y limitaciones conocidas](/pyzed/es/guides/stability/).

## ¿En qué se diferencia Pyzed de tkinter?

tkinter viene con Python y sirve para utilidades pequeñas, pero sus widgets se ven anticuados, el estilo es
limitado y los layouts complejos requieren mucho código. Pyzed dibuja una interfaz moderna y con temas usando la
GPU, trae componentes de alto nivel como un editor de código, tablas, árboles, paleta de comandos y
notificaciones, tiene un diseñador visual y usa un modelo declarativo de `view()` y estado en lugar de modificar
widgets a mano. tkinter no necesita instalación; Pyzed necesita `pip install pyzed-ui`.

## ¿En qué se diferencia Pyzed de Kivy?

Kivy está pensado para apps táctiles y móviles y usa su propio lenguaje KV. Pyzed está pensado para apps de
escritorio (interfaces densas y manejadas con teclado, como editores, paneles y herramientas), se escribe en
Python puro sin otro lenguaje y renderiza a través de Rust e Iced. Si necesitas Android o iOS, hoy Kivy encaja
mejor.

## ¿En qué se diferencia Pyzed de PyQt y PySide?

Qt es un toolkit de C++ grande y maduro, con widgets de aspecto nativo y una API enorme. Pyzed es mucho más
pequeño y sencillo: describes la interfaz a partir de tu estado con funciones de Python, los estilos funcionan
como CSS y los componentes tienen un aspecto moderno desde el principio. Pyzed tiene licencia MIT, mientras que
PyQt es GPL o comercial y PySide es LGPL. Qt sigue teniendo más widgets, soporte de accesibilidad y años de uso
en producción.

## ¿En qué se diferencia Pyzed de Flet?

Flet construye la interfaz con Flutter y la controla desde Python, y además puede apuntar a web y móviles. Pyzed
ejecuta la interfaz en el mismo proceso mediante una extensión de Rust, sin cliente aparte, y se centra en apps de
escritorio con aspecto de IDE, un diseñador visual y un componente de editor de código.

## ¿Pyzed es rápido?

El layout, el texto, el resaltado de sintaxis y el dibujo ocurren en Rust, y el árbol de widgets que devuelve tu
`view()` está hecho de objetos de Rust inmutables y baratos. El GIL se libera mientras corre el bucle de eventos,
así que tus hilos de Python siguen trabajando. Para muchos datos, las listas y tablas virtuales muestran cientos
de miles de filas y `@pz.memo` evita reconstruir las partes de la vista que no cambiaron. Mira
[Rendimiento](/pyzed/es/guides/performance/) y [Cómo funciona](/pyzed/es/guides/how-it-works/).

## ¿Hay un diseñador visual de interfaces?

Sí. [Pyzed Design](/pyzed/es/editor/) te permite dibujar ventanas y componentes reutilizables arrastrando y
soltando, editar sus propiedades y estilos, escribir los manejadores de eventos en un editor de Python con
autocompletado y diagnósticos, y ejecutarlos con F5. Los formularios se guardan como un archivo `.pzform` legible
más un archivo de Python. [Descárgalo](/pyzed/es/download/) para Windows, macOS o Linux.

## ¿Puedo hacer interfaces con efectos y animaciones?

Sí. Cualquier widget se puede animar con presets, keyframes y transiciones, y los controles pueden tener
rotación, desenfoque, glow, bloom, glass y opacidad, con temas claros, oscuros y propios. Mira
[Animación y efectos](/pyzed/es/animation/) y [Temas](/pyzed/es/theming/themes/).

## ¿Pyzed funciona con agentes de IA para programar?

Sí. `pyzed mcp` (instala `pyzed-ui[mcp]`) es un [servidor MCP](/pyzed/es/guides/mcp/) que da a agentes como
Cursor, VS Code o Zed la firma exacta de cada componente, esta documentación, buenas prácticas, comprobación de
código y capturas del resultado. Esta documentación también se publica para modelos de lenguaje en
[llms.txt](https://albakore.github.io/pyzed/es/llms.txt) y
[llms-full.txt](https://albakore.github.io/pyzed/es/llms-full.txt), y Pyzed Design tiene un
[panel del agente](/pyzed/es/editor/ai-agents/) integrado.

## ¿Puedo añadir funciones de IA a mi propia app?

Sí. [`pyzed.agents`](/pyzed/es/guides/agents/) habla con Anthropic, OpenAI, Gemini, OpenRouter, Ollama y
servidores compatibles con OpenAI, deja que el modelo llame a tus funciones de Python como herramientas,
transmite su respuesta a la interfaz y guarda las claves de API en el llavero del sistema.

## ¿Cómo distribuyo una app de Pyzed?

`pyzed build` empaqueta un proyecto como app independiente (una carpeta o un solo archivo) para Windows, macOS o
Linux que funciona en equipos sin Python. Usa PyInstaller por debajo; compila cada plataforma en esa plataforma o
en una matriz de CI. Mira [Empaquetado](/pyzed/es/packaging/build/).

## ¿Puedo probar una app de Pyzed sin ventana?

Sí. `app.screenshot(path)` renderiza el estado actual fuera de pantalla con el renderizador por software, sin
pantalla ni GPU, así que funciona en CI. Tu estado y tus manejadores son Python normal y se prueban como
cualquier otro código. Mira [Tests](/pyzed/es/guides/testing/).

## ¿Pyzed soporta lectores de pantalla?

Todavía no. Pyzed respeta el ajuste de reducir movimiento del sistema y admite atajos de teclado, pero el soporte
de lectores de pantalla depende de Iced y aún falta. Mira [Accesibilidad](/pyzed/es/guides/accessibility/).

## ¿Necesito saber Rust?

No. Solo escribes Python: clases, funciones y lambdas. Rust solo hace falta si compilas Pyzed desde el código
fuente o [contribuyes](/pyzed/es/contributing/) con un widget nativo nuevo.
