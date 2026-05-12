import Script from "next/script";

export const metadata = {
  title: "wr3 — Telegram Mini App",
};

/**
 * Mini-App-only layout — pulls in Telegram WebApp SDK from CDN before any
 * client component touches `window.Telegram`. The strategy="beforeInteractive"
 * guarantees the script is parsed before hydration.
 */
export default function MiniAppLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <Script
        src="https://telegram.org/js/telegram-web-app.js"
        strategy="beforeInteractive"
      />
      <div className="mx-auto max-w-2xl px-4 py-6">{children}</div>
    </>
  );
}
