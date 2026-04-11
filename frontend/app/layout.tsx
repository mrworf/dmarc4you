import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "@/app/providers";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "DMARCWatch",
  description: "DMARC monitoring for domains, dashboards, ingest, search, and admin workflows.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const runtimeConfig = {
    apiBaseUrl: process.env.NEXT_PUBLIC_API_BASE_URL ?? "",
    csrfCookieName: process.env.NEXT_PUBLIC_CSRF_COOKIE_NAME ?? "dmarc_csrf",
    requestIdHeaderName: process.env.NEXT_PUBLIC_REQUEST_ID_HEADER_NAME ?? "X-Request-ID",
  };

  return (
    <html lang="en">
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: `window.__DMARC_RUNTIME_CONFIG__ = ${JSON.stringify(runtimeConfig)};`,
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
