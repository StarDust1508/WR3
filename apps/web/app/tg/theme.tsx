"use client";

/**
 * Bridges Telegram WebApp themeParams to CSS variables.
 *
 * Telegram passes a color set in themeParams (bg_color, text_color, hint_color,
 * link_color, button_color, button_text_color, etc). We translate them to
 * CSS vars on <html> so the entire UI matches whichever theme the user
 * runs Telegram in (light / dark / custom).
 *
 * Fallback values are sane dark-theme defaults — the page is readable even
 * if Telegram never injects (e.g. browser-opened).
 */

import { useEffect } from "react";
import type { TgWebApp } from "@/lib/tg-session";

type ThemeParams = NonNullable<TgWebApp["themeParams"]>;

function applyTheme(tp: ThemeParams | undefined, scheme: "light" | "dark" | undefined) {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  const set = (k: string, v: string | undefined) => {
    if (v) root.style.setProperty(k, v);
  };

  // Defaults align with TG dark theme so a blank Mini App doesn't flash white.
  const isLight = scheme === "light";

  set("--tg-bg", tp?.bg_color ?? (isLight ? "#ffffff" : "#0f1115"));
  set("--tg-secondary-bg", tp?.secondary_bg_color ?? (isLight ? "#f4f4f5" : "#17191f"));
  set("--tg-section-bg", tp?.section_bg_color ?? (isLight ? "#ffffff" : "#1c1f26"));
  set("--tg-text", tp?.text_color ?? (isLight ? "#0a0a0a" : "#fafafa"));
  set("--tg-hint", tp?.hint_color ?? (isLight ? "#727272" : "#8a8f99"));
  set("--tg-subtitle", tp?.subtitle_text_color ?? tp?.hint_color ?? (isLight ? "#52525b" : "#a1a1aa"));
  set("--tg-link", tp?.link_color ?? "#3b82f6");
  set("--tg-accent", tp?.accent_text_color ?? tp?.link_color ?? "#3b82f6");
  set("--tg-button", tp?.button_color ?? "#3b82f6");
  set("--tg-button-text", tp?.button_text_color ?? "#ffffff");
  set("--tg-section-header", tp?.section_header_text_color ?? tp?.hint_color ?? "#8a8f99");
  set("--tg-destructive", tp?.destructive_text_color ?? "#ef4444");

  root.dataset.tgScheme = scheme ?? "dark";
}

export function TelegramThemeBridge() {
  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (!tg) {
      // Browser-opened (no Telegram). Apply dark defaults.
      applyTheme(undefined, "dark");
      return;
    }

    tg.ready?.();
    tg.expand?.();
    applyTheme(tg.themeParams, tg.colorScheme);

    const onThemeChanged = () => applyTheme(tg.themeParams, tg.colorScheme);
    tg.onEvent?.("themeChanged", onThemeChanged);
    return () => tg.offEvent?.("themeChanged", onThemeChanged);
  }, []);

  return null;
}
