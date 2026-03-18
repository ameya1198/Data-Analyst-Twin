# Anvaya — Brand Guidelines

> *Ancient logic. Modern intelligence.*

---

## Brand Identity

**Name:** Anvaya  
**Meaning:** Sanskrit — "finding the logical thread connecting data points"  
**Tagline:** Ancient logic. Modern intelligence.  
**Category:** AI Data Intelligence Platform

---

## Logo

### Wordmark
- All-caps: `ANVAYA`
- Font: system sans-serif, weight 400 (regular)
- Letter spacing: `0.26em`
- Amber underline accent beneath the "A" only

### Favicon
- Devanagari character: **अ** (the Sanskrit letter A)
- Background: Navy `#26215C`
- Glyph: Amber `#EF9F27`
- Font: serif (Georgia)
- Corner radius: ~19% of size

### Files
| File | Use |
|------|-----|
| `assets/favicon.svg` | Browser tab, PWA icon |
| `assets/logo-light.svg` | Light backgrounds |
| `assets/logo-dark.svg`  | Dark backgrounds |
| `components/AnvayaLogo.jsx` | React wordmark component |
| `components/AnvayaFavicon.jsx` | React favicon/icon component |
| `components/AnvayaNavbar.jsx` | Ready-to-use navbar |

---

## Colour Palette

| Name | Hex | Usage |
|------|-----|-------|
| Navy | `#26215C` | Primary dark, favicon background, CTA buttons |
| Purple | `#534AB7` | Accent colour, links, hover states |
| Purple Mid | `#7F77DD` | Hover transitions |
| Lavender | `#EEEDFE` | Subtle section backgrounds |
| Amber | `#EF9F27` | Underline accent, favicon glyph, highlights |
| Amber Dark | `#BA7517` | Amber hover state |

---

## Typography

| Role | Style |
|------|-------|
| Wordmark | Sans-serif, 400 weight, `letter-spacing: 0.26em`, ALL CAPS |
| Tagline | Sans-serif, 400 weight, `letter-spacing: 0.30em`, ALL CAPS, 9–10px |
| अ glyph | Serif (Georgia), amber on navy |

---

## Usage Rules

✅ **Do**
- Use the amber underline only under the "A"
- Keep generous letter-spacing on the wordmark
- Use the favicon at 16px, 32px, or 64px
- Pair navy background with amber favicon on dark themes

❌ **Don't**
- Stretch or distort the wordmark
- Change the amber accent to another colour
- Use the logo on busy backgrounds without a clear contrast zone
- Use the serif font for anything other than the अ glyph

---

## Quick Start (React / Next.js)

```jsx
import { AnvayaNavbar } from './components/AnvayaNavbar'
import { AnvayaLogo }   from './components/AnvayaLogo'
import { AnvayaFavicon } from './components/AnvayaFavicon'

// Full navbar
<AnvayaNavbar />

// Logo only (hero)
<AnvayaLogo variant="light" size="xl" showTagline />

// Favicon mark (32px)
<AnvayaFavicon size={32} />
```

Add to your `<head>`:
```html
<link rel="icon" href="/assets/favicon.svg" type="image/svg+xml" />
<meta name="theme-color" content="#26215C" />
```

---

*Anvaya — Find the thread. See the truth.*
