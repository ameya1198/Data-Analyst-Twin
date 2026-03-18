# Anvaya UI Redesign — Minimalist & Chic
# Use 21st.dev Magic UI components wherever applicable

## Design Direction
- **Aesthetic**: Minimal, editorial, high-end SaaS — think Linear, Vercel, Raycast
- **Mood**: Dark navy accents on clean white/light gray — not flat, but restrained
- **Motion**: Subtle fade-ins, smooth transitions — nothing flashy
- **Typography**: Tight, confident, well-spaced
- **No**: Rounded bubbly cards, heavy shadows, gradient blobs, generic blue buttons

---

## 1. NAVBAR (top bar)

**Current issues**: Too cramped, favicon feels misaligned, "Disconnected" looks like an error

**Changes**:
- Increase navbar height to 52px, add `border-bottom: 1px solid rgba(0,0,0,0.06)`
- Favicon + wordmark: already good — keep the navy अ + ANVAYA amber underline
- Replace "Disconnected" badge:
  - When disconnected: subtle gray dot + "Offline" text in muted gray
  - When connected: small green pulse dot + "Connected"
  - Use 21st Magic UI `StatusBadge` or `AnimatedBadge` component
- Dark mode toggle: move to far right, use 21st `ThemeToggle`
- Add subtle `backdrop-blur` if navbar overlaps content on scroll

```jsx
// Navbar status badge
// 21st Magic UI: use <AnimatedBadge> or build with:
<div className="flex items-center gap-1.5 text-xs text-gray-400">
  <span className="w-1.5 h-1.5 rounded-full bg-gray-300" /> {/* or bg-green-400 with animate-pulse */}
  Disconnected
</div>
```

---

## 2. LEFT SIDEBAR (Chat History)

**Current issues**: Too wide, wastes space, "Current Chat" highlight is heavy

**Changes**:
- Reduce sidebar width from ~190px to 160px
- "Chat History" heading: smaller, all-caps, `letter-spacing: 0.1em`, muted color
- "Current Chat" item:
  - Remove heavy highlight background
  - Use a left border accent instead: `border-left: 2px solid #EF9F27`
  - Light background: `bg-amber-50/40`
- Add a `+` new chat button at the top of the sidebar
- Use 21st Magic UI `SidebarNav` or `AnimatedList` for chat history items

---

## 3. HERO / EMPTY STATE (center panel)

**Current issues**: Icon is generic, title font too heavy for minimalist feel, subtitle too wide, prompt cards feel disconnected

### Hero Icon
Replace the generic chart icon with the Anvaya favicon mark:
```jsx
<div className="w-16 h-16 rounded-2xl bg-[#26215C] flex items-center justify-center shadow-sm">
  <span style={{ fontFamily: 'serif', fontSize: '36px', color: '#EF9F27' }}>अ</span>
</div>
```

### Hero Title
```jsx
<h1 style={{
  fontFamily: 'sans-serif',
  fontWeight: 400,
  fontSize: '28px',
  letterSpacing: '0.18em',
  color: '#1a1a2e'
}}>
  ANVAYA
</h1>
// Amber underline
<div style={{ width: '32px', height: '2.5px', backgroundColor: '#EF9F27', borderRadius: '2px', margin: '6px auto' }} />
```

### Hero Subtitle
Narrow the subtitle max-width and lighten the text:
```jsx
<p style={{
  maxWidth: '380px',
  textAlign: 'center',
  fontSize: '14px',
  lineHeight: '1.7',
  color: '#888',
  letterSpacing: '0.01em'
}}>
  Upload a dataset and ask anything. EDA, SQL, visualizations,
  statistical tests — through natural conversation.
</p>
```

### Prompt Cards (4 cards)
**Current issues**: Cards look like disabled buttons, inconsistent weight

Use 21st Magic UI `HoverCard` or `MagicCard` with:
- Border: `1px solid rgba(0,0,0,0.07)`
- Background: `white` with very subtle hover: `bg-gray-50`
- Remove icons or make them 14px, stroke-only, muted gray
- Title: 13px, medium weight, `#1a1a2e`
- Subtitle: 12px, `#aaa`
- Hover: border color shifts to `#534AB7`, subtle lift with `translateY(-1px)`
- No heavy box shadows

