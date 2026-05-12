import { TerminalPageShell } from "@/components/terminal-page-shell";

export const metadata = { title: "wr3 — условия использования" };

export default function TosPage() {
  return (
    <TerminalPageShell title="условия использования">
      <p style={{ color: "#a8e6a8", fontSize: 12 }}>
        // обновлено: май 2026. Простым языком — формально-юридическая
        версия появится к публичному запуску.
      </p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ что такое wr3</h2>
      <p>
        wr3 — это автоматизированный AI-аудит-пайплайн, который анализирует
        предоставленный исходный код смарт-контракта. На выходе — оценка
        (0–100) и список находок. wr3 не заменяет ручное ревью.
      </p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ чем wr3 НЕ является</h2>
      <ul>
        <li>Не страховщик. Мы не покрываем убытки от эксплойтов, которые пропустили или неверно классифицировали.</li>
        <li>Не финансовый совет. Оценка — сигнал, а не рекомендация.</li>
        <li>Не исчерпывающий аудит. AI галлюцинирует, статические анализаторы пропускают баги — ручное ревью всё ещё важно.</li>
      </ul>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ ответственность</h2>
      <p>Ограничена стоимостью аудита (или $0 для free-тарифа).</p>

      <h2 style={{ color: "#4ade80", fontSize: 14, marginTop: 24 }}>$ открытость</h2>
      <p>
        Веса оценки, severity-классификатор и весь пайплайн лежат в открытом{" "}
        <a href="https://github.com/StarDust1508/WR3" style={{ color: "#4ade80" }}>GitHub</a> —
        можно проверить.
      </p>
    </TerminalPageShell>
  );
}
