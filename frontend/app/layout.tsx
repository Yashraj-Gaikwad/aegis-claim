import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AegisClaim Control Center",
  description: "Zero-silent-failure clinical-financial adjudication",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
