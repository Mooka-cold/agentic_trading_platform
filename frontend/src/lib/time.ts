const SHANGHAI_TZ = 'Asia/Shanghai';

function parseInputAsDate(input: string | number | Date): Date {
  if (input instanceof Date) return input;
  if (typeof input === 'number') return new Date(input);

  const raw = input.trim();
  if (!raw) return new Date(input);

  // If backend returns naive datetime (no timezone), treat it as UTC.
  // e.g. "2026-04-14T09:05:35" or "2026-04-14 09:05:35"
  const hasTimezone = /([zZ]|[+\-]\d{2}:?\d{2})$/.test(raw);
  if (!hasTimezone) {
    const normalized = raw.replace(' ', 'T');
    return new Date(`${normalized}Z`);
  }
  return new Date(raw);
}

export function formatTimeCN(input: string | number | Date): string {
  return parseInputAsDate(input).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: SHANGHAI_TZ,
  });
}

export function formatMinuteTimeCN(input: string | number | Date): string {
  return parseInputAsDate(input).toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
    timeZone: SHANGHAI_TZ,
  });
}

export function formatDateTimeCN(input: string | number | Date): string {
  return parseInputAsDate(input).toLocaleString('zh-CN', {
    hour12: false,
    timeZone: SHANGHAI_TZ,
  });
}
