---
title: Coming from Next.js
description: "Every Next.js App Router concept and its Pyzed name: files, data fetching, server actions, middleware, hooks, metadata and what is not supported."
sidebar:
  order: 5
---

| Next.js | Pyzed |
| --- | --- |
| `app/` folder, `page.tsx` | `app/` folder, `page.py` |
| `layout.tsx`, `template.tsx` | `layout.py`, `template.py` |
| `loading.tsx`, `error.tsx`, `not-found.tsx` | `loading.py`, `error.py`, `not_found.py` |
| `middleware.ts` + `config.matcher` | `middleware.py` + `matcher` (one per folder) |
| `[id]`, `[...slug]`, `[[...slug]]`, `(group)`, `_private` | the same |
| `@/` imports | the folder that holds `app/` is importable |
| async server component | `async def load(params)` + `def page(data)` |
| `fetch` cache, `revalidate` | the page cache and `stale_time` |
| `revalidatePath(path)` | `router.invalidate(path)` or `@pz.action(invalidate=...)` |
| `router.refresh()` | `router.refresh()` |
| server actions + `useActionState` | `@pz.action` with `pending`, `result`, `error` |
| `NextResponse.redirect`, `.rewrite` | `request.redirect(...)`, `request.rewrite(...)` |
| headers set by middleware | `request.locals` → `locals` |
| `generateMetadata` / `metadata` | `def title(data)`, `title`, `metadata` |
| `title.template` | `title_template = "%s · Shop"` |
| `<Link href prefetch>` | `pz.link(href, content, prefetch=True)` |
| `useRouter`, `usePathname`, `useParams`, `useSearchParams` | `pz.use_router`, `pz.use_pathname`, `pz.use_params`, `pz.use_search_params` |
| `notFound()`, `redirect()` | `pz.not_found()`, `pz.redirect()` |
| React context | `provide` in a layout + `pz.use_context` |
| Zustand, Redux, Jotai | `pz.Store` |
| `create-next-app` | `pyzed new NAME --router` |
| `next dev` | `pyzed dev main.py` |
| `next build` output | `pyzed route list` |

## What is different

- **There is no server.** `load`, actions and middleware run in the app, off the UI thread. They
  call your API or your database like any Python code.
- **Every page is a client component**, with state that lasts while it is shown. There is no
  hydration and no `"use client"`.
- **The history is the app's own**: Alt+Left and Alt+Right, the mouse's side buttons and
  Android's back button move in it.
- **Notifications** (`pz.notify`) are native and a click can open a page.

Parallel routes (`@slot`) and intercepting routes (`(.)photo`) are not supported yet.
