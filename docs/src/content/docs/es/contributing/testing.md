---
title: Tests
description: Cómo se organizan los tests, cómo probar componentes de ui sin ventana y cómo funcionan los tests de regresión visual y sus imágenes de referencia.
sidebar:
  order: 5
---

Los tests están en `tests/` y se ejecutan con pytest sin pantalla: no necesitan GPU ni display.

```bash
pytest tests                      # todo (uv run pytest tests)
pytest tests -m "not visual"      # sin las comparaciones de capturas
pytest tests/test_ui_overlays.py  # un archivo
```

## Probar componentes de `ui`

Los componentes de `pyzed.ui` son funciones que devuelven widgets. Los widgets son objetos opacos de Rust,
así que para mirar dentro usa el ayudante `ui_tree`: mientras dura el test sustituye `pyzed._core` por un
grabador, y cada widget que construye un componente pasa a ser un `Node` con su `kind`, sus `args`
posicionales y sus `props` con nombre.

```python
import pytest

import pyzed as pz
from pyzed.ui import navigation as nav
from ui_tree import install


@pytest.fixture
def tree(monkeypatch):
    return install(monkeypatch)


def test_tab_bar_selects_by_id(tree):
    selected = []
    bar = nav.tab_bar([nav.Tab("a", "a.py")], "a", on_select=selected.append, theme=pz.themes.ONE_DARK)
    bar.button_with("a.py").args[1]()           # pulsa la pestaña
    assert selected == ["a"]
    assert bar.props["bg"] == pz.themes.ONE_DARK.tab_bar
```

`Node.find(kind, where)`, `find_all`, `walk`, `texts()` y `button_with(text)` buscan en el árbol.
Pasa un `theme=` explícito para que los colores esperados no dependan del tema actual. Para comprobar que
un componente se dibuja de verdad, constrúyelo dentro de una `App` y llama a `App.screenshot` (mira el final
de `tests/test_ui_workspace.py`).

## Tests de regresión visual

`tests/test_visual.py` dibuja cada escena de `tests/visual/scenes.py` con `App.screenshot` y la compara,
píxel a píxel, con su imagen de referencia en `tests/visual/references/`. Un píxel cuenta como cambiado si
un canal difiere en más de 16; el test falla si cambia más del 0,05 % de los píxeles.

Las referencias se dibujan en **Linux x86-64 con el renderizador por CPU** (tiny-skia; `tests/conftest.py` pone
`WGPU_BACKEND=dx12`, que no existe en Linux, así que iced recurre a él). Otras plataformas rasterizan el texto
de forma algo distinta (también ARM), así que allí las comparaciones se omiten salvo con `PYZED_VISUAL=1`. Los tests
visuales necesitan Pillow (`pip install pillow`; está en el grupo `test` de `pyproject.toml`).

### Cuando falla una comparación

El test escribe dos imágenes en `tests/visual/output/` (ignorada por git):

- `<escena>.actual.png`: lo que dibuja el código ahora.
- `<escena>.diff.png`: la referencia, atenuada, con los píxeles cambiados en rojo.

En la CI se suben como el artefacto **visual-diffs-…** del job de tests de Linux.

### Actualizar las referencias

Si el cambio es intencionado (cambiaste el aspecto de un componente a propósito, o fusionaste un cambio que
lo hizo), regenera las referencias y súbelas con tu cambio:

```bash
pytest tests/test_visual.py --update-snapshots                # todas las escenas que cambiaron
pytest tests/test_visual.py --update-snapshots -k palette     # solo las que coinciden con "palette"
git add tests/visual/references
```

`--update-snapshots` solo reescribe las imágenes que cambiaron de verdad, así que las demás no se tocan.
Ejecútalo en Linux para que las imágenes coincidan con lo que dibuja la CI. Si dos ramas cambian la misma
referencia, resuelve el conflicto regenerándola después del merge.

### Añadir una escena

Añade a `tests/visual/scenes.py` una función que devuelva una `App`, decorada con `@scene`:

```python
@scene("badges", size=(320, 120))
def badges():
    return _app(lambda: pz.container(pz.row([ui.badge("new", tint="accent"), ui.count_badge(3)], spacing=8), padding=16))
```

Después crea su referencia con `pytest tests/test_visual.py --update-snapshots -k badges` y sube el
PNG. Mantén las escenas pequeñas y deterministas: sin relojes, datos aleatorios ni archivos de fuera del
repositorio. Las animaciones se dibujan en su estado final. Una referencia cuya escena se borró hace fallar
`test_every_reference_has_a_scene`, así que borra la imagen junto con la escena.
