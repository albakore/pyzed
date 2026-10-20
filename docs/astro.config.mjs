// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';
import starlightSidebarTopics from 'starlight-sidebar-topics';

// Published on GitHub Pages: https://albakore.github.io/pyzed/
// English lives at the root; every other language is a folder in src/content/docs (es/ ...).
/** A sidebar group listing a docs folder, with its Spanish label. */
function group(label, es, directory, extra = {}) {
	return { label, translations: { es }, items: [{ autogenerate: { directory } }], ...extra };
}

/**
 * The top-level sections: each one is a link in the header navbar (src/components/Header.astro)
 * and has its own sidebar. A page belongs to the section whose sidebar lists it.
 */
const topics = [
	{
		id: 'learn',
		label: { en: 'Learn', es: 'Aprender' },
		link: '/getting-started/introduction/',
		icon: 'open-book',
		items: [
			{
				label: 'Start here',
				translations: { es: 'Empezar' },
				items: [
					{ slug: 'getting-started/introduction' },
					{ slug: 'getting-started/installation' },
					{ slug: 'getting-started/quickstart' },
					{ slug: 'getting-started/new-project' },
				],
			},
			{
				label: 'Tutorials',
				translations: { es: 'Tutoriales' },
				items: [
					{ slug: 'tutorials' },
					group('Basic', 'Básicos', 'tutorials/basic'),
					group('Intermediate', 'Intermedios', 'tutorials/intermediate'),
					group('Advanced', 'Avanzados', 'tutorials/advanced'),
				],
			},
			group('Guides', 'Guías', 'guides'),
			group('Why Pyzed', 'Por qué Pyzed', 'why', { collapsed: true }),
			{ slug: 'examples' },
			{ slug: 'faq' },
		],
	},
	{
		id: 'library',
		label: { en: 'Library', es: 'Biblioteca' },
		link: '/library/',
		icon: 'puzzle',
		items: [group('Components', 'Componentes', 'library'), group('Blocks', 'Bloques', 'blocks')],
	},
	{
		id: 'designer',
		label: { en: 'Designer', es: 'Diseñador' },
		link: '/editor/',
		icon: 'pencil',
		items: [
			{
				label: 'Start',
				translations: { es: 'Empezar' },
				items: [
					{ slug: 'editor' },
					{ slug: 'download', badge: { text: 'app', variant: 'success' } },
					{ slug: 'editor/interface' },
					{ slug: 'editor/examples' },
					{ slug: 'editor/projects' },
				],
			},
			{
				label: 'Views',
				translations: { es: 'Vistas' },
				items: [
					{ slug: 'editor/views' },
					{ slug: 'editor/form-view' },
					{ slug: 'editor/component-designer' },
					{ slug: 'editor/shader-view' },
					{ slug: 'editor/code-editor' },
				],
			},
			{
				label: 'Designing forms',
				translations: { es: 'Diseñar formularios' },
				items: [
					{ slug: 'editor/toolbox-and-canvas' },
					{ slug: 'editor/properties' },
					{ slug: 'editor/layouts' },
					{ slug: 'editor/styles-and-themes' },
					{ slug: 'editor/animations-and-effects' },
					{ slug: 'editor/events' },
					{ slug: 'editor/non-visual-components' },
					{ slug: 'editor/data-binding' },
				],
			},
			{
				label: 'Run, files and AI',
				translations: { es: 'Ejecutar, archivos e IA' },
				items: [
					{ slug: 'editor/console-and-running' },
					{ slug: 'editor/files-and-scripting' },
					{ slug: 'editor/ai-agents' },
				],
			},
			{
				label: 'Reference',
				translations: { es: 'Referencia' },
				items: [
					{ slug: 'editor/menus-and-commands' },
					{ slug: 'editor/keyboard-shortcuts' },
					{ slug: 'editor/keymap' },
					{ slug: 'editor/settings' },
					{ slug: 'editor/reference' },
					{ slug: 'editor/tips-and-tricks' },
				],
			},
		],
	},
	{
		id: 'shading',
		label: { en: 'Shading', es: 'Shading' },
		link: '/shading/',
		icon: 'star',
		items: [
			{ slug: 'shading' },
			{ slug: 'shading/getting-started' },
			{ slug: 'shading/shader-designer' },
			{ slug: 'shading/recipes' },
			group('Node catalog', 'Catálogo de nodos', 'shading/nodes'),
			{
				label: 'In code',
				translations: { es: 'En código' },
				items: [{ slug: 'shading/shader-graphs' }, { slug: 'shading/shaders' }],
			},
		],
	},
	{
		id: 'theming',
		label: { en: 'Theming', es: 'Temas' },
		link: '/theming/',
		icon: 'moon',
		items: [{ autogenerate: { directory: 'theming' } }],
	},
	{
		id: 'distribute',
		label: { en: 'Distribute', es: 'Distribuir' },
		link: '/packaging/',
		icon: 'rocket',
		items: [{ autogenerate: { directory: 'packaging' } }],
	},
	{
		id: 'showcase',
		label: { en: 'Showcase', es: 'Showcase' },
		link: '/showcase/',
		icon: 'laptop',
		items: [group('Showcase', 'Showcase', 'showcase'), group('Games', 'Videojuegos', 'games')],
	},
	{
		id: 'audio',
		label: { en: 'Audio', es: 'Audio' },
		link: '/audio/engine/getting-started/',
		icon: 'star',
		items: [group('Engine', 'Motor', 'audio/engine')],
	},
	{
		id: 'integrations',
		label: { en: 'Integrations', es: 'Integraciones' },
		link: '/integrations/overview/',
		icon: 'link',
		items: [{ autogenerate: { directory: 'integrations' } }],
	},
	{
		id: 'ai',
		label: { en: 'AI', es: 'IA' },
		link: '/ai/',
		icon: 'comment-alt',
		items: [{ autogenerate: { directory: 'ai' } }],
	},
	{
		id: 'reference',
		label: { en: 'Reference', es: 'Referencia' },
		link: '/reference/',
		icon: 'list-format',
		items: [
			group('API reference', 'Referencia de la API', 'reference'),
			{ slug: 'changelog', badge: { text: 'releases', variant: 'tip' } },
			group('Contributing', 'Contribuir', 'contributing', { collapsed: true }),
		],
	},
];

