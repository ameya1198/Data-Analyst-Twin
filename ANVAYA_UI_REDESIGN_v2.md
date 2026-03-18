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

**Changes**:
- Height: `52px`
- Background: `white`, `border-bottom: 0.5px solid rgba(0,0,0,0.06)`
- Left: navy अ favicon (28×28px, border-radius 6px) + ANVAYA wordmark + amber underline
- Right: green pulse dot + "Connected" text (gray dot + "Offline" when disconnected)
- Far right: theme toggle button (28×28px, subtle border)
- Use 21st Magic UI `AnimatedBadge` or `StatusIndicator` for the connection badge

```jsx
<nav style={{ height: 52, display: 'flex', alignItems: 'center',
  justifyContent: 'space-between', padding: '0 20px',
  background: 'white', borderBottom: '0.5px solid rgba(0,0,0,0.06)' }}>

  {/* Brand */}
  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
    <div style={{ width: 28, height: 28, background: '#26215C',
      borderRadius: 6, display: 'flex', alignItems: 'center',
      justifyContent: 'center', fontFamily: 'serif',
      fontSize: 16, color: '#EF9F27' }}>अ</div>
    <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
      <span style={{ fontSize: 13, fontWeight: 400,
        letterSpacing: '0.22em', color: '#1a1a2e' }}>ANVAYA</span>
      <div style={{ width: 16, height: 2,
        background: '#EF9F27', borderRadius: 1 }} />
    </div>
  </div>

  {/* Status + theme toggle */}
  <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 5,
      fontSize: 11, color: '#aaa' }}>
      <div style={{ width: 6, height: 6, borderRadius: '50%',
        background: '#1D9E75' }} /> {/* animate-pulse when connected */}
      Connected
    </div>
    <ThemeToggle /> {/* 21st Magic UI ThemeToggle */}
  </div>
</nav>
```

---

## 2. LEFT SIDEBAR

**Changes**:
- Width: `160px`
- Background: `white`, `border-right: 0.5px solid rgba(0,0,0,0.06)`
- "New chat" button at top: small, subtle border, `+ New chat`
- "HISTORY" label: 10px, `letter-spacing: 0.12em`, muted gray, all-caps
- Active chat item: `border-left: 2px solid #EF9F27`, `background: rgba(250,238,218,0.35)`
- Inactive items: no background, just muted text
- Use 21st Magic UI `AnimatedList` for chat history items

```jsx
<aside style={{ width: 160, background: 'white',
  borderRight: '0.5px solid rgba(0,0,0,0.06)',
  padding: '16px 0', display: 'flex',
  flexDirection: 'column', gap: 4 }}>

  {/* New chat button */}
  <button style={{ display: 'flex', alignItems: 'center', gap: 7,
    margin: '0 10px 10px', padding: '7px 10px',
    borderRadius: 7, border: '0.5px solid rgba(0,0,0,0.08)',
    background: '#f5f5f3', fontSize: 12, color: '#666',
    cursor: 'pointer' }}>
    <PlusIcon size={12} /> New chat
  </button>

  <span style={{ fontSize: 10, letterSpacing: '0.12em',
    color: '#bbb', padding: '0 14px',
    marginBottom: 6, textTransform: 'uppercase' }}>History</span>

  {/* Active chat */}
  <div style={{ padding: '8px 14px', fontSize: 12, color: '#1a1a2e',
    borderLeft: '2px solid #EF9F27',
    background: 'rgba(250,238,218,0.35)',
    borderRadius: '0 6px 6px 0' }}>
    Current chat
  </div>

  {/* Other chats */}
  {chats.map(chat => (
    <div key={chat.id} style={{ padding: '8px 14px', fontSize: 12,
      color: '#888', borderLeft: '2px solid transparent',
      cursor: 'pointer' }}>{chat.title}</div>
  ))}
</aside>
```

---

## 3. HERO / EMPTY STATE (center panel)

**Remove entirely**: the 4 prompt cards (Upload & explore, Visualize, Query with SQL, Statistical test).

**Replace with**: icon + wordmark + short subtitle + input bar + hint chips.

### Hero icon
```jsx
<div style={{ width: 60, height: 60, background: '#26215C',
  borderRadius: 16, display: 'flex', alignItems: 'center',
  justifyContent: 'center', fontFamily: 'serif',
  fontSize: 32, color: '#EF9F27', marginBottom: 22 }}>
  अ
</div>
```

### Hero title + accent
```jsx
<h1 style={{ fontSize: 22, fontWeight: 400, letterSpacing: '0.22em',
  color: '#1a1a2e', lineHeight: 1, marginBottom: 8 }}>
  ANVAYA
</h1>
<div style={{ width: 28, height: 2.5, background: '#EF9F27',
  borderRadius: 2, margin: '0 auto 20px' }} />
```

### Hero subtitle
```jsx
<p style={{ fontSize: 13, color: '#aaa', lineHeight: 1.7,
  textAlign: 'center', maxWidth: 340 }}>
  Upload a dataset, then ask anything. Your data analyst is ready.
</p>
```

---

## 4. INPUT BAR

**Changes**:
- Shape: `border-radius: 12px` — NOT a full pill
- Border: `0.5px solid rgba(0,0,0,0.12)`, on focus: `border-color: rgba(83,74,183,0.5)`
- Placeholder: `"Ask anything about your data..."` — never "Connecting..."
- Send button: navy `#26215C`, `border-radius: 8px`, arrow-up icon
- Below input: hint chips row (see below)
- Use 21st Magic UI `AnimatedInput` for the input field

