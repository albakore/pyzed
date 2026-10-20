---
title: Servidor MCP
description: "Conecta Cursor, VS Code, Zed, Claude Desktop o cualquier cliente MCP a Pyzed: componentes, documentación, generadores de código, validación y capturas sin pantalla para agentes de IA."
sidebar:
  order: 1
---

`pyzed mcp` es un servidor del [Model Context Protocol](https://modelcontextprotocol.io) que viene con Pyzed. Le da
a un agente de IA lo que sabe una persona experta en Pyzed, sacado de la **versión instalada** del paquete: la firma
y la documentación de cada componente, los iconos, los temas, esta documentación, los ejemplos y bloques,
generadores de apps, componentes y formularios, dos validadores, un renderizador sin pantalla y herramientas de
proyecto para construir una app completa en una carpeta.

Esta página es la versión corta. La [referencia completa de MCP](/pyzed/es/guides/mcp/) lista cada herramienta,
recurso y prompt.

## Conecta tu agente

La mayoría de los clientes MCP (Claude Desktop, Cursor, Windsurf y otros) leen un JSON con esta forma, como
`.cursor/mcp.json` en tu proyecto:

```json
{
  "mcpServers": {
    "pyzed": {
      "command": "uvx",
      "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"]
    }
  }
}
```

VS Code lee `.vscode/mcp.json`:

```json
{
  "servers": {
    "pyzed": { "type": "stdio", "command": "uvx", "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"] }
  }
}
```

Zed y otros editores aceptan el mismo comando y argumentos en sus propios ajustes (Zed los llama *context servers*).

:::tip[Usa el entorno de tu proyecto]
En un proyecto creado con `pyzed new`, apunta el agente al entorno del proyecto para que el servidor vea la misma
versión de Pyzed y **tus propios componentes**: `"command": "uv", "args": ["run", "pyzed", "mcp"]`. Si Pyzed ya está
instalado, `"command": "pyzed", "args": ["mcp"]` también sirve.
:::

`uvx` ejecuta el servidor sin instalar nada antes; necesita [uv](https://docs.astral.sh/uv/). Sin uv, ejecuta
`pip install "pyzed-ui[mcp]"` (Python 3.10 o superior) y usa `pyzed mcp` como comando.

## Qué puede hacer el agente

| Grupo | Herramientas | Para |
| --- | --- | --- |
| Aprender | `get_guide`, `list_guides`, `list_docs`, `read_docs` | Leer cómo funciona Pyzed, sus reglas, el recetario de ejemplos ejecutables, temas como juegos o shaders y cualquier página de esta documentación (en inglés o español). |
| Consultar | `list_components`, `describe_component`, `search_reference`, `read_reference`, `search_icons`, `list_themes`, `editor_keymap` | Obtener firmas exactas, parámetros, nombres de iconos, tokens de color y atajos en vez de adivinarlos. |
| Reutilizar | `list_examples`, `read_example` | Leer los ejemplos, los [Bloques](/pyzed/es/blocks/) (`read_example("blocks/settings")`), juegos, showcase e integraciones con backend. |
| Generar | `new_app`, `new_component`, `new_form` | Partir de esqueletos correctos: una app, un `pz.Component`, un formulario del diseñador. |
| Comprobar | `validate_code`, `validate_form` | Detectar nombres que no existen, argumentos mal escritos, efectos en `view()` y formularios rotos antes de ejecutar. |
| Ver | `screenshot` | Renderizar la app o un componente sin pantalla y recibir un PNG. |
| Planificar | `plan_app` | Encontrar los bloques, ejemplos, componentes y guías que necesita una app, y los pasos para construirla. |
| Construir | `project_info`, `create_project`, `list_files`, `read_file`, `write_files`, `add_dependency`, `check_project`, `run_tests`, `screenshot_project` | Crear un proyecto, escribirlo, añadir librerías, revisarlo, probarlo y mirarlo, en la carpeta donde corre el servidor y en el entorno del propio proyecto. |
| Ver en vivo | `start_live_preview`, `live_preview_status`, `stop_live_preview` | Abrir la app en una ventana con hot reload, para verla cambiar mientras el agente escribe cada archivo. |

Los prompts `create_app`, `create_component`, `create_form` y `build_project` (una app completa, de principio a fin) empiezan una tarea con los pasos correctos, y los
clientes que admiten recursos pueden adjuntar `pyzed://best-practices` o `pyzed://docs/{slug}`.

## Peticiones que aprovechan el servidor

- *"Usa las herramientas MCP de pyzed. Lee primero las buenas prácticas y luego construye..."*: los agentes siguen
  mejor las instrucciones sobre sus herramientas cuando las nombras.
- *"Valida con validate_code y mira una captura antes de responder."*: el agente cierra el ciclo.
- *"Parte del bloque de dashboard."*: una pantalla probada es mejor base que un archivo vacío.
- *"Consulta describe_component de ui.table antes de usarlo."*: para componentes con muchos parámetros.

Más en la [guía de prompts](/pyzed/es/ai/prompting/), con una sesión completa y las salidas reales de las herramientas.

## Seguridad

- Por **stdio** (lo habitual) el servidor solo habla con el agente que lo inició.
- `screenshot` **ejecuta el código que recibe** en otro proceso, con un límite de 60 segundos y sin abrir ventanas.
  Trátalo como ejecutar código tú mismo: los agentes suelen pedir permiso antes de usar herramientas; mantenlo así
  con prompts que no sean de confianza.
- Las herramientas de proyecto solo leen y escriben dentro de la carpeta donde arrancó el servidor (o `--root RUTA`),
  nunca archivos que puedan guardar secretos (`.env`, claves...), y ejecutan uv, ruff, ty y pytest ahí.
- `pyzed mcp --transport streamable-http` lo sirve en `127.0.0.1` sin autenticación; ahí `screenshot` y las
  herramientas de proyecto están desactivados salvo que añadas `--allow-code`.

## Problemas frecuentes

| Problema | Solución |
| --- | --- |
| El agente no muestra herramientas `pyzed` | Ejecuta a mano el comando de la configuración (`uvx --from "pyzed-ui[mcp]" pyzed mcp`): debería quedarse esperando en silencio. Revisa los registros MCP del cliente. |
| `ModuleNotFoundError: mcp` | Instala el extra: `pip install "pyzed-ui[mcp]"`. Hace falta Python 3.10+. |
| El agente no conoce tus componentes | Ejecuta el servidor desde el entorno del proyecto (`uv run pyzed mcp`) para que los importe. |
| La documentación no se puede leer sin conexión | Las páginas se leen de una copia del repositorio o se descargan de GitHub; sin conexión, usa una copia local o las [páginas en Markdown](/pyzed/es/ai/llms-txt/). |
| Las capturas tardan demasiado | El código debe definir una `pz.App` o una función `preview()`; un trabajo largo en `__init__` llega al límite de 60 segundos. |

## Sin MCP

Todo el servidor es Python normal y se puede usar desde scripts, tests o tu propio agente:

```python
from pyzed.mcp import knowledge, scaffold, validate

print(knowledge.describe_component("ui.progress")["signature"])
print(validate.check_code(open("main.py").read())["issues"])
print(scaffold.app("Notes", layout="workspace"))
```

Los agentes que no pueden usar MCP pueden leer la documentación como texto: mira
[llms.txt y reglas para editores](/pyzed/es/ai/llms-txt/).
