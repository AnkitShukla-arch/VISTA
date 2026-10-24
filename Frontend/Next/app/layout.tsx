import type { Metadata } from "next";
import { ThemeProvider } from "next-themes";
import "./globals.css";
import "./roles.css";
import { AppShell } from "@/components/app-shell";

export const metadata: Metadata = {
  title: "VISTA · Clinical intelligence",
  description: "Meaning-based search across clinical reports.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="en" suppressHydrationWarning><body>
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange={false}>
      <AppShell>{children}</AppShell>
    </ThemeProvider>
  </body></html>;
}
