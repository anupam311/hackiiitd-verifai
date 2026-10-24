import type { Metadata, Viewport } from "next";
import "./globals.css";
import { AppProviders } from "@/providers/AppProviders";

export const metadata: Metadata = {
  title: { default: "VERIFAI — Don't just find it. Verify it.", template: "%s · VERIFAI" },
  description: "Evidence-first opportunity discovery and claim-level verification.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#101b3a" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" data-theme="light">
      <body>
        <AppProviders>{children}</AppProviders>
      </body>
    </html>
  );
}
