import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — приватность" };

const HEADING = { color: "#d4ffd4", fontSize: 18, marginTop: 28, fontWeight: 700 };
const HI = "#a8e6a8";

export default function PrivacyPage() {
  return (
    <TerminalPageShell title="Приватность" eyebrow="// privacy · обновлено: май 2026">
      <h2 style={HEADING}>Что мы храним</h2>
      <ul>
        <li>Telegram user id, username и display name — для привязки сканов к аккаунту.</li>
        <li>Входные данные сканов (адреса, опционально вставленный исходник) — для запуска пайплайна.</li>
        <li>Результаты сканов (находки, оценки) — видны только вам, пока вы сами не разрешите попадание в публичный лидерборд.</li>
      </ul>

      <h2 style={HEADING}>Третьи стороны</h2>
      <ul>
        <li>
          <b style={{ color: HI }}>api.navy</b> — обрабатывает LLM-вызовы (триаж, PoC,
          fuzzing). NavyAI — reseller-proxy; политика хранения не подтверждена как
          zero-retention. Сырые 0-day-эксплойты через этот канал не отправляем.
        </li>
        <li>
          <b style={{ color: HI }}>Etherscan V2</b> — публичный API для verified-source
          контрактов.
        </li>
        <li>
          <b style={{ color: HI }}>GoPlus Security</b> — публичный endpoint
          token-security для Tokenomics-оценки.
        </li>
        <li>
          <b style={{ color: HI }}>Cloudflare</b> — хостинг Mini App и веб-версии.
        </li>
      </ul>

      <h2 style={HEADING}>Удаление данных</h2>
      <p>
        Напишите{" "}
        <a href="https://t.me/KitronBot" style={{ color: "#4ade80", textDecoration: "underline" }}>
          @KitronBot
        </a>{" "}
        слово <code>delete</code> — удалим аккаунт и связанные сканы в течение 72 часов.
      </p>
    </TerminalPageShell>
  );
}
