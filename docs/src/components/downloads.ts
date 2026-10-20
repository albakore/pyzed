// The Pyzed Design downloads, attached to every GitHub release (built by scripts/build_designer.py in
// .github/workflows/release.yml). Rename them here only.
export const RELEASES_URL = 'https://github.com/albakore/pyzed/releases';

/** The portable zips: what the app's updater downloads, and the download of releases up to 1.2.0. */
export const DESIGNER_ASSETS = {
	windows: 'pyzed-design-windows-x86_64.zip',
	macos: 'pyzed-design-macos-arm64.zip',
	linux: 'pyzed-design-linux-x86_64.zip',
} as const;

/** The installers: a per-user setup program on Windows and a disk image on macOS (Linux uses install.sh). */
export const DESIGNER_INSTALLERS = {
	windows: 'pyzed-design-windows-x86_64-setup.exe',
	macos: 'pyzed-design-macos-arm64.dmg',
	linux: DESIGNER_ASSETS.linux,
} as const;

/** The last release without installers: the page offers them for newer ones. */
export const INSTALLERS_AFTER = '1.2.0';

/** The Linux installer, served by this site. */
export const INSTALL_SH = 'https://albakore.github.io/pyzed/install.sh';

export type Platform = keyof typeof DESIGNER_ASSETS;

/** Whether ``version`` (``1.3.0``, ``1.3.0-rc.1``...) comes with installers. */
export const hasInstallers = (version: string | undefined) => {
	if (!version) return false;
	const parts = (v: string) => v.split('-')[0].split('.').map((n) => parseInt(n, 10) || 0);
	const [a, b] = [parts(version), parts(INSTALLERS_AFTER)];
	for (let i = 0; i < 3; i++) if ((a[i] ?? 0) !== (b[i] ?? 0)) return (a[i] ?? 0) > (b[i] ?? 0);
	return false;
};

/** Link to a file of the latest stable release (GitHub redirects it to the file). */
export const downloadUrl = (platform: Platform, installers = false) =>
	`${RELEASES_URL}/latest/download/${(installers ? DESIGNER_INSTALLERS : DESIGNER_ASSETS)[platform]}`;
