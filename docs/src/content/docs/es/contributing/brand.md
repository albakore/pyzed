---
title: Marca
description: "La marca de Pyzed: el logo de la pitón y el wordmark, los iconos de la app, las paletas Grafito y Papel, la tipografía IBM Plex y cómo los usa esta web."
sidebar:
  order: 7
---

La pitón dibuja la "p" de Pyzed y la reemplaza en el wordmark. El lomo coincide con la altura de x de IBM Plex
Sans y la cola baja como un descendente. Los logos, los iconos de la app y los tokens de color están en
[`assets/brand`](https://github.com/albakore/pyzed/tree/main/assets/brand); `scripts/brand.py` los genera todos a
partir de los mismos trazos y colores.

## Logo

| Archivo | Uso |
| --- | --- |
| `pyzed-wordmark.svg`, `pyzed-wordmark-dark.svg` | El logo principal, sobre fondo claro y oscuro (al menos 72 px de ancho) |
| `pyzed-design.svg`, `pyzed-design-dark.svg` | El lockup de Pyzed Design |
| `pyzed-mark.svg`, `pyzed-mark-dark.svg` | El isotipo solo, desde 24 px (barras de navegación y de título) |
| `pyzed-mark-small.svg` | Una silueta sin ojos, para 16 a 20 px |
| `pyzed-mark-black.svg`, `pyzed-mark-white.svg` | Una sola tinta |
| `app-icon.svg`, `app-icon-dark.svg` | El icono de la app, índigo y grafito |

Deja alrededor del isotipo un margen tan ancho como su cabeza, y no lo estires, gires ni cambies de color fuera
de la paleta de abajo.

## Color

Superficies grafito en capas, como un editor de código. El índigo es la marca y el ámbar se reserva para LEDs y
displays, con el lenguaje de paneles de un rack de audio. El oscuro («Grafito») es el modo por defecto; el claro
(«Papel») mantiene las mismas jerarquías.

| Token | Grafito (oscuro) | Papel (claro) |
| --- | --- | --- |
| Fondo | `#0D0E11` | `#F6F7F9` |
| Superficie | `#14161B` | `#FFFFFF` |
| Panel | `#191C22` | `#F1F3F6` |
| Elevado | `#222630` | `#E7EAF0` |
| Borde | `#2A2F39` | `#DCE0E7` |
| Texto | `#E7E9EE` | `#14161B` |
| Texto secundario | `#9AA1AE` | `#576070` |
| Índigo | `#8B83FF` | `#4F46E5` |
| Índigo sólido (botones) | `#5B50F0` | `#4F46E5` |
| LED ámbar | `#F5A524` | `#F5A524` |

`assets/brand/tokens.json` tiene todos los tokens, también los del display (LCD), la cuadrícula del lienzo y los
colores de código.

## Tipografía

**IBM Plex Sans** para todo lo que se lee: titulares 700, subtítulos 600 y texto 400. Es la misma familia que
usan los componentes de Pyzed. **IBM Plex Mono** para código, teclas, etiquetas y antetítulos.

## En esta web

- Los colores son variables CSS en `docs/src/styles/custom.css`: las `--sl-color-*` de Starlight más
  `--pz-brand`, `--pz-surface`, `--pz-led`, `--pz-lcd` y el resto, para los componentes de `docs/src/components`.
- El wordmark de la cabecera es `src/components/brand/Wordmark.astro`; `Mark.astro` dibuja el isotipo en línea
  para que tome el color del texto que lo rodea. Sus trazos se copian de `scripts/brand.py`.
- Los bloques de código usan dos temas de Expressive Code hechos con los colores de código de la marca, en
  `docs/src/styles/code`.
- El favicon es `assets/brand/favicon.svg`; `python docs/scripts/gen_og.py` dibuja las tarjetas sociales y los
  iconos PNG a partir del icono de la app.
