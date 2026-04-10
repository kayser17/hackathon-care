import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Care MVP",
  description: "Base de hackathon para producto de salud",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="es">
      <body>{children}</body>
    </html>
  );
}
