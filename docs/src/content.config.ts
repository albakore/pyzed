import { defineCollection } from 'astro:content';
import { z } from 'astro/zod';
import { docsLoader } from '@astrojs/starlight/loaders';
import { docsSchema } from '@astrojs/starlight/schema';

export const collections = {
	docs: defineCollection({
		loader: docsLoader(),
		schema: docsSchema({
			extend: z.object({
				/**
				 * Shows the page title as a section hero (src/components/PageTitle.astro): an eyebrow with an
				 * icon above the title, and a lead paragraph (`lead`, or else the page description) below it.
				 */
				section: z
					.object({ eyebrow: z.string(), icon: z.string().optional(), lead: z.string().optional() })
					.optional(),
			}),
		}),
	}),
};
