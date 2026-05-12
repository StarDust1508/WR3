/**
 * Inline SVG wr3 mark — no external image fetch, no Telegram CSP gotcha.
 *
 * Design: stacked monospace "wr3" inside a rounded square. Uses --tg-button
 * for the chip background and --tg-button-text for the glyph so it adapts to
 * whichever Telegram theme is active.
 */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 64 64"
      role="img"
      aria-label="wr3"
      style={{ display: "block" }}
    >
      <rect
        x="2"
        y="2"
        width="60"
        height="60"
        rx="14"
        fill="var(--tg-button)"
      />
      <text
        x="50%"
        y="55%"
        textAnchor="middle"
        dominantBaseline="middle"
        fontFamily='ui-monospace, "SF Mono", Menlo, Consolas, monospace'
        fontWeight="700"
        fontSize="22"
        fill="var(--tg-button-text)"
        letterSpacing="-0.04em"
      >
        wr3
      </text>
    </svg>
  );
}