```jsx
<div style={{ width: '100%', padding: '14px 20px 18px' }}>
  <div style={{ display: 'flex', alignItems: 'center',
    background: 'white', border: '0.5px solid rgba(0,0,0,0.12)',
    borderRadius: 12, padding: '4px 4px 4px 16px', gap: 8,
    maxWidth: 640, margin: '0 auto' }}>
    <input
      placeholder="Ask anything about your data..."
      style={{ flex: 1, border: 'none', background: 'transparent',
        fontSize: 13, outline: 'none', padding: '8px 0' }}
    />
    <button style={{ width: 32, height: 32, background: '#26215C',
      borderRadius: 8, border: 'none', cursor: 'pointer',
      display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <ArrowUpIcon size={14} color="white" />
    </button>
  </div>

  {/* Hint chips */}
  <div style={{ display: 'flex', alignItems: 'center',
    justifyContent: 'center', gap: 6, marginTop: 10, flexWrap: 'wrap' }}>
    {['Explore my data', 'Show me a chart', 'Write SQL', 'Run a statistical test']
      .map(hint => (
        <button key={hint} onClick={() => setInput(hint)}
          style={{ fontSize: 11, color: '#aaa',
            background: 'white', border: '0.5px solid rgba(0,0,0,0.08)',
            borderRadius: 20, padding: '4px 10px', cursor: 'pointer' }}>
          {hint}
        </button>
      ))}
  </div>
</div>
```

> **Note**: Hint chips are subtle suggestion pills below the input.
> Clicking a chip fills the input — it does NOT submit automatically.
> They replace the old 4-card grid entirely.

---

## 5. RIGHT SIDEBAR (Datasets)

**Changes**:
- Width: `220px`
- Section labels: 10px, `letter-spacing: 0.12em`, muted, all-caps
- Upload dropzone:
  - `border: 1.5px dashed rgba(0,0,0,0.1)`
  - Hover: `border-color: #534AB7`, `background: rgba(238,237,254,0.3)`
  - Upload icon: 20px, stroke-only, gray
  - Text: "Add dataset" (12px medium) + "CSV, Excel, JSON, Parquet" (11px muted)
  - Use 21st Magic UI `FileUpload` or `DashedDropzone`
- "No datasets uploaded yet": 11px, centered, `color: #bbb`
- "10 rows max" badge: tiny, muted background pill, right-aligned

```jsx
<aside style={{ width: 220, background: 'white',
  borderLeft: '0.5px solid rgba(0,0,0,0.06)',
  padding: 16, display: 'flex', flexDirection: 'column', gap: 16 }}>

  <div>
    <p style={{ fontSize: 10, letterSpacing: '0.12em',
      color: '#bbb', textTransform: 'uppercase', marginBottom: 10 }}>
      Datasets
    </p>

    {/* Dropzone — use 21st Magic UI FileUpload */}
    <div style={{ border: '1.5px dashed rgba(0,0,0,0.1)',
      borderRadius: 10, padding: '20px 12px', textAlign: 'center',
      cursor: 'pointer' }}
      onMouseEnter={e => e.currentTarget.style.borderColor = '#534AB7'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'rgba(0,0,0,0.1)'}>
      <UploadIcon size={18} style={{ color: '#bbb', margin: '0 auto 8px' }} />
      <p style={{ fontSize: 12, fontWeight: 500, color: '#666', marginBottom: 3 }}>
        Add dataset
      </p>
      <p style={{ fontSize: 11, color: '#bbb' }}>
        CSV, Excel, JSON, Parquet
      </p>
    </div>

    <p style={{ fontSize: 11, color: '#bbb', textAlign: 'center', padding: '20px 0' }}>
      No datasets uploaded yet
    </p>
  </div>

  <div>
    <div style={{ display: 'flex', justifyContent: 'space-between',
      alignItems: 'center', marginBottom: 8 }}>
      <p style={{ fontSize: 10, letterSpacing: '0.12em',
        color: '#bbb', textTransform: 'uppercase' }}>Dataset preview</p>
      <span style={{ fontSize: 10, color: '#bbb',
        background: '#f5f5f3', padding: '2px 7px',
        borderRadius: 4 }}>10 rows max</span>
    </div>
    <p style={{ fontSize: 11, color: '#bbb', textAlign: 'center', padding: '20px 0' }}>
      Select a dataset to preview
    </p>
  </div>
</aside>
```

---

## 6. BACKGROUND & SPACING

- App background: `#f5f5f3` (warm light gray)
- Center panel background: `#f5f5f3` — same as app bg, no card wrapper
- White surfaces: navbar, sidebars, input bar, dropzone, hint chips
- Consistent border: `0.5px solid rgba(0,0,0,0.06)` on all dividers
- Hero vertical padding: `padding-top: 60px` minimum so it breathes

---

## 7. 21st Magic UI Components Summary

| Area | Component |
|------|-----------|
| Connection badge | `AnimatedBadge` / `StatusIndicator` |
| Input bar | `AnimatedInput` |
| File upload box | `FileUpload` / `DashedDropzone` |
| Chat history list | `AnimatedList` |
| Theme toggle | `ThemeToggle` |
| Page/chat transitions | `FadeIn` / `AnimatePresence` |

---

## 8. What NOT to Change

- Do not add back the 4 prompt cards (Upload & explore, Visualize, Query with SQL, Statistical test)
- Do not change any functional logic or agent behaviour
- Do not change the 3-column layout structure
- Do not change dataset upload logic
- Do not change chat message rendering
- Do not change the Anvaya navbar branding (अ favicon + ANVAYA wordmark)
- Do not use pill-shaped inputs (use border-radius 12px, not 9999px)

---

## 9. Priority Order

1. Hero empty state — remove cards, add hint chips
2. Input bar — shape, placeholder, send button
3. Navbar — status badge, theme toggle
4. Left sidebar — new chat button, active state
5. Right sidebar — dropzone hover state

---

*Anvaya — Ancient logic. Modern intelligence.*
