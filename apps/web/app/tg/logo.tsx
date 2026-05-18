/**
 * Terminal-style wr3 mark. Pure CSS/text — no SVG fetch, no images.
 * Looks like an ASCII prompt with a blinking cursor and a subtle green glow.
 */
export function Logo({ size = 40 }: { size?: number }) {
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 4,
        fontFamily:
          'ui-monospace, "SF Mono", Menlo, "JetBrains Mono", Consolas, monospace',
        fontWeight: 700,
        fontSize: size * 0.45,
        lineHeight: 1,
        color: "var(--hb-primary)",
        padding: `${size * 0.18}px ${size * 0.25}px`,
        border: "1px solid var(--hb-primary)",
        borderRadius: 4,
        letterSpacing: "-0.04em",
        textTransform: "lowercase",
        boxShadow:
          "0 0 12px rgba(74, 222, 128, 0.15), 0 0 4px rgba(74, 222, 128, 0.1)",
        animation: "pulse-glow 3s ease-in-out infinite",
      }}
      aria-label="wr3"
    >
      wr3
      <span
        style={{
          display: "inline-block",
          width: size * 0.08,
          height: size * 0.45,
          background: "var(--hb-primary)",
          animation: "hb-blink 1s steps(1) infinite",
        }}
        aria-hidden
      />
    </span>
  );
}
