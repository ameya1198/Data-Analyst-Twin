// AnvayaFavicon.jsx
// Reusable favicon mark — navy square with amber अ
// Also works as an app icon, navbar badge, loading indicator

export function AnvayaFavicon({ size = 32, className = '' }) {
  const radius = Math.round(size * 0.19)   // ~6px at 32px
  const fontSize = Math.round(size * 0.68)  // ~22px at 32px
  const textY = Math.round(size * 0.81)     // ~26px at 32px

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      viewBox={`0 0 ${size} ${size}`}
      width={size}
      height={size}
      className={className}
      aria-label="Anvaya"
    >
      <rect width={size} height={size} rx={radius} fill="#26215C" />
      <text
        x={size / 2}
        y={textY}
        textAnchor="middle"
        fontSize={fontSize}
        fill="#EF9F27"
        fontFamily="Georgia, serif"
      >
        अ
      </text>
    </svg>
  )
}
