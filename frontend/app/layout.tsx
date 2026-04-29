import type { Metadata } from "next";

import "./globals.css";
import { Providers } from "@/app/providers";
import { buildRuntimeConfigScript, buildServerRuntimeConfig } from "@/lib/runtime-env";

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
  const runtimeConfig = buildServerRuntimeConfig();

  return (
    <html lang="en">
      <body>
        <script
          dangerouslySetInnerHTML={{
            __html: buildRuntimeConfigScript(runtimeConfig),
          }}
        />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
