// Builds the llms.txt family (https://llmstxt.org) and the raw Markdown copy of every page from the
// docs content collection. Used by the endpoints in src/pages (llms*.txt, llms/<section>.txt,
// <page>.md). Every page added to src/content/docs shows up here automatically.
import { readFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { getCollection, type CollectionEntry } from 'astro:content';
import release from '../generated/release.json';

export const SITE = 'https://albakore.github.io/pyzed';
export type Lang = 'en' | 'es';
type Entry = CollectionEntry<'docs'>;

export interface Page {
	/** "library/button" ("" for the home page), without the language prefix. */
	slug: string;
	lang: Lang;
	title: string;
	description: string;
	order: number;
	entry: Entry;
}

/** Section order and names. New folders are added after these, in alphabetical order. */
const SECTIONS: [string, string, string, string][] = [
	// folder, English, Spanish, one-line summary used in llms.txt (English)
	['getting-started', 'Getting started', 'Empezar', 'Install Pyzed and build a first window.'],
	['tutorials', 'Tutorials', 'Tutoriales', 'Complete apps built step by step, sorted into basic, intermediate and advanced.'],
	['guides', 'Guides', 'Guías', 'Layout, architecture, events, animation, async, windows, testing and more.'],
	['animation', 'Animation', 'Animación', 'Animating any widget: presets, keyframes, transitions, timelines like Godot\'s AnimationPlayer and effects.'],
	['why', 'Why Pyzed', 'Por qué Pyzed', 'How Pyzed compares with tkinter, Kivy, PyQt/PySide, Flet and others.'],
	['library', 'Component library', 'Biblioteca de componentes', 'Every Pyzed UI component with usage and API.'],
	['blocks', 'Blocks', 'Bloques', 'Ready-made screens and sections built from components.'],
	['download', 'Pyzed Design download', 'Descargar Pyzed Design', 'The standalone visual designer.'],
	['editor', 'Pyzed Design manual', 'Manual de Pyzed Design', 'Every panel of the visual designer.'],
	['shading', 'Shading', 'Shading', 'GPU shaders: node-based shader graphs (.pzshad), the Shader view and WGSL.'],
	['theming', 'Theming', 'Temas', 'Themes, color tokens, styles, icons and fonts.'],
	['packaging', 'Distribution', 'Distribución', 'Packaging apps for Windows, macOS and Linux with pyzed build.'],
	['showcase', 'Showcase', 'Showcase', 'Demos of effects, shaders and game-style interfaces, with their code.'],
	['games', 'Games', 'Videojuegos', 'Real-time games step by step: Snake, Breakout and Neon Invaders.'],
	['audio', 'Audio', 'Audio', 'Music apps: the modular audio engine (pyzed.audio), knobs, faders, waveforms, spectrum, a VCV Rack-style rack and demos.'],
	['integrations', 'Integrations', 'Integraciones', 'Pyzed as the desktop frontend of FastAPI, Django, SQLAlchemy and more.'],
	['ai', 'AI agents', 'Agentes de IA', 'Building with AI agents: MCP server, llms.txt, the Agent panel and pyzed.agents.'],
	['components', 'Components by category', 'Componentes por categoría', 'Older category pages of the pyzed.ui components.'],
	['reference', 'API reference', 'Referencia de la API', 'Every class, function and parameter.'],
	['examples', 'Examples', 'Ejemplos', 'Example apps in the repository.'],
	['faq', 'FAQ', 'Preguntas frecuentes', 'Short answers to common questions.'],
	['contributing', 'Contributing', 'Contribuir', 'Developing Pyzed itself and its documentation.'],
	['changelog', 'Changelog', 'Novedades', 'Changes in every release.'],
];
/** Sections listed under "## Optional" in llms.txt (an agent can skip them). */
const OPTIONAL = new Set(['components', 'contributing', 'changelog']);
/** Sections in llms-small.txt: what you need to write a Pyzed app, without the long reference pages. */
const SMALL = new Set(['getting-started', 'why', 'tutorials', 'guides', 'theming', 'shading', 'packaging', 'ai', 'faq']);

export function sectionOf(slug: string): string {
	return slug.split('/')[0] ?? '';
}

export function sectionTitle(section: string, lang: Lang): string {
	const known = SECTIONS.find(([s]) => s === section);
	if (known) return lang === 'es' ? known[2] : known[1];
	return section.replace(/-/g, ' ').replace(/^./, (c) => c.toUpperCase());
}

function sectionRank(section: string): number {
	const i = SECTIONS.findIndex(([s]) => s === section);
	return i < 0 ? SECTIONS.length : i;
}

/** Pages whose order comes from the sidebar config instead of their frontmatter. */
const PINNED = ['getting-started/introduction', 'getting-started/installation', 'getting-started/quickstart', 'getting-started/new-project'];

export async function pages(lang: Lang): Promise<Page[]> {
	const entries = await getCollection('docs', (e) => !e.data.draft);
	const out: Page[] = [];
	for (const entry of entries) {
		let id = entry.id === 'index' ? '' : entry.id.replace(/\/index$/, '');
		const isEs = id === 'es' || id.startsWith('es/');
		if ((lang === 'es') !== isEs) continue;
		if (isEs) id = id.slice(3);
		const pinned = PINNED.indexOf(id);
		const order =
			id.split('/').length === 1 || /\/index$/.test(entry.id) ? -1 : pinned >= 0 ? pinned : (entry.data.sidebar?.order ?? 1000);
		out.push({ slug: id, lang, title: entry.data.title, description: entry.data.description ?? '', order, entry });
	}
	return out.sort(
		(a, b) =>
			sectionRank(sectionOf(a.slug)) - sectionRank(sectionOf(b.slug)) ||
			sectionOf(a.slug).localeCompare(sectionOf(b.slug)) ||
			a.order - b.order ||
			a.title.localeCompare(b.title),
	);
}

export function pageUrl(page: Pick<Page, 'slug' | 'lang'>): string {
	return `${SITE}/${page.lang === 'es' ? 'es/' : ''}${page.slug ? `${page.slug}/` : ''}`;
}

/** Where the raw Markdown of a page is served: /pyzed/library/button.md, /pyzed/index.md. */
export function markdownUrl(page: Pick<Page, 'slug' | 'lang'>): string {
	const path = page.slug || 'index';
	return `${SITE}/${page.lang === 'es' ? 'es/' : ''}${path}.md`;
}

// ------------------------------------------------------------------------------- MDX -> Markdown

function attr(tag: string, name: string): string | undefined {
	const m = tag.match(new RegExp(`\\b${name}=(?:"([^"]*)"|'([^']*)'|\\{["'\`]([^"'\`]*)["'\`]\\})`));
	return m ? (m[1] ?? m[2] ?? m[3]) : undefined;
}

/** The raw files a page imports with `?raw` (the tutorials' full sources). */
function rawImports(body: string, filePath: string | undefined): Map<string, string> {
	const out = new Map<string, string>();
	if (!filePath) return out;
	const dir = dirname(resolve(process.cwd(), filePath));
	for (const m of body.matchAll(/^import\s+(\w+)\s+from\s+['"]([^'"]+)\?raw['"];?\s*$/gm)) {
		try {
			out.set(m[1], readFileSync(resolve(dir, m[2]), 'utf8').replace(/\s+$/, ''));
		} catch {
			// A missing file only loses the code block.
		}
	}
	return out;
}

/** Turn MDX components into plain Markdown (outside code blocks only). */
function prose(source: string, raws: Map<string, string>): string {
	// Inline code is kept as written.
	const spans: string[] = [];
	const text = source.replace(/`[^`\n]+`/g, (m) => `\u0000${spans.push(m) - 1}\u0000`);
	return (
		text
			// ESM imports/exports and MDX comments.
			.replace(/^(import|export)\s[^\n]*$/gm, '')
			.replace(/\{\/\*[\s\S]*?\*\/\}/g, '')
			// <Code code={x} lang="py" title="file.py" />: the imported file as a code block.
			.replace(/<Code\b([^>]*?)\/>/g, (_, attrs: string) => {
				const name = attrs.match(/code=\{(\w+)\}/)?.[1];
				const code = name ? raws.get(name) : undefined;
				if (!code) return '';
				const title = attr(attrs, 'title');
				const lang = attr(attrs, 'lang') ?? '';
				return `${title ? `\`${title}\`:\n\n` : ''}\`\`\`${lang}\n${code}\n\`\`\``;
			})
			// <LinkCard title="" description="" href="" />: a list item.
			.replace(/<LinkCard\b([\s\S]*?)\/>/g, (_, attrs: string) => {
				const title = attr(attrs, 'title') ?? '';
				const href = attr(attrs, 'href') ?? '';
				const desc = attr(attrs, 'description');
				return `- [${title}](${href})${desc ? `: ${desc}` : ''}`;
			})
			// Any other self-closing component (previews, screenshots, widgets) carries no text.
			.replace(/<[A-Z][\w.]*\b[^>]*?\/>/g, '')
			// Opening tags: keep a title or label as text.
			.replace(/<([A-Z][\w.]*)\b([^>]*)>/g, (_, name: string, attrs: string) => {
				const title = attr(attrs, 'title') ?? attr(attrs, 'label');
				if (name === 'Aside') {
					const type = attr(attrs, 'type') ?? 'note';
					return `\n**${title ?? type.charAt(0).toUpperCase() + type.slice(1)}:**\n`;
				}
				if (name === 'TabItem') return title ? `\n**${title}:**\n` : '';
				if (title && /Feature|Section/.test(name)) return `\n## ${title}\n`;
				return title ? `\n**${title}**\n` : '';
			})
			.replace(/<\/[A-Z][\w.]*>/g, '')
			// Images point at build assets; keep their description only.
			.replace(/!\[([^\]]*)\]\([^)]*\)/g, (_, alt: string) => (alt ? `(Image: ${alt})` : ''))
			// Site links become absolute so the text works anywhere.
			.replace(/\]\(\/pyzed\//g, `](${SITE}/`)
			.replace(/href="\/pyzed\//g, `href="${SITE}/`)
			.replace(/\u0000(\d+)\u0000/g, (_, i: string) => spans[Number(i)])
	);
}

/** The page body as clean Markdown: no frontmatter, imports or components, absolute links. */
export function cleanMarkdown(entry: Entry): string {
	const body = (entry.body ?? '').replace(/\r\n/g, '\n');
	const raws = rawImports(body, entry.filePath);
	const isMdx = /\.mdx$/.test(entry.filePath ?? '');
	const out: string[] = [];
	let buffer: string[] = [];
	let fence: { marker: string; indent: string } | null = null;
	const flush = () => {
		if (buffer.length) out.push(prose(buffer.join('\n'), raws));
		buffer = [];
	};
	for (const line of body.split('\n')) {
		const m = line.match(/^(\s*)(`{3,}|~{3,})/);
		if (!fence && m) {
			flush();
			fence = { marker: m[2], indent: m[1] };
			out.push(isMdx ? line.trimStart() : line);
		} else if (fence) {
			if (m && m[2].startsWith(fence.marker) && line.trim() === m[2]) {
				out.push(isMdx ? line.trimStart() : line);
				fence = null;
			} else out.push(isMdx && line.startsWith(fence.indent) ? line.slice(fence.indent.length) : line);
		} else buffer.push(isMdx ? line.replace(/^\t+/, '') : line);
	}
	flush();
	return (
		out
			.join('\n')
			.replace(/[ \t]+$/gm, '')
			// A tab whose content was only a preview leaves its label alone: drop it.
			.replace(/^\*\*[^*\n]+:\*\*\n\s*(?=\*\*[^*\n]+:\*\*\n|(?![\s\S]))/gm, '')
			.replace(/\n{3,}/g, '\n\n')
			.trim()
	);
}

