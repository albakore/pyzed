---
title: Introducción
description: Qué es Pyzed, cómo funciona y cuándo usarlo.
---

**Pyzed** es una librería para crear interfaces de escritorio en Python con el rendimiento de
[Iced](https://iced.rs), un toolkit de GUI escrito en Rust. Incluye una colección de componentes
inspirados en el editor [Zed](https://zed.dev): pestañas, árbol de archivos, paleta de comandos,
editor de código, terminal, menús, notificaciones y un workspace con paneles acoplables.

![Recreación de Zed hecha con Pyzed (tema One Light)](../../../../../screenshots/zed-one-light.png)

## Cómo funciona

Tu código Python describe **qué** se ve. Rust se encarga de **cómo** se dibuja.

```
Python                         Rust (pyzed._core, PyO3)                 Iced 0.14
App.view() ──► árbol de Widget ──► render.rs: Widget → iced::Element ──► layout + wgpu/tiny-skia
App.update() ◄── mensajes ◄────── app.rs: Message, Command → Task ◄──── eventos (ratón, teclado)
```

- `view()` devuelve un árbol de `Widget`. Son objetos inmutables de Rust, así que construirlo es barato.
- Cuando el usuario interactúa, Pyzed llama a tu `update(mensaje)` o directamente al callable
  que pasaste (`on_press=self.guardar`). Después vuelve a llamar a `view()`.
- El layout, el texto, el resaltado de sintaxis y el dibujado ocurren en Rust.
- El GIL se libera mientras corre el bucle de eventos, así que tus hilos de Python siguen trabajando.

## Cuándo usar Pyzed

- Herramientas de escritorio, paneles internos, editores y utilidades que deben sentirse rápidas.
- Interfaces densas al estilo de un IDE, con muchos paneles, listas y atajos de teclado.
- Apps que quieres probar o documentar con capturas generadas sin pantalla.

## Qué necesitas saber

Python básico: clases, funciones y lambdas. No hace falta saber Rust ni Iced.

Continúa con la [instalación](/pyzed/es/getting-started/installation/) o salta directamente al
[inicio rápido](/pyzed/es/getting-started/quickstart/).
