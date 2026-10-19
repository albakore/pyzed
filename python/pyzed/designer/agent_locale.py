"""Spanish texts of the Agent panel, inline assist and the AI agents settings (see ``locale``)."""

from __future__ import annotations

from .. import i18n

ES = {
    # Panel and commands
    "Agent": "Agente", "Agent panel": "Panel del agente", "AI agents": "Agentes de IA",
    "AI agents settings": "Ajustes de los agentes de IA", "AI agents settings…": "Ajustes de los agentes de IA…",
    "Generate a form with AI…": "Generar un formulario con IA…",
    "Generate a component with AI…": "Generar un componente con IA…",
    "Inline assist": "Asistente en línea",
    "Create a new form for ": "Crea un formulario nuevo para ",
    "Create a reusable component that ": "Crea un componente reutilizable que ",
    "History": "Historial", "New thread": "Nueva conversación", "No threads yet": "Todavía no hay conversaciones",
    "Your conversations with the agent show up here.": "Tus conversaciones con el agente aparecen aquí.",
    "Write": "Escribir", "Ask": "Preguntar", "Minimal": "Mínimo",
    "May read and change the open form, its code and files in the project.":
        "Puede leer y cambiar el formulario abierto, su código y los archivos del proyecto.",
    "Reads only: answers questions and suggests code without changing anything.":
        "Solo lee: responde preguntas y sugiere código sin cambiar nada.",
    "No tools: a plain conversation with the model.": "Sin herramientas: una conversación simple con el modelo.",
    "Ask, or describe what to build…": "Pregunta o describe qué construir…",
    "Send (Enter)": "Enviar (Intro)", "Working…": "Trabajando…", "Thinking…": "Pensando…", "Thought": "Razonamiento",
    "What should we build?": "¿Qué construimos?",
    "The agent sees the open form and its code, edits them like you would, and can create new forms and components.":
        "El agente ve el formulario abierto y su código, los edita como lo harías tú y puede crear formularios y "
        "componentes nuevos.",
    "Create a login form with email, password and a Sign in button":
        "Crea un formulario de inicio de sesión con correo, contraseña y un botón Entrar",
    "Create a reusable user card component with an avatar, a name and a role":
        "Crea un componente de tarjeta de usuario con avatar, nombre y rol",
    "Align the controls of this form and give them consistent margins":
        "Alinea los controles de este formulario y dales márgenes uniformes",
    "Write the handlers of this form and validate the inputs":
        "Escribe los manejadores de este formulario y valida los campos",
    "Connect a model": "Conecta un modelo",
    "Add an API key or sign in with the browser to start. Keys are kept in the system keychain.":
        "Añade una clave de API o inicia sesión con el navegador para empezar. Las claves se guardan en el llavero "
        "del sistema.",
    "Set up AI agents…": "Configurar los agentes de IA…", "Set up a model provider first.":
        "Primero configura un proveedor de modelos.",
    "The agent stopped": "El agente se detuvo", "Retry": "Reintentar",
    "Allow the agent to continue?": "¿Dejas que el agente continúe?", "Allow": "Permitir",
    "Always allow": "Permitir siempre", "Deny": "Denegar",
    "The agent changed {files}": "El agente cambió {files}", "Each change is also an undo step.":
        "Cada cambio también se puede deshacer.", "Reject": "Rechazar", "Keep": "Conservar",
    "Changes rejected": "Cambios rechazados", "Agent changes": "Cambios del agente",
    "Agent edit applied": "Edición del agente aplicada",
    "Describe the change (Enter to run)…": "Describe el cambio (Intro para ejecutar)…",
    "The answer had no code.": "La respuesta no traía código.",
    # Tools shown in the thread
    "Reading the open document": "Leyendo el documento abierto", "Adding a control": "Añadiendo un control",
    "Changing a control": "Cambiando un control", "Removing controls": "Quitando controles",
    "Changing the form": "Cambiando el formulario", "Selecting controls": "Seleccionando controles",
    "Wiring an event": "Conectando un evento", "Writing a handler": "Escribiendo un manejador",
    "Writing the module": "Escribiendo el módulo", "Creating a document": "Creando un documento",
    "Saving": "Guardando", "Reading a Pyzed guide": "Leyendo una guía de Pyzed",
    "Listing components": "Listando componentes", "Reading a component's reference": "Leyendo la referencia de un componente",
    "Searching icons": "Buscando iconos", "Listing themes": "Listando temas",
    "Reading the documentation": "Leyendo la documentación", "Listing the documentation": "Listando la documentación",
    "Writing an app skeleton": "Escribiendo el esqueleto de una app",
    "Writing a component skeleton": "Escribiendo el esqueleto de un componente", "Checking code": "Revisando el código",
    "Checking a form": "Revisando un formulario", "Listing files": "Listando archivos",
    "Reading a file": "Leyendo un archivo", "Searching the project": "Buscando en el proyecto",
    "Writing a file": "Escribiendo un archivo",
    # Settings
    "Model providers, keys and sign-in, permissions": "Proveedores de modelos, claves e inicio de sesión, permisos",
    "Providers": "Proveedores", "Not set up": "Sin configurar", "API key": "Clave de API", "Paste a key": "Pega una clave",
    "Or set {env}": "O define {env}", "Sign in with the browser": "Iniciar sesión con el navegador",
    "Get a key": "Obtener una clave", "Remove key": "Quitar la clave", "Sign out": "Cerrar sesión",
    "Refresh models": "Actualizar modelos", "Server URL": "URL del servidor", "{count} models: {names}":
        "{count} modelos: {names}", "{count} models found": "{count} modelos encontrados",
    "Signed in to {provider}": "Sesión iniciada en {provider}", "Signed out": "Sesión cerrada",
    "Key removed": "Clave eliminada", "Key saved in the system keychain": "Clave guardada en el llavero del sistema",
    "No system keychain: the key is kept until you close the designer":
        "No hay llavero del sistema: la clave se conserva hasta que cierres el diseñador",
    "Key kept for this session only": "Clave solo para esta sesión", "Key from the environment": "Clave del entorno",
    "Signed in with the Anthropic CLI": "Sesión de la CLI de Anthropic", "No key needed": "No necesita clave",
    "Keys are stored in {where}": "Las claves se guardan en {where}",
    "Never in Pyzed's settings files. Threads are saved on this computer only.":
        "Nunca en los archivos de ajustes de Pyzed. Las conversaciones se guardan solo en este equipo.",
    "No system keychain found": "No se encontró un llavero del sistema",
    "Keys you paste are kept only until you close the designer. Install the keyring package or set the key in an "
    "environment variable.": "Las claves que pegues se conservan solo hasta que cierres el diseñador. Instala el "
                             "paquete keyring o define la clave en una variable de entorno.",
    "Default model": "Modelo predeterminado", "Effort": "Esfuerzo",
    "How much the model thinks before answering (Claude)": "Cuánto piensa el modelo antes de responder (Claude)",
    "Ask before writing files": "Preguntar antes de escribir archivos",
    "Creating forms and saving files waits for your OK": "Crear formularios y guardar archivos espera tu permiso",
    "Show thinking": "Mostrar el razonamiento", "Rules": "Reglas",
    "e.g. Answer in Spanish. Use snake_case names.": "p. ej. Responde en español. Usa nombres snake_case.",
    "Instructions added to every thread": "Instrucciones añadidas a cada conversación",
    # Providers
    "Claude models, with an API key or the Anthropic CLI sign-in":
        "Modelos Claude, con clave de API o la sesión de la CLI de Anthropic",
    "GPT models with an API key": "Modelos GPT con clave de API",
    "Gemini models with a Google AI Studio key": "Modelos Gemini con una clave de Google AI Studio",
    "Hundreds of models behind one account; sign in with the browser":
        "Cientos de modelos con una sola cuenta; inicia sesión con el navegador",
    "Models running on this computer, no key needed": "Modelos que corren en este equipo, sin clave",
    "Models served by LM Studio on this computer": "Modelos servidos por LM Studio en este equipo",
    "Any server that speaks the OpenAI Chat Completions API":
        "Cualquier servidor compatible con la API Chat Completions de OpenAI",
}

i18n.add("es", {"designer": ES})
