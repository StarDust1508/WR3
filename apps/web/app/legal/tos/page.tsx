import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — условия использования" };

const HEADING = { color: "#d4ffd4", fontSize: 18, marginTop: 28, fontWeight: 700 };

export default function TosPage() {
  return (
    <TerminalPageShell title="Условия использования" eyebrow="// terms · обновлено: май 2026">
      <h2 style={HEADING}>Что такое wr3</h2>
      <p>
        wr3 — автоматизированный AI-пайплайн аудита смарт-контрактов. На выходе:
        оценка по шкале 0–100, список находок с severity и (для платных тарифов)
        Foundry-PoC. wr3 не заменяет ручное ревью.
      </p>

      <h2 style={HEADING}>Чем wr3 НЕ является</h2>
      <ul>
        <li>Не страховщик. Мы не покрываем убытки от эксплойтов.</li>
        <li>Не финансовый совет. Оценка — сигнал, а не рекомендация.</li>
        <li>
          Не исчерпывающий аудит. LLM ошибаются, статические анализаторы пропускают
          баги — ручное ревью остаётся обязательным для критичных контрактов.
        </li>
      </ul>

      <h2 style={HEADING}>Ответственность</h2>
      <p>Ограничена стоимостью аудита (или $0 для free-тарифа).</p>

      <h2 style={HEADING}>Открытость</h2>
      <p>
        Веса оценки, severity-классификатор и весь пайплайн опубликованы в{" "}
        <a href="https://github.com/StarDust1508/WR3" style={{ color: "#4ade80", textDecoration: "underline" }}>
          GitHub
        </a>{" "}
        — методологию можно проверить.
      </p>
    </TerminalPageShell>
  );
}
