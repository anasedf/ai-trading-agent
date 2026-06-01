// Centralized time formatting.
//
// The backend stores and serializes timestamps as NAIVE UTC (no timezone
// suffix, e.g. "2026-06-01T04:46:00"). `new Date("...")` on such a string
// parses it as BROWSER-LOCAL time, which silently shifts every displayed time
// by the user's offset. We fix that here by tagging naive strings as UTC, then
// format in the user's chosen timezone (persisted in localStorage, defaulting
// to the browser's detected zone).

const TZ_KEY = "ui_timezone";

export const COMMON_TIMEZONES = [
  "UTC",
  "Asia/Bangkok",
  "Asia/Singapore",
  "Asia/Tokyo",
  "Asia/Kolkata",
  "Asia/Dubai",
  "Europe/London",
  "Europe/Berlin",
  "Europe/Moscow",
  "America/New_York",
  "America/Chicago",
  "America/Los_Angeles",
  "Australia/Sydney",
];

export function browserTimezone(): string {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
  } catch {
    return "UTC";
  }
}

export function getTimezone(): string {
  if (typeof window === "undefined") return "UTC";
  return localStorage.getItem(TZ_KEY) || browserTimezone();
}

export function setTimezone(tz: string): void {
  if (typeof window !== "undefined") localStorage.setItem(TZ_KEY, tz);
}

// Treat a backend timestamp as UTC: append "Z" unless it already carries a
// timezone designator (Z, or a +hh:mm / -hh:mm offset).
function asUTC(iso: string): Date {
  if (!iso) return new Date(NaN);
  const hasTz = /[zZ]$/.test(iso) || /[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasTz ? iso : iso + "Z");
}

export function formatTime(iso: string, tz: string = getTimezone()): string {
  const d = asUTC(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", { timeZone: tz, hour: "2-digit", minute: "2-digit" });
}

export function formatDateTime(iso: string, tz: string = getTimezone()): string {
  const d = asUTC(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-GB", {
    timeZone: tz,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatDate(iso: string, tz: string = getTimezone()): string {
  const d = asUTC(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    timeZone: tz,
    day: "numeric",
    month: "short",
    year: "numeric",
  });
}

// Long heading used to group items by day, e.g. "Monday, 1 June".
export function formatDayHeading(iso: string, tz: string = getTimezone()): string {
  const d = asUTC(iso);
  if (isNaN(d.getTime())) return "—";
  return d.toLocaleDateString("en-GB", {
    timeZone: tz,
    weekday: "long",
    month: "long",
    day: "numeric",
  });
}
