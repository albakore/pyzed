# Contributing to Pyzed

Thanks for helping! This guide explains how to set up the project, how changes
get reviewed and merged, and the conventions that keep the history and the
release notes readable. By taking part you agree to follow the
[Code of Conduct](CODE_OF_CONDUCT.md).

## Ways to help

- **Report a bug** or **ask for a feature** with the
  [issue forms](https://github.com/albakore/pyzed/issues/new/choose). Search
  the existing issues first.
- **Improve the docs or a translation**: the site lives in `docs/` (see
  [Writing docs](#writing-docs)).
- **Send a pull request**. For anything bigger than a small fix, open an issue
  first so we can agree on the approach before you spend time on it.
- **Security problems** are never reported in public issues: see
  [SECURITY.md](SECURITY.md).

## Development setup

You need Python 3.9+, a stable Rust toolchain (`rustup`) and, on Linux, the
usual X11/Wayland development libraries.

With [uv](https://docs.astral.sh/uv/):

```sh
git clone https://github.com/albakore/pyzed
cd pyzed
uv sync                              # creates .venv, builds the Rust core (release), installs pyzed editable
uv run pytest tests
uv run python examples/gallery.py
```

`uv sync` installs the `test` group (maturin, pytest). Python changes under
`python/pyzed/` are picked up directly, and after changing Rust code the next
`uv run` or `uv sync` rebuilds the core (`[tool.uv] cache-keys` in
`pyproject.toml`). Add `--extra designer` for ty and ruff.

With pip:

```sh
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install maturin pytest
maturin develop --release            # builds the Rust core and installs pyzed
pytest tests
```

Use `--release`: debug builds of Iced are too slow to use the real window.
After changing Rust code, run `maturin develop --release` again.

Before pushing, run the same checks as CI:

```sh
cargo fmt --check
cargo clippy -- -D warnings
uv run pytest tests                  # or: pytest tests
```

### Project layout

| Path | What it holds |
| --- | --- |
| `src/` | Rust core (PyO3 + Iced): widgets, renderer bridge, runtime |
| `python/pyzed/` | Python package: `App`, themes, icons, `ui` components, CLI |
| `tests/` | pytest suite (runs off-screen, no GPU needed) |
| `examples/` | runnable examples and the tutorial |
| `docs/` | documentation site (Astro Starlight) |
| `scripts/` | release and maintenance scripts |

### Writing docs

The site is in `docs/`; see the
[docs contributing guide](https://albakore.github.io/pyzed/guides/contributing-docs/)
for how to run it locally, regenerate the API reference and the component
screenshots. If you add or change public API, document it in the same PR.

The docs are bilingual: English pages live at the root of `docs/src/content/docs/` and
the Spanish translation under `docs/src/content/docs/es/`, with the same paths. Add or
change a page in both languages when you can; a missing translation falls back to English.

## Pull requests

1. Fork the repository and create a branch from `main`
   (`feature/hot-reload`, `fix/editor-scroll`, `docs/tutorial-typo`).
2. Keep each PR focused on one change. Add or update tests for behavior
   changes, and docs for user-facing ones.
3. Make sure `cargo fmt`, `clippy` and `pytest` pass locally.
4. Open the PR with a [gitmoji title](#commit-messages-and-pr-titles) and fill
   in the template. Link the issue it closes (`Closes #123`).
5. A maintainer reviews it. Push follow-up commits to the same branch; there
   is no need to squash them yourself.
6. PRs are merged with **Squash and merge**, so the PR title becomes the
   commit on `main` and the line in the release notes.

CI must be green before merging: lint, tests on Linux, macOS and Windows, the
changelog preview and the PR title check. Docs-only changes skip the build.

## Commit messages and PR titles

Pyzed follows [FastAPI](https://github.com/fastapi/fastapi)'s style: every
commit on `main` (that is, every PR title) starts with a
[gitmoji](https://gitmoji.dev), followed by a short sentence in the
imperative, in English, with no trailing period:

```text
✨ Add hot reload for running apps
🐛 Fix line numbers when the editor wraps lines
📝 Add a tutorial for multiple windows
```

The emoji decides the section of the release notes:

| Emoji | Use it for | Release notes section |
| --- | --- | --- |
| 💥 | A breaking change (also mark it in the PR description) | Breaking Changes |
| ✨ | A new feature, widget or component | Features |
| 🐛 | A bug fix | Fixes |
| 🚑️ | A critical hotfix | Fixes |
| 🔒️ | A security fix | Fixes |
| ♻️ | A refactor with no behavior change | Refactors |
| ⚡️ | A performance improvement | Refactors |
| 🎨 | Code formatting or structure | Refactors |
| 🔥 | Removing code or files | Refactors |
| ⬆️ / ⬇️ | Upgrading / downgrading a dependency | Upgrades |
| 📌 | Pinning a dependency | Upgrades |
| 📝 | Documentation | Docs |
| ✏️ | Typo fixes | Docs |
| 🌐 | Translations of the docs | Translations |
| ✅ | Adding or updating tests | Internal |
| 👷 | CI and build workflows | Internal |
| 💚 | Fixing a broken CI build | Internal |
| 🔧 | Configuration files | Internal |
| 🔨 | Development scripts | Internal |
| 🔖 | Release commits (maintainers only) | (not listed) |

Shortcodes such as `:sparkles:` work too. Conventional Commits prefixes
(`feat:`, `fix:` ...) are still understood by the changelog generator, but new
PR titles must use gitmoji; the **PR title** check enforces it.

Commits must be authored by you: do not add `Co-authored-by` trailers or
generated-by footers to commits or PR descriptions.

## Releases

Maintainers publish releases by bumping the version in `Cargo.toml` and
pushing a `vX.Y.Z` tag. The release workflow builds the wheels, publishes them
on PyPI, writes the version's section in [CHANGELOG.md](CHANGELOG.md) from the
gitmoji titles and creates the GitHub Release. The full checklist is in
[RELEASING.md](RELEASING.md).

## License

By contributing you agree that your contributions are licensed under the
[MIT License](LICENSE).
