---
title: Agentes de IA
description: "El panel del agente de Pyzed Design: un agente de IA que crea formularios y componentes y escribe su código Python, con asistente en línea y varios modelos."
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
2. La primera vez el panel te pide **conectar un modelo** y muestra los proveedores principales. Pulsa uno para
   [iniciar sesión con el navegador](#iniciar-sesión), o **Todos los proveedores…** para el resto.
3. Escribe lo que quieres y pulsa <kbd>Intro</kbd>, o elige una de las sugerencias.

Claude necesita las dependencias opcionales (`anthropic` y `keyring`); el Pyzed Design compilado ya las trae:

```bash
pip install "pyzed-ui[agents]"     # o: uv add "pyzed-ui[agents]"
```

![Una conversación vacía con sugerencias](../../../../../screenshots/designer-agent-empty.png)

### Iniciar sesión

El inicio de sesión ocurre dentro de Pyzed Design; no hace falta ningún otro programa.

- **Anthropic, OpenAI, Gemini, xAI, Mistral, DeepSeek, Groq**: estos proveedores no permiten que otras apps inicien
  sesión con OAuth, así que Pyzed abre la página de claves de API del proveedor en tu navegador. Crea una clave
  allí y pulsa su botón **Copiar**. Pyzed detecta la clave copiada, la comprueba con el proveedor, la guarda en el
  llavero del sistema y carga los modelos del proveedor. Mientras espera, una tarjeta **Iniciando sesión** ofrece
  **Pegar la clave** (leer el portapapeles ahora), **Abrir la página otra vez** y **Cancelar**. El portapapeles solo
  se lee mientras se ve esa tarjeta (cinco minutos como mucho), y solo se usa un texto que parezca una clave de ese
  proveedor.
- **OpenRouter**: OAuth real con PKCE. Apruebas a Pyzed en la página de OpenRouter y la clave que emite vuelve a
  Pyzed directamente; no hay nada que copiar.
- **Ollama, LM Studio**: no hay que iniciar sesión. Al pulsarlos se piden los modelos al servidor local.

Siempre puedes pegar una clave a mano en los [ajustes](#ajustes) o definir la variable de entorno del proveedor.

![Iniciando sesión en Anthropic: la página de claves está abierta y Pyzed espera la clave copiada](../../../../../screenshots/designer-agent-connect.png)

## El panel

| Parte | Qué hace |
| --- | --- |
| **Cabecera** | El título de la conversación, **Nueva conversación** (<kbd>+</kbd>), **Historial**, **Expandir el panel** (ocupa toda la ventana; púlsalo otra vez para devolverlo a su dock) y los **ajustes** del agente. |
| **Conversación** | Tus mensajes, las respuestas del agente (Markdown), su razonamiento (**Razonamiento**, plegado) y una línea por cada herramienta que usa: un indicador mientras corre, una marca cuando funcionó y una cruz roja cuando falló. Pulsa una línea para ver la entrada y el resultado. |
| **Cambios del agente** | Tras una ejecución que cambió algo: **Rechazar** deja cada formulario y archivo de código que tocó como estaban antes; **Conservar** oculta la barra. Deshacer (<kbd>Ctrl</kbd>+<kbd>Z</kbd>) sigue retrocediendo un cambio cada vez. |
| **Cuadro de mensaje** | <kbd>Intro</kbd> envía. Escribe <kbd>@</kbd> para [añadir contexto](#añadir-contexto-con-) y <kbd>/</kbd> para [comandos](#comandos-con-). Mientras el agente trabaja, el botón de enviar pasa a ser **Detener**. |
| **+** | Empieza una mención con @, como escribir <kbd>@</kbd>. |
| **Modo de permisos** | Qué puede hacer el agente sin preguntar (ver abajo). |
| **Modelo** | Todos los proveedores con sus modelos. Un proveedor sin configurar muestra **Conectar…**, que inicia sesión ahí mismo. |
| **Esfuerzo** | Cuánto piensa el modelo antes de responder: **Bajo**, **Medio**, **Alto**, **Muy alto**, **Máximo**. Solo modelos Claude. |
| **Rápido** | Modo rápido: respuestas más rápidas a mayor precio, en Claude Opus 5.5 y Opus 5 a través de la API de Claude. |

| Modo de permisos | Qué puede hacer el agente |
| --- | --- |
| **Preguntar antes de escribir** | Edita el formulario abierto y su código libremente (cada cambio se puede deshacer); pregunta antes de crear documentos o escribir archivos. Es el modo por defecto. |
| **Omitir permisos** | Nunca pregunta. |
| **Solo lectura** | Solo lee: responde preguntas y sugiere código sin cambiar nada. |
| **Solo conversación** | Sin herramientas: una conversación simple con el modelo. |

![Todos los proveedores en el selector de modelos](../../../../../screenshots/designer-agent-models.png)

Cada mensaje lleva una nota breve de dónde estás (el documento abierto, los controles seleccionados, el manejador
del editor de código), así que "alinea estos" o "valida este campo" se refieren a lo que tienes delante.

### Añadir contexto con @

Escribe <kbd>@</kbd> (o pulsa **+**) y elige qué adjuntar: la **selección**, el **formulario** abierto, su
**código**, uno de sus **controles** o un **archivo** del proyecto. Sigue escribiendo para filtrar la lista;
<kbd>Intro</kbd> elige la fila resaltada. Lo que elijas aparece como una etiqueta sobre el mensaje y su contenido
va con el mensaje, así el agente no tiene que buscarlo. Los archivos que pueden tener secretos (`.env`, claves…)
nunca se ofrecen.

![Añadir contexto con @](../../../../../screenshots/designer-agent-mention.png)

### Comandos con /

Escribe <kbd>/</kbd> al principio del mensaje:

| Comando | Hace |
| --- | --- |
| `/new` | Empieza una conversación nueva. |
| `/history` | Muestra las conversaciones pasadas. |
| `/settings` | Abre los ajustes de los agentes de IA. |
| `/form`, `/component` | Empieza una petición para generar un formulario o un componente. |
| `/explain` | Explica el formulario abierto y sus manejadores. |
| `/fix` | Revisa el código del formulario con `validate_code` y corrige lo que encuentre. |
| `/tidy` | Alinea los controles e iguala los márgenes. |

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

En el modo **Preguntar antes de escribir**, las herramientas que **crean o escriben archivos** preguntan antes: una
tarjeta muestra **Permitir**, **Permitir siempre** (el resto de la sesión) y **Denegar**. **Omitir permisos** se la
salta. Los cambios al documento abierto nunca preguntan, porque se pueden deshacer.

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
| **Anthropic** | **Iniciar sesión con el navegador**, clave de API o `ANTHROPIC_API_KEY` | Los modelos Claude transmiten resúmenes de su razonamiento, usan pensamiento adaptativo y admiten esfuerzo y modo rápido. Si existe un perfil de la CLI de Anthropic (`ant auth login`) también se usa, pero la CLI no hace falta. |
| **OpenAI** | **Iniciar sesión con el navegador**, clave de API u `OPENAI_API_KEY` | |
| **Google Gemini** | **Iniciar sesión con el navegador**, clave de AI Studio o `GEMINI_API_KEY` | A través del endpoint compatible con OpenAI de Gemini. |
| **OpenRouter** | **Iniciar sesión con el navegador** (OAuth), clave de API u `OPENROUTER_API_KEY` | OAuth con PKCE: la clave que OpenRouter emite para Pyzed va al llavero. |
| **xAI**, **Mistral**, **DeepSeek**, **Groq** | **Iniciar sesión con el navegador**, clave de API o `XAI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY` | Sus modelos aparecen tras iniciar sesión. |
| **Ollama**, **LM Studio** | Nada: corren en tu equipo | Cambia la **URL del servidor** si corren en otra máquina. |
| **Compatible con OpenAI** | URL del servidor y una clave si la necesita | vLLM, llama.cpp, una pasarela de empresa… |

Pulsa un proveedor para abrirlo: **Iniciar sesión con el navegador** (ver [Iniciar sesión](#iniciar-sesión)), pega
una clave y **Guardar**, **Obtener una clave** (abre la página de claves del proveedor), **Quitar la clave** y
**Actualizar modelos**, que pide al proveedor su lista de modelos para que aparezcan en el selector.

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
| **Modo rápido** | Respuestas más rápidas a mayor precio (Claude Opus 5.5 y Opus 5). También en el cuadro de mensaje. |
| **Preguntar antes de escribir archivos** | Crear formularios y componentes y guardar archivos esperan tu permiso. Activado por defecto; equivale a los modos **Preguntar antes de escribir** / **Omitir permisos**. |
| **Mostrar el razonamiento** | Muestra los resúmenes del razonamiento del modelo en la conversación. |
| **Reglas** | Instrucciones añadidas a cada conversación, como las reglas de Zed: "Responde en español", "Nombra los botones con el sufijo `_button`"… |

## Historial

**Historial** en la cabecera lista tus conversaciones, de la más reciente a la más antigua. Pulsa una para
continuarla (el agente recuerda toda la conversación) o bórrala. Se guardan las últimas 200.

## Usar agentes en tu propia app

El agente no está atado al diseñador: `pyzed.agents` da a cualquier app los mismos proveedores, el llavero y el
bucle del agente. Consulta [Agentes de IA en tu app](/pyzed/es/guides/agents/).
