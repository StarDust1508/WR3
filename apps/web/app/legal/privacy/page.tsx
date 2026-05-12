import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — приватность" };

export default function PrivacyPage() {
  return (
    <TerminalPageShell title="приватность">
      <p style={{ color: "#a8e6a8", fontSize: 12 }}>// обновлено: май 2026</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ что мы храним</h2>
      <ul>
        <li>Твой Telegram user id, username и display name — для привязки сканов к тебе.</li>
        <li>Входные данные сканов (адреса, опционально вставленный исходник) — для запуска пайплайна.</li>
        <li>Результаты сканов (находки, оценки) — показываются только тебе, если ты сам не включишь публичный лидерборд.</li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ третьи стороны</h2>
      <ul>
        <li>
          <b style={{ color: "#a8e6a8" }}>api.navy</b> — отвечает за LLM-вызовы (триаж / PoC / fuzzing).
          NavyAI — это reseller-proxy; политика хранения не подтверждена как «zero retention».
          Сырые 0-day эксплойты через них не гоняем.
        </li>
        <li>
          <b style={{ color: "#a8e6a8" }}>Etherscan V2</b> — публичный API для подтянуть verified-source контрактов.
        </li>
        <li>
          <b style={{ color: "#a8e6a8" }}>Cloudflare</b> — хостит Mini App.
        </li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ удаление данных</h2>
      <p>
        Напиши <a href="https://t.me/KitronBot" style={{ color: "#4ade80" }}>@KitronBot</a> слово{" "}
        <code>delete</code> — удалим аккаунт и все привязанные сканы в течение 72 часов.
      </p>
    </TerminalPageShell>
  );
}
