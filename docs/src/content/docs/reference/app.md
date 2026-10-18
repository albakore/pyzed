---
title: "App y ejecución"
description: "La clase App, run, screenshot, post y load_font."
sidebar:
  order: 1
---

<!-- Archivo generado por docs/scripts/gen_api.py. Edita docs/scripts/api_docs.py. -->

Todo lo que necesitas para arrancar una aplicación. Ver también la guía de
[arquitectura](/pyzed/guides/architecture/).

## Aplicación

### `App`

Clase base de las aplicaciones (arquitectura Elm, como Iced). Sobrescribe `view()` y, si usas
mensajes, `update(message)`. El estado vive en atributos de la instancia.

| Atributo de clase | Por defecto | Descripción |
| --- | --- | --- |
| `title` | `"Pyzed"` | Título de la ventana. Puede ser un callable (o propiedad) que devuelva el texto. |
| `size` | `(1280, 800)` | Tamaño inicial de la ventana. |
| `min_size` | `None` | Tamaño mínimo. |
| `resizable` | `True` | Si se puede redimensionar. |
| `decorations` | `True` | Muestra el marco y los botones del sistema. |
| `scale` | `1.0` | Factor de escala de toda la interfaz. |
| `font_size` | `14` | Tamaño de texto por defecto. |
| `theme` | `themes.ONE_DARK` | Tema actual. Cámbialo en cualquier momento. |

| Método | Descripción |
| --- | --- |
| `view()` | Devuelve el árbol de widgets. Se llama después de cada mensaje. |
| `update(message)` | Recibe los mensajes. Puede devolver un `Command`, una lista de ellos u otro mensaje. |
| `on_start()` | Opcional. Se ejecuta una vez al arrancar; puede devolver un `Command`. |
| `on_key(combo)` | Opcional. Recibe cada tecla como `"ctrl-shift-p"`, `"escape"`, `"up"`… |
| `run()` | Abre la ventana y bloquea hasta que se cierra. |
| `screenshot(path, *, size=None, scale=2.0, wait=0.1)` | Renderiza el estado actual a un PNG sin ventana. |

Si `view()` lanza una excepción, la ventana muestra el traceback en lugar de cerrarse.

### `run`

```python
run(app)
```

Ejecuta una app: abre la ventana y bloquea hasta que se cierra. Acepta la clase o una instancia.

| Parámetro | Descripción |
| --- | --- |
| `app` | Una instancia de `App` (o la clase, que se instancia sin argumentos). |

### `screenshot`

```python
screenshot(app, path, *, size=None, scale=2.0, wait=0.1)
```

Renderiza `app` fuera de pantalla (sin ventana ni GPU) y guarda un PNG. Útil para tests y documentación.

| Parámetro | Descripción |
| --- | --- |
| `app` | Una instancia de `App` (o la clase, que se instancia sin argumentos). |
| `path` | Ruta del PNG de salida. |
| `size` | Tamaño lógico `(ancho, alto)`. Por defecto, `app.size`. |
| `scale` | Factor de escala del PNG (2.0 = retina). |
| `wait` | Segundos que se esperan antes de capturar (para tareas de `on_start`). |

```python
pz.screenshot(MiApp, "docs/ui.png", size=(800, 600))
```

### `post`

```python
post(message)
```

Envía un mensaje a la app en ejecución desde **cualquier hilo**. Lanza `RuntimeError` si no hay ninguna app corriendo.

| Parámetro | Descripción |
| --- | --- |
| `message` | Cualquier valor de Python, o un callable. |

```python
def worker():
    for i in range(100):
        time.sleep(0.05)
        pz.post(("progress", i / 100))

threading.Thread(target=worker, daemon=True).start()
```

### `load_font`

```python
load_font(source)
```

Carga una fuente extra (ruta a un `.ttf`/`.otf` o sus bytes) para usarla por su nombre de familia: `text("hola", font="JetBrains Mono")`.

| Parámetro | Descripción |
| --- | --- |
| `source` | Ruta del archivo de fuente o `bytes`. |
