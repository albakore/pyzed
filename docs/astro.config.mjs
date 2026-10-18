// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// Publicado en GitHub Pages: https://albakore.github.io/pyzed/
export default defineConfig({
	site: 'https://albakore.github.io',
	base: '/pyzed',
	// Los tutoriales importan el código de ../examples con `?raw`.
	vite: { server: { fs: { allow: ['..'] } } },
	integrations: [
		starlight({
			title: 'Pyzed',
			description:
				'Interfaces modernas y rápidas en Python, renderizadas por Iced (Rust), con componentes inspirados en Zed.',
			logo: { src: './src/assets/logo.svg', replacesTitle: false },
			favicon: '/favicon.svg',
			defaultLocale: 'root',
			locales: { root: { label: 'Español', lang: 'es' } },
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
					label: 'Empezar',
					items: [
						{ label: 'Introducción', slug: 'getting-started/introduction' },
						{ label: 'Instalación', slug: 'getting-started/installation' },
						{ label: 'Inicio rápido', slug: 'getting-started/quickstart' },
						{ label: 'Crear un proyecto', slug: 'getting-started/new-project' },
					],
				},
				{ label: 'Tutoriales', items: [{ autogenerate: { directory: 'tutorials' } }] },
				{ label: 'Guías', items: [{ autogenerate: { directory: 'guides' } }] },
				{ label: 'Componentes', items: [{ autogenerate: { directory: 'components' } }] },
				{ label: 'Referencia de la API', items: [{ autogenerate: { directory: 'reference' } }] },
				{ label: 'Ejemplos', slug: 'examples' },
				{ label: 'Novedades', slug: 'changelog', badge: { text: 'releases', variant: 'tip' } },
			],
		}),
	],
});
