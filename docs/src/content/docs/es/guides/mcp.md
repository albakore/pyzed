---
title: Servidor MCP para agentes de IA
description: Conecta Claude, Cursor, VS Code y otros agentes de IA a Pyzed para que conozcan sus componentes y buenas prácticas, y generen y comprueben código.
sidebar:
  order: 16
---

Pyzed incluye un servidor [MCP](https://modelcontextprotocol.io). Conéctalo a tu agente de IA (Claude Code,
Claude Desktop, Cursor, VS Code, Zed...) y el agente deja de adivinar: consulta la firma exacta de cada widget
y componente, lee esta documentación, sigue las buenas prácticas de Pyzed, genera apps, componentes y
formularios del diseñador, comprueba el código que escribe e incluso mira una captura del resultado.

## Instalación

El servidor es un extra opcional del paquete (necesita Python 3.10 o superior):

```bash
pip install "pyzed-ui[mcp]"     # o: uv add "pyzed-ui[mcp]"
pyzed mcp                       # arranca el servidor por stdio (también python -m pyzed.mcp)
```

Casi nunca lo ejecutas tú: lo arranca el agente. Con [uv](https://docs.astral.sh/uv/) el agente puede
ejecutarlo sin instalar nada antes, con `uvx --from "pyzed-ui[mcp]" pyzed mcp`.

## Conecta tu agente

### Claude Code

```bash
claude mcp add pyzed -- uvx --from "pyzed-ui[mcp]" pyzed mcp
```

Dentro de un proyecto creado con `pyzed new`, usa el entorno del propio proyecto para que el servidor vea la
misma versión de Pyzed y tus componentes: `claude mcp add pyzed -- uv run pyzed mcp`.

### Claude Desktop, Cursor y otros clientes

La mayoría de clientes leen un JSON con la misma forma (`claude_desktop_config.json`, `.cursor/mcp.json`...):

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

### VS Code

En `.vscode/mcp.json`:

```json
{
  "servers": {
    "pyzed": { "type": "stdio", "command": "uvx", "args": ["--from", "pyzed-ui[mcp]", "pyzed", "mcp"] }
  }
}
```

Si Pyzed ya está instalado en un entorno, `"command": "pyzed", "args": ["mcp"]` funciona en todos.

## Qué recibe el agente

### Herramientas

| Herramienta | Qué hace |
| --- | --- |
| `get_guide` | Cómo funciona Pyzed (`"overview"`) y sus reglas (`"best-practices"`). |
| `list_components` | Cada widget (`pz.*`), componente estilo Zed (`pz.ui.*`), tipo de la caja de herramientas del diseñador y clase `pz.Component`, con un resumen de una línea. Filtra por `kind`, `query` o `category`. |
| `describe_component` | La firma, la documentación y los parámetros de un widget o componente (`"pz.column"`, `"ui.button"`), o las propiedades y eventos de un tipo del diseñador (`"designer:button"`). |
| `search_icons` | Nombres de iconos Lucide para `icon=` y `pz.icon`. |
| `list_themes` | Los temas incluidos y los tokens de color que aceptan los estilos (`"accent"`, `"panel"`...). |
| `list_docs`, `read_docs` | Las páginas de esta documentación, en inglés o en español. |
| `list_examples`, `read_example` | El código de las apps de ejemplo (un editor tipo Zed, una lista de tareas, diálogos...). |
| `new_app` | Un script `pz.App` ejecutable: un punto de partida simple o un workspace tipo Zed. |
| `new_component` | El esqueleto de un `pz.Component` con sus props, estado y eventos. |
| `new_form` | Un formulario del diseñador visual: el `.pzform` y su módulo de handlers. |
| `validate_code` | Revisa el código sin ejecutarlo: nombres que no existen en `pz` o `pz.ui`, argumentos que una función no acepta, apps sin `view()`, componentes sin `render()`, efectos secundarios en `view()`, lambdas en bucles que no capturan la variable y las comprobaciones de pyflakes de ruff si está instalado. |
| `validate_form` | Revisa un `.pzform` (tipos, propiedades, eventos, nombres, contenedores) y que su módulo de handlers defina cada handler. |
| `screenshot` | Dibuja el código fuera de pantalla (sin ventana ni GPU) y devuelve un PNG, para que el agente vea lo que construyó. |

### Recursos y prompts

Los clientes que admiten recursos pueden adjuntar `pyzed://guide`, `pyzed://best-practices`,
`pyzed://components`, `pyzed://themes`, `pyzed://docs`, `pyzed://component/{name}` y
`pyzed://docs/{slug}` (con `--` en lugar de `/`, como `guides--layout`).

Los prompts `create_app`, `create_component` y `create_form` empiezan una tarea con los pasos correctos:
leer las guías, buscar componentes existentes, generar, validar y previsualizar.

## Ejemplo de sesión

> Haz un componente de Pyzed que muestre una valoración con estrellas y deje cambiarla.

Una ejecución típica del agente con el servidor conectado:

1. `get_guide("best-practices")` y luego `list_components(query="rating")` para comprobar que no existe nada parecido.
2. `new_component("star rating", props=[{"name": "value", "type": "int", "default": 0}], events={"change": "Se eligió una estrella."}, icon="star")`.
3. Completa `render()` con `pz.row`, `pz.text(...).on(click=...)` y `self.emit("change", i)`, consultando
   `describe_component("pz.text")` para los parámetros.
4. `validate_code(code)` y `screenshot(code + "def preview():\n    return StarRating(value=3)")` para verlo.

## Cómo funciona

El servidor vive en el paquete (`pyzed.mcp`), así que lo que sabe coincide siempre con la versión instalada:
las firmas y docstrings salen del propio código, las descripciones de esta referencia y la caja de
herramientas del diseñador de su registro, incluidas tus propias clases `pz.Component`. Las páginas de la
documentación y los ejemplos se leen del repositorio si trabajas desde el código fuente y, si no, se
descargan de GitHub en el tag de la versión instalada.

`screenshot` ejecuta el código en un proceso aparte con un límite de 60 segundos y sustituye `pz.run`, así
que no se abre ninguna ventana. Usa el mismo renderizador fuera de pantalla que
[tests y capturas](/pyzed/es/guides/testing/).

`pyzed.mcp.knowledge`, `pyzed.mcp.scaffold` y `pyzed.mcp.validate` son Python normal y funcionan sin el SDK
de MCP, por ejemplo desde tus propios scripts o tests.
