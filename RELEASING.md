# Releasing a version

Release notes are generated from the gitmoji commit titles on `main` (see
[CONTRIBUTING.md](CONTRIBUTING.md#commit-messages-and-pr-titles)), grouped like
FastAPI's: Breaking Changes, Features, Fixes, Refactors, Upgrades, Docs,
Translations and Internal.

## Steps

1. Optionally write notes by hand under `## [Unreleased]` in `CHANGELOG.md`,
   for example a `### Highlights` section. They are merged with the generated
   entries; if the version already has its own section, it is used as is.
   Preview what would be generated with:

   ```sh
   pip install git-cliff
   python scripts/changelog.py --preview
   ```

2. Bump the version in `Cargo.toml` (the only source; `pyproject.toml` reads it
   from there) and refresh `Cargo.lock` with `cargo update -p pyzed`. Use a
   suffix for a pre-release: `0.3.0-rc.1`, `0.3.0-beta.1`. Refresh the list of
   pages and examples the MCP server ships with
   `python docs/scripts/gen_mcp_index.py`. Merge that change with a PR titled
   `🔖 Release 0.3.0`.

3. Create and push the tag from `main`:

   ```sh
   git switch main && git pull
   git tag v0.3.0
   git push origin v0.3.0
   ```

   Creating a release on GitHub with a new `v0.3.0` tag on `main` works too.

The **Release** workflow (`.github/workflows/release.yml`) then:

- checks that the tag matches `Cargo.toml`;
- builds the wheels (Linux x86_64/aarch64, macOS arm64/x86_64, Windows x64)
  and the sdist, and tests each wheel. The README links are made absolute
  (`scripts/pypi_readme.py`) so images show up on PyPI;
- publishes on PyPI with Trusted Publishing;
- adds the version's section to `CHANGELOG.md` on `main`;
- creates the GitHub Release with those notes, marked as *latest* when it is
  stable or as a *pre-release* when it has a suffix;
- redeploys the documentation site (`docs.yml`), which marks the latest
  stable version.

## One-time PyPI setup

Already done for `pyzed-ui`. For reference, the trusted publisher at
<https://pypi.org/manage/account/publishing/> is:

| Field | Value |
| --- | --- |
| PyPI project name | `pyzed-ui` |
| Owner | `albakore` |
| Repository name | `pyzed` |
| Workflow name | `release.yml` |
| Environment name | `pypi` |

The name `pyzed` was already taken on PyPI, so the package is published as
`pyzed-ui` (`pip install pyzed-ui`); in code it is still `import pyzed`.
