// AnvayaNavbar.jsx
// Drop-in navbar for your landing page
// Props: transparent (bool) — use on hero sections over the flowing lines bg

import { AnvayaFavicon } from './AnvayaFavicon'
import { AnvayaLogo } from './AnvayaLogo'

export function AnvayaNavbar({ transparent = false }) {
  return (
    <nav
      className={`
        fixed top-0 left-0 right-0 z-50
        flex items-center justify-between
        px-8 py-4
        ${transparent
          ? 'bg-transparent'
          : 'bg-white/80 backdrop-blur-md border-b border-black/5'
        }
      `}
    >
      {/* Left: favicon + wordmark */}
      <a href="/" className="flex items-center gap-3 no-underline">
        <AnvayaFavicon size={32} />
        <AnvayaLogo variant="light" size="md" />
      </a>

      {/* Center: nav links */}
      <div className="hidden md:flex items-center gap-8">
        {['Features', 'Pricing', 'Docs', 'Blog'].map((link) => (
          <a
            key={link}
            href={`/${link.toLowerCase()}`}
            className="text-sm text-gray-500 hover:text-[#26215C] tracking-wide transition-colors"
          >
            {link}
          </a>
        ))}
      </div>

      {/* Right: CTA */}
      <div className="flex items-center gap-3">
        <a
          href="/login"
          className="text-sm text-gray-500 hover:text-[#26215C] tracking-wide transition-colors"
        >
          Sign in
        </a>
        <a
          href="/signup"
          className="
            text-sm text-white font-medium
            bg-[#26215C] hover:bg-[#534AB7]
            px-5 py-2 rounded-full
            tracking-wide transition-colors
          "
        >
          Get started →
        </a>
      </div>
    </nav>
  )
}
