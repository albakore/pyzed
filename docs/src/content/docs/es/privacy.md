---
title: Política de privacidad
description: "Qué envían Pyzed y Pyzed Design por la red, qué guardan en tu ordenador y cómo desactivar cada parte. Sin cuentas, sin anuncios y sin rastreo."
---

_Última actualización: 23 de octubre de 2026._

Pyzed es un proyecto de código abierto mantenido por Kevin Kener ([albakore](https://github.com/albakore)). Esta
página cubre la librería **pyzed-ui**, la aplicación **Pyzed Design** y esta web. En resumen: no hay cuentas, ni
anuncios, ni rastreo. Pyzed no recopila nada sobre ti. Las pocas conexiones que hace la aplicación están abajo,
con cómo desactivar cada una.

## La librería pyzed-ui

La librería no recopila ni envía nada por su cuenta. Una aplicación hecha con Pyzed solo se conecta a internet si
quien la desarrolla lo programa (por ejemplo con [`pyzed.updater`](/pyzed/es/packaging/updates/) o una petición
web en su propio código). Eso es responsabilidad de quien la desarrolla, bajo su propia política de privacidad.

## Pyzed Design

### Conexiones que hace

| Qué | Adónde | Cuándo | Cómo desactivarlo |
| --- | --- | --- | --- |
| **Buscar actualizaciones** y descargarlas | GitHub (`api.github.com`, `github.com`) | Una vez al día en segundo plano, y cuando eliges *Buscar actualizaciones* | **Ajustes → General → Buscar actualizaciones** |
| Notas de **Novedades** | GitHub | Tras una actualización, o cuando las abres | No hace falta: solo se leen las notas de la versión |
| **Crear proyectos e instalar paquetes** | El índice de paquetes de Python (pypi.org), las descargas de Python y el instalador de uv (astral.sh), a través de [uv](https://docs.astral.sh/uv/) | Cuando creas un proyecto, añades un paquete o lo actualizas | No crear ni actualizar proyectos (uv funciona sin conexión con lo que ya descargó) |
| **Proyectos de ejemplo** que falten en tu copia | GitHub | Cuando abres la galería y los ejemplos no están instalados | No hace falta en la aplicación instalada: vienen con ella |
| **Agentes de IA** (panel Agent y asistencia en línea) | El proveedor que **tú eliges y configuras**: Anthropic, OpenAI, Google, GitHub, OpenRouter, Mistral, Groq, xAI, DeepSeek, o un programa de agente instalado en tu ordenador | Solo después de añadir un proveedor y enviar un mensaje | No añadir proveedores, o quitarlos en los ajustes del panel Agent |
| **Lista de programas de agente** | El registro de Agent Client Protocol (`cdn.agentclientprotocol.com`) | Cuando exploras agentes para instalar | No abrir la lista |
| **Telemetría** | Solo una dirección que escribas **tú** | Nunca por defecto (ver abajo) | Está desactivada salvo que la actives |

Lo que reciben estos servicios es lo que lleva cualquier conexión (tu dirección IP y un nombre de programa como
`pyzed-updater`) y, en el caso de un proveedor de IA, los mensajes que envías y el código o los archivos que
adjuntas. Cada servicio lo trata según su propia política de privacidad. Pyzed nunca envía tu código, tus
archivos, tus claves ni tus ajustes al proyecto ni a nadie más.

### Telemetría (desactivada por defecto)

Pyzed Design no recopila datos de uso salvo que lo actives en **Ajustes → Telemetría**. Si está activada, cuenta
los comandos que usas y mide el arranque, el dibujado y los comandos, y guarda esas cifras en `telemetry.json`
dentro de la carpeta de ajustes de Pyzed, en tu ordenador. Nada sale de tu ordenador salvo que además escribas
una dirección a la que enviarlo (por ejemplo, un servidor tuyo). Nunca se registran código, textos, nombres de
archivo ni rutas. `PYZED_TELEMETRY=0` la desactiva digan lo que digan los ajustes. Detalles:
[Ajustes → Telemetría](/pyzed/es/editor/settings/#telemetría).

### Qué se queda en tu ordenador

- **Ajustes, proyectos recientes, distribuciones de paneles, logs y actualizaciones descargadas**, en la carpeta
  de ajustes de Pyzed (`%APPDATA%\pyzed` en Windows, `~/Library/Application Support/pyzed` en macOS,
  `~/.config/pyzed` en Linux).
- **Claves de API e inicios de sesión** de los proveedores de IA, en el llavero del sistema (Administrador de
  credenciales de Windows, Llavero de macOS, Secret Service en Linux), nunca en archivos de texto.
- **Tus proyectos**, en las carpetas que elijas.

Al borrar la aplicación y esa carpeta de ajustes se elimina todo lo que guardó Pyzed Design.

### Cambios en los ajustes de otros programas

Para que los agentes de IA instalados en tu ordenador (Claude Code, Cursor, Gemini CLI, Codex, VS Code, Zed...)
puedan usar la ayuda de Pyzed, Pyzed Design añade el servidor MCP de Pyzed a sus archivos de ajustes, una vez por
agente. Solo cambia su propia entrada `pyzed`, guarda una copia de cada archivo a su lado (`.pyzed-backup`) antes
del primer cambio y te dice a qué agentes lo añadió. Se desactiva en los ajustes del panel Agent: **El MCP de
Pyzed en tus agentes → Añadirlo a los agentes nuevos al iniciar**.

## Esta web

La documentación está alojada en GitHub Pages, que, como cualquier servidor web, ve tu dirección IP (ver la
[declaración de privacidad de GitHub](https://docs.github.com/es/site-policy/privacy-policies/github-general-privacy-statement)).
Las páginas cargan sus fuentes desde Google Fonts. La web no usa cookies, ni analítica, ni anuncios.

## Firma de código

Las versiones de Pyzed Design para Windows pueden estar firmadas por [SignPath Foundation](https://signpath.org),
con un certificado gratuito de [SignPath.io](https://signpath.io). La firma solo demuestra que los archivos salen
de las compilaciones públicas de este proyecto. No añade ninguna recopilación de datos.

## Cambios y contacto

Si esta política cambia, la versión nueva se publicará en esta página con su fecha, y en las
[novedades](/pyzed/es/changelog/). Para cualquier pregunta, abre un issue en
[github.com/albakore/pyzed/issues](https://github.com/albakore/pyzed/issues).