/** One page as a standalone Markdown document. */
export function pageMarkdown(page: Page, level = 1): string {
	const h = '#'.repeat(level);
	const parts = [`${h} ${page.title}`, ''];
	if (page.description) parts.push(`> ${page.description}`, '');
	parts.push(`Source: ${pageUrl(page)}`, '', shiftHeadings(cleanMarkdown(page.entry), level - 1));
	return parts.join('\n').trim() + '\n';
}

function shiftHeadings(md: string, by: number): string {
	if (!by) return md;
	let inFence = false;
	return md
		.split('\n')
		.map((line) => {
			if (/^\s*(```|~~~)/.test(line)) inFence = !inFence;
			if (inFence) return line;
			return line.replace(/^(#{1,5}) /, (_, h: string) => `${'#'.repeat(Math.min(6, h.length + by))} `);
		})
		.join('\n');
}

// ------------------------------------------------------------------------------- llms.txt files

const INTRO = {
	en: {
		summary:
			'Pyzed is an open-source (MIT) Python framework for building native desktop GUIs. Python describes the interface; Iced, a GPU-accelerated GUI toolkit written in Rust, lays it out and draws it. It aims to be a frontend framework for desktop apps (mobile and web later), with 90+ components whose look is inspired by the Zed editor, themes, node-based GPU shaders, packaging for every desktop platform and Pyzed Design, a drag-and-drop visual designer in the spirit of Visual Basic, Qt Designer and Godot.',
		facts: [
			'Install: `pip install pyzed-ui` (or `uv add pyzed-ui`); import it as `import pyzed as pz` and `from pyzed import ui`. Python 3.10+, prebuilt wheels for Windows, macOS and Linux.',
			'Model: an `App` subclass with state, `view()` returning a widget tree and callbacks or `update(message)`, like the Elm architecture. Layout, text, syntax highlighting and drawing run in Rust; the GIL is released while the event loop runs.',
			'A modern alternative to tkinter, Kivy, PyQt/PySide, wxPython, Dear PyGui and Flet for desktop tools, dashboards, editors and IDE-like apps, with themes, animation and effects (glow, bloom, glass, blur).',
			'Pyzed Design is a free standalone visual designer (forms saved as `.pzform` plus a Python file); download it from the GitHub releases.',
			'AI agents: `pyzed mcp` (extra `pyzed-ui[mcp]`) is an MCP server that gives coding agents the exact API, these docs, best practices and screenshots; `pyzed.agents` adds model-powered features to your own apps.',
			'Every page is also available as Markdown at the same URL with `.md` instead of the trailing slash (for example {md}). The whole English documentation is in {full}; a shorter version is in {small}.',
		],
		docs: 'Docs',
		optional: 'Optional',
		version: 'Latest stable release',
	},
	es: {
		summary:
			'Pyzed es un framework de código abierto (MIT) para crear GUIs de escritorio nativas en Python. Python describe la interfaz; Iced, un toolkit de GUI acelerado por GPU escrito en Rust, la organiza y la dibuja. Busca ser un framework de frontend para apps de escritorio (más adelante móvil y web), con más de 90 componentes cuyo aspecto se inspira en el editor Zed, temas, shaders de GPU por nodos, empaquetado para todas las plataformas de escritorio y Pyzed Design, un diseñador visual de arrastrar y soltar al estilo de Visual Basic, Qt Designer y Godot.',
		facts: [
			'Instalación: `pip install pyzed-ui` (o `uv add pyzed-ui`); se importa como `import pyzed as pz` y `from pyzed import ui`. Python 3.10+, wheels precompilados para Windows, macOS y Linux.',
			'Modelo: una subclase de `App` con estado, `view()` que devuelve un árbol de widgets y callbacks o `update(message)`, como la arquitectura Elm. El layout, el texto, el resaltado de sintaxis y el dibujo corren en Rust; el GIL se libera mientras corre el bucle de eventos.',
			'Una alternativa moderna a tkinter, Kivy, PyQt/PySide, wxPython, Dear PyGui y Flet para herramientas de escritorio, paneles, editores y apps tipo IDE, con temas, animaciones y efectos (glow, bloom, glass, desenfoque).',
			'Pyzed Design es un diseñador visual gratuito e independiente (los formularios se guardan como `.pzform` más un archivo de Python); se descarga desde las releases de GitHub.',
			'Agentes de IA: `pyzed mcp` (extra `pyzed-ui[mcp]`) es un servidor MCP que da a los agentes de código la API exacta, esta documentación, buenas prácticas y capturas; `pyzed.agents` añade funciones con modelos a tus propias apps.',
			'Cada página está también en Markdown en la misma URL con `.md` en lugar de la barra final (por ejemplo {md}). Toda la documentación en español está en {full}.',
		],
		docs: 'Documentación',
		optional: 'Opcional',
		version: 'Última versión estable',
	},
};

function line(page: Page): string {
	const desc = page.description.replace(/\s+/g, ' ').trim();
	return `- [${page.title}](${pageUrl(page)})${desc ? `: ${desc}` : ''}`;
}

function bySection(list: Page[]): Map<string, Page[]> {
	const map = new Map<string, Page[]>();
	for (const p of list) {
		if (!p.slug) continue;
		const s = sectionOf(p.slug);
		map.set(s, [...(map.get(s) ?? []), p]);
	}
	return map;
}

export async function llmsTxt(lang: Lang): Promise<string> {
	const t = INTRO[lang];
	const list = await pages(lang);
	const prefix = lang === 'es' ? `${SITE}/es` : SITE;
	const version = release.latestStable?.version;
	const facts = t.facts.map((f) =>
		f
			.replace('{md}', `${prefix}/getting-started/quickstart.md`)
			.replace('{full}', `${prefix}/llms-full.txt`)
			.replace('{small}', `${SITE}/llms-small.txt`),
	);
	const out = [`# Pyzed`, '', `> ${t.summary}`, '', ...facts.map((f) => `- ${f}`)];
	if (version) out.push(`- ${t.version}: ${version} (${SITE}/${lang === 'es' ? 'es/' : ''}changelog/).`);
	out.push(`- GitHub: https://github.com/albakore/pyzed · PyPI: https://pypi.org/project/pyzed-ui/`, '');
	const sections = bySection(list);
	const optional: string[] = [];
	for (const [section, items] of sections) {
		const block = [`## ${sectionTitle(section, lang)}`, '', ...items.map(line), ''];
		if (OPTIONAL.has(section)) optional.push(...block.map((l) => l.replace(/^## /, '### ')));
		else out.push(...block);
	}
	if (optional.length) out.push(`## ${t.optional}`, '', ...optional);
	return out.join('\n').trim() + '\n';
}

/** Several pages concatenated, each with its source URL. */
export async function llmsFull(lang: Lang, keep: (section: string) => boolean = () => true, heading?: string): Promise<string> {
	const list = (await pages(lang)).filter((p) => p.slug && keep(sectionOf(p.slug)));
	const t = INTRO[lang];
	const out = [`# ${heading ?? 'Pyzed'}`, '', `> ${t.summary}`, ''];
	let current = '';
	for (const page of list) {
		const section = sectionOf(page.slug);
		if (section !== current) {
			current = section;
			out.push(`## ${sectionTitle(section, lang)}`, '');
		}
		out.push(pageMarkdown(page, 3), '');
	}
	return out.join('\n').replace(/\n{3,}/g, '\n\n').trim() + '\n';
}

export const llmsSmall = (lang: Lang) => llmsFull(lang, (s) => SMALL.has(s), 'Pyzed (essentials)');

export async function sections(lang: Lang): Promise<string[]> {
	return [...bySection(await pages(lang)).keys()];
}

export const textResponse = (body: string, type = 'text/plain') =>
	new Response(body, { headers: { 'Content-Type': `${type}; charset=utf-8` } });
