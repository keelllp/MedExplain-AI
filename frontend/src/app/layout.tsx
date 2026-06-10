import type { Metadata, Viewport } from "next";
import { Fraunces, Hanken_Grotesk, Geist_Mono } from "next/font/google";

import { DisclaimerFooter } from "@/components/disclaimer-footer";
import { TopNav } from "@/components/top-nav";
import { Providers } from "@/app/providers";

import "./globals.css";

const hanken = Hanken_Grotesk({
  subsets: ["latin"],
  variable: "--font-hanken",
  display: "swap",
});

const fraunces = Fraunces({
  subsets: ["latin"],
  variable: "--font-fraunces",
  display: "swap",
});

const geistMono = Geist_Mono({
  subsets: ["latin"],
  variable: "--font-geist-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: "MedExplain AI — understand your medical reports",
  description:
    "Understand your medical reports in plain language. Educational only — never a diagnosis.",
};

export const viewport: Viewport = {
  colorScheme: "light",
  themeColor: "#f7f4ec",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${hanken.variable} ${fraunces.variable} ${geistMono.variable}`}
    >
      <body className="flex min-h-screen flex-col">
        <Providers>
          <TopNav />
          <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 sm:px-6 sm:py-10 lg:px-8">
            {children}
          </main>
          <DisclaimerFooter />
        </Providers>
      </body>
    </html>
  );
}
