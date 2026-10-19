// /pyzed/llms/<section>.txt: one documentation section (guides, library, editor...) as one file.
import type { APIRoute, GetStaticPaths } from 'astro';
import { llmsFull, sectionTitle, sections, textResponse } from '../../lib/llms';

export const getStaticPaths = (async () =>
	(await sections('en')).map((section) => ({ params: { section } }))) satisfies GetStaticPaths;

export const GET: APIRoute = async ({ params }) => {
	const section = params.section!;
	return textResponse(await llmsFull('en', (s) => s === section, `Pyzed: ${sectionTitle(section, 'en')}`));
};
