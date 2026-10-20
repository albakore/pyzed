---
title: "Demos"
description: "Demos de lo que Pyzed puede dibujar: HUD, menús e inventarios de videojuegos, paneles de cristal esmerilado, bloom y shaders de GPU reales, todo en Python."
section:
  eyebrow: "Showcase"
  icon: "laptop"
  lead: "Lo que Pyzed puede dibujar: interfaces de juegos, paneles de cristal, bloom y shaders de GPU. Cada demo es un archivo de Python que puedes ejecutar y estudiar."
sidebar:
  order: 0
  label: "Resumen"
---

:::note[Más demos en camino]
Se están añadiendo demos de formularios, utilidades y shaders, cada una con un tutorial que explica cómo está hecha. Los juegos tienen sus propias páginas en esta sección.
:::

Pyzed dibuja con la GPU, así que una app de escritorio en Python puede verse como un videojuego o un sistema operativo modernos: desenfoque real del fondo (`glass`), luz que desborda de las partes brillantes (`bloom`), rotación, transparencia y tus propios shaders WGSL (`pz.shader`). Cada demo es un archivo de [`examples/showcase`](https://github.com/albakore/pyzed/tree/main/examples/showcase); ejecútala y luego lee cómo está hecha.

## [HUD de videojuego](/pyzed/es/showcase/hud/)

Un HUD de videojuego en Python: barras de vida y maná, un minimapa de radar hecho con un shader, una barra de habilidades con enfriamientos y paneles de cristal.

[![HUD de videojuego](../../../../assets/showcase/hud.png)](/pyzed/es/showcase/hud/)

## [Menú principal de videojuego](/pyzed/es/showcase/main-menu/)

Un menú principal synthwave en Python con un fondo de shader que sigue al ratón, un título brillante y botones de cristal que se elevan en hover.

[![Menú principal de videojuego](../../../../assets/showcase/main-menu.png)](/pyzed/es/showcase/main-menu/)

## [Inventario de RPG](/pyzed/es/showcase/inventory/)

Una pantalla de inventario de RPG en Python donde la rareza de los objetos brilla con glow y bloom, con un panel de detalles de cristal animado sobre un shader de brasas.

[![Inventario de RPG](../../../../assets/showcase/inventory.png)](/pyzed/es/showcase/inventory/)

## [Centro de control de cristal](/pyzed/es/showcase/glass-dashboard/)

Un panel profesional de cristal esmerilado en Python: reproductor, luces, clima y agenda con desenfoque real del fondo sobre colores en movimiento.

[![Centro de control de cristal](../../../../assets/showcase/glass-dashboard.png)](/pyzed/es/showcase/glass-dashboard/)

## [Galería de shaders](/pyzed/es/showcase/shaders/)

Seis shaders de GPU escritos en WGSL y mostrados como widgets de Pyzed: plasma, ondas que siguen al ratón, un túnel, una pantalla CRT, celdas de Voronoi y fuego.

[![Galería de shaders](../../../../assets/showcase/shaders.png)](/pyzed/es/showcase/shaders/)

Aprende las piezas en [Animación y efectos](/pyzed/es/guides/animation/) y [Shaders](/pyzed/es/shading/shaders/).
