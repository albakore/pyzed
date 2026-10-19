---
title: Enlace de datos y validación
description: "Enlaza controles a los datos en Pyzed Design, valida lo que escribe el usuario, traduce textos con @claves y previsualiza con otro tema o idioma."
sidebar:
  order: 6.5
---

Un formulario puede mostrar y editar **datos** sin una línea de código de pegamento: enlaza cada control a un campo
de `form.data`, dale **reglas** a los controles de entrada y llama a `form.validate()` antes de usar los datos.

## Enlazar un control

Selecciona un control y rellena **Enlazar a** en la sección **Datos** de [Propiedades](/pyzed/es/editor/properties/).
El campo es un nombre (`email`) o una ruta dentro de datos anidados (`customer.address.city`, `items.0.title`).

![La sección Datos de un cuadro de texto: enlazado a email, obligatorio, con patrón y mensaje](../../../../../screenshots/editor-data.png)

- Los **controles de entrada** se enlazan en los dos sentidos: muestran el campo y escriben de vuelta lo que el
  usuario teclea o elige. Los cuadros de texto, áreas de texto y búsquedas enlazan `text`; las casillas e
  interruptores `checked`; los grupos de opciones, desplegables, controles segmentados, barras de pestañas y listas
  `selected`; los deslizadores y cuadros numéricos `value`.
- Los **controles de visualización** solo lo muestran: etiquetas, encabezados, insignias, enlaces, chips, markdown y
  avisos enlazan `text`, las estadísticas y barras de progreso `value`, las imágenes `source`, los gráficos `values`
  y las tablas `data`.
- En un control de visualización, **Enlazar a** también puede ser una **expresión de Python** sobre los campos de
  los datos, que se vuelve a evaluar en cada renderizado:

  ```python
  f"Iniciando sesión como {email}" if email else ""
  f"{len(items)} artículos, {sum(i.price for i in items):.2f} €"
  ```

  Los diccionarios anidados se leen con puntos (`customer.city`); `data` es el objeto entero y `form` el formulario
  en ejecución. Una ruta a un campo que todavía no existe deja el valor diseñado del control; una expresión que
  lanza una excepción también lo deja y muestra el error en la ventana.

## Los datos del formulario

`form.data` es lo que pasó el formulario que abrió este, o un diccionario que el formulario crea por su cuenta:

```python
def edit_click(form):
    return form.open("customer", data=selected_customer)  # un dict, una dataclass, cualquier objeto
```

| Abierto con | `form.data` es |
| --- | --- |
| `data=` un dict o un objeto | Ese mismo objeto: lo que edita el usuario lo cambia en el sitio. |
| Nada, con controles enlazados | Un dict nuevo, rellenado con los valores diseñados de los controles (`{"email": "", "remember": False}`). |

Asignar `form.data = {...}` lo reemplaza y refresca todos los controles enlazados; así se carga un registro:

```python
def form_load(form):
    form.data = database.load_customer(42)
```

## Reglas de validación

La sección **Datos** también tiene las reglas de los controles de dos sentidos. Las reglas dependen del tipo de
control:

| Regla | Controles | Falla cuando |
| --- | --- | --- |
| **Obligatorio** | Todos los controles de entrada | El valor está vacío (una casilla sin marcar, en casillas e interruptores). |
| **Longitud mínima**, **Longitud máxima** | Cuadros de texto, áreas de texto, búsquedas | El texto es más corto o más largo. |
| **Patrón** | Cuadros de texto, áreas de texto, búsquedas | El texto entero no cumple la expresión regular. |
| **Mínimo**, **Máximo** | Deslizadores, cuadros numéricos | El número es menor o mayor. |
| **Mensaje** | Todos los controles de entrada | Reemplaza el mensaje predeterminado de cualquier regla (`@clave` lo traduce). |

