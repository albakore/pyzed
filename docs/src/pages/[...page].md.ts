// Every docs page as raw Markdown next to its HTML: /pyzed/library/button/ -> /pyzed/library/button.md,
// /pyzed/ -> /pyzed/index.md, /pyzed/es/ -> /pyzed/es/index.md. See src/lib/llms.ts.
import type { APIRoute, GetStaticPaths } from 'astro';
import { pageMarkdown, pages, textResponse, type Page } from '../lib/llms';

export const getStaticPaths = (async () => {
	const all = [...(await pages('en')), ...(await pages('es'))];
	return all.map((page) => ({
		params: { page: `${page.lang === 'es' ? 'es/' : ''}${page.slug || 'index'}` },
		props: { page },
	}));
}) satisfies GetStaticPaths;

export const GET: APIRoute = ({ props }) => textResponse(pageMarkdown((props as { page: Page }).page), 'text/markdown');
