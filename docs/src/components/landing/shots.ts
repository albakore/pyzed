// Screenshots used by the landing page, looked up by name so both languages share them.
// "designer" -> docs/screenshots/designer.png; "tutorials/multi-window" -> src/assets/tutorials/multi-window.png
import type { ImageMetadata } from 'astro';

type Module = { default: ImageMetadata };
const screenshots = import.meta.glob<Module>('../../../screenshots/*.png', { eager: true });
const assets = import.meta.glob<Module>('../../assets/**/*.png', { eager: true });

export function shot(name: string): ImageMetadata {
	const found = screenshots[`../../../screenshots/${name}.png`] ?? assets[`../../assets/${name}.png`];
	if (!found) throw new Error(`Unknown screenshot: ${name}`);
	return found.default;
}
