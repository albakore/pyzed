---
title: Agentes de IA en tu app
description: "pyzed.agents: añade IA a apps de escritorio en Python con Anthropic, OpenAI, Gemini, OpenRouter u Ollama, da herramientas al modelo y transmite respuestas."
sidebar:
  order: 17
---

`pyzed.agents` es el motor del [panel del agente](/pyzed/es/editor/ai-agents/) del diseñador, y funciona en
cualquier app de Pyzed: una sola API para varios proveedores de modelos, herramientas escritas como funciones de
Python normales, eventos en streaming para la UI, conversaciones guardadas y claves en el llavero del sistema
operativo.

```bash
pip install "pyzed-ui[agents]"     # anthropic (Claude) y keyring
```

## Un primer agente

```python
from pyzed import agents

agents.set_key("anthropic", "sk-ant-…")          # una vez: se guarda en el llavero del sistema


@agents.tool
def stock(product: str) -> int:
    """Cuántas unidades de un producto hay en stock.

    product: el nombre del producto.
    """
    return {"chair": 4, "desk": 0}.get(product, 0)


agent = agents.Agent("anthropic:claude-opus-5-5", tools=[stock], system="Ayudas al personal de la tienda.")
print(agent.run("¿Puedo vender dos escritorios hoy?"))
```

`run` llama al modelo, ejecuta las herramientas que pide, le devuelve los resultados y repite hasta que el modelo
responde. Devuelve la última respuesta y nunca lanza excepciones: los fallos (una clave mala, sin red) llegan como
un evento `"error"` y como el texto devuelto. `agent.messages` guarda la conversación, así que el siguiente `run`
la continúa.

## Modelos y proveedores

Un modelo se nombra `"<proveedor>:<modelo>"`:

