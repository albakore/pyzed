---
title: El agente de Pyzed Design
description: "El agente de IA de Pyzed Design de un vistazo: un compositor al estilo de Zed que crea formularios, componentes y apps completas, ve imágenes, usa servidores MCP y agentes externos e inicia sesión en muchos proveedores de modelos."
sidebar:
  order: 2
  label: Agente en Pyzed Design
---

Pyzed Design, el diseñador visual, tiene un agente de IA en su panel derecho. Describes una pantalla con palabras y
el agente coloca los controles, conecta los eventos, escribe los handlers en Python, crea formularios, componentes o
un proyecto entero, mira el resultado y comprueba su propio código. Cada cambio en el formulario abierto es un paso
normal de deshacer, y **Rechazar** devuelve todo lo que tocó una ejecución.

![El agente añadió un interruptor y conectó su evento](../../../../../screenshots/designer-agent.png)

Esta página es un resumen. El manual completo, con cada botón, comando y ajuste, está en
[Pyzed Design → Agentes de IA](/pyzed/es/editor/ai-agents/).

## De un vistazo

| Función | Qué hace | Detalles |
| --- | --- | --- |
| **Compositor** | Un cuadro de mensaje al estilo de Zed: <kbd>@</kbd> adjunta la selección, el formulario, su código, un control o un archivo; <kbd>/</kbd> ejecuta comandos como `/app`, `/fix`, `/tidy` y `/look`. | [El panel](/pyzed/es/editor/ai-agents/#el-panel) |
| **Modos de permisos** | **Preguntar antes de escribir** (por defecto), **Omitir permisos**, **Solo lectura** y **Solo conversación**. Los cambios en el formulario abierto nunca preguntan, porque se pueden deshacer. | [Modos de permisos](/pyzed/es/editor/ai-agents/#el-panel) |
| **Muchos proveedores** | Anthropic, OpenAI, Gemini, Vertex AI, GitHub Copilot, OpenRouter, xAI, Mistral, DeepSeek, Groq, Ollama, LM Studio y cualquier servidor compatible con OpenAI, con esfuerzo y modo rápido en Claude. | [Proveedores](/pyzed/es/editor/ai-agents/#proveedores) |
| **Inicio de sesión** | Iniciar sesión con el navegador (se recoge la clave copiada), OAuth de OpenRouter, **Iniciar sesión con GitHub** (flujo de dispositivo) e **Iniciar sesión con Google** para Vertex AI. | [Iniciar sesión](/pyzed/es/editor/ai-agents/#iniciar-sesión) |
| **Claude sin clave** | La federación de identidad de cargas de trabajo cambia el token de tu proveedor de identidad por un token de Claude de corta duración. | [Claude sin clave de API](/pyzed/es/editor/ai-agents/#claude-sin-clave-de-api) |
| **Imágenes** | Adjunta o pega imágenes, o una captura del formulario; el agente también mira el formulario por su cuenta con `screenshot_form`. | [Imágenes](/pyzed/es/editor/ai-agents/#imágenes) |
| **Apps completas** | `/app` crea un proyecto, añade paquetes, escribe formularios y componentes, los mira y ejecuta las comprobaciones. | [Crear una aplicación](/pyzed/es/editor/ai-agents/#crear-una-aplicación) |
| **Servidores MCP** | Suma las herramientas de cualquier servidor del Model Context Protocol (comando local o URL); sus secretos van al llavero. | [Servidores MCP](/pyzed/es/editor/ai-agents/#servidores-mcp) |
| **Agentes externos** | Ejecuta Claude Code, Gemini CLI, Codex o cualquier agente del Agent Client Protocol dentro del panel, compartiendo el servidor MCP de Pyzed. | [Agentes externos](/pyzed/es/editor/ai-agents/#agentes-externos) |
| **Asistente en línea** | <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> en el editor de código reescribe un handler o el archivo en su sitio. | [Asistente en línea](/pyzed/es/editor/ai-agents/#asistente-en-línea) |
| **Credenciales** | Las claves y tokens viven en el llavero del sistema, nunca en los ajustes ni en el proyecto. | [Claves de API y credenciales](/pyzed/es/ai/api-keys/) |

![Añadir contexto con @](../../../../../screenshots/designer-agent-mention.png)

## Una primera sesión

1. Abre el panel: la pestaña **Agente** del dock derecho, o <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd>.
2. Conecta un modelo: pulsa un proveedor e inicia sesión, o elige un modelo local. Consulta
   [Claves de API y credenciales](/pyzed/es/ai/api-keys/) para las claves, las variables de entorno y las buenas
   prácticas.
3. Pide una pantalla: *"Un formulario de cliente: nombre, email, un desplegable de país y Guardar / Cancelar; Guardar
   valida el email y muestra un aviso"*. Luego afínala: selecciona controles y pide, adjunta un boceto o ejecuta
   `/look` y `/fix`.
4. Revisa la ejecución con **Conservar** o **Rechazar** y pulsa <kbd>F5</kbd> para ejecutar el formulario.

Hay consejos para buenos prompts en
[Cómo obtener buenos resultados](/pyzed/es/editor/ai-agents/#cómo-obtener-buenos-resultados) y en la
[guía de prompts](/pyzed/es/ai/prompting/).

## El mismo agente en tu propia app

El panel funciona sobre `pyzed.agents`, que cualquier app de Pyzed puede usar: los mismos proveedores, el llavero,
imágenes, servidores MCP, agentes externos, herramientas escritas como funciones de Python y eventos en streaming.
Consulta [Crear apps con IA](/pyzed/es/ai/ai-apps/) y [Agentes de IA en tu app](/pyzed/es/guides/agents/).
