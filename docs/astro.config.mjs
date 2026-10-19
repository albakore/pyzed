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
				'Fast, modern desktop UIs in Python, rendered by Iced (Rust), with components inspired by the Zed editor.',
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
			head: [
				{ tag: 'link', attrs: { rel: 'preconnect', href: 'https://fonts.googleapis.com' } },
				{
					tag: 'link',
					attrs: {
						rel: 'stylesheet',
						href: 'https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap',
					},
				},
			],
			components: { SiteTitle: './src/components/SiteTitle.astro' },
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
				group('Tutorials', 'Tutoriales', 'tutorials'),
				group('Pyzed Design', 'Pyzed Design', 'editor'),
				group('Guides', 'Guías', 'guides'),
				group('Component library', 'Biblioteca de componentes', 'library'),
				group('Contributing', 'Contribuir', 'contributing'),
				group('API reference', 'Referencia de la API', 'reference'),
				{ slug: 'examples' },
				{ slug: 'changelog', badge: { text: 'releases', variant: 'tip' } },
			],
		}),
	],
});
