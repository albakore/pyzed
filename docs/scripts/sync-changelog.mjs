// Lee ../CHANGELOG.md y genera:
//   src/content/docs/changelog.md   la página "Novedades" del sitio
//   src/generated/release.json      la última versión estable (la usa la cabecera y la portada)
// Se ejecuta antes de `astro dev` y `astro build` (ver package.json).
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const root = resolve(here, '..');
const source = resolve(root, '..', 'CHANGELOG.md');

const text = readFileSync(source, 'utf8').replace(/\r\n/g, '\n');

// Encabezados aceptados: "## [0.2.0] - 2026-11-02", "## 0.2.0 (2026-11-02)", "## v0.2.0".
const HEADING = /^## +\[?v?(\d[^\]\s(]*)\]?(?:[^\d\n]*(\d{4}-\d{2}-\d{2}))?.*$/gm;
const PRERELEASE = /(-|a\d|b\d|rc|dev)/i;

const releases = [];
for (const match of text.matchAll(HEADING)) {
	const version = match[1];
	releases.push({ version, date: match[2] ?? null, stable: !PRERELEASE.test(version), index: match.index });
}
const latestStable = releases.find((r) => r.stable) ?? null;
const latest = releases[0] ?? null;

// Cuerpo: se quita el título "# Changelog" y la introducción hasta la primera versión.
const firstSection = text.search(/^## /m);
let body = firstSection >= 0 ? text.slice(firstSection) : '';
// Quita "Sin publicar" si está vacío.
body = body.replace(/^## +\[?(Unreleased|Sin publicar)\]?\s*\n(?=## |\s*$)/im, '');
// Marca la última estable y las preliminares.
body = body.replace(HEADING, (line, version) => {
	if (latestStable && version === latestStable.version) return `${line}\n\n<span class="release-tag stable">Última estable</span>`;
	if (PRERELEASE.test(version)) return `${line}\n\n<span class="release-tag pre">Preliminar</span>`;
	return line;
});

const intro = latestStable
	? `La última versión estable es **${latestStable.version}**${latestStable.date ? ` (${latestStable.date})` : ''}.\n\n` +
		'```bash\npip install --upgrade pyzed-ui==' + latestStable.version + '\n```\n'
	: 'Todavía no hay una versión estable publicada.\n';

const page = `---
title: Novedades
description: Cambios, mejoras, correcciones y breaking changes de cada versión de Pyzed.
editUrl: https://github.com/albakore/pyzed/edit/main/CHANGELOG.md
tableOfContents:
  maxHeadingLevel: 2
---

<!-- Archivo generado por docs/scripts/sync-changelog.mjs a partir de CHANGELOG.md. No lo edites a mano. -->

${intro}
Las notas de cada versión también están en [GitHub Releases](https://github.com/albakore/pyzed/releases).

${body.trim()}
`;

writeFileSync(resolve(root, 'src/content/docs/changelog.md'), page);
mkdirSync(resolve(root, 'src/generated'), { recursive: true });
writeFileSync(
	resolve(root, 'src/generated/release.json'),
	JSON.stringify({ latestStable, latest, releases: releases.map(({ index, ...r }) => r) }, null, '\t') + '\n',
);
console.log(`changelog: ${releases.length} versiones; última estable: ${latestStable?.version ?? 'ninguna'}`);
