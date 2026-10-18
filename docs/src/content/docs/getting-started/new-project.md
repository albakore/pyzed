---
title: Crear un proyecto
description: Genera una app completa con la CLI de Pyzed.
---

Pyzed instala el comando `pyzed`, que crea un proyecto listo para ejecutar:

```bash
pyzed new mi-app
cd mi-app
python main.py
```

Esto genera:

```
mi-app/
├── main.py            # app con barra de título, sidebar, barra de estado y paleta de comandos
└── requirements.txt   # pyzed
```

La plantilla ya incluye:

- Un `ui.workspace` con barra de título, panel izquierdo y barra de estado.
- Navegación entre páginas con `ui.list_item`.
- Una paleta de comandos que se abre con <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd>
  y se cierra con <kbd>Esc</kbd>.
- Un botón para alternar entre tema claro y oscuro.

## Buscar iconos

Pyzed incluye los ~2000 iconos de [Lucide](https://lucide.dev). Para buscar nombres:

```bash
pyzed icons folder
# folder, folder-open, folder-git, folder-plus, ...
```

Úsalos con `pz.icon("folder")` o con el parámetro `icon=` de los componentes.

## Ejecutar como módulo

`python -m pyzed` es equivalente al comando `pyzed`:

```bash
python -m pyzed new otra-app
```
