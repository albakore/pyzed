---
title: Estabilidad y limitaciones conocidas
description: "Qué promete Pyzed 1.x sobre su API de Python, cómo se retiran funciones de una versión a otra y qué no hace todavía el framework."
sidebar:
  order: 30
---

## Versiones

Desde la 1.0.0, Pyzed sigue el [versionado semántico](https://semver.org/lang/es/):

- Las versiones **patch** (`1.0.x`) solo corrigen errores.
- Las versiones **minor** (`1.x.0`) añaden funciones y nunca rompen el código que usa la API pública.
- Las versiones **major** (`2.0.0`) son las únicas que pueden quitar o cambiar API pública.

La API pública es todo lo documentado en la [referencia de la API](/pyzed/es/reference/app/) y en estas guías. Los
nombres que empiezan con guion bajo y todo lo que está en `pyzed.designer` son internos y pueden cambiar en
cualquier versión.

`pyzed.agents`, `pyzed.mcp` y la API de animaciones son **provisionales** en 1.x: siguen las mismas reglas, pero
una versión minor todavía puede ajustar detalles que resulten equivocados, y el cambio siempre aparece en
*Breaking Changes* en las [notas de versión](/pyzed/es/changelog/).

## Deprecaciones

Antes de quitar API pública, sigue funcionando al menos durante una versión minor y avisa con un
`DeprecationWarning` que nombra su reemplazo. Se quita en la siguiente versión major.

Los archivos de Pyzed Design (`.pzform` y componentes) llevan una versión de formato. Pyzed abre los de su
versión y anteriores, y rechaza un archivo guardado por un Pyzed más nuevo en lugar de perder en silencio lo que
no conoce.

## Limitaciones conocidas

| Área | Limitación |
| --- | --- |
| Accesibilidad | Todavía no hay soporte para lectores de pantalla: Iced no expone información de accesibilidad. El teclado sí funciona (Tab pasa de un campo a otro, ver [Accesibilidad](/pyzed/es/guides/accessibility/)). |
| Efectos | Con el renderizador de GPU no se dibujan sombras bajo cajas rellenas con un degradado. |
| Animaciones | Se pueden animar 17 propiedades (opacidad, posición, escala, rotación, desenfoque, colores, radio, grosor del borde, glow, tamaño, padding y tamaño de fuente); cualquier otra propiedad de estilo cambia de golpe. |
| Muchos datos | Las listas y tablas virtuales necesitan filas de la misma altura. Cada actualización sigue llamando a `view()`; [`@pz.memo`](/pyzed/es/guides/performance/) se salta los subárboles que no cambiaron. |
| Plataformas | En Linux los wheels necesitan glibc 2.28 o posterior, o musl (Alpine), donde el motor de audio no tiene dispositivos de sonido. Las builds de Pyzed Design todavía no están firmadas. Android es un prototipo (`android/build_apk.py`); iOS y el navegador todavía no son destinos. |
| Python | Python free-threaded (3.13t, 3.14t) no está soportado. Pyzed necesita Python 3.10 o posterior. |
