# Anvaya Font System
# Apply Cormorant Garamond + DM Sans across the entire codebase

---

## Overview

Anvaya uses two fonts with a clear separation of roles:

| Font | Role | Where |
|------|------|-------|
| **Cormorant Garamond** | Brand identity — presenting Anvaya | Wordmark, hero titles, tagline, footer quote, section headings (landing only) |
| **DM Sans** | Functional — doing the work | Body text, nav links, chat messages, labels, badges, inputs, UI copy |

**Core rule:**
- Cormorant appears wherever Anvaya is *presenting itself*
- DM Sans appears wherever Anvaya is *doing the work*
- Never use Cormorant inside chat message bubbles, data output, or small UI labels
- Never use serif fonts at sizes below 14px

---

## 1. Installation (Next.js)

```js
// app/layout.tsx or pages/_app.tsx
import { Cormorant_Garamond, DM_Sans } from 'next/font/google'

const cormorant = Cormorant_Garamond({
  subsets: ['latin'],
  weight: ['300', '400'],
  style: ['normal', 'italic'],
  variable: '--font-cormorant',
  display: 'swap',
})

const dmSans = DM_Sans({
  subsets: ['latin'],
  weight: ['300', '400', '500'],
  variable: '--font-dm-sans',
  display: 'swap',
})

export default function RootLayout({ children }) {
  return (
    <html lang="en" className={`${cormorant.variable} ${dmSans.variable}`}>
      <body style={{ fontFamily: 'var(--font-dm-sans), sans-serif' }}>
        {children}
      </body>
    </html>
  )
}
```

> **Important:** Set `DM Sans` as the default `body` font.
> Cormorant must always be applied explicitly — never inherited globally.

---

## 2. Tailwind Config

```js
// tailwind.config.js
module.exports = {
  theme: {
    extend: {
      fontFamily: {
        sans:      ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
        serif:     ['var(--font-cormorant)', 'Georgia', 'serif'],
        cormorant: ['var(--font-cormorant)', 'Georgia', 'serif'],
        dm:        ['var(--font-dm-sans)', 'system-ui', 'sans-serif'],
      },
    },
  },
}
```

Usage in Tailwind:
```jsx
<h1 className="font-cormorant font-light tracking-[0.26em]">ANVAYA</h1>
<p  className="font-sans font-light">Body text here</p>
```

---

## 3. CSS Variables (if not using Tailwind)

```css
:root {
  --font-brand:  'Cormorant Garamond', Georgia, serif;
  --font-ui:     'DM Sans', system-ui, sans-serif;
}

body {
  font-family: var(--font-ui);
  font-weight: 300;
}
```

---

## 4. Full Type Spec — Apply Exactly as Described

### WORDMARK (both landing + chat navbar)
```jsx
<span style={{
  fontFamily: 'var(--font-cormorant)',
  fontSize: '18px',        // navbar size
  fontWeight: 300,
  letterSpacing: '0.22em',
  color: '#1a1a2e',
}}>
  ANVAYA
</span>
```

### HERO TITLE — Landing page
```jsx
<h1 style={{
  fontFamily: 'var(--font-cormorant)',
  fontSize: '52px',
  fontWeight: 300,
  letterSpacing: '0.26em',
  color: '#1a1a2e',
  lineHeight: 1,
}}>
  ANVAYA
</h1>
```

### HERO TITLE — Chat empty state
```jsx
<h1 style={{
  fontFamily: 'var(--font-cormorant)',
  fontSize: '24px',
  fontWeight: 300,
  letterSpacing: '0.22em',
  color: '#1a1a2e',
}}>
  ANVAYA
</h1>
```

### TAGLINE / FOOTER QUOTE
```jsx
<p style={{
  fontFamily: 'var(--font-cormorant)',
  fontStyle: 'italic',
  fontSize: '17px',
  fontWeight: 300,
  letterSpacing: '0.01em',
  color: '#1a1a2e',
}}>
  "Ancient logic. Modern intelligence."
</p>
```

### FOOTER ATTRIBUTION
```jsx
<p style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '11px',
  fontWeight: 400,
  letterSpacing: '0.22em',
  color: '#aaa',
}}>
  — ANVAYA
</p>
```

