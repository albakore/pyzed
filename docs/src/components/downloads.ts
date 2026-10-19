// The Pyzed Design downloads: one zip per platform, attached to every GitHub release
// (built by scripts/build_designer.py in .github/workflows/release.yml). Rename them here only.
export const RELEASES_URL = 'https://github.com/albakore/pyzed/releases';

export const DESIGNER_ASSETS = {
	windows: 'pyzed-design-windows-x86_64.zip',
	macos: 'pyzed-design-macos-arm64.zip',
	linux: 'pyzed-design-linux-x86_64.zip',
} as const;

export type Platform = keyof typeof DESIGNER_ASSETS;

/** Link to the asset of the latest stable release (GitHub redirects it to the file). */
export const downloadUrl = (platform: Platform) => `${RELEASES_URL}/latest/download/${DESIGNER_ASSETS[platform]}`;