// Pages that moved to their own section: old URLs keep working (see contributing/docs.md).
const MOVED = {
	'guides/shaders': 'shading/shaders',
	'guides/shader-graphs': 'shading/shader-graphs',
	'editor/shader-designer': 'shading/shader-designer',
	'guides/theming': 'theming/themes',
	'guides/styles': 'theming/styles',
	'guides/icons-fonts': 'theming/icons-fonts',
	'guides/packaging': 'packaging/build',
	'tutorials/step-by-step': 'tutorials/basic/step-by-step',
	'tutorials/todo-app': 'tutorials/basic/todo-app',
	'tutorials/background-tasks': 'tutorials/intermediate/background-tasks',
	'tutorials/zed-like-editor': 'tutorials/advanced/code-editor',
};
const redirects = Object.fromEntries(
	Object.entries(MOVED).flatMap(([from, to]) => [
		[`/${from}`, `/pyzed/${to}/`],
		[`/es/${from}`, `/pyzed/es/${to}/`],
	]),
);

export default defineConfig({
	site: 'https://albakore.github.io',
	base: '/pyzed',
	redirects,
	// Tutorials import the code in ../examples with `?raw`.
	vite: { server: { fs: { allow: ['..'] } } },
	integrations: [
		// Renders ```mermaid code blocks; must come before Starlight.
		mermaid({ theme: 'default', autoTheme: true }),
		starlight({
			title: 'Pyzed',
			description:
				'Pyzed is an open-source Python frontend framework for native desktop apps rendered by Rust (Iced), with 90+ components, a drag-and-drop visual designer, themes and GPU shaders.',
			logo: { src: './src/assets/logo.svg', replacesTitle: false },
			favicon: '/favicon.svg',
			defaultLocale: 'root',
			locales: {
				root: { label: 'English', lang: 'en' },
				es: { label: 'Español', lang: 'es' },
			},
			social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/albakore/pyzed' }],
			editLink: { baseUrl: 'https://github.com/albakore/pyzed/edit/main/docs/' },
			lastUpdated: true,
			customCss: ['./src/styles/custom.css'],
			// SEO/GEO: per-page titles, descriptions, social cards, hreflang and JSON-LD (see contributing/seo.md).
			routeMiddleware: './src/routeData.ts',
			head: [
				{ tag: 'meta', attrs: { name: 'author', content: 'albakore and the Pyzed contributors' } },
				{ tag: 'meta', attrs: { name: 'robots', content: 'index, follow, max-image-preview:large, max-snippet:-1' } },
				{ tag: 'meta', attrs: { name: 'theme-color', content: '#181a1f', media: '(prefers-color-scheme: dark)' } },
				{ tag: 'meta', attrs: { name: 'theme-color', content: '#ffffff', media: '(prefers-color-scheme: light)' } },
				{ tag: 'meta', attrs: { name: 'application-name', content: 'Pyzed' } },
				{ tag: 'link', attrs: { rel: 'manifest', href: '/pyzed/manifest.webmanifest' } },
				{ tag: 'link', attrs: { rel: 'apple-touch-icon', href: '/pyzed/apple-touch-icon.png' } },
				{ tag: 'link', attrs: { rel: 'icon', type: 'image/png', sizes: '192x192', href: '/pyzed/icon-192.png' } },
				// For AI assistants and answer engines: https://llmstxt.org
				{ tag: 'link', attrs: { rel: 'alternate', type: 'text/plain', title: 'llms.txt', href: '/pyzed/llms.txt' } },
				{ tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
				{ tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: true } },
				{
					tag: 'link',
					attrs: {
						rel: 'stylesheet',
						href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap',
					},
				},
			],
			components: {
				Header: './src/components/Header.astro',
				PageTitle: './src/components/PageTitle.astro',
				SiteTitle: './src/components/SiteTitle.astro',
				Footer: './src/components/Footer.astro',
			},
			plugins: [
				starlightSidebarTopics(topics, {
					// The older category pages of pyzed.ui (not in any sidebar) belong to the library.
					topics: { library: ['/components/**', '/es/components/**'] },
				}),
			],
			expressiveCode: {
				themes: ['one-dark-pro', 'one-light'],
				styleOverrides: {
					borderRadius: '0.7rem',
					borderColor: 'var(--pz-frame-border)',
					codeFontFamily: 'var(--__sl-font-mono)',
					codePaddingBlock: '1rem',
				},
			},
		}),
	],
});