### SECTION HEADINGS — Landing page only
```jsx
<h2 style={{
  fontFamily: 'var(--font-cormorant)',
  fontSize: '36px',
  fontWeight: 400,
  letterSpacing: '-0.01em',
  color: '#1a1a2e',
}}>
  Built to cover your needs
</h2>
```

### BODY TEXT / DESCRIPTIONS — Both
```jsx
<p style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '14px',
  fontWeight: 300,
  lineHeight: 1.7,
  color: '#888',
}}>
  Description text here
</p>
```

### NAV LINKS — Both
```jsx
<a style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '13px',
  fontWeight: 300,
  letterSpacing: '0.04em',
  color: '#888',
}}>
  Features
</a>
```

### CHAT MESSAGES — Chat only
```jsx
// Both user and assistant bubbles
<p style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '13px',
  fontWeight: 300,
  lineHeight: 1.65,
}}>
  Message text
</p>
```

### UI LABELS / BADGES / EYEBROWS
```jsx
<span style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '10px',
  fontWeight: 400,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: '#bbb',
}}>
  DATASETS
</span>
```

### INPUT PLACEHOLDER
```jsx
<input
  placeholder="Ask anything about your data..."
  style={{
    fontFamily: 'var(--font-dm-sans)',
    fontSize: '13px',
    fontWeight: 300,
  }}
/>
```

### CTA BUTTON
```jsx
<button style={{
  fontFamily: 'var(--font-dm-sans)',
  fontSize: '13px',
  fontWeight: 400,
  letterSpacing: '0.04em',
}}>
  Start analysing →
</button>
```

---

## 5. Tailwind Shorthand Classes

Add these to your `globals.css` for quick reuse:

```css
/* globals.css */

.font-wordmark {
  font-family: var(--font-cormorant);
  font-weight: 300;
  letter-spacing: 0.22em;
}

.font-hero {
  font-family: var(--font-cormorant);
  font-weight: 300;
  letter-spacing: 0.26em;
}

.font-quote {
  font-family: var(--font-cormorant);
  font-style: italic;
  font-weight: 300;
  letter-spacing: 0.01em;
}

.font-section-heading {
  font-family: var(--font-cormorant);
  font-weight: 400;
  letter-spacing: -0.01em;
}

.font-body {
  font-family: var(--font-dm-sans);
  font-weight: 300;
  line-height: 1.7;
}

.font-label {
  font-family: var(--font-dm-sans);
  font-weight: 400;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.font-chat {
  font-family: var(--font-dm-sans);
  font-weight: 300;
  line-height: 1.65;
}
```

---

## 6. What to Replace

Search the codebase and replace these:

| Find | Replace with |
|------|-------------|
| `font-family: Inter` | `font-family: var(--font-dm-sans)` |
| `font-family: system-ui` | `font-family: var(--font-dm-sans)` |
| `font-family: sans-serif` (on body) | `font-family: var(--font-dm-sans)` |
| `className="font-sans"` on headings/wordmark | `className="font-cormorant font-light"` |
| `font-bold` or `font-semibold` on body text | `font-medium` or `font-normal` — DM Sans at 300/400 is sufficient |

---

## 7. What NOT to Change

- Do NOT apply Cormorant to chat message bubbles
- Do NOT apply Cormorant to data output (tables, SQL results, stats)
- Do NOT apply Cormorant to form inputs or placeholders
- Do NOT apply Cormorant to sidebar labels, badges, or status indicators
- Do NOT use font-weight 600 or 700 anywhere — the brand uses 300/400/500 only
- Do NOT change the `font-family: Georgia, serif` on the अ favicon glyph

---

## 8. Google Fonts Fallback (non-Next.js)

```html
<!-- In <head> -->
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet" />
```

```css
:root {
  --font-cormorant: 'Cormorant Garamond', Georgia, serif;
  --font-dm-sans:   'DM Sans', system-ui, sans-serif;
}
```

---

## 9. Quick Summary

```
Cormorant Garamond (300/400, italic for quotes)
  → ANVAYA wordmark (both pages)
  → Hero titles (both pages)
  → Tagline + footer quote
  → Landing page section headings

DM Sans (300/400/500)
  → Everything else
  → All chat UI
  → All functional text
  → Inputs, labels, badges, buttons
```

---

*Anvaya — Ancient logic. Modern intelligence.*
