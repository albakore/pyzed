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

   Creating a release on GitHub with a new `v0.3.0` tag on `main` works too. The workflow turns it
   into a draft until its files are attached, so the download page, `install.sh` and the app's
   updater keep offering the previous version meanwhile (and if a build fails).

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

## Optional secrets

The workflow also builds the standalone Pyzed Design app (`scripts/build_designer.py --installer`)
on Linux, Windows and macOS: a portable zip per platform (what the app's updater downloads), the
per-user Windows setup program (Inno Setup, `installer/windows/pyzed-design.iss`) and the macOS
`.dmg`. The release also carries `install.sh` (the Linux installer, served by the docs site from
`docs/public/install.sh`) and a `SHA256SUMS` it checks downloads with. Every secret below is optional: without them the
release still runs, the app is just unsigned or signs in without a bundled OAuth
app. Add them under *Settings → Secrets and variables → Actions*.

| Secret | Used for |
| --- | --- |
| `PYZED_GITHUB_CLIENT_ID` | Client ID of the GitHub App the Agent panel signs in to GitHub Copilot with (device flow). |
| `PYZED_GOOGLE_CLIENT_ID` | Client ID of the Google OAuth app (desktop type) for signing in to Vertex AI. |
| `PYZED_GOOGLE_CLIENT_SECRET` | Its client secret (not confidential for desktop apps). |
| `MACOS_CERTIFICATE`, `MACOS_CERTIFICATE_PASSWORD` | A base64 "Developer ID Application" `.p12` and its password, imported into a temporary keychain. |
| `MACOS_CODESIGN_IDENTITY` | The identity that signs the `.app` with the hardened runtime. |
| `APPLE_ID`, `APPLE_TEAM_ID`, `APPLE_APP_PASSWORD` | Notarize the signed app and staple the ticket. |
| `WINDOWS_CERTIFICATE`, `WINDOWS_CERTIFICATE_PASSWORD` | A base64 `.pfx` and its password: Authenticode signature with a timestamp. |

The three OAuth values are written by `scripts/build_designer.py` as the
`pyzed_oauth_apps` module and bundled **only into the Pyzed Design builds**; they
never go into the repository or the PyPI wheels. Without them, signing in with
GitHub or Google needs the user's own OAuth app (in the provider's settings, or
`PYZED_GITHUB_CLIENT_ID` / `PYZED_GOOGLE_CLIENT_ID` / `PYZED_GOOGLE_CLIENT_SECRET`
in the environment); API keys and the other sign-ins work as usual.

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
