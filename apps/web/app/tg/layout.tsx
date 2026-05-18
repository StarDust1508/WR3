import Script from "next/script";
import "./tg-globals.css";
import { TelegramThemeBridge } from "./theme";

export const metadata = {
  title: "wr3 — Telegram Mini App",
};

/**
 * Mini-App-only layout.
 *
 * - Pulls in Telegram WebApp SDK (telegram-web-app.js) BEFORE hydration so
 *   `window.Telegram.WebApp` is available the moment any client component
 *   tries to read initData / themeParams.
 * - Loads its own CSS file so the global Tailwind utilities used on the
 *   web don't leak generic zinc colors into the Mini App.
 * - Mounts <TelegramThemeBridge /> which copies themeParams into CSS
 *   variables (`--tg-bg`, `--tg-button` etc.). The whole UI reads those.
 */
export default function MiniAppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script
        src="https://telegram.org/js/telegram-web-app.js"
        strategy="beforeInteractive"
      />
      <TelegramThemeBridge />
      <div className="tg-scroll tg-animate-in">{children}</div>
    </>
  );
}
