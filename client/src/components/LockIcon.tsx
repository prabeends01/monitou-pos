/** A single inline SVG lock glyph — not worth pulling in the separate
 * @fluentui/react-icons package (not currently a dependency) for one icon.
 * `@fluentui/react-components` itself ships components, not icons. */
export default function LockIcon({ size = 16 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 20 20"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      <rect x="4" y="9" width="12" height="9" rx="1.5" fill="currentColor" />
      <path
        d="M6.5 9V6.5a3.5 3.5 0 0 1 7 0V9"
        stroke="currentColor"
        strokeWidth="1.6"
        fill="none"
        strokeLinecap="round"
      />
    </svg>
  );
}
