import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "@/app/globals.css";
import { ToastProvider } from "@/components/ui/Toast";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-sans",
  preload: true,
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-mono",
  preload: true,
});

export const metadata: Metadata = {
  title: "Amazon Image Automation",
  description: "Automated Amazon product image generation pipeline with Gemini, watermark removal, and compliance tracking.",
  keywords: ["amazon", "ai", "image generation", "gemini", "automation", "ecommerce"],
  authors: [{ name: "Brandcentral" }],
  creator: "Brandcentral",
  publisher: "Brandcentral",
  formatDetection: {
    telephone: false,
  },
  metadataBase: new URL("https://brandcentral.example.com"),
  openGraph: {
    type: "website",
    locale: "en_US",
    url: "https://brandcentral.example.com",
    title: "Amazon Image Automation",
    description: "Automated Amazon product image generation pipeline",
    siteName: "Amazon Image Automation",
  },
  twitter: {
    card: "summary_large_image",
    title: "Amazon Image Automation",
    description: "Automated Amazon product image generation pipeline",
  },
  robots: {
    index: false,
    follow: false,
  },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#171717" },
  ],
  width: "device-width",
  initialScale: 1,
  maximumScale: 5,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${inter.variable} ${jetbrainsMono.variable} antialiased`} suppressHydrationWarning>
      <head>
        <link rel="icon" href="/favicon.ico" sizes="any" />
        <link rel="apple-touch-icon" href="/apple-touch-icon.png" />
        <link rel="manifest" href="/manifest.json" />
      </head>
      <body className={`${inter.className} ${jetbrainsMono.className} bg-surface-50 text-surface-900 min-h-screen`}>
        <ToastProvider>
          {children}
        </ToastProvider>
      </body>
    </html>
  );
}