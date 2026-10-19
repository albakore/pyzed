---
title: Agentes de IA en tu app
description: pyzed.agents - habla con Claude, OpenAI, Gemini, OpenRouter, Ollama y servidores compatibles con OpenAI, da herramientas al modelo, transmite su respuesta a tu UI y guarda las claves en el llavero del sistema.
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
| `anthropic` | `anthropic:claude-opus-5-5` | `set_key`, `ANTHROPIC_API_KEY` o un perfil de `ant auth login` |
| `openai` | `openai:<modelo>` | `set_key` u `OPENAI_API_KEY` |
| `google` | `google:<modelo gemini>` | `set_key` o `GEMINI_API_KEY` |
| `openrouter` | `openrouter:anthropic/claude-opus-5-5` | `set_key`, `OPENROUTER_API_KEY` o `agents.login.openrouter_login()` |
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
| `profile` | `"write"` (todas las herramientas), `"ask"` (solo las que no tienen `writes=True`) o `"minimal"` (ninguna). |
| `confirm_writes` | Llama a `confirm(tool, args)` antes de una herramienta con `writes=True` (activo por defecto). Sin un callback `confirm` esas herramientas se rechazan; desactívalo para que se ejecuten sin preguntar. |
| `rules` | Texto añadido al prompt de sistema. |
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
(listar, leer, buscar y escribir archivos, nunca fuera de `carpeta`).

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

agents.login.ant_login()              # Anthropic: ejecuta `ant auth login` (navegador); el SDK lee el perfil
key = agents.login.openrouter_login() # OpenRouter: navegador + PKCE, devuelve una clave
agents.set_key("openrouter", key)
```

Las claves viven en el llavero del sistema (`keyring`, servicio `pyzed`); `PYZED_KEYRING=0` lo desactiva y
`agents.secrets.use(SecretStore(mi_backend))` conecta tu propia bóveda (cualquier objeto con `get_password` /
`set_password` / `delete_password` de keyring).

## Conversaciones

```python
store = agents.ThreadStore()                      # agents/threads en la carpeta de ajustes de Pyzed
thread = agents.Thread(model="ollama:qwen3:8b")
agent = agents.Agent(thread.model, messages=thread.messages)
agent.run("Hola")
store.save(thread)                                # JSON en este equipo; sin claves
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
