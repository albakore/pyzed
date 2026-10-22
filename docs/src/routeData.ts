// SEO and GEO for every page: titles, descriptions, Open Graph / Twitter cards, hreflang only for
// pages that really exist in each language, and JSON-LD structured data (WebSite, Organization,
// SoftwareApplication, SoftwareSourceCode, TechArticle, BreadcrumbList, FAQPage).
// Registered in astro.config.mjs as Starlight's `routeMiddleware`. See contributing/seo.md.
import { defineRouteMiddleware } from '@astrojs/starlight/route-data';
import { getCollection } from 'astro:content';
import release from './generated/release.json';

const SITE = 'https://albakore.github.io';
const BASE = '/pyzed';
const HOME = `${SITE}${BASE}/`;
const REPO = 'https://github.com/albakore/pyzed';
const VERSION = release.latestStable?.version ?? release.latest?.version;

type Lang = 'en' | 'es';

const TEXT = {
	en: {
		homeTitle: 'Pyzed - Native Python desktop GUI framework with a visual designer',
		shortSuffix: 'Pyzed, Python desktop GUI',
		librarySuffix: 'Python GUI component | Pyzed',
		reference: 'API reference',
		descSuffix: 'Pyzed: native Python desktop GUIs rendered in Rust.',
		ogLocale: 'en_US',
		home: 'Pyzed',
		keywords:
			'pyzed-ui, Python GUI, Python desktop GUI, desktop apps in Python, native GUI, Rust, Iced, tkinter alternative, Kivy alternative, PyQt alternative, Flet alternative, visual designer, GUI builder, Python frontend framework, shaders, cross-platform, Windows, macOS, Linux',
		siteDescription:
			'Pyzed is an open-source Python frontend framework for native desktop apps rendered by Iced (Rust), with 90+ components, themes, node-based GPU shaders and Pyzed Design, a drag-and-drop visual designer.',
		designDescription:
			'Pyzed Design is the free visual designer for Pyzed: draw desktop windows and components by drag and drop, wire their events to Python and run them.',
		imageAlt: 'Pyzed - native desktop apps in pure Python, with the Pyzed Design visual designer',
	},
	es: {
		homeTitle: 'Pyzed - Framework de GUI de escritorio nativa para Python con diseñador visual',
		shortSuffix: 'Pyzed, GUI de escritorio en Python',
		librarySuffix: 'componente de GUI para Python | Pyzed',
		reference: 'Referencia de la API',
		descSuffix: 'Pyzed: GUIs de escritorio nativas en Python renderizadas en Rust.',
		ogLocale: 'es_ES',
		home: 'Pyzed',
		keywords:
			'pyzed-ui, GUI en Python, interfaces de escritorio en Python, apps de escritorio con Python, GUI nativa, Rust, Iced, alternativa a tkinter, alternativa a Kivy, alternativa a PyQt, alternativa a Flet, diseñador visual, constructor de interfaces, framework de frontend en Python, shaders, multiplataforma, Windows, macOS, Linux',
		siteDescription:
			'Pyzed es un framework de frontend de código abierto para apps de escritorio nativas en Python renderizadas por Iced (Rust), con más de 90 componentes, temas, shaders de GPU por nodos y el diseñador visual Pyzed Design.',
		designDescription:
			'Pyzed Design es el diseñador visual gratuito de Pyzed: dibuja ventanas y componentes arrastrando y soltando, conecta sus eventos a Python y ejecútalos.',
		imageAlt: 'Pyzed - apps de escritorio nativas en Python puro, con el diseñador visual Pyzed Design',
	},
} as const;

/** Which social card (docs/public/og/<card>.png, made by scripts/gen_og.py) a page uses. */
function cardFor(slug: string): string {
	const [section = ''] = slug.split('/');
	if (['ai'].includes(section) || ['guides/agents', 'guides/mcp', 'editor/ai-agents'].includes(slug)) return 'ai';
	if (section === 'why' || slug === 'faq') return 'why';
	if (section === 'editor' || section === 'download' || slug.endsWith('designer')) return 'design';
	if (['library', 'components', 'blocks'].includes(section)) return 'library';
	if (section === 'tutorials' || section === 'examples') return 'tutorials';
	if (['guides', 'reference', 'contributing', 'shading', 'theming', 'packaging'].includes(section)) return 'guides';
	return 'default';
}

