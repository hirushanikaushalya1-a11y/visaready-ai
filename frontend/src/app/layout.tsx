import type { Metadata, Viewport } from "next";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "VisaReady AI – Prepare your visa application with confidence", template: "%s · VisaReady AI" },
  description:
    "An intelligent visa preparation platform that helps you understand your requirements, organise your evidence and identify potential application weaknesses before submission.",
};

export const viewport: Viewport = { width: "device-width", initialScale: 1, themeColor: "#0b1f4d" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="min-h-dvh antialiased">
        <AuthProvider>{children}</AuthProvider>
      </body>
    </html>
  );
}
