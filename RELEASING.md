# Publicar una versión

Los mensajes de commit (y los títulos de PR, que son el commit al hacer
*squash merge*) siguen [Conventional Commits](https://www.conventionalcommits.org/es/v1.0.0/):
`feat:`, `fix:`, `perf:`, `refactor:`, `docs:`, `test:`, `build:`, `ci:`,
`chore:`. Un `!` (`feat!: ...`) o un pie `BREAKING CHANGE: ...` marca un
cambio incompatible. Con eso se arma el changelog de cada release.

## Pasos

1. Si quieres, redacta a mano las notas bajo `## [Sin publicar]` en
   `CHANGELOG.md` (formato [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)).
   Al publicar se combinan con las generadas desde los commits; si la versión
   ya tiene su propia sección, se usa tal cual.
2. Sube la versión en `Cargo.toml` (es la única fuente; `pyproject.toml` la
   toma de ahí) y actualiza `Cargo.lock` con `cargo update -p pyzed`.
   Para una pre-release usa un sufijo: `0.2.0-rc.1`, `0.2.0-beta.1`.
3. Haz merge del PR en `main`.
4. Crea y empuja el tag:

   ```sh
   git tag v0.2.0
   git push origin v0.2.0
   ```

El workflow **Release** (`.github/workflows/release.yml`) entonces:

- verifica que el tag coincide con `Cargo.toml`;
- compila wheels (Linux x86_64/aarch64, macOS arm64/x86_64, Windows x64) y el
  sdist, y prueba cada wheel;
- publica en PyPI con Trusted Publishing;
- crea la GitHub Release con sus notas (breaking changes, nuevas funciones,
  mejoras, correcciones…), marcada como *latest* si es estable o como
  *pre-release* si lleva sufijo;
- añade la sección de la versión a `CHANGELOG.md` en `main` y vuelve a
  desplegar la web de documentación (`docs.yml`), que marca la última versión
  estable.

Para ver qué entraría en la próxima versión:
`pip install git-cliff && python scripts/changelog.py --preview`.

## Configuración única en PyPI

En <https://pypi.org/manage/account/publishing/> añade un *pending publisher*:

| Campo | Valor |
| --- | --- |
| PyPI project name | `pyzed-ui` |
| Owner | `albakore` |
| Repository name | `pyzed` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

El nombre `pyzed` ya está ocupado en PyPI, así que el paquete se publica como
`pyzed-ui` (`pip install pyzed-ui`); en código se sigue importando `import pyzed`.

Y en GitHub, *Settings → Environments*, crea el entorno `pypi` (opcionalmente
con aprobación manual antes de publicar).