/** "es/library/button" -> { lang: "es", slug: "library/button" }. */
function split(id: string): { lang: Lang; slug: string } {
	if (id === 'es' || id.startsWith('es/')) return { lang: 'es', slug: id.slice(3) };
	return { lang: 'en', slug: id };
}

const pageUrl = (lang: Lang, slug: string) =>
	`${SITE}${BASE}/${lang === 'es' ? 'es/' : ''}${slug ? `${slug}/` : ''}`;

let ids: Promise<Set<string>> | undefined;
/** Every page id in the docs collection ("library/button", "es/library/button", "" for home). */
function pageIds(): Promise<Set<string>> {
	ids ??= getCollection('docs').then(
		(entries) => new Set(entries.map((e) => (e.id === 'index' ? '' : e.id.replace(/\/index$/, '')))),
	);
	return ids;
}

type Head = { tag: string; attrs?: Record<string, string | boolean | undefined>; content?: string }[];

function setMeta(head: Head, key: 'name' | 'property', name: string, content: string) {
	const found = head.find((t) => t.tag === 'meta' && t.attrs?.[key] === name);
	if (found) found.attrs!.content = content;
	else head.push({ tag: 'meta', attrs: { [key]: name, content } });
}

/** Markdown to plain text, for JSON-LD answers. */
function plain(md: string): string {
	return md
		.replace(/```[\s\S]*?```/g, '')
		.replace(/!\[[^\]]*\]\([^)]*\)/g, '')
		.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1')
		.replace(/[*_`]/g, '')
		.replace(/^\s*[-*]\s+/gm, '- ')
		.replace(/\n{2,}/g, '\n')
		.replace(/\n(?!- )/g, ' ')
		.trim();
}

/** "## Question" + answer paragraphs from a FAQ page. */
function faqItems(body: string) {
	const items: { q: string; a: string }[] = [];
	const parts = body.split(/^## +/m).slice(1);
	for (const part of parts) {
		const nl = part.indexOf('\n');
		const q = part.slice(0, nl).trim();
		const a = plain(part.slice(nl + 1).split(/^#{1,2} /m)[0]);
		if (q.endsWith('?') && a) items.push({ q, a });
	}
	return items;
}

type SidebarEntry = { type: 'link' | 'group'; label: string; href?: string; isCurrent?: boolean; entries?: SidebarEntry[] };

/** The sidebar groups (with the first link of each) that contain the current page. */
function trail(entries: SidebarEntry[], path: { label: string; href?: string }[] = []): { label: string; href?: string }[] | null {
	for (const e of entries) {
		if (e.type === 'link' && e.isCurrent) return path;
		if (e.type === 'group' && e.entries) {
			const first = e.entries.find((x) => x.type === 'link');
			const found = trail(e.entries, [...path, { label: e.label, href: first?.href }]);
			if (found) return found;
		}
	}
	return null;
}

/** Every link of a sidebar, nested groups included. */
function hrefs(entries: SidebarEntry[], out = new Set<string>()): Set<string> {
	for (const e of entries) {
		if (e.type === 'link' && e.href) out.add(e.href);
		if (e.entries) hrefs(e.entries, out);
	}
	return out;
}

export const onRequest = defineRouteMiddleware(async (context) => {
	const route = context.locals.starlightRoute;
	// "Previous" and "Next" stay inside the current section (the sidebar of its topic).
	if (route.hasSidebar && context.locals.starlightSidebarTopics?.isPageWithTopic) {
		const links = hrefs((route.sidebar ?? []) as SidebarEntry[]);
		if (route.pagination.prev && !links.has(route.pagination.prev.href)) route.pagination.prev = undefined;
		if (route.pagination.next && !links.has(route.pagination.next.href)) route.pagination.next = undefined;
	}
	const head = route.head as Head;
	const data = route.entry.data;
	const { lang, slug } = split(route.id);
	const t = TEXT[lang];
	const isHome = slug === '';
	const all = await pageIds();
	const exists = (l: Lang) => all.has(l === 'es' ? (slug ? `es/${slug}` : 'es') : slug);
	const url = route.isFallback ? pageUrl('en', slug) : pageUrl(lang, slug);

	// Title: a descriptive one for the home page and component pages, a fuller one for short titles.
	const title = head.find((x) => x.tag === 'title');
	if (title) {
		if (isHome) title.content = t.homeTitle;
		else if (slug.startsWith('library/') && slug !== 'library') title.content = `${data.title} - ${t.librarySuffix}`;
		else if (slug.startsWith('editor/')) title.content = `${data.title} - Pyzed Design`;
		// The older category pages ("Forms") would share a title with Showcase pages.
		else if (slug.startsWith('components/'))
			title.content = `${data.title} - ${lang === 'es' ? 'componentes de GUI para Python' : 'Python GUI components'} | Pyzed`;
		else if (slug.startsWith('reference/')) title.content = `${data.title} - ${t.reference} | Pyzed`;
		else if (`${data.title} | Pyzed`.length <= 32) title.content = `${data.title} | ${t.shortSuffix}`;
	}

	// Description: never missing, never too thin.
	let description = (data.description ?? '').trim();
	if (description.length < 90) description = description ? `${description.replace(/\.?$/, '.')} ${t.descSuffix}` : t.siteDescription;
	setMeta(head, 'name', 'description', description);
	setMeta(head, 'property', 'og:description', description);

	// A fallback page (an untranslated page shown in Spanish) points search engines at the original.
	const canonical = head.find((x) => x.tag === 'link' && x.attrs?.rel === 'canonical');
	if (canonical) canonical.attrs!.href = url;
	setMeta(head, 'property', 'og:url', url);
	if (route.isFallback) setMeta(head, 'name', 'robots', 'noindex, follow');

	// hreflang only for languages the page is really translated to.
	for (let i = head.length - 1; i >= 0; i--) {
		const a = head[i].attrs;
		if (head[i].tag === 'link' && a?.rel === 'alternate' && (a.hreflang === 'es' || a.hreflang === 'en') && !exists(a.hreflang as Lang)) {
			head.splice(i, 1);
		}
	}

	// Open Graph and Twitter.
	const card = cardFor(slug);
	const image = `${SITE}${BASE}/og/${card}${lang === 'es' ? '.es' : ''}.png`;
	const ogTitle = isHome ? t.homeTitle : data.title;
	setMeta(head, 'property', 'og:title', ogTitle);
	setMeta(head, 'property', 'og:type', isHome ? 'website' : 'article');
	setMeta(head, 'property', 'og:locale', t.ogLocale);
	const other: Lang = lang === 'es' ? 'en' : 'es';
	if (exists(other)) setMeta(head, 'property', 'og:locale:alternate', TEXT[other].ogLocale);
	setMeta(head, 'property', 'og:image', image);
	setMeta(head, 'property', 'og:image:width', '1200');
	setMeta(head, 'property', 'og:image:height', '630');
	setMeta(head, 'property', 'og:image:type', 'image/png');
	setMeta(head, 'property', 'og:image:alt', t.imageAlt);
	setMeta(head, 'name', 'twitter:title', ogTitle);
	setMeta(head, 'name', 'twitter:description', description);
	setMeta(head, 'name', 'twitter:image', image);
	setMeta(head, 'name', 'twitter:image:alt', t.imageAlt);
	setMeta(head, 'name', 'keywords', t.keywords);
	// The same page as raw Markdown, for AI assistants (src/pages/[...page].md.ts).
	if (!route.isFallback) {
		const md = `${SITE}${BASE}/${lang === 'es' ? 'es/' : ''}${slug || 'index'}.md`;
		head.push({ tag: 'link', attrs: { rel: 'alternate', type: 'text/markdown', href: md, title: 'Markdown' } });
	}
	if (route.lastUpdated instanceof Date && !isHome) {
		setMeta(head, 'property', 'article:modified_time', route.lastUpdated.toISOString());
	}

	// JSON-LD.
	const org = {
		'@type': 'Organization',
		'@id': `${HOME}#organization`,
		name: 'Pyzed',
		url: HOME,
		logo: { '@type': 'ImageObject', url: `${SITE}${BASE}/icon-512.png`, width: 512, height: 512 },
		sameAs: [REPO, 'https://pypi.org/project/pyzed-ui/'],
	};
	const website = {
		'@type': 'WebSite',
		'@id': `${HOME}#website`,
		url: HOME,
		name: 'Pyzed',
		description: TEXT.en.siteDescription,
		inLanguage: ['en', 'es'],
		publisher: { '@id': `${HOME}#organization` },
	};
	const library = {
		'@type': 'SoftwareSourceCode',
		'@id': `${HOME}#library`,
		name: 'Pyzed',
		alternateName: 'pyzed-ui',
		description: t.siteDescription,
		url: HOME,
		codeRepository: REPO,
		programmingLanguage: ['Python', 'Rust'],
		runtimePlatform: 'CPython 3.10+',
		license: 'https://opensource.org/licenses/MIT',
		version: VERSION,
		author: { '@id': `${HOME}#organization` },
		targetProduct: { '@id': `${HOME}#designer` },
	};
	const designer = {
		'@type': 'SoftwareApplication',
		'@id': `${HOME}#designer`,
		name: 'Pyzed Design',
		description: t.designDescription,
		url: pageUrl(lang, 'download'),
		applicationCategory: 'DeveloperApplication',
		applicationSubCategory: 'GUI builder',
		operatingSystem: 'Windows, macOS, Linux',
		softwareVersion: VERSION,
		downloadUrl: `${REPO}/releases/latest`,
		releaseNotes: pageUrl(lang, 'changelog'),
		screenshot: `${SITE}${BASE}/og/design.png`,
		license: 'https://opensource.org/licenses/MIT',
		isAccessibleForFree: true,
		offers: { '@type': 'Offer', price: '0', priceCurrency: 'USD' },
		publisher: { '@id': `${HOME}#organization` },
	};
	const graph: Record<string, unknown>[] = [org, website];

	if (isHome) graph.push(library, designer);
	else {
		if (slug === 'download') graph.push(designer);
		if (slug === 'getting-started/introduction') graph.push(library);

		const crumbs = trail((route.sidebar ?? []) as SidebarEntry[]) ?? [];
		const items = [{ name: t.home, item: pageUrl(lang, '') }];
		// The top-level section of the header navbar (starlight-sidebar-topics), when it is not this page.
		const topic = context.locals.starlightSidebarTopics?.topics.find((x) => x.isCurrent);
		if (topic) {
			const href = new URL(topic.link, SITE).href;
			if (href !== url) items.push({ name: topic.label, item: href });
		}
		crumbs.forEach((c, i) => {
			// The top group links to its section's overview page when there is one (/library/, /editor/...).
			const section = slug.split('/')[0];
			const overview = i === 0 && section !== slug && exists(lang) && all.has(lang === 'es' ? `es/${section}` : section);
			const href = overview ? pageUrl(lang, section) : c.href ? new URL(c.href, SITE).href : undefined;
			if (href && href !== url && !items.some((x) => x.item === href)) items.push({ name: c.label, item: href });
		});
		items.push({ name: data.title, item: url });
		graph.push({
			'@type': 'BreadcrumbList',
			itemListElement: items.map((x, i) => ({ '@type': 'ListItem', position: i + 1, name: x.name, item: x.item })),
		});

		const faq = slug === 'faq' ? faqItems(route.entry.body ?? '') : [];
		if (faq.length) {
			graph.push({
				'@type': 'FAQPage',
				'@id': `${url}#faq`,
				url,
				inLanguage: lang,
				mainEntity: faq.map(({ q, a }) => ({
					'@type': 'Question',
					name: q,
					acceptedAnswer: { '@type': 'Answer', text: a },
				})),
			});
		} else {
			graph.push({
				'@type': 'TechArticle',
				'@id': `${url}#article`,
				headline: data.title,
				description,
				url,
				mainEntityOfPage: url,
				inLanguage: lang,
				image,
				...(route.lastUpdated instanceof Date ? { dateModified: route.lastUpdated.toISOString() } : {}),
				author: { '@id': `${HOME}#organization` },
				publisher: { '@id': `${HOME}#organization` },
				isPartOf: { '@id': `${HOME}#website` },
				about: { '@id': `${HOME}#library` },
				proficiencyLevel:
					slug === 'tutorials' || slug.startsWith('tutorials/basic/') || slug.startsWith('getting-started/') ? 'Beginner' : 'Expert',
			});
		}
	}

	head.push({
		tag: 'script',
		attrs: { type: 'application/ld+json' },
		content: JSON.stringify({ '@context': 'https://schema.org', '@graph': graph }).replace(/</g, '\\u003c'),
	});
});
