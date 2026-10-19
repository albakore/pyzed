// Reads benchmarks/results/<date>.json (copied to src/data/benchmarks.json) for the "Why Pyzed" pages.
import data from '../../data/benchmarks.json';

export type Metric = 'import' | 'first_frame' | 'rss' | 'update' | 'install' | 'loc';
export interface Stat { median: number; min: number; max: number; stdev: number; n: number }
export interface Point { lib: string; name: string; version: string; value: number; min?: number; max?: number; stat?: Stat }

export const isPyzed = (lib: string) => lib === 'pyzed' || lib === 'pyzed-cpu';

export const NAMES: Record<string, string> = {
	pyzed: 'Pyzed',
	'pyzed-cpu': 'Pyzed (CPU renderer)',
	tkinter: 'tkinter',
	customtkinter: 'CustomTkinter',
	pyside6: 'PySide6 (Qt)',
	kivy: 'Kivy',
	dearpygui: 'Dear PyGui',
	flet: 'Flet',
	toga: 'Toga',
	nicegui: 'NiceGUI',
};

export const bench: any = data;

/** Seconds become milliseconds; memory and sizes stay in MB; lines stay lines. */
const SCALE: Record<Metric, number> = { import: 1000, first_frame: 1000, update: 1000, rss: 1, install: 1, loc: 1 };

export function version(lib: string): string {
	const entry = bench.libs[lib] ?? bench.size_only?.[lib];
	if (!entry) return '';
	const v = Object.entries(entry.versions ?? {}).filter(([, v]) => v);
	if (lib === 'tkinter') return `Tk ${bench.machine.tk}`;
	if (lib === 'pyzed-cpu') return `${v[0]?.[1] ?? ''} · tiny-skia`;
	return v.map(([, v]) => v).slice(0, 1).join('');
}

export function points(metric: Metric, opts: { rows?: string; app?: string } = {}): Point[] {
	const out: Point[] = [];
	const scale = SCALE[metric];
	const add = (lib: string, stat: any) => {
		if (stat == null) return;
		if (typeof stat === 'number') {
			out.push({ lib, name: NAMES[lib] ?? lib, version: version(lib), value: stat * scale });
			return;
		}
		out.push({
			lib,
			name: NAMES[lib] ?? lib,
			version: version(lib),
			value: stat.median * scale,
			min: stat.min * scale,
			max: stat.max * scale,
			stat,
		});
	};
	for (const [lib, entry] of Object.entries<any>(bench.libs)) {
		// The CPU-renderer variant is the same package: only its window numbers differ.
		if (lib === 'pyzed-cpu' && ['import', 'install', 'loc'].includes(metric)) continue;
		if (metric === 'import') add(lib, entry.import);
		else if (metric === 'install') add(lib, entry.install_mb == null ? null : entry.install_mb + (entry.install_extra_mb ?? 0));
		else if (metric === 'loc') add(lib, entry.loc?.[opts.app ?? 'counter']);
		else add(lib, entry.apps?.[opts.rows ?? '1000']?.[metric]);
	}
	if (metric === 'install') for (const [lib, entry] of Object.entries<any>(bench.size_only ?? {})) add(lib, entry.install_mb);
	return out.sort((a, b) => a.value - b.value);
}

export function fmt(value: number, metric: Metric): string {
	if (metric === 'loc') return String(Math.round(value));
	if (metric === 'update' && value < 10) return value.toFixed(1);
	return value >= 100 ? Math.round(value).toLocaleString('en-US') : value.toFixed(value >= 10 ? 0 : 1);
}

export const UNITS: Record<Metric, { en: string; es: string }> = {
	import: { en: 'ms', es: 'ms' },
	first_frame: { en: 'ms', es: 'ms' },
	update: { en: 'ms', es: 'ms' },
	rss: { en: 'MB', es: 'MB' },
	install: { en: 'MB', es: 'MB' },
	loc: { en: 'lines', es: 'líneas' },
};

/** "pyzed 1.1.0, tkinter (Tk 9.0.3), …" for the machine and versions list. */
export function versionsLine(): string {
	return Object.keys(bench.libs)
		.filter((lib) => lib !== 'pyzed-cpu')
		.map((lib) => `${NAMES[lib] ?? lib} ${version(lib)}`)
		.join(', ');
}
