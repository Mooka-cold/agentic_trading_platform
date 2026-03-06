import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatTime(date: string | number | Date): string {
  if (!date) return '';
  
  // Force UTC interpretation if string lacks timezone info
  let d: Date;
  if (typeof date === 'string' && !date.endsWith('Z') && !date.includes('+')) {
      d = new Date(date + 'Z');
  } else {
      d = new Date(date);
  }

  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
    // timeZone: 'Asia/Shanghai' // Removed to use system timezone
  }).format(d);
}

export function formatDateTime(date: string | number | Date): string {
  if (!date) return '';

  // Force UTC interpretation if string lacks timezone info
  let d: Date;
  if (typeof date === 'string' && !date.endsWith('Z') && !date.includes('+')) {
      d = new Date(date + 'Z');
  } else {
      d = new Date(date);
  }

  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false
    // timeZone: 'Asia/Shanghai' // Removed to use system timezone
  }).format(d);
}
