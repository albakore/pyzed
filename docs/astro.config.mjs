// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';
import mermaid from 'astro-mermaid';

// Published on GitHub Pages: https://albakore.github.io/pyzed/
// English lives at the root; every other language is a folder in src/content/docs (es/ ...).
/** A sidebar group listing a docs folder, with its Spanish label. */
function group(label, es, directory) {
	return { label, translations: { es }, items: [{ autogenerate: { directory } }] };
}

export default defineConfig({
	site: 'https://albakore.github.io',
	base: '/pyzed',
	// Tutorials import the code in ../examples with `?raw`.
	vite: { server: { fs: { allow: ['..'] } } },
	integrations: [
		// Renders ```mermaid code blocks; must come before Starlight.
		mermaid({ theme: 'default', autoTheme: true }),
		starlight({
			title: 'Pyzed',
			description:
				'Pyzed is an open-source Python framework for native desktop GUIs rendered by Rust (Iced), with Zed-style components and a drag-and-drop visual designer.',
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
						href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap',
					},
				},
			],
			components: { SiteTitle: './src/components/SiteTitle.astro', Footer: './src/components/Footer.astro' },
			expressiveCode: { themes: ['one-dark-pro', 'one-light'] },
			sidebar: [
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
				{ slug: 'download', badge: { text: 'app', variant: 'success' } },
				group('Why Pyzed', 'Por qué Pyzed', 'why'),
				group('Tutorials', 'Tutoriales', 'tutorials'),
				group('Showcase', 'Demos', 'showcase'),
				group('Integrations', 'Integraciones', 'integrations'),
				group('Games', 'Videojuegos', 'games'),
				group('Pyzed Design', 'Pyzed Design', 'editor'),
				group('Guides', 'Guías', 'guides'),
				group('Component library', 'Biblioteca de componentes', 'library'),
				group('Blocks', 'Bloques', 'blocks'),
				group('AI agents', 'Agentes de IA', 'ai'),
				group('Contributing', 'Contribuir', 'contributing'),
				group('API reference', 'Referencia de la API', 'reference'),
				{ slug: 'examples' },
				{ slug: 'faq' },
				{ slug: 'changelog', badge: { text: 'releases', variant: 'tip' } },
			],
		}),
	],
});
