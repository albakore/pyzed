---
title: Tests y capturas
description: Renderiza tu app sin ventana para tests, documentación e integración continua.
sidebar:
  order: 10
---

`app.screenshot(ruta)` dibuja el estado actual de la app **fuera de pantalla** y guarda un PNG.
No necesita ventana, display ni GPU (usa el renderizador por software), así que funciona en CI.

```python
app = MiApp()
app.items = ["uno", "dos"]          # prepara el estado que quieras mostrar
app.screenshot("docs/lista.png", size=(480, 320), scale=2)
```

- `size`: tamaño lógico; por defecto `App.size`.
- `scale`: densidad del PNG (2 = retina).
- `wait`: segundos a esperar antes de capturar, por si `on_start` lanzó trabajo.

Todas las imágenes de esta documentación se generan así:

```bash
python examples/screenshots.py              # capturas grandes (docs/screenshots)
python docs/scripts/component_shots.py      # ilustraciones de componentes
```

## Probar la lógica

Como el estado vive en tu objeto, `update` y los callbacks se prueban como Python normal:

```python
def test_counter():
    app = Counter()
    app.update("increment")
    app.update("increment")
    assert app.count == 2
```

## Probar que la vista se dibuja

`view()` debe devolver un `Widget` sin lanzar excepciones. Una captura es una buena prueba de humo:

```python
def test_view_renders(tmp_path):
    app = MiApp()
    app.screenshot(tmp_path / "ui.png", size=(800, 600))
    assert (tmp_path / "ui.png").stat().st_size > 0
```

Si `view()` lanza, la captura muestra el traceback en lugar de la interfaz, igual que la ventana.
