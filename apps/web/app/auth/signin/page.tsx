import Link from "next/link";
import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — вход" };

const PRIMARY = "#4ade80";
const HI = "#d4ffd4";
const MUTED = "#5a8a5a";
const DIM = "#3a5e3a";
const FG = "#a8e6a8";
const BG = "#0a0e0a";

export default function SignInPage() {
  return (
    <TerminalPageShell title="вход">
      <p style={{ color: MUTED, fontSize: 12 }}>
        // wr3 авторизация — через Telegram. SIWE и email в дорожной карте.
      </p>

      <section
        style={{
          marginTop: 24,
          padding: 20,
          background: BG,
          border: `1px solid ${DIM}`,
          borderRadius: 6,
        }}
      >
        <h2 style={{ color: PRIMARY, fontSize: 13, margin: 0, fontWeight: 700 }}>
          $ telegram (активен)
        </h2>
        <p style={{ color: FG, fontSize: 13, marginTop: 12, lineHeight: 1.7 }}>
          В один тап. Telegram подписывает <code>initData</code> токеном бота.
          Бэкенд проверяет HMAC и выдаёт JWT. Без паролей, без email.
        </p>

        <ol style={{ color: FG, fontSize: 12, lineHeight: 1.8, paddingLeft: 20, marginTop: 12 }}>
          <li>Жми кнопку ниже — откроется @KitronBot.</li>
          <li>В Telegram нажми <code>Start</code>.</li>
          <li>Тапни кнопку меню <code>wr3 audit</code> внизу чата.</li>
          <li>Готово, ты вошёл.</li>
        </ol>

        <a
          href="https://t.me/KitronBot"
          style={{
            display: "inline-block",
            marginTop: 16,
            background: PRIMARY,
            color: BG,
            border: `1px solid ${PRIMARY}`,
            padding: "12px 20px",
            borderRadius: 4,
            textDecoration: "none",
            fontSize: 12,
            fontWeight: 700,
            letterSpacing: "0.04em",
            textTransform: "uppercase",
          }}
        >
          $ открыть @KitronBot →
        </a>

        <p style={{ color: DIM, fontSize: 10, marginTop: 12 }}>
          // уже в @KitronBot? Просто нажми <code>wr3 audit</code> — сюда возвращаться не нужно.
        </p>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ color: HI, fontSize: 12, margin: 0, fontWeight: 700 }}>
          $ siwe (sign-in with ethereum)
          <span
            style={{
              color: MUTED,
              fontSize: 10,
              fontWeight: 400,
              marginLeft: 8,
              letterSpacing: 0,
              textTransform: "none",
            }}
          >
            // в дорожной карте
          </span>
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          Для wallet-нативных разработчиков. Подпиши структурированное сообщение в
          MetaMask / Rabby / Ledger; бэкенд восстанавливает адрес EOA и привязывает
          к wr3-аккаунту. Пока не подключено — появится с публичной бетой.
        </p>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2 style={{ color: HI, fontSize: 12, margin: 0, fontWeight: 700 }}>
          $ email
          <span
            style={{
              color: MUTED,
              fontSize: 10,
              fontWeight: 400,
              marginLeft: 8,
              letterSpacing: 0,
              textTransform: "none",
            }}
          >
            // в дорожной карте
          </span>
        </h2>
        <p style={{ color: MUTED, fontSize: 12, marginTop: 8 }}>
          Magic-link через Resend. Для команд, у которых нет кошельков с seed-фразой.
        </p>
      </section>

      <p style={{ color: DIM, fontSize: 11, marginTop: 32 }}>
        // уже вошёл? Открой Mini App напрямую:{" "}
        <Link href="/tg" style={{ color: PRIMARY }}>/tg</Link>
      </p>
    </TerminalPageShell>
  );
}
