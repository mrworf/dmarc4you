export function isLikelyEmail(value: string | null | undefined): boolean {
  const trimmed = (value ?? "").trim();
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed);
}

export function isHttpUrl(value: string | null | undefined): boolean {
  const trimmed = (value ?? "").trim();
  if (!trimmed) {
    return false;
  }
  try {
    const parsed = new URL(trimmed);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}
