// Asks GitHub which stable release has each Pyzed Design download and writes
//   src/generated/downloads.json   {platform: {version, file, url, installer}} (null: no release has it)
// so the download page links a file that exists: a release published before its builds are attached,
// or one whose designer build failed, is skipped for the previous one. Runs after sync-changelog.mjs.
// Without network (or rate limited) it falls back to the latest release's links.
import { mkdirSync, writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { DESIGNER_ASSETS, DESIGNER_INSTALLERS, RELEASES_URL, hasInstallers } from '../src/components/downloads.ts';

const here = dirname(fileURLToPath(import.meta.url));
const out = resolve(here, '..', 'src/generated/downloads.json');
const api = 'https://api.github.com/repos/albakore/pyzed/releases?per_page=30';

const fallback = () =>
	Object.fromEntries(
		Object.entries(DESIGNER_INSTALLERS).map(([platform, file]) => [
			platform,
			{ version: null, file, url: `${RELEASES_URL}/latest/download/${file}`, installer: true },
		]),
	);

let downloads;
try {
	const get = (token) =>
		fetch(api, {
			headers: { Accept: 'application/vnd.github+json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
			signal: AbortSignal.timeout(15000),
		});
	let response = await get(process.env.GITHUB_TOKEN);
	if (!response.ok && process.env.GITHUB_TOKEN) response = await get(null); // a token for another site
	if (!response.ok) throw new Error(`GitHub answered ${response.status}`);
	const releases = (await response.json()).filter((r) => !r.draft && !r.prerelease);
	downloads = Object.fromEntries(
		Object.keys(DESIGNER_ASSETS).map((platform) => {
			for (const release of releases) {
				const version = release.tag_name.replace(/^v/, '');
				const names = hasInstallers(version)
					? [DESIGNER_INSTALLERS[platform], DESIGNER_ASSETS[platform]]
					: [DESIGNER_ASSETS[platform]];
				for (const name of names) {
					const asset = release.assets.find((a) => a.name === name);
					if (asset)
						return [
							platform,
							{ version, file: name, url: asset.browser_download_url, installer: name === DESIGNER_INSTALLERS[platform] },
						];
				}
			}
			return [platform, null];
		}),
	);
	console.log(`downloads: ${Object.entries(downloads).map(([p, d]) => `${p} ${d?.version ?? 'none'}`).join(', ')}`);
} catch (error) {
	console.warn(`downloads: could not list the releases (${error.message}); linking the latest release`);
	downloads = fallback();
}

mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, JSON.stringify(downloads, null, '\t') + '\n');