| Proveedor | Ejemplo | Credenciales |
| --- | --- | --- |
| `anthropic` | `anthropic:claude-opus-5-5` | `set_key`, `ANTHROPIC_API_KEY` (también sirve un perfil de `ant auth login`) o [federación de identidades](#claude-sin-clave-de-api) |
| `openai` | `openai:<modelo>` | `set_key` u `OPENAI_API_KEY` |
| `google` | `google:<modelo gemini>` | `set_key` o `GEMINI_API_KEY` |
| `openrouter` | `openrouter:anthropic/claude-opus-5-5` | `set_key`, `OPENROUTER_API_KEY` o `agents.login.openrouter_login()` |
| `xai`, `mistral`, `deepseek`, `groq` | `groq:<modelo>` | `set_key` o `XAI_API_KEY`, `MISTRAL_API_KEY`, `DEEPSEEK_API_KEY`, `GROQ_API_KEY` |
| `github` | `github:openai/gpt-4.1` | GitHub Models: `agents.login.github_device_code()` (flujo de dispositivo), un token detallado con el permiso Models o `GITHUB_TOKEN` |
| `vertex` | `vertex:google/gemini-2.5-pro` | Gemini en Vertex AI: `agents.login.google_login()` o las credenciales de gcloud del equipo; `settings.provider("vertex").project` |
| `ollama`, `lmstudio` | `ollama:qwen3:8b` | ninguna (local) |
| `custom` | `custom:<modelo>` | la URL del servidor en los ajustes y una clave si hace falta |

`agents.list_models("openai")` pide a un proveedor sus modelos. Claude va por el SDK oficial `anthropic` con
pensamiento adaptativo, el ajuste `effort`, caché de prompts y el respaldo del servidor ante rechazos; el resto de
proveedores, por la API Chat Completions compatible con OpenAI.

## Ajustes

```python
settings = agents.AgentSettings(model="ollama:qwen3:8b", effort="medium", profile="ask",
                                rules="Responde en español.")
settings.provider("ollama").base_url = "http://gpu-box:11434/v1"
agent = agents.Agent(tools=[stock], settings=settings)
```

| Campo | Significado |
| --- | --- |
| `model` | Modelo predeterminado. |
| `effort` | `low`, `medium`, `high`, `xhigh` o `max` (Claude). |
| `fast` | Modo rápido en los modelos de `providers.FAST_MODELS` (Claude Opus 5.5 y Opus 5, solo la API de Claude): respuestas más rápidas a mayor precio. |
| `profile` | `"write"` (todas las herramientas), `"ask"` (solo las que no tienen `writes=True`) o `"minimal"` (ninguna). |
| `mode` | El modo de permisos del panel del agente, un atajo sobre `profile` y `confirm_writes`: `"ask"`, `"bypass"`, `"read"` o `"chat"`. |
| `confirm_writes` | Llama a `confirm(tool, args)` antes de una herramienta con `writes=True` (activo por defecto). Sin un callback `confirm` esas herramientas se rechazan; desactívalo para que se ejecuten sin preguntar. |
| `rules` | Texto añadido al prompt de sistema. |
| `keep_history` | Si Pyzed Design guarda las conversaciones en este equipo (activo por defecto). |
| `providers[id].base_url` / `.models` | URL del servidor y modelos ofrecidos para un proveedor. |

`agents.providers.load()` y `save()` leen y escriben `agents.json` en la carpeta de ajustes de Pyzed (los ajustes
del diseñador); las claves nunca forman parte de él.

## Herramientas

`@agents.tool` construye el esquema JSON a partir de la firma: `str`, `int`, `float`, `bool`, `list`, `dict` y
`Optional[...]`; los argumentos con valor por defecto son opcionales. El primer párrafo del docstring describe la
herramienta y las líneas `nombre: texto` describen los argumentos. Devuelve un texto o cualquier cosa que JSON
pueda codificar.

```python
@agents.tool(writes=True, title="Haciendo un pedido")
def order(product: str, units: int) -> dict:
    """Pide unidades de un producto al proveedor."""
    ...
```

| Opción | Significado |
| --- | --- |
| `writes=True` | Cambia algo: se omite en el perfil `"ask"` y se confirma antes cuando `confirm_writes` está activo. |
| `ui=True` | Se ejecuta a través del `executor` del agente (ver abajo). |
| `title` | Texto corto para tu UI mientras corre. |

Los argumentos del modelo se comprueban contra el esquema antes de ejecutar la función; un argumento erróneo o
ausente, o una excepción, vuelve al modelo como error para que corrija la llamada.

Herramientas listas: `agents.pyzed_tools()` (componentes, iconos, temas, documentación, generadores y
comprobaciones de Pyzed, lo mismo que el [servidor MCP](/pyzed/es/guides/mcp/)) y `agents.file_tools(carpeta)`
(listar, leer, buscar y escribir archivos, nunca fuera de `carpeta`). Las herramientas de archivos nunca abren
claves ni credenciales (`.env`, `*.pem`, `*.key`, claves SSH...; `agents.tools.SECRET_FILES`), así que una
inyección de prompt en un archivo del proyecto no puede enviarlas al proveedor; pasa `hidden=` para cambiar la lista.

## Imágenes

Los modelos que admiten imágenes pueden verlas en un mensaje, y las herramientas pueden devolverlas:

```python
image = agents.Image.open("maqueta.png")          # PNG, JPEG, GIF o WebP, hasta agents.agent.IMAGE_LIMIT
agent.run([{"type": "text", "text": "Construye esta pantalla."}, agents.image_block(image)])


@agents.tool
def chart() -> list:
    """Dibuja el gráfico de ventas."""
    return ["El gráfico:", agents.Image(render_png())]   # el texto y las imágenes vuelven al modelo
```

`image_block` también acepta los bytes o una ruta. Una herramienta que devuelve un `Image`, o una lista con texto e
imágenes, responde con ellos; los proveedores que no admiten imágenes en los resultados de herramientas las reciben
en el mensaje siguiente.

## Servidores MCP

`agents.mcp_client` se conecta a servidores del [Model Context Protocol](https://modelcontextprotocol.io), locales
(stdio) o remotos (Streamable HTTP), y convierte sus herramientas en herramientas del agente:

```python
from pyzed.agents import mcp_client, providers

fetch = providers.MCPServerConfig("fetch", "uvx", ["mcp-server-fetch"])
github = providers.MCPServerConfig("github", url="https://api.githubcopilot.com/mcp/",
                                   secret_names=["Authorization"])
mcp_client.set_secrets("github", {"Authorization": "Bearer …"})   # en el llavero

servers = mcp_client.Servers([fetch, github], cwd=".")
agent = agents.Agent("anthropic:claude-opus-5-5", tools=servers.tools())
...
servers.close()
```

Las herramientas se llaman `mcp_<servidor>_<herramienta>` y las que el servidor no marca con `readOnlyHint` son
`writes=True`, así que se confirman antes. `secret_names` lista las variables de entorno (stdio) o cabeceras (HTTP)
cuyos valores `set_secrets` guarda en el llavero. Un servidor que falla se omite; pasa `on_error(servidor, mensaje)`
a `tools()` para enterarte. `mcp_client.MCPClient` habla directamente con un servidor (`list_tools`, `call`).

## Agentes externos

`agents.acp` ejecuta agentes que hablan el [Agent Client Protocol](https://agentclientprotocol.com) (Claude Code,
Gemini CLI, Codex…) como su propio programa y transmite su trabajo con los mismos eventos que `Agent`:

```python
from pyzed.agents import acp

config = acp.preset("claude-code")        # o "gemini", "codex", o providers.ACPAgentConfig(nombre, comando, args)
own = acp.pyzed_mcp_server()              # el servidor MCP de Pyzed, o None sin el paquete mcp
agent = acp.ACPAgent(config, cwd="mi_app", confirm=lambda tool, args: True,
                     mcp_servers=[own] if own else [])
print(agent.run("Añade un tema oscuro a la app", on_event=print))
agent.close()
```

El agente lee y escribe archivos a través de Pyzed, solo dentro de `cwd` y nunca los de `SECRET_FILES`. Sus
peticiones de permiso siguen `settings.mode`: `"bypass"` las permite, `"read"` solo permite lecturas, `"chat"` las
rechaza y `"ask"` llama a `confirm`. `acp.installed(config)` dice si su programa está en el `PATH`, y los ajustes
los guardan en `AgentSettings.acp_agents` (y los servidores MCP en `mcp_servers`;
`acp.mcp_entries(settings.mcp_servers)` también se los pasa al agente).

## Streaming en la UI

`run` bloquea, así que en una app llámalo desde un hilo y pasa los eventos a la UI. Las vistas de Pyzed corren en
el hilo de la UI, así que pon los eventos en una cola y vacíala desde una suscripción `pz.every`:

```python
import queue, threading
import pyzed as pz
from pyzed import agents, ui


class Chat(pz.App):
    def __init__(self):
        self.agent = agents.Agent("anthropic:claude-opus-5-5")
        self.events = queue.Queue()
        self.answer, self.prompt, self.busy = "", "", False

    def send(self):
        self.busy, self.answer = True, ""
        threading.Thread(target=self.agent.run, args=(self.prompt,),
                         kwargs={"on_event": self.events.put}, daemon=True).start()

    def poll(self):
        while not self.events.empty():
            event = self.events.get()
            if event.kind == "text":
                self.answer += event.text
            elif event.kind == "done":
                self.busy = False

    def subscriptions(self):
        return [pz.every(1 / 30, self.poll, key="chat")] if self.busy else []

    def view(self):
        return pz.column([
            ui.markdown(self.answer),
            ui.input(self.prompt, lambda v: setattr(self, "prompt", v), on_submit=self.send),
        ], spacing=8, padding=16)
```

Eventos: `text` y `thinking` (un trozo nuevo de la respuesta o del resumen del razonamiento), `tool_call` y
`tool_result` (`tool`, `args`, `call_id`, `result`, `error`), `turn` (terminó una respuesta del modelo, con
`usage`), `error` y `done`. `agent.stop()` cancela desde cualquier hilo.

Las herramientas que tocan el estado de tu app también deben correr en el hilo de la UI: pasa `executor=` (una
función que ejecuta un callable allí y devuelve su resultado) y márcalas con `ui=True`. El diseñador hace
exactamente eso, y por eso las ediciones del agente son pasos normales de deshacer.

## Claves e inicio de sesión

```python
agents.set_key("openai", "sk-…")      # True: en el llavero; False: sin llavero, solo para esta sesión
agents.get_key("openai")              # la clave guardada o la variable de entorno
agents.delete_key("openai")
agents.secrets.store().backend_name   # backend de keyring en uso, o "memory (this session only)"

key = agents.login.openrouter_login() # OpenRouter: navegador + PKCE, devuelve una clave
agents.set_key("openrouter", key)

agents.login.key_page("anthropic")    # los demás: abre la página de claves de API del proveedor...
agents.providers.looks_like_key("anthropic", texto_copiado)  # ...y dice si un texto copiado es su clave
```

GitHub y Google también inician sesión sin clave, con apps OAuth que registras tú (sus ID van en los ajustes del
proveedor, o en `PYZED_GITHUB_CLIENT_ID` / `PYZED_GOOGLE_CLIENT_ID`):

```python
code = agents.login.github_device_code(client_id)          # muestra code.user_code y abre code.verification_uri
token = agents.login.github_device_token(client_id, code)  # espera hasta que se aprueba
agents.providers.save_token("github", token)               # en el llavero; se renueva cuando caduca

token = agents.login.google_login(client_id, client_secret) # navegador + PKCE, ámbito cloud-platform
agents.providers.save_token("vertex", token)
```

Sin iniciar sesión, `vertex` usa las credenciales de gcloud del equipo (`gcloud auth application-default login`) y
`github` acepta como clave un token detallado con el permiso Models.

Aparte de estos, solo OpenRouter ofrece OAuth a otras apps. Para el resto, Pyzed Design abre la página de claves y vigila el
portapapeles unos minutos; cuando se copia un texto que cumple `looks_like_key`, lo comprueba con
`list_models(key=...)` y lo guarda con `set_key`. Tu app puede hacer lo mismo.

Las claves viven en el llavero del sistema (`keyring`, servicio `pyzed`); `PYZED_KEYRING=0` lo desactiva y
`agents.secrets.use(SecretStore(mi_backend))` conecta tu propia bóveda (cualquier objeto con `get_password` /
`set_password` / `delete_password` de keyring). El orden de búsqueda, la variable de entorno de cada proveedor y
cómo mantener las claves seguras están en [Claves de API y credenciales](/pyzed/es/ai/api-keys/).

### Claude sin clave de API

Con la federación de identidad de cargas de trabajo, un token de tu proveedor de identidad (GitHub Actions, Google
Cloud, Azure, Okta, Kubernetes…) se cambia por un token de Claude de corta duración, así que no se guarda ninguna
clave. Crea el emisor y la regla en la Claude Console y luego:

```python
settings = agents.AgentSettings()
settings.federation = agents.providers.FederationSettings(
    rule_id="fdrl_…", organization_id="…", service_account_id="svac_…",
    token_source="command", token_command="gcloud auth print-identity-token")
agent = agents.Agent("anthropic:claude-opus-5-5", settings=settings)
```

`token_source` es `"file"` (`token_file`, o `ANTHROPIC_IDENTITY_TOKEN_FILE`), `"command"` (imprime un token nuevo)
o `"env"` (`token_env`, `ANTHROPIC_IDENTITY_TOKEN` por defecto). Una clave guardada tiene prioridad sobre la
federación. `providers.credential_source("anthropic", settings=settings)` dice de dónde salen las credenciales.

## Conversaciones

```python
store = agents.ThreadStore()                      # agents/threads en la carpeta de ajustes de Pyzed
thread = agents.Thread(model="ollama:qwen3:8b")
agent = agents.Agent(thread.model, messages=thread.messages)
agent.run("Hola")
store.save(thread)                                # JSON que solo tú puedes leer; sin claves
store.list()                                      # la más reciente primero
```

## Pruebas

Pasa `stream=` a `Agent` para cambiar el modelo por un guion, así las pruebas corren sin red y siempre igual:

```python
from pyzed.agents import llm

def fake(model, system, messages, tools, *, settings, on_event, cancel):
    if len(messages) == 1:
        return llm.Turn([{"type": "tool_use", "id": "1", "name": "stock", "input": {"product": "desk"}}], "tool_use")
    return llm.Turn([{"type": "text", "text": "No quedan escritorios."}])

agent = agents.Agent("x", tools=[stock], stream=fake, settings=agents.AgentSettings())
assert agent.run("¿Escritorios?") == "No quedan escritorios."
```

## Una app de chat completa

[Crear apps con IA](/pyzed/es/ai/ai-apps/) construye un chat completo con streaming sobre una API compatible con
OpenAI, con detener, errores y tests sin red, y muestra cómo usar `pyzed.agents` desde `pz.Command.perform` y
`pz.post`.
