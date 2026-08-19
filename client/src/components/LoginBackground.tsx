import { tokens } from "@fluentui/react-components";

/**
 * Original decorative background for the login screen — clean white/red
 * corporate look (matches the red+white identity used across heavy
 * equipment/industrial brands), with a light blueprint-style grid and an
 * abstract lifting-boom silhouette. Not a reproduction of any real
 * equipment photo or trademarked logo.
 */
export default function LoginBackground() {
  return (
    <div
      style={{
        position: "absolute",
        inset: 0,
        overflow: "hidden",
        backgroundColor: "#ffffff",
      }}
    >
      {/* bold red corner banner, corporate hero-section style */}
      <div
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          width: "58%",
          height: "62%",
          background: `linear-gradient(135deg, ${tokens.colorBrandBackground} 0%, ${tokens.colorPaletteRedForeground1} 55%, transparent 100%)`,
          clipPath: "polygon(38% 0%, 100% 0%, 100% 100%, 0% 100%)",
          opacity: 0.95,
        }}
      />
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          width: "48%",
          height: "40%",
          background: `linear-gradient(45deg, ${tokens.colorNeutralBackground3} 0%, transparent 75%)`,
          clipPath: "polygon(0% 100%, 62% 100%, 0% 20%)",
        }}
      />

      {/* light blueprint hex grid */}
      <svg width="100%" height="100%" style={{ position: "absolute", inset: 0, opacity: 0.5 }}>
        <defs>
          <pattern id="hexgrid" width="56" height="97" patternUnits="userSpaceOnUse">
            <path d="M28 0 L56 16 L56 48 L28 64 L0 48 L0 16 Z" fill="none" stroke="#d9dce2" strokeWidth="1" />
          </pattern>
          <radialGradient id="gridFade" cx="72%" cy="30%" r="70%">
            <stop offset="0%" stopColor="white" stopOpacity="0.9" />
            <stop offset="100%" stopColor="white" stopOpacity="0.1" />
          </radialGradient>
          <mask id="gridMask">
            <rect width="100%" height="100%" fill="url(#gridFade)" />
          </mask>
        </defs>
        <rect width="100%" height="100%" fill="url(#hexgrid)" mask="url(#gridMask)" />
      </svg>

      {/* boom crane silhouette, steel-gray with red boom accent, bottom-right */}
      <svg
        viewBox="0 0 620 560"
        preserveAspectRatio="xMaxYMax meet"
        style={{
          position: "absolute",
          right: "4%",
          bottom: "0",
          width: "38%",
          maxWidth: 480,
          height: "70%",
          opacity: 0.5,
        }}
        aria-hidden
      >
        <g fill="none" strokeLinecap="round" strokeLinejoin="round">
          <rect x="160" y="490" width="200" height="40" rx="6" fill="#eceef1" stroke="#c7ccd4" strokeWidth="2" />
          <rect x="248" y="60" width="24" height="440" rx="4" fill="#eceef1" stroke="#c7ccd4" strokeWidth="2" />
          {Array.from({ length: 9 }).map((_, i) => {
            const y = 90 + i * 46;
            return (
              <path
                key={i}
                d={`M 248 ${y} L 272 ${y + 30} M 272 ${y} L 248 ${y + 30}`}
                stroke="#d9dce2"
                strokeWidth="3"
              />
            );
          })}
          <path d="M 260 96 L 600 20" stroke={tokens.colorBrandBackground} strokeWidth="9" strokeOpacity="0.9" />
          <path d="M 260 118 L 140 148" stroke="#b7bdc7" strokeWidth="7" />
          <path d="M 200 500 L 140 148" stroke="#d9dce2" strokeWidth="3" strokeDasharray="1 5" />
          <path d="M 600 20 L 480 260" stroke="#c7ccd4" strokeWidth="2" strokeDasharray="2 6" />
          <rect
            x="462"
            y="260"
            width="34"
            height="42"
            rx="4"
            fill="#ffffff"
            stroke={tokens.colorBrandBackground}
            strokeOpacity="0.8"
            strokeWidth="2"
          />
        </g>
      </svg>
    </div>
  );
}
