---
title: Trucos y consejos
description: "Pequeños hábitos que te hacen más rápido en Pyzed Design: atajos, selección múltiple, guías inteligentes, plantillas y trucos para crear formularios."
sidebar:
  order: 14
---

## Colocar y ordenar

- **Dibuja en lugar de soltar**: haz clic en un componente de la caja de herramientas y arrastra un rectángulo en el
  formulario. El control toma exactamente ese tamaño, ajustado a la cuadrícula, y te ahorras redimensionarlo.
- **Añade sin la caja de herramientas**: <kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>A</kbd>, escribe dos o tres letras,
  <kbd>Enter</kbd>. Con el dock izquierdo oculto (<kbd>Ctrl</kbd>+<kbd>B</kbd>) el lienzo tiene todo el ancho.
- **Elige la referencia de alineación**: tras seleccionar varios controles, haz clic en el que ya está bien. Pasa a
  ser el control principal (borde más grueso), y **Mismo ancho** / **Mismo alto** copian *su* tamaño.
- **Alinea con el formulario**: con un solo control seleccionado, los botones de alinear lo ajustan a los bordes y
  al centro del formulario; **Centrar en el formulario** centra toda la selección como grupo.
- **Empuja en pasos de cuadrícula**: <kbd>Shift</kbd>+flechas mueve un paso de cuadrícula, las flechas solas un
  píxel. Varios empujones seguidos son un solo paso de deshacer.
- **Cancela un arrastre fallido**: pulsa <kbd>Esc</kbd> antes de soltar el ratón y todo vuelve a su sitio.
- **Arregla una disposición desordenada de golpe**: sin nada seleccionado, **Ajustar la selección a la cuadrícula**
  (barra de herramientas) ajusta todos los controles del formulario a la cuadrícula.
- **¿Las guías te estorban?** Apaga las **Guías inteligentes** (regla) o el **Snap** (imán, o clic en *Snap* en la
  barra de estado) para colocar al píxel, y vuelve a encenderlos después.

## Contenedores

- **Envuelve, no reconstruyas**: selecciona controles que ya están bien y usa **Group in a row / column / grid /
  panel** en el menú contextual. El contenedor se crea a su alrededor.
- **Agarra el contenedor, no su hijo**: usa la pestaña sobre su esquina superior izquierda, o su fila en la
  estructura.
- **Empuja al final**: un **Espaciador** en una fila flex empuja todo lo que va detrás hasta el otro extremo; dos
  espaciadores centran lo que hay entre ellos.
- **Columnas iguales**: en una fila flex, da a cada hijo **Crecer** 1; en una grilla, usa **Alto de fila** 0 para
  que las filas se repartan el alto.
- **Hazla redimensionable**: ancla el contenedor principal por los cuatro lados y deja que los contenedores flex de
  dentro se repartan el espacio con **Crecer**. Ejecuta con <kbd>F5</kbd> y cambia el tamaño de la ventana para
  comprobarlo.

## Estructura

- **Oculta mientras trabajas**: el ojo de la estructura oculta un control (un diálogo, una capa encima) para
  trabajar en lo que hay debajo. Acuérdate de volver a mostrarlo, o hazlo visible desde código
  (`form.panel.show()`).
- **Bloquea el fondo**: bloquea los paneles grandes y las imágenes para que un arrastre despistado no los mueva
  mientras colocas los controles de encima. Las herramientas de alinear e igualar tamaños también saltan los
  controles bloqueados.
- **Reordena los hijos de un flex** arrastrando sus filas en la estructura: la línea muestra exactamente dónde caen.

## Código

- **Enter es "editar código"**: selecciona un control y pulsa <kbd>Enter</kbd> para saltar al manejador de su
  evento principal.
- **Primero el nombre, luego el código**: renombra los controles (**Nombre** y <kbd>Enter</kbd>) antes de escribir
  manejadores. Renombrar después sigue actualizando los manejadores que siguen la convención `control_evento`, pero
  el código que menciona `form.button1` en otros sitios no se reescribe.
- **Deja que el autocompletado te enseñe**: `form.` lista los controles, `form.status.` las propiedades de ese
  control, `event.` los campos del evento, y el panel de documentación muestra la descripción de cada propiedad.
- **Inserta llamadas a miembros**: en un componente diseñado colocado, abre su flecha en la estructura y haz clic
  en un método para escribir `form.card.rate()` en el cursor.
- **Comparte lógica entre controles**: los manejadores son funciones normales, así que pon la parte común en una
  función auxiliar al principio del archivo y llámala desde cada manejador; `event.sender` dice qué control lanzó
  el evento.
- **Formatea al aplicar**: activa *Format with ruff on Apply* en los ajustes del editor y pulsa **Apply** para
  ordenar el manejador que acabas de escribir.
- **Letra más grande para demos**: <kbd>Ctrl</kbd>+<kbd>=</kbd> en el editor de código, <kbd>Ctrl</kbd>+<kbd>0</kbd>
  para volver.
- **Restart servers** después de `uv add` / `uv sync` si el autocompletado aún no conoce un paquete nuevo.

## Ejecutar

- **F5 ejecuta lo que ves**: dentro del entorno del proyecto, Ejecutar usa el documento actual, con los cambios sin
  guardar. Deja la ventana abierta y pulsa <kbd>Ctrl</kbd>+<kbd>S</kbd> para actualizarla en su sitio, conservando lo
  que escribiste en ella.
- **Lee la consola, no la terminal**: los eventos muestran sus valores
  (`email.change ('ada@') → email_change()`), y los errores, la traza completa empezando por tu manejador. Fíltrala
  por el nombre de un control para seguir solo ese.
- **Apaga el registro de eventos** (Ajustes → Ejecución) cuando un temporizador o un deslizador inundan la consola.
- **Prueba los componentes por separado**: abre un `.pzcomp` y pulsa <kbd>F5</kbd>; la vista previa lista cada
  evento personalizado que lanza el componente, con su valor.

## La disposición del editor

- **Dos paneles a la vez**: mueve **Eventos** al dock izquierdo (o al superior) con el botón del dock, para ver
  Propiedades y Eventos a la vez.
- **Pliega las secciones que no usas** en Propiedades: siguen plegadas mientras pasas de un control a otro.
- **¿Perdiste un panel?** **Ver → Restablecer los paneles** lo devuelve todo a su sitio.
- **Ajustes portátiles**: define `PYZED_CONFIG_DIR` para llevar los ajustes del editor con un proyecto o en un USB.

## Archivos

- **Guarda los dos archivos en git**: el `.pzform` es JSON legible que da buenos diffs, y el `.py` es Python normal.
  Quien revise puede leer los dos.
- **Edita el código donde quieras**: el editor solo reescribe las funciones manejadoras que gestiona, así que puedes
  tener el archivo de código abierto también en Zed o VS Code; ejecuta con `pyzed run app.pzform --reload` para ver
  cada guardado.
- **Las plantillas te adelantan trabajo**: la plantilla *Diálogo* ya conecta Aceptar y Cancelar; *Ajustes* muestra
  una grilla de etiquetas y campos. Registra las tuyas con `designer.register_template`.
