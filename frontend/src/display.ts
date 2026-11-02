import type {InterlockState} from "./api";

/** Display helpers for backend values that may be serialized without timezone info. */
export function parseBackendTimestamp(value: string | null | undefined): number {
  if (!value) return Number.NaN;
  // SQLite-backed API datetimes are naive UTC. Keep explicit offsets as supplied.
  const hasTimezone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value);
  return Date.parse(hasTimezone ? value : `${value}Z`);
}

export function elapsedSeconds(startedAt: string | null | undefined, now = Date.now()): number {
  const start = parseBackendTimestamp(startedAt);
  return Number.isFinite(start) ? Math.max(0, (now - start) / 1000) : 0;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return "—";
  return `${String(Math.floor(seconds / 60)).padStart(2, "0")}:${String(Math.floor(seconds % 60)).padStart(2, "0")}`;
}

export function textureScoreRange(texture: string, smoothness: number): string {
  if (texture === "coarse") return "24–34 / 100";
  if (texture === "medium") return "48–58 / 100";
  if (texture === "fine") return "72–80 / 100";
  const minimum = Math.max(0, Math.min(100, smoothness - 3));
  const maximum = Math.max(minimum, Math.min(100, smoothness + 3));
  return `${minimum}–${maximum} / 100`;
}

export type InterlockKey = keyof InterlockState;

export const INTERLOCK_OPTIONS: {key: InterlockKey; label: string; safeLabel: string; unsafeLabel: string}[] = [
  {key:"jar_present",label:"Jar present",safeLabel:"Present",unsafeLabel:"Missing"},
  {key:"lid_locked",label:"Lid locked",safeLabel:"Locked",unsafeLabel:"Unlocked"},
  {key:"attachment_present",label:"Attachment present",safeLabel:"Present",unsafeLabel:"Missing"},
];

export function updateInterlockState(state: InterlockState, key: InterlockKey, value: boolean): InterlockState {
  return {...state,[key]:value};
}

export function unsafeInterlockLabels(state: InterlockState): string[] {
  return INTERLOCK_OPTIONS.filter(option=>!state[option.key]).map(option=>option.label);
}

export function safeEventSeverity(value: unknown): string {
  return typeof value === "string" && value.trim().length > 0 ? value : "Info";
}

export function adaptivePulsePattern(eventType: string, newState: Record<string, unknown> | null | undefined): string | null {
  if(eventType!=="adaptive")return null;
  const pattern=newState?.pulse_pattern;
  return typeof pattern==="string"&&pattern.trim().length>0?pattern:null;
}
