---
title: Componentes no visuales
description: "Temporizadores, atajos de teclado, vigilantes de archivos, procesos, tareas en segundo plano, peticiones web, el portapapeles, ajustes, diálogos de archivos, notificaciones, información del sistema, el lanzador y los monitores de red y batería en Pyzed Design: componentes con propiedades y eventos que no dibujan nada."
sidebar:
  order: 6.2
---

Algunas partes de una app tienen **propiedades y eventos pero nada que mostrar**: un temporizador que hace tick, una
carpeta que vigilas, un comando que corre en segundo plano. Visual Basic y Qt Designer las guardaban en una
**bandeja bajo el formulario**, y Pyzed Design hace lo mismo. No se dibujan en el formulario, ni al diseñar ni al
ejecutar: solo aparecen en la bandeja y en el **Outline**, donde pertenecen al formulario.

![Añadiendo un Temporizador, un Vigilante de archivos y una Petición web desde la caja de herramientas: cada uno va a la bandeja bajo el formulario y un doble clic abre su handler de tick](/pyzed/media/services/tray.webp)

## Añadir uno

1. Búscalo en la caja de herramientas, en **Componentes** o **Sistema** (o escribe su nombre en **Buscar componentes…**).
2. **Haz clic**: va directo a la bandeja, seleccionado y con sus propiedades a la derecha. Arrastrarlo al
   formulario hace lo mismo; nunca queda dentro de un contenedor.
3. Ajusta sus propiedades en el panel **Propiedades** y haz **doble clic** en su ficha para escribir el handler de
   su evento principal (`tick` en un temporizador, `output` en un proceso...). El panel **Eventos** los lista todos.

| En la bandeja | Resultado |
| --- | --- |
| Clic en una ficha | Selecciona el componente. |
| Doble clic en una ficha | Abre el handler de su evento principal. |
| Clic derecho en una ficha | Ver código, Ayuda, Cortar, Copiar, Duplicar, Activar o Desactivar, Eliminar. |

En el **Outline**, los componentes no visuales aparecen después de los controles, bajo **No visuales**. No tienen
posición, tamaño, estilo ni animaciones: solo sus propias propiedades y **Habilitado** (un componente desactivado
no lanza eventos). Copiar, pegar, deshacer y renombrar funcionan como con cualquier control, y al renombrar uno se
renombran sus handlers.

## Los componentes

| Componente | Qué hace | Eventos |
| --- | --- | --- |
| **Temporizador** | Lanza `tick` cada `interval` milisegundos mientras `running` está activo. Desactiva `repeat` para un solo tick (un retardo). | `tick` (la cuenta) |
| **Atajo** | Un atajo de teclado para toda la ventana: `keys` como `ctrl-s`, varios separados por comas. `mod-s` es <kbd>Cmd</kbd>+<kbd>S</kbd> en macOS y <kbd>Ctrl</kbd>+<kbd>S</kbd> en el resto. | `activate` (la combinación) |
| **Vigilante de archivos** | Vigila una carpeta (`path`), los archivos que encajan con `pattern` (`*.csv`, varios separados por `;`), con `recursive` para las subcarpetas. | `change` (las rutas cambiadas), `created`, `modified`, `deleted` (una ruta) |
| **Proceso** | Ejecuta `command` en `directory` y entrega lo que imprime, línea a línea. `autostart` lo inicia al abrir el formulario. | `output`, `error_output` (una línea), `finished` (código de salida), `started` (id del proceso), `failed` |
| **Tarea en segundo plano** | Ejecuta trabajo lento en un hilo aparte para que la ventana siga respondiendo. | `work` (en el hilo), `progress`, `done` (el resultado), `failed` (la excepción) |
| **Petición web** | Llama a `url` con `method`, `headers` (una línea `Nombre: valor` por cabecera) y `body`, en segundo plano. | `response` (la respuesta), `failed` (sin respuesta) |
| **Portapapeles** | Copia y pega texto; con `watch` se entera de lo que se copia, en esta app o en otra. | `change`, `paste` (el texto) |
| **Ajustes** | Valores que se guardan entre ejecuciones (un JSON por usuario) y el valor de los controles de `remember`. | `change` (`(clave, valor)`) |
| **Diálogo de archivos** | El diálogo del sistema: `mode` es `open`, `open_many`, `save` o `folder`; `filters` lleva una línea `Imágenes: png, jpg` por filtro. | `chosen` (la ruta o una lista), `cancelled` |
| **Notificación** | Una notificación de escritorio con `title` y `text`. | `shown`, `failed` |
| **Información del sistema** | El ordenador: `os`, `os_version`, `machine`, `hostname`, `user`, `home`, `cpu_count`, `language`, la memoria y el disco libre (de `disk_path`). Con `interval` vuelve a mirar cada cierto tiempo. | `update` (un diccionario con todo) |
| **Lanzador** | Abre `target` con el programa que usa el sistema para eso: un archivo, una carpeta, una página web o un enlace `mailto:`. | `opened`, `failed` (el destino) |
| **Monitor de red** | Si se llega a internet, probando `host`:`port` cada `interval` ms mientras `running`. | `change` (`True`/`False`), `online`, `offline` |
| **Monitor de batería** | La carga de la batería y si está enchufada, cada `interval` ms. | `change` (`(porcentaje, enchufada)`), `low` (bajo `low_level`), `plugged`, `unplugged` |

