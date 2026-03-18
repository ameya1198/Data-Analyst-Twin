// AnvayaLogo.jsx
// Usage: <AnvayaLogo variant="light" size="md" showTagline />

export function AnvayaLogo({
  variant = 'light',   // 'light' | 'dark'
  size = 'md',         // 'sm' | 'md' | 'lg' | 'xl'
  showTagline = false,
  className = '',
}) {
  const sizes = {
    sm: { word: 'text-base',  accent: 'w-4 h-0.5', gap: 'gap-1' },
    md: { word: 'text-xl',   accent: 'w-5 h-0.5', gap: 'gap-1' },
    lg: { word: 'text-3xl',  accent: 'w-7 h-1',   gap: 'gap-1.5' },
    xl: { word: 'text-5xl',  accent: 'w-10 h-1',  gap: 'gap-2' },
  }

  const colors = {
    light: {
      wordmark: 'text-[#1a1a2e]',
      tagline:  'text-[#888888]',
    },
    dark: {
      wordmark: 'text-white',
      tagline:  'text-[#AFA9EC]',
    },
  }

  const { word, accent, gap } = sizes[size]
  const { wordmark, tagline } = colors[variant]

  return (
    <div className={`flex flex-col items-start ${gap} ${className}`}>
      {/* Wordmark */}
      <span
        className={`font-sans font-normal tracking-[0.26em] ${word} ${wordmark}`}
      >
        ANVAYA
      </span>

      {/* Amber accent underline beneath the "A" */}
      <div
        className={`${accent} bg-[#EF9F27] rounded-full`}
        aria-hidden="true"
      />

      {/* Optional tagline */}
      {showTagline && (
        <span
          className={`font-sans font-normal tracking-[0.30em] text-[9px] uppercase ${tagline}`}
        >
          Ancient logic. Modern intelligence.
        </span>
      )}
    </div>
  )
}
