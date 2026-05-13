import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — вход" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#8bb88b";
const DIM = "#547654";
const FG = "#a8e6a8";
const BG = "#0a0e0a";

export default function SignInPage() {
  return (
    <TerminalPageShell title="Вход" eyebrow="// auth">
      <p style={{ color: MUTED, fontSize: 14, lineHeight: 1.6 }}>
        wr3 — Telegram-native. Авторизация через @KitronBot, без паролей и email.
      </p>

      <section
        style={{
          marginTop: 32,
          padding: 24,
          background: BG,
          border: `1px solid ${DIM}`,
          borderRadius: 8,
        }}
      >
        <h2
          style={{
            color: HI,
            fontSize: 16,
            margin: 0,
            fontWeight: 700,
            letterSpacing: "-0.01em",
          }}
        >
          Как это работает
        </h2>
        <p
          style={{
            color: FG,
            fontSize: 14,
            marginTop: 12,
            lineHeight: 1.7,
          }}
        >
          Telegram подписывает <code>initData</code> токеном бота, бэкенд
          проверяет HMAC и выдаёт JWT. Один тап — и вы внутри.
        </p>

        <ol
          style={{
            color: FG,
            fontSize: 13,
            lineHeight: 1.9,
            paddingLeft: 24,
            marginTop: 16,
          }}
        >
          <li>Откройте @KitronBot по кнопке ниже.</li>
          <li>
            В Telegram нажмите <code>Start</code>.
          </li>
          <li>
            Откройте меню <code>wr3 audit</code> внизу чата.
          </li>
          <li>Готово.</li>
        </ol>

        <a
          href="https://t.me/KitronBot"
          style={{
            display: "inline-block",
            marginTop: 20,
            background: PRIMARY,
            color: BG,
            border: `1px solid ${PRIMARY}`,
            padding: "12px 22px",
            borderRadius: 4,
            textDecoration: "none",
            fontSize: 14,
            fontWeight: 700,
          }}
        >
          Открыть @KitronBot
        </a>
      </section>

      <p style={{ color: DIM, fontSize: 12, marginTop: 32 }}>
        Уже вошли?{" "}
        <Link href="/tg" style={{ color: PRIMARY, textDecoration: "underline" }}>
          Открыть Mini App
        </Link>
      </p>
    </TerminalPageShell>
  );
}
