# Anvaya Rebrand Instructions for Cursor

You are helping rebrand a product called **"Data Analyst Twin"** to **"Anvaya"**.
Apply the following changes across the entire codebase wherever relevant.

---

## 1. Name & Text Replacements

| Find | Replace |
|------|---------|
| `Data Analyst Twin` | `Anvaya` |
| `data analyst twin` | `Anvaya` |
| `data-analyst-twin` | `anvaya` |
| `DataAnalystTwin` | `Anvaya` |
| `DAT` (as an abbreviation) | `Anvaya` |

---

## 2. Tagline

Wherever a subtitle, meta description, or hero subheading describes the product, replace it with:

> **Ancient logic. Modern intelligence.**

Secondary tagline (for meta descriptions, og:description, longer contexts):

> An AI agent that mimics how a real data analyst thinks — upload your data and get EDA, visualizations, SQL, statistical tests, and actionable insights, all through natural conversation.

---

## 3. Favicon

Replace the existing favicon with the following SVG.
Save it as `favicon.svg` in your `/public` folder and update any references to `favicon.ico`, `favicon.png`, or existing `.svg` favicons.

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="6" fill="#26215C"/>
  <text x="16" y="26" text-anchor="middle"
    font-size="22" fill="#EF9F27" font-family="serif">अ</text>
</svg>
```

Update `<head>` to include:
```html
<link rel="icon" href="/favicon.svg" type="image/svg+xml" />
<link rel="apple-touch-icon" href="/favicon.svg" />
<meta name="theme-color" content="#26215C" />
```

---

## 4. Logo / Wordmark Component

Wherever a logo, site title, or brand name is rendered in the navbar, hero, or footer, replace it with this component pattern:

### React (JSX)
```jsx
// Wordmark — use in hero sections
<div className="flex flex-col items-start gap-1">
  <span style={{
    fontFamily: 'sans-serif',
    fontWeight: 400,
    fontSize: '48px',
    letterSpacing: '0.26em',
    color: '#1a1a2e'
  }}>
    ANVAYA
  </span>
  {/* Amber underline accent under the A only */}
  <div style={{
    width: '40px',
    height: '3.5px',
    backgroundColor: '#EF9F27',
    borderRadius: '2px'
  }} />
  <span style={{
    fontFamily: 'sans-serif',
    fontWeight: 400,
    fontSize: '10px',
    letterSpacing: '0.30em',
    color: '#888888',
    textTransform: 'uppercase'
  }}>
    Ancient logic. Modern intelligence.
  </span>
</div>
```

### Navbar version (smaller, with favicon icon)
```jsx
<a href="/" style={{ display: 'flex', alignItems: 'center', gap: '12px', textDecoration: 'none' }}>
  {/* Favicon mark */}
  <svg width="32" height="32" viewBox="0 0 32 32" xmlns="http://www.w3.org/2000/svg">
    <rect width="32" height="32" rx="6" fill="#26215C"/>
    <text x="16" y="26" textAnchor="middle" fontSize="22" fill="#EF9F27" fontFamily="serif">अ</text>
  </svg>
  {/* Wordmark */}
  <div style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
    <span style={{ fontFamily: 'sans-serif', fontWeight: 400, fontSize: '18px', letterSpacing: '0.22em', color: '#1a1a2e' }}>
      ANVAYA
    </span>
    <div style={{ width: '20px', height: '2.5px', backgroundColor: '#EF9F27', borderRadius: '2px' }} />
  </div>
</a>
```

### Tailwind version (if using Tailwind CSS)
```jsx
// Navbar logo
<a href="/" className="flex items-center gap-3 no-underline">
  <svg width="32" height="32" viewBox="0 0 32 32">
    <rect width="32" height="32" rx="6" fill="#26215C"/>
    <text x="16" y="26" textAnchor="middle" fontSize="22" fill="#EF9F27" fontFamily="serif">अ</text>
  </svg>
  <div className="flex flex-col gap-0.5">
    <span className="font-sans font-normal text-lg tracking-[0.22em] text-[#1a1a2e]">ANVAYA</span>
    <div className="w-5 h-0.5 bg-[#EF9F27] rounded-full" />
  </div>
</a>
```

---

## 5. Colour Tokens

Replace any existing brand/primary colour variables with these. Add to your global CSS, `tailwind.config.js`, or design token file:

### CSS Variables
```css
:root {
  --anvaya-navy:        #26215C;
  --anvaya-purple:      #534AB7;
  --anvaya-purple-mid:  #7F77DD;
  --anvaya-lavender:    #EEEDFE;
  --anvaya-amber:       #EF9F27;
  --anvaya-amber-dark:  #BA7517;
}
```

### Tailwind (`tailwind.config.js`)
```js
colors: {
  anvaya: {
    navy:          '#26215C',
    purple:        '#534AB7',
    'purple-mid':  '#7F77DD',
    lavender:      '#EEEDFE',
    amber:         '#EF9F27',
    'amber-dark':  '#BA7517',
  }
}
```

---

## 6. Meta Tags

Replace all `<title>`, `<meta name="description">`, and Open Graph tags with:

```html
<title>Anvaya — Ancient Logic. Modern Intelligence.</title>
<meta name="description" content="An AI agent that mimics how a real data analyst thinks — upload your data and get EDA, visualizations, SQL, statistical tests, and actionable insights, all through natural conversation." />

<meta property="og:title"       content="Anvaya — Ancient Logic. Modern Intelligence." />
<meta property="og:description" content="Upload your data and get EDA, visualizations, SQL, statistical tests, and actionable insights through natural conversation." />
<meta property="og:site_name"   content="Anvaya" />

<meta name="twitter:title"       content="Anvaya — Ancient Logic. Modern Intelligence." />
<meta name="twitter:description" content="Upload your data and get EDA, visualizations, SQL, statistical tests, and actionable insights through natural conversation." />
```

---

## 7. Footer

Replace any footer brand name / copyright text with:

```html
<span>© 2025 Anvaya. Ancient logic. Modern intelligence.</span>
```

Or in JSX:
```jsx
<p style={{ fontSize: '13px', color: '#888', letterSpacing: '0.06em' }}>
  © 2025 Anvaya &nbsp;·&nbsp; Ancient logic. Modern intelligence.
</p>
```

---

## 8. Page Title (browser tab)

```html
<title>Anvaya — Ancient Logic. Modern Intelligence.</title>
```

---

## 9. What NOT to change

- Do **not** change any functional logic, API calls, or data processing code.
- Do **not** change any file/folder names unless they explicitly contain `data-analyst-twin` or `dat`.
- Do **not** change UI copy that describes features (e.g. "EDA", "SQL generation", "Statistical tests") — only change the product name and tagline.
- Do **not** change any environment variables or API keys.

---

## 10. Summary Checklist

- [ ] All instances of "Data Analyst Twin" renamed to "Anvaya"
- [ ] Favicon updated to navy + amber अ SVG
- [ ] Navbar logo updated with favicon mark + ANVAYA wordmark + amber underline
- [ ] Hero title updated to ANVAYA with tagline
- [ ] `<title>` tag updated
- [ ] Meta description updated
- [ ] Open Graph tags updated
- [ ] Footer updated
- [ ] Brand colour tokens added to CSS / Tailwind config
- [ ] `theme-color` meta tag set to `#26215C`

---

*Anvaya — Find the thread. See the truth.*
