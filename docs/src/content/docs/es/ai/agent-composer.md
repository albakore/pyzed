---
title: Compositor del agente en Pyzed Design
description: "El agente de IA de Pyzed Design: un compositor al estilo de Zed con modos de permiso, selector de modelo, esfuerzo, contexto con @ y comandos con / que crea formularios y componentes y escribe su código Python."
sidebar:
  order: 2
---

Pyzed Design, el diseñador visual, tiene un agente de IA en su panel derecho. Describes una pantalla con palabras y
el agente coloca los controles, conecta los eventos, escribe los handlers en Python, crea formularios y componentes
nuevos y comprueba su propio código. Cada cambio en el formulario abierto es un paso normal de deshacer, y
**Rechazar** devuelve todo lo que tocó una ejecución.

![El agente añadió un interruptor y conectó su evento](../../../../../screenshots/designer-agent.png)

El manual completo del panel está en [Pyzed Design → Agentes de IA](/pyzed/es/editor/ai-agents/). Esta página es un
recorrido por el compositor y por cómo sacarle partido.

## El compositor

El cuadro de mensaje al pie del panel sigue el modelo del compositor del agente de Zed:

| Parte | Qué hace |
| --- | --- |
| **Mensaje** | <kbd>Intro</kbd> envía. Mientras el agente trabaja, el botón de enviar se convierte en **Detener**. |
| **Contexto con @** | Escribe <kbd>@</kbd> (o pulsa **+**) para adjuntar la **selección**, el **formulario** abierto, su **código**, un **control** o un **archivo** del proyecto. Lo que elijas va con el mensaje, así el agente no tiene que buscarlo. Los archivos que pueden tener secretos (`.env`, claves) nunca se ofrecen. |
| **Comandos con /** | `/new`, `/history`, `/settings`, `/form`, `/component`, `/explain`, `/fix` y `/tidy`. `/fix` pasa `validate_code` por el código del formulario y corrige lo que encuentra; `/tidy` alinea los controles e iguala los márgenes. |
| **Modo de permisos** | **Preguntar antes de escribir** (por defecto: edita el formulario libremente y pregunta antes de crear o escribir archivos), **Omitir permisos**, **Solo lectura** o **Solo conversación**. |
| **Modelo** | Todos los proveedores y sus modelos. Un proveedor sin configurar muestra **Conectar…**, que inicia sesión ahí mismo. |
| **Esfuerzo** y **Rápido** | Cuánto piensa el modelo antes de responder y el modo rápido, en los modelos que los admiten. |
| **Expandir** | El panel ocupa toda la ventana para conversaciones largas; pulsa otra vez para devolverlo a su sitio. |

![Añadir contexto con @](../../../../../screenshots/designer-agent-mention.png)

## Conectar un modelo

La primera vez, el panel lista los proveedores principales. Pulsa uno para iniciar sesión: Pyzed abre la página de
claves del proveedor, detecta la clave cuando la copias, la comprueba y la guarda en el **llavero del sistema**
(nunca en un archivo de ajustes ni en el proyecto). OpenRouter inicia sesión con OAuth. Los modelos locales con
**Ollama** o **LM Studio** no necesitan nada, y cualquier servidor **compatible con OpenAI** (vLLM, llama.cpp, la
pasarela de tu empresa) funciona con su URL.

![Todos los proveedores en el selector de modelo](../../../../../screenshots/designer-agent-models.png)

## Qué puede tocar el agente

El agente trabaja con herramientas, igual que un cliente MCP usa el [servidor MCP](/pyzed/es/ai/mcp/):

- **El documento abierto**: leerlo, añadir, cambiar, mover y quitar controles, cambiar el título, tamaño, tema y
  estilo del formulario, y seleccionar controles para que los veas.
- **Código**: conectar eventos, escribir un handler o el módulo entero (debe ser Python válido) y validarlo.
- **Documentos nuevos**: crear formularios y componentes junto al abierto y abrirlos en pestañas.
- **Conocimiento**: componentes, iconos, temas y esta documentación.
- **Archivos del proyecto**: listar, leer, buscar y escribir archivos, nunca fuera de la carpeta del proyecto ni
  archivos con secretos.

Cada mensaje lleva una nota breve de dónde estás (el documento abierto, los controles seleccionados, el handler del
editor de código), así *"alinea estos"* o *"valida este campo"* se refieren a lo que estás mirando.

## Asistente en línea

En el editor de código, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> (o el botón ✦) abre una barra sobre el código.
Describe el cambio y el modelo reescribe el handler o el archivo; **Deshacer** y **Conservar** deciden, y nada se
aplica al formulario hasta que pulsas **Aplicar**.

![Asistente en línea sobre un handler](../../../../../screenshots/designer-agent-inline.png)

## Cómo obtener buenos resultados

- **Empieza por la pantalla, no por los widgets.** *"Un formulario de cliente: nombre, email, un desplegable de país
  y Guardar / Cancelar; Guardar valida el email y muestra un aviso"* da al agente el objetivo y las reglas a la vez.
- **Selecciona y luego pide.** Selecciona varios controles y di *"ponlos en una fila con 8 px de separación"*.
- **Usa @ para ser preciso.** `@email_input` y *"acepta solo direcciones de la empresa"* no deja dudas sobre el
  control.
- **Deja que se compruebe.** Termina las peticiones con *"y luego ejecuta /fix"*, o pídele que valide antes de
  responder.
- **Guarda reglas en los ajustes.** Las *Reglas* de los ajustes de agentes se añaden a cada conversación:
  *"Responde en español"*, *"Nombra los botones con el sufijo `_button`"*, *"Usa el tema Gruvbox Dark"*.
- **Revisa y conserva.** Tras una ejecución, la barra **Cambios del agente** ofrece **Conservar** o **Rechazar** para
  toda la ejecución.

## El mismo agente en tu app

El panel funciona sobre `pyzed.agents`, que cualquier app Pyzed puede usar: los mismos proveedores, el llavero,
herramientas escritas como funciones Python y eventos en streaming. Mira [Crear apps con IA](/pyzed/es/ai/ai-apps/)
y [Agentes de IA en tu app](/pyzed/es/guides/agents/).
