---
title: Atajos de teclado
description: "Todos los atajos de teclado de Pyzed Design, el diseñador de GUIs para Python: comandos globales, el lienzo, los diálogos y el editor de código."
sidebar:
  order: 12
---

Pulsa <kbd>F1</kbd> en el editor para ver esta lista con buscador. En macOS, <kbd>Cmd</kbd> funciona donde un atajo
global dice <kbd>Ctrl</kbd>.

## Globales

Funcionan en cualquier sitio, incluso mientras escribes en el editor de código.

| Teclas | Comando |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>N</kbd> | Nuevo formulario |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>N</kbd> | Nuevo componente |
| <kbd>Ctrl</kbd>+<kbd>O</kbd> | Abrir |
| <kbd>Ctrl</kbd>+<kbd>P</kbd> | Ir a un archivo |
| <kbd>Ctrl</kbd>+<kbd>S</kbd> | Guardar |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>S</kbd> | Guardar como |
| <kbd>Ctrl</kbd>+<kbd>,</kbd> | Ajustes |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> | Paleta de comandos |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd> | Añadir control |
| <kbd>Ctrl</kbd>+<kbd>B</kbd> | Mostrar u ocultar el dock izquierdo |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>B</kbd> | Mostrar u ocultar el dock derecho |
| <kbd>Ctrl</kbd>+<kbd>J</kbd> | Mostrar u ocultar el dock inferior |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Y</kbd> | Consola |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>A</kbd> | Mostrar el [panel del agente](/pyzed/es/editor/ai-agents/) |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>I</kbd> | [Asistente en línea](/pyzed/es/editor/ai-agents/#asistente-en-línea) en el editor de código |
| <kbd>F5</kbd> | Ejecutar |
| <kbd>Shift</kbd>+<kbd>F5</kbd> | Detener |
| <kbd>F7</kbd> | Editar el código |
| <kbd>F1</kbd> | Atajos de teclado |
| <kbd>Shift</kbd>+<kbd>F1</kbd> | [Referencia](/pyzed/es/editor/reference/) del control seleccionado o del nombre bajo el cursor |

Con un diálogo abierto solo actúan las teclas de la paleta, Ajustes y Atajos de teclado; las demás esperan a que se
cierre.

## Lienzo

Actúan cuando el lienzo tiene el teclado: después de hacer clic en el formulario, en un control, en una fila de la
caja de herramientas o en una fila de la estructura. Llevar el puntero a un dock le da el teclado a ese panel (así
escribir en un campo nunca mueve un control), y el editor de código lo conserva mientras escribes; haz clic otra vez
en el lienzo para recuperar sus atajos.

| Teclas | Acción |
| --- | --- |
| <kbd>←</kbd> <kbd>→</kbd> <kbd>↑</kbd> <kbd>↓</kbd> | Mover la selección 1 px |
| <kbd>Shift</kbd>+flechas | Moverla un paso de cuadrícula (1 px con el snap apagado) |
| <kbd>Supr</kbd>, <kbd>Retroceso</kbd> | Eliminar la selección |
| <kbd>Ctrl</kbd>+<kbd>C</kbd> | Copiar |
| <kbd>Ctrl</kbd>+<kbd>X</kbd> | Cortar |
| <kbd>Ctrl</kbd>+<kbd>V</kbd> | Pegar |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Duplicar |
| <kbd>Ctrl</kbd>+<kbd>A</kbd> | Seleccionar todos los controles |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> | Deshacer |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd>, <kbd>Ctrl</kbd>+<kbd>Y</kbd> | Rehacer |
| <kbd>Enter</kbd> | Abrir el código del evento principal del control seleccionado |
| <kbd>G</kbd> | Mostrar u ocultar la cuadrícula |
| <kbd>Esc</kbd> | Cancelar un arrastre, cerrar un menú o soltar la herramienta de colocar y volver al puntero |

## Ratón

| Gesto | Acción |
| --- | --- |
| Clic | Seleccionar un control (en uno ya seleccionado: hacerlo el principal) |
| Arrastrar un control | Mover la selección; soltarla sobre un contenedor la mete dentro |
| Arrastrar un asa | Redimensionar |
| Arrastrar en un hueco | Selección con rectángulo |
| Doble clic en un control | Abrir el código de su evento principal, o un componente diseñado en su pestaña |
| Clic derecho | Menú contextual |
| Arrastrar desde la caja de herramientas | Colocar un control donde lo sueltas |
| Arrastrar una fila de la estructura | Reordenar, o mover a otro contenedor |
| Arrastrar el tirador bajo el formulario | Redimensionar el formulario |
| <kbd>Ctrl</kbd>+rueda en el editor de código | Tamaño de letra |

## Listas, paletas y diálogos

| Teclas | Acción |
| --- | --- |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Moverse por la paleta de comandos y Añadir control |
| <kbd>Enter</kbd> | Ejecutar el comando resaltado, añadir el control resaltado, enviar el campo de un diálogo |
| <kbd>Esc</kbd> | Cerrar el diálogo, la paleta o el menú |

## Árbol del proyecto

Después de hacer clic en el árbol de la [pestaña Proyecto](/pyzed/es/editor/projects/#archivos), como en el panel de
proyecto de Zed:

| Teclas | Acción |
| --- | --- |
| <kbd>↑</kbd> <kbd>↓</kbd> | Mover la selección |
| <kbd>←</kbd> <kbd>→</kbd> | Cerrar / abrir la carpeta |
| <kbd>Enter</kbd> | Abrir el archivo |
| <kbd>Ctrl</kbd>+<kbd>N</kbd> / <kbd>Alt</kbd>+<kbd>N</kbd> | Nuevo archivo / nueva carpeta |
| <kbd>F2</kbd> | Renombrar |
| <kbd>Ctrl</kbd>+<kbd>X</kbd> / <kbd>Ctrl</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>V</kbd> | Cortar / copiar / pegar |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Duplicar |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Deshacer / rehacer un cambio de archivos |
| <kbd>Supr</kbd> / <kbd>Ctrl</kbd>+<kbd>Supr</kbd> | Mover a la papelera / borrar para siempre |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>R</kbd> | Mostrar en el gestor de archivos |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Enter</kbd> | Abrir con la app predeterminada |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> / <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>C</kbd> | Copiar la ruta / la ruta relativa |

## Editor de código

| Teclas | Acción |
| --- | --- |
| <kbd>Ctrl</kbd>+<kbd>Espacio</kbd> | Mostrar sugerencias |
| <kbd>↑</kbd> / <kbd>↓</kbd> | Moverse por la lista de sugerencias (da la vuelta) |
| <kbd>RePág</kbd> / <kbd>AvPág</kbd> | Nueve filas en la lista, o una página en el código |
| <kbd>Enter</kbd>, <kbd>Tab</kbd> | Aceptar la sugerencia |
| <kbd>Esc</kbd> | Cerrar la lista de sugerencias |
| <kbd>Tab</kbd> | Sangrar con espacios |
| <kbd>Enter</kbd> | Línea nueva manteniendo la sangría (un nivel más después de `:`) |
| <kbd>Retroceso</kbd> | Dentro de la sangría, quitar un nivel |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>[</kbd> | Plegar el bloque alrededor del cursor |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>]</kbd> | Desplegarlo |
| <kbd>Ctrl</kbd>+<kbd>=</kbd> / <kbd>Ctrl</kbd>+<kbd>-</kbd> / <kbd>Ctrl</kbd>+<kbd>0</kbd> | Letra más grande, más pequeña, por defecto |
| <kbd>Ctrl</kbd>+<kbd>←</kbd> / <kbd>→</kbd> | Moverse por palabras |
| <kbd>Ctrl</kbd>+<kbd>Inicio</kbd> / <kbd>Fin</kbd> | Principio o final del código |
| <kbd>Shift</kbd>+movimiento | Seleccionar |
| <kbd>Ctrl</kbd>+<kbd>A</kbd>, <kbd>Ctrl</kbd>+<kbd>C</kbd>, <kbd>Ctrl</kbd>+<kbd>X</kbd>, <kbd>Ctrl</kbd>+<kbd>V</kbd> | Seleccionar todo, copiar, cortar, pegar |
| <kbd>Ctrl</kbd>+<kbd>F</kbd> / <kbd>Ctrl</kbd>+<kbd>H</kbd> | Buscar / buscar y reemplazar |
| <kbd>F3</kbd> / <kbd>Shift</kbd>+<kbd>F3</kbd> | Coincidencia siguiente / anterior |
| <kbd>Ctrl</kbd>+<kbd>G</kbd> | Ir a la línea |
| <kbd>Alt</kbd>+clic | Añadir un cursor |
| <kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Añadir un cursor arriba / abajo |
| <kbd>Ctrl</kbd>+<kbd>D</kbd> | Seleccionar la siguiente coincidencia como otro cursor |
| <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>L</kbd> | Seleccionar todas las coincidencias |
| <kbd>Alt</kbd>+<kbd>↑</kbd> / <kbd>↓</kbd> | Subir / bajar la línea |
| <kbd>Ctrl</kbd>+<kbd>Alt</kbd>+<kbd>Shift</kbd>+<kbd>↓</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>K</kbd> | Duplicar / borrar la línea |
| <kbd>Ctrl</kbd>+<kbd>/</kbd> | Comentar o descomentar |
| <kbd>Ctrl</kbd>+<kbd>Z</kbd> / <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>Z</kbd> | Deshacer / rehacer |
| <kbd>Ctrl</kbd>+<kbd>K</kbd> <kbd>Ctrl</kbd>+<kbd>0</kbd> / <kbd>J</kbd> | Plegar / desplegar todo |

La lista completa está en [el componente editor de código](/pyzed/es/components/code/#varios-cursores-y-los-atajos-de-zed).
