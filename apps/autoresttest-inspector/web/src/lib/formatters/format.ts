export function formatNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat().format(value);
}

export function formatCompactNumber(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return new Intl.NumberFormat(undefined, {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatPercent(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return "n/a";
  }
  return `${(value * 100).toFixed(1)}%`;
}

export function formatDate(value: string | null | undefined): string {
  if (!value) {
    return "n/a";
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

export function truncate(value: string, length = 120): string {
  if (value.length <= length) {
    return value;
  }
  return `${value.slice(0, length)}...`;
}
