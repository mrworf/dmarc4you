import type { ReactNode } from "react";

function normalizeCountryCode(countryCode: string | null | undefined): string | null {
  const value = (countryCode ?? "").trim().toUpperCase();
  return /^[A-Z]{2}$/.test(value) ? value : null;
}

export function countryCodeToFlag(countryCode: string | null | undefined): string {
  const normalizedCode = normalizeCountryCode(countryCode);
  if (!normalizedCode) {
    return "";
  }
  return String.fromCodePoint(...normalizedCode.split("").map((character) => 127397 + character.charCodeAt(0)));
}

export function renderCountryLabel(countryCode: string | null | undefined, countryName: string | null | undefined): ReactNode {
  const flag = countryCodeToFlag(countryCode);
  const normalizedName = (countryName ?? "").trim();
  const normalizedCode = normalizeCountryCode(countryCode);
  const label = normalizedName || normalizedCode || "n/a";

  if (!flag) {
    return label;
  }

  return (
    <span className="country-cell">
      <span aria-hidden="true" className="country-flag">
        {flag}
      </span>
      <span>{label}</span>
    </span>
  );
}
