import "@fontsource-variable/google-sans-flex/opsz.css";
import "@fontsource-variable/google-sans-code";
import "material-symbols/rounded.css";
import "@/styles/globals.css";
import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AppBar, Keyboard, ModeGate, Notifications, Providers } from "@/components/shell";

export const metadata: Metadata = { title: "HackHive", description: "Local AI video incident detection" };
export const viewport: Viewport = { width: "device-width", initialScale: 1 };

// Runs before first paint: ?theme=light|dark wins (not persisted), else the saved choice, else dark (DESIGN §9.7).
const THEME = `(()=>{try{var q=new URLSearchParams(location.search).get("theme");var t=q==="light"||q==="dark"?q:localStorage.getItem("hh-theme");document.documentElement.dataset.theme=t==="light"?"light":"dark"}catch(e){}})()`;
const FAVICON = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%231A73E8' stroke-width='2' stroke-linejoin='round'%3E%3Cpath d='M12 2.5 20.5 7.25v9.5L12 21.5l-8.5-4.75v-9.5Z'/%3E%3C/svg%3E";

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" data-theme="dark" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
        <link rel="icon" href={FAVICON} />
      </head>
      <body>
        <div id="root">
          <Providers>
            <AppBar />
            <main className="flex min-h-0 flex-1 flex-col">{children}</main>
            <Notifications />
            <ModeGate />
            <Keyboard />
          </Providers>
        </div>
      </body>
    </html>
  );
}