Un valor vacío solo falla **Obligatorio**, así que un correo opcional con patrón acepta el campo en blanco. Los
mensajes predeterminados ("Este campo es obligatorio", "Al menos 8 caracteres") siguen el idioma de la app.

El formulario en ejecución comprueba las reglas de un control **mientras el usuario escribe** y muestra el mensaje
en una burbuja bajo el control, que se marca con un borde rojo:

![El formulario de inicio de sesión en ejecución: el correo no cumple su patrón y la contraseña vacía es obligatoria](../../../../../screenshots/editor-validation.png)

## Validar desde el código

```python
def sign_in_click(form):
    if not form.validate():          # comprueba cada control visible y habilitado y muestra los errores
        return
    auth.sign_in(form.data["email"], form.data["password"])
```

| Código | Hace |
| --- | --- |
| `form.validate()` | Comprueba las reglas de cada control enlazado (se saltan los ocultos y deshabilitados) y devuelve `True` si todos pasan. |
| `form.valid` | `True` mientras ningún control muestre un error. |
| `form.errors` | `{"email": "Enter a valid email", ...}`: los controles que muestran un error. |
| `form.email.validate()` | Comprueba un solo control; `True` si pasa. |
| `form.email.error` | El mensaje del control, o `None`. Asigna un texto para mostrar tu propio error (`form.email.error = "Ya registrado"`) o `None` para quitarlo. |

Así, una comprobación en el servidor se ve como cualquier otra:

```python
async def sign_in_click(form):
    if form.validate() and not await api.email_free(form.data["email"]):
        form.email.error = "Ese correo ya está registrado"
```

## Textos traducibles

Cualquier propiedad de texto que empiece por `@` es una **clave de traducción**: una etiqueta cuyo texto es
`@login.title` muestra `pz.t("login.title")` en el idioma de la app. `@@` escribe una `@` literal. Los elementos de
una lista (las opciones de un desplegable, las pestañas de una barra) se traducen uno a uno, igual que el título del
formulario y el mensaje de una regla.

Los catálogos viven en una carpeta `locales/` junto al formulario, o en cualquier carpeta superior hasta la raíz del
proyecto (`pyproject.toml` o `.git`), un archivo por idioma:

```json title="locales/es.json"
{"login": {"title": "Iniciar sesión", "email": "Correo", "sign_in": "Entrar"}}
```

El diseñador y el formulario en ejecución los cargan solos. Consulta [Traducciones](/pyzed/es/guides/i18n/) para
plurales, idiomas de respaldo y cambiar el idioma en tiempo de ejecución.

## Vista previa con otro tema o idioma

**Ver → Vista previa con tema…** y **Ver → Vista previa con idioma…** eligen un tema y un idioma para el lienzo sin
tocar el formulario: el formulario conserva su tema y la app su idioma, y la primera entrada de cada selector vuelve a
ellos.

![El formulario de inicio de sesión con One Light y en español, con el selector de idioma abierto](../../../../../screenshots/editor-preview.png)

Mientras hay una vista previa activa, la barra de estado la muestra (haz clic para elegir otra) y **Ejecutar**
(<kbd>F5</kbd>) arranca el formulario con el mismo tema e idioma, para probar todo el flujo en español o con un tema
claro. El formulario en ejecución los lee de las variables de entorno `PYZED_PREVIEW_THEME` y
`PYZED_PREVIEW_LANGUAGE`, que también funcionan desde una terminal:

```bash
PYZED_PREVIEW_LANGUAGE=es PYZED_PREVIEW_THEME="One Light" uv run python main.py
```

## Copiar controles entre formularios

Copiar (<kbd>Ctrl</kbd>+<kbd>C</kbd>) pone los controles seleccionados en el **portapapeles del sistema**, con sus
enlaces y reglas, para pegarlos en otro formulario, en otra pestaña u otra ventana de Pyzed Design. Consulta
[Caja de herramientas y lienzo](/pyzed/es/editor/toolbox-and-canvas/#portapapeles-e-historial).
