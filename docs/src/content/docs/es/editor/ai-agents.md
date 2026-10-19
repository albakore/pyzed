---
title: Agentes de IA
description: El panel del agente de Pyzed Design - un agente de IA que crea formularios y componentes, escribe su código y edita el formulario abierto, con asistente en línea en el editor de código, varios proveedores de modelos y claves guardadas en el llavero del sistema.
sidebar:
  order: 10.5
---

El panel **Agente** (dock derecho, junto a Propiedades y Eventos) es un agente de IA al estilo del de Zed.
Describe lo que quieres y lee el formulario abierto, añade y ordena controles, conecta eventos, escribe los
manejadores, crea formularios y componentes nuevos y revisa su propio código. Cada cambio que hace es un paso
normal de deshacer, y puedes rechazar toda la ejecución de una vez.

![El agente añadió un interruptor y conectó su evento](../../../../../screenshots/designer-agent.png)

## Primeros pasos

1. Abre el panel: la pestaña **Agente** del dock derecho, **Ver → Panel del agente** o <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd>.
2. La primera vez el panel te pide **conectar un modelo**. **Configurar los agentes de IA…** abre los
   [ajustes](#ajustes): pega una clave de API o pulsa **Iniciar sesión con el navegador**.
3. Escribe lo que quieres y pulsa <kbd>Intro</kbd>, o elige una de las sugerencias.

Claude necesita las dependencias opcionales (`anthropic` y `keyring`); el Pyzed Design compilado ya las trae:

```bash
pip install "pyzed-ui[agents]"     # o: uv add "pyzed-ui[agents]"
```

![Una conversación vacía con sugerencias](../../../../../screenshots/designer-agent-empty.png)

## El panel

| Parte | Qué hace |
| --- | --- |
| **Cabecera** | El título de la conversación, **Nueva conversación** (<kbd>+</kbd>), **Historial** y los **ajustes** del agente. |
| **Conversación** | Tus mensajes, las respuestas del agente (Markdown), su razonamiento (**Razonamiento**, plegado) y una línea por cada herramienta que usa: un indicador mientras corre, una marca cuando funcionó y una cruz roja cuando falló. Pulsa una línea para ver la entrada y el resultado. |
| **Cambios del agente** | Tras una ejecución que cambió algo: **Rechazar** deja cada formulario y archivo de código que tocó como estaban antes; **Conservar** oculta la barra. Deshacer (<kbd>Ctrl</kbd>+<kbd>Z</kbd>) sigue retrocediendo un cambio cada vez. |
| **Cuadro de mensaje** | <kbd>Intro</kbd> envía. Mientras el agente trabaja, el botón de enviar pasa a ser **Detener**. |
| **Modelo** | El modelo de esta conversación (y de las nuevas). Solo aparecen los proveedores configurados. |
| **Perfil** | **Escribir**: puede cambiar el formulario abierto, su código y archivos del proyecto. **Preguntar**: solo lee, responde y sugiere código. **Mínimo**: sin herramientas, una conversación simple. |

Cada mensaje lleva una nota breve de dónde estás (el documento abierto, los controles seleccionados, el manejador
del editor de código), así que "alinea estos" o "valida este campo" se refieren a lo que tienes delante.

### Qué puede hacer el agente

| Herramienta | Hace |
| --- | --- |
| `get_document` | Lee el formulario o componente abierto: ajustes, cada control con su rect, props, eventos y estilo, la selección y el código. |
| `add_control`, `update_control`, `remove_controls` | Coloca, cambia, mueve a un contenedor, renombra y borra controles. Tipos y props se comprueban contra la caja de herramientas. |
| `set_form`, `select_controls` | Cambia el título, tamaño, tema o estilo del formulario; selecciona controles para que los veas. |
| `wire_event`, `set_handler`, `set_code` | Conecta eventos y escribe un manejador o el módulo entero (debe ser Python válido). |
| `new_document`, `save_document` | Crea un formulario o componente junto al abierto y lo abre en una pestaña; guarda. |
| `list_components`, `describe_component`, `search_icons`, `list_themes`, `read_docs`… | El mismo conocimiento que el [servidor MCP](/pyzed/es/guides/mcp/): componentes, iconos, temas y esta documentación. |
| `validate_code`, `validate_form` | Revisan código y formularios antes de devolverlos. |
| `list_files`, `read_file`, `search_text`, `write_file` | Trabajan con archivos del proyecto, nunca fuera de su carpeta. |

Las herramientas que **crean o escriben archivos** preguntan antes: una tarjeta muestra **Permitir**,
**Permitir siempre** (el resto de la sesión) y **Denegar**. Desactiva **Preguntar antes de escribir archivos** en
los ajustes para saltarla. Los cambios al documento abierto nunca preguntan, porque se pueden deshacer.

## Generar formularios y componentes

**Ver → Generar un formulario con IA…** y **Generar un componente con IA…** (también en la paleta de comandos)
abren el panel con el principio de la petición ya escrito: termina la frase y pulsa <kbd>Intro</kbd>. Por ejemplo:

> Crea un formulario nuevo para un cliente: nombre, correo, un desplegable de país y botones Guardar / Cancelar;
> Guardar valida el correo y muestra un aviso.

El agente crea `customer.pzform` y `customer.py`, los abre, coloca y alinea los controles, conecta los botones y
escribe los manejadores. Con un componente crea el `.pzcomp` y su clase, que luego aparece en la caja de
herramientas como cualquier [componente](/pyzed/es/editor/component-designer/).

## Asistente en línea

En el editor de código, <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> (o el botón ✦ de su cabecera) abre una barra
sobre el código. Describe el cambio y pulsa <kbd>Intro</kbd>: el modelo reescribe el manejador (o el archivo
entero, en modo archivo completo) y el editor muestra el resultado. **Deshacer** devuelve el código anterior y
**Conservar** cierra la barra. Nada se aplica al formulario hasta que pulses **Aplicar**, como con tus propias
ediciones.

![Asistente en línea sobre un manejador](../../../../../screenshots/designer-agent-inline.png)

## Ajustes

**Ajustes → Agentes de IA → Ajustes de los agentes de IA…**, el engranaje de la cabecera del panel o **Ajustes de
los agentes de IA…** en la paleta de comandos.

![Proveedores, claves y opciones del agente](../../../../../screenshots/designer-agent-settings.png)

### Proveedores

| Proveedor | Cómo conectarlo | Notas |
| --- | --- | --- |
| **Anthropic** | Clave de API, `ANTHROPIC_API_KEY` o **Iniciar sesión con el navegador** | El inicio de sesión usa la CLI oficial de Anthropic (`ant auth login`); la CLI guarda el token de corta duración en su propia carpeta y Pyzed nunca lo ve. Los modelos Claude transmiten resúmenes de su razonamiento y usan pensamiento adaptativo. |
| **OpenAI** | Clave de API u `OPENAI_API_KEY` | |
| **Google Gemini** | Clave de AI Studio o `GEMINI_API_KEY` | A través del endpoint compatible con OpenAI de Gemini. |
| **OpenRouter** | **Iniciar sesión con el navegador**, clave de API u `OPENROUTER_API_KEY` | El inicio de sesión usa OAuth con PKCE: se abre la página de OpenRouter y la clave que emite para Pyzed va al llavero. |
| **Ollama**, **LM Studio** | Nada: corren en tu equipo | Cambia la **URL del servidor** si corren en otra máquina. |
| **Compatible con OpenAI** | URL del servidor y una clave si la necesita | vLLM, llama.cpp, Groq, Mistral, DeepSeek, una pasarela de empresa… |

Pulsa un proveedor para abrirlo: pega una clave y **Guardar**, **Iniciar sesión con el navegador**, **Obtener una
clave** (abre la página de claves del proveedor), **Quitar la clave** / **Cerrar sesión** y **Actualizar
modelos**, que pide al proveedor su lista de modelos para que aparezcan en el selector.

### Dónde se guardan las claves

Las claves y tokens van al **llavero del sistema operativo**: Llavero en macOS, Administrador de credenciales en
Windows, Secret Service (GNOME Keyring, KWallet) en Linux, bajo el servicio `pyzed`. Nunca se escriben en los
archivos de ajustes de Pyzed, en las conversaciones ni en el proyecto. Si no hay llavero, una clave que pegues se
conserva en memoria hasta que cierres el diseñador, y los ajustes lo indican; en ese caso usa una variable de
entorno.

El resto también se queda en tu equipo: los ajustes en `agents.json` y las conversaciones en `agents/threads/`,
ambos en la [carpeta de ajustes de Pyzed](/pyzed/es/editor/settings/#dónde-se-guardan). No se envía nada a ningún
sitio salvo las peticiones al proveedor que elijas.

### Opciones del agente

| Ajuste | Qué hace |
| --- | --- |
| **Modelo predeterminado** | El modelo con el que empiezan las conversaciones nuevas. |
| **Esfuerzo** | Cuánto piensa el modelo antes de responder (`low` … `max`). Solo Claude; `high` por defecto. |
| **Preguntar antes de escribir archivos** | Crear formularios y componentes y guardar archivos esperan tu permiso. Activado por defecto. |
| **Mostrar el razonamiento** | Muestra los resúmenes del razonamiento del modelo en la conversación. |
| **Reglas** | Instrucciones añadidas a cada conversación, como las reglas de Zed: "Responde en español", "Nombra los botones con el sufijo `_button`"… |

## Historial

**Historial** en la cabecera lista tus conversaciones, de la más reciente a la más antigua. Pulsa una para
continuarla (el agente recuerda toda la conversación) o bórrala. Se guardan las últimas 200.

## Usar agentes en tu propia app

El agente no está atado al diseñador: `pyzed.agents` da a cualquier app los mismos proveedores, el llavero y el
bucle del agente. Consulta [Agentes de IA en tu app](/pyzed/es/guides/agents/).
