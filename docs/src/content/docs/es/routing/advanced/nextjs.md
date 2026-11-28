---
title: Si vienes de Next.js
description: "Cada concepto del App Router de Next.js y su nombre en Pyzed: archivos, carga de datos, server actions, middleware, hooks, metadata y lo que aún no está."
sidebar:
  order: 5
---

| Next.js | Pyzed |
| --- | --- |
| carpeta `app/`, `page.tsx` | carpeta `app/`, `page.py` |
| `layout.tsx`, `template.tsx` | `layout.py`, `template.py` |
| `loading.tsx`, `error.tsx`, `not-found.tsx` | `loading.py`, `error.py`, `not_found.py` |
| `middleware.ts` + `config.matcher` | `middleware.py` + `matcher` (uno por carpeta) |
| `[id]`, `[...slug]`, `[[...slug]]`, `(group)`, `_private` | lo mismo |
| imports con `@/` | la carpeta que contiene `app/` se puede importar |
| server component async | `async def load(params)` + `def page(data)` |
| caché de `fetch`, `revalidate` | la caché de páginas y `stale_time` |
| `revalidatePath(path)` | `router.invalidate(path)` o `@pz.action(invalidate=...)` |
| `router.refresh()` | `router.refresh()` |
| server actions + `useActionState` | `@pz.action` con `pending`, `result`, `error` |
| `NextResponse.redirect`, `.rewrite` | `request.redirect(...)`, `request.rewrite(...)` |
| cabeceras que pone el middleware | `request.locals` → `locals` |
| `generateMetadata` / `metadata` | `def title(data)`, `title`, `metadata` |
| `title.template` | `title_template = "%s · Shop"` |
| `<Link href prefetch>` | `pz.link(href, content, prefetch=True)` |
| `useRouter`, `usePathname`, `useParams`, `useSearchParams` | `pz.use_router`, `pz.use_pathname`, `pz.use_params`, `pz.use_search_params` |
| `notFound()`, `redirect()` | `pz.not_found()`, `pz.redirect()` |
| contexto de React | `provide` en un layout + `pz.use_context` |
| Zustand, Redux, Jotai | `pz.Store` |
| `create-next-app` | `pyzed new NOMBRE --router` |
| `next dev` | `pyzed dev main.py` |
| salida de `next build` | `pyzed route list` |

## Qué cambia

- **No hay servidor.** `load`, las acciones y el middleware corren en la app, fuera del hilo de
  la interfaz. Llaman a tu API o a tu base de datos como cualquier código Python.
- **Cada página es un client component**, con un estado que dura mientras se ve. No hay
  hidratación ni `"use client"`.
- **El historial es de la propia app**: Alt+Izquierda y Alt+Derecha, los botones laterales del
  ratón y el botón atrás de Android se mueven por él.
- **Las notificaciones** (`pz.notify`) son nativas y un clic puede abrir una página.

Las rutas paralelas (`@slot`) y las rutas que interceptan (`(.)photo`) aún no están.
