import type { Metadata } from "next";
import type { Viewport } from "next";
import "./globals.css";
import PwaRegistrar from "./pwa-registrar";

export const metadata: Metadata = {
  title: "Care Parent Dashboard",
  description: "Panel frontend para padres con alertas y respuesta del LLM",
  manifest: "/manifest.webmanifest",
  applicationName: "Care Parent Dashboard",
  formatDetection: {
    telephone: false,
    date: false,
    address: false,
    email: false,
    url: false,
  },
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "Care",
  },
  icons: {
    icon: [
      { url: "/icon.svg", type: "image/svg+xml" },
      { url: "/icon-maskable.svg", type: "image/svg+xml", sizes: "any" },
    ],
    apple: [{ url: "/icon.svg" }],
  },
};

export const viewport: Viewport = {
  themeColor: "#13262f",
  colorScheme: "light",
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>
        <PwaRegistrar />
        {children}
      </body>
    </html>
  );
}