La página de cada componente en la referencia integrada (<kbd>Shift</kbd>+<kbd>F1</kbd> con él seleccionado) lista
todas sus propiedades y eventos con el nombre de su handler.

## Usarlos desde los handlers

Son atributos del formulario como cualquier control. Sus propiedades se leen y escriben como atributos, y tienen
**métodos**:

```python
def run_click(form, event):
    if form.proc.running:
        form.proc.kill()
    else:
        form.proc.start(form.command.text)     # o el comando puesto en el diseñador


def proc_output(form, event):
    form.output.text += event.value + "\n"     # una línea de lo que imprimió el programa


def proc_finished(form, event):
    form.status.text = "Hecho." if event.value == 0 else f"Terminó con el código {event.value}."
```

| Componente | Métodos y estado |
| --- | --- |
| Temporizador | `start()`, `stop()`, `running`, `count` |
| Atajo | `matches(combo)` |
| Vigilante de archivos | `start()`, `stop()`, `running`, `check()` |
| Proceso | `start(command=None)`, `write(text)`, `kill()`, `running`, `exit_code`, `pid` |
| Tarea en segundo plano | `run(value)`, `cancel()`, `report(progress)`, `busy`, `cancelled`, `result` |
| Petición web | `send(url=None, json=None, body=None)`, `busy`, `response` |
| Portapapeles | `copy(text)` y `paste()` (comandos: devuélvelos), `text` |
| Ajustes | `settings1["clave"]`, `settings1["clave"] = valor`, `get(clave, defecto)`, `set()`, `delete()`, `keys()` |
| Diálogo de archivos | `show()` (un comando: devuélvelo), `path`, `paths` |
| Notificación | `show(text=None)` |
| Información del sistema | `check()`, `env(name)`, `folder("documents")`, `memory_available`, `disk_free`, `is_windows`, `is_mac`, `is_linux` |
| Lanzador | `open(target=None)`, `reveal(path)` (lo muestra en el explorador de archivos), `email(to, subject, body)` |
| Monitor de red | `check()`, `online`, `start()`, `stop()` |
| Monitor de batería | `check()`, `percent`, `plugged`, `has_battery` |

Los eventos que ocurren en segundo plano (una línea de salida, un archivo que cambia, una respuesta web) llegan a tus
handlers en el hilo de la ventana, así que pueden cambiar controles sin problema. La única excepción es el evento
`work` de la tarea en segundo plano:

```python
def count_click(form, event):
    form.primes.run(200_000)                   # empieza el trabajo en un hilo


def primes_work(form, event):                  # corre en el hilo: no toques controles aquí
    found = 0
    for n in range(2, event.value):
        if event.sender.cancelled:             # se llamó a form.primes.cancel()
            return None
        if all(n % d for d in range(2, int(n ** 0.5) + 1)):
            found += 1
        if n % 2000 == 0:
            event.sender.report(n * 100 // event.value)
    return found                               # llega a done


def primes_progress(form, event):
    form.progress.value = event.value


def primes_done(form, event):
    form.status.text = f"{event.value:,} primos"
```

Los comandos se devuelven, como en cualquier handler:

```python
def open_click(form, event):
    return form.file_dialog1.show()            # abre el diálogo del sistema


def file_dialog1_chosen(form, event):
    form.editor.text = Path(event.value).read_text()


def copy_click(form, event):
    return form.clipboard1.copy(form.editor.text)


def http1_response(form, event):
    if event.value.ok:
        form.stars.text = str(event.value.json()["stargazers_count"])
```

![El ejemplo Task runner en marcha: el proceso entrega su salida, el temporizador mueve el reloj y la tarea en segundo plano llena la barra de progreso](/pyzed/media/services/runner.webp)

El ejemplo **Task runner** (`examples/designer/tasks.pzform`) usa siete a la vez: un Temporizador para el reloj, un
Proceso para el comando, una Tarea en segundo plano que cuenta primos, un Vigilante de archivos, unos Ajustes que
recuerdan el comando, un Atajo (<kbd>Ctrl</kbd>+<kbd>R</kbd>) y una Notificación. Ábrelo con
`pyzed design examples/designer/tasks.pzform`.

## Recordar lo que dejó el usuario

Pon un componente **Ajustes** en el formulario y escribe nombres de controles en **Recordar**, uno por línea: al
cerrar el formulario se guardan sus valores (el texto de una caja, el estado de una casilla, el valor de un
deslizador...) y la próxima vez que se abra vuelven a estar ahí. El archivo es `<formulario>.<componente>.json` en la
carpeta de ajustes de Pyzed de cada usuario, o el nombre de **Archivo**. Tus propios valores van en el mismo archivo:

```python
def form_load(form, event):
    form.volume.value = form.prefs.get("volume", 50)


def volume_change(form, event):
    form.prefs["volume"] = event.value
```

## En código, sin el diseñador

Cada componente es una clase de [`pyzed.services`](/pyzed/es/guides/services/) (`pz.Timer`, `pz.Process`,
`pz.FileWatcher`...), así que los mismos objetos funcionan en un `pz.App` escrito a mano o en un script sin ventana.

:::tip
Un **Proceso** o un **Vigilante de archivos** muy activos pueden llenar la consola de eventos: `output`,
`error_output`, `progress` y `tick` nunca se registran, y **Ajustes → Ejecución** desactiva el registro de eventos
para el resto.
:::