```jsx
// 21st Magic UI — use <MagicCard> or <HoverBorderCard>
// Or build manually:
<div className="
  grid grid-cols-2 gap-3 mt-8 w-full max-w-md
">
  {prompts.map(p => (
    <button key={p.title} className="
      group text-left p-4 rounded-xl
      border border-black/7 bg-white
      hover:border-[#534AB7]/40 hover:bg-gray-50/80
      transition-all duration-200 hover:-translate-y-px
    ">
      <p className="text-[13px] font-medium text-[#1a1a2e] mb-1">{p.title}</p>
      <p className="text-[12px] text-gray-400 leading-snug">{p.subtitle}</p>
    </button>
  ))}
</div>
```

---

## 4. INPUT BAR (bottom)

**Current issues**: "Connecting..." placeholder is alarming, bar feels too rounded and blobby

**Changes**:
- Use a flatter input: `border-radius: 12px` (not fully pill)
- Border: `1px solid rgba(0,0,0,0.1)`, on focus: `border-color: #534AB7`
- Placeholder: `"Ask anything about your data..."` (not "Connecting...")
- Show connecting state differently — a tiny pulsing dot in the corner, not in the input
- Send button: navy `#26215C` background, arrow icon, no text
- Use 21st Magic UI `AnimatedInput` or `GlowingInput` (subtle version)

```jsx
<div className="relative w-full max-w-2xl">
  <input
    className="
      w-full px-5 py-3.5 pr-12
      rounded-xl border border-black/10
      bg-white text-sm text-gray-700
      placeholder:text-gray-300
      focus:outline-none focus:border-[#534AB7]/50
      transition-colors duration-200
    "
    placeholder="Ask anything about your data..."
  />
  <button className="
    absolute right-2 top-1/2 -translate-y-1/2
    w-8 h-8 rounded-lg bg-[#26215C]
    flex items-center justify-center
    hover:bg-[#534AB7] transition-colors
  ">
    <ArrowUpIcon className="w-4 h-4 text-white" />
  </button>
</div>
```

---

## 5. RIGHT SIDEBAR (Datasets)

**Current issues**: "DATASETS" heading is too prominent, dashed upload box is heavy

**Changes**:
- "DATASETS" + "DATASET PREVIEW" headers: 10px, `letter-spacing: 0.12em`, muted gray — already ok, just reduce font weight
- Upload box:
  - Use 21st Magic UI `FileUpload` or `DashedDropzone`
  - Reduce dashed border opacity to `rgba(0,0,0,0.12)`
  - Icon: smaller, 16px, gray
  - Text: "Drop a file or click to upload" — 12px, gray
  - On hover: dashed border turns `#534AB7`, background `#EEEDFE/30`
- "No datasets uploaded yet": 12px, centered, `color: #bbb`
- "10 rows max" label: even smaller, `color: #ccc`

```jsx
// 21st Magic UI — use <FileUpload> component
// Hover state: border-[#534AB7] bg-[#EEEDFE]/30
```

---

## 6. OVERALL SPACING & BACKGROUND

- Main background: keep `#F3F4F6` (light gray) — good
- Center panel background: `white` with no border, just natural separation
- Increase vertical padding in the center panel hero area — add `padding-top: 80px`
- Ensure consistent 20px gaps between all sections

---

## 7. 21st Magic UI Components to use (summary)

| Area | Component |
|------|-----------|
| Status badge (navbar) | `AnimatedBadge` / `StatusIndicator` |
| Prompt cards | `MagicCard` / `HoverBorderCard` |
| Input bar | `AnimatedInput` / `PlaceholderInput` |
| File upload box | `FileUpload` / `DashedDropzone` |
| Chat history list | `AnimatedList` |
| Theme toggle | `ThemeToggle` |
| Page transitions | `FadeIn` / `AnimatePresence` |

---

## 8. What NOT to change

- Do not change any functional logic or agent behaviour
- Do not change the sidebar panel layout (3-column structure is good)
- Do not change dataset upload logic
- Do not change the chat message rendering logic
- Keep the existing Anvaya navbar branding (favicon + wordmark)

---

## Priority Order

1. Hero empty state (icon, title, cards) — biggest visual impact
2. Input bar (users see this constantly)
3. Upload dropzone in right sidebar
4. Navbar status badge
5. Left sidebar refinement

---

*Anvaya — Ancient logic. Modern intelligence.*
