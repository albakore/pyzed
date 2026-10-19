---
title: Ajustes
description: Las preferencias de Pyzed Design y de su editor de código, dónde se guardan y cómo traducir el editor.
sidebar:
  order: 13
---

**Ajustes** (<kbd>Ctrl</kbd>+<kbd>,</kbd>, el engranaje a la derecha de la barra de título, o el menú ☰) reúne las
preferencias del propio editor. Los cambios se aplican al momento y se guardan enseguida; **Listo** cierra el
diálogo.

![El diálogo de ajustes](../../../../../screenshots/designer-settings.png)

## Apariencia

| Ajuste | Qué hace |
| --- | --- |
| **Tema** | El tema del editor (One Dark, One Light, Ayu, Gruvbox...). Los formularios conservan su propio tema. |
| **Idioma** | *Idioma del sistema*, English o Español: el idioma de los menús y paneles. |
| **Barra de herramientas** | Muestra u oculta la barra de herramientas. |
| **Barra de estado** | Muestra u oculta la barra de estado. |

## Lienzo del formulario

| Ajuste | Qué hace |
| --- | --- |
| **Mostrar la cuadrícula** | La cuadrícula de puntos del lienzo (también <kbd>G</kbd>). |
| **Ajustar a la cuadrícula** | Redondea posiciones y tamaños a la cuadrícula. |
| **Guías inteligentes** | Alinea con otros controles al arrastrar. |
| **Mostrar controles ocultos** | Dibuja atenuados los controles con Visible apagado. Apagado los quita del lienzo (siguen en la estructura). |
| **Cuadrícula de los formularios nuevos** | El paso de cuadrícula (2 a 64) que reciben los formularios y componentes que creas. Luego cada formulario conserva el suyo en Propiedades. |

## Ejecución

| Ajuste | Qué hace |
| --- | --- |
| **Guardar antes de ejecutar** | <kbd>F5</kbd> guarda antes el documento. |
| **Abrir la consola al ejecutar** | Trae la consola al frente cuando arranca un formulario. |
| **Registrar los eventos en la consola** | Escribe cada evento que atiende el formulario en ejecución, con su valor y su manejador. |

## Paneles

| Ajuste | Qué hace |
| --- | --- |
| **Disposición → Restablecer** | Devuelve cada panel a su dock y tamaño iniciales. |
| **Editor de código → Ajustes del editor…** | Los [ajustes del editor de código](/pyzed/es/editor/code-editor/#ajustes-del-editor): fuente, tabulación, cursor, sugerencias, servidores de lenguaje. |
| **Agentes de IA → Ajustes de los agentes de IA…** | Los [ajustes del agente](/pyzed/es/editor/ai-agents/#ajustes): proveedores de modelos, claves e inicio de sesión con el navegador, modelo predeterminado, esfuerzo y permisos. |

## Telemetría

El diseñador puede guardar datos de uso y rendimiento para ayudar a mejorarlo, pero solo si la activas: viene
**desactivada**. En **Ajustes → Telemetría**, *Recopilar datos de uso y rendimiento* registra:

- cuántas veces usas cada comando y cada acción del editor (`command.save`, `editor.select_next`…);
- cuánto tarda el diseñador en arrancar, en dibujar un fotograma y en ejecutar cada comando (cantidad, total,
  máximo y un histograma);
- el número de sesiones y su duración.

Nunca registra tu código, textos, nombres de formularios o de archivos, ni rutas. Los datos se guardan en
`telemetry.json` en la carpeta de configuración de Pyzed; **Ver** lo abre y **Borrar** lo vacía (y cambia el id
aleatorio de la instalación).

Nada sale de tu equipo salvo que además indiques un **Destino**: entonces el diseñador envía allí los datos como
JSON al cerrarse y vuelve a contar desde cero. Si el envío falla, se reintenta la próxima vez.
`PYZED_TELEMETRY=0` desactiva la telemetría digan lo que digan los ajustes.

```json
{"schema": 1, "installation": "4f0c…", "app": "pyzed-designer", "version": "0.4.0", "os": "linux",
 "arch": "x86_64", "python": "3.13", "since": "…", "until": "…", "sessions": 3,
 "counters": {"command.save": 12, "editor.select_next": 7},
 "timings": {"render": {"count": 840, "total_ms": 2210.4, "max_ms": 41.2, "buckets": [690, 120, 25, 5, 0, 0, 0, 0]}}}
```

Los `buckets` cuentan duraciones de hasta 4, 8, 16, 33, 50, 100 y 250 ms, y las más largas.

## Dónde se guardan

Todo lo que recuerda el editor va a un único archivo, `designer.json`, en la carpeta de ajustes de Pyzed:

| Plataforma | Carpeta |
| --- | --- |
| Windows | `%APPDATA%\pyzed` |
| macOS | `~/Library/Application Support/pyzed` |
| Linux | `$XDG_CONFIG_HOME/pyzed` o `~/.config/pyzed` |

Define `PYZED_CONFIG_DIR` para usar otra carpeta (útil para una instalación portátil o para tests). El archivo tiene
dos secciones: `"designer"` (tema, idioma, valores del lienzo, barra de herramientas y de estado, opciones de
ejecución, archivos recientes, y en qué dock está cada panel, qué docks están ocultos y sus tamaños) y `"editor"`
(el editor de código). Los valores no válidos se ignoran y se usan los de por defecto, así que un archivo editado a
mano no puede romper el editor.

```json
{
  "designer": { "theme": "One Light", "language": "es", "grid": 8, "snap": true, "console_on_run": true,
                "docks": { "events": "left" }, "sizes": { "right": 360 }, "recent": ["/home/ada/shop/ui/main.pzform"] },
  "editor": { "font_size": 15, "tab_size": 4, "minimap": false, "cursor_shape": "block", "format_on_apply": true }
}
```

## Traducir el editor

La interfaz del editor se traduce con [`pz.t`](/pyzed/es/guides/i18n/). El inglés y el español vienen incluidos;
añade un catálogo bajo la clave `designer` para traducirlo a otro idioma. El ajuste **Idioma** ofrece los incluidos;
para otro idioma, deja que el editor siga al sistema o pon `"language"` en la sección `designer` de
`designer.json`.

Las cadenas que faltan se muestran en inglés, así que una traducción parcial ya funciona.
