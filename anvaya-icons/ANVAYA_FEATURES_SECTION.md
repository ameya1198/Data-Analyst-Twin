# Anvaya Features Section — Bento Grid with Custom Icons
# Apply using Magic UI: BentoGrid + MagicCard + BorderBeam + BlurFade

---

## Overview

Replace the current features section (4 cards with generic grid-background icons)
with a 5-feature asymmetric bento grid using custom SVG icons.
Use Magic UI components throughout.

---

## 1. Icon Files

Copy all SVG files from `/anvaya-icons/` into `/public/icons/features/`.

| File | Feature | Use on |
|------|---------|--------|
| `icon-eda.svg` | Exploratory analysis | Light card (lavender bg) |
| `icon-visualizations.svg` | Visualizations | Light card (amber bg) |
| `icon-sql.svg` | SQL generation | Light card (lavender bg) |
| `icon-sql-dark.svg` | SQL generation | Dark navy card |
| `icon-stats.svg` | Statistical tests | Light card (teal bg) |
| `icon-stats-dark.svg` | Statistical tests | Dark navy card |
| `icon-cleaning.svg` | Data cleaning | Light card (teal bg) |
| `icon-cleaning-dark.svg` | Data cleaning | Dark navy card |
| `icon-eda-dark.svg` | Exploratory analysis | Dark navy card |
| `icon-visualizations-dark.svg` | Visualizations | Dark navy card |

> Use the `-dark` variant whenever the card background is navy `#26215C`.
> Use the regular variant on all white/light cards.

---

## 2. Icon Wrapper Styles

Each icon sits inside a small rounded container. Match the container color to the icon:

| Feature | Icon bg color | Hex |
|---------|--------------|-----|
| Exploratory analysis | Lavender | `#EEEDFE` |
| Visualizations | Amber light | `#FAEEDA` |
| SQL generation | Navy (on dark card) | `rgba(255,255,255,0.08)` |
| Statistical tests | Teal light | `#E1F5EE` |
| Data cleaning | Teal light | `#E1F5EE` |

```jsx
// Icon wrapper component
<div style={{
  width: 40,
  height: 40,
  borderRadius: 10,
  background: '#EEEDFE', // change per feature
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginBottom: 14,
}}>
  <img src="/icons/features/icon-eda.svg" width={22} height={22} alt="" />
</div>
```

---

## 3. Bento Grid Layout — Layout C (asymmetric, recommended)

```
┌─────────────┬──────────────────────────┐
│   EDA       │   SQL generation         │
│  (white)    │   (dark navy) ← WIDE     │
├─────────────┼──────────────┬───────────┤
│  Stats      │  Visualize   │  Cleaning │
│ (dark navy) │  (white)     │ (white)   │
└─────────────┴──────────────┴───────────┘
```

Grid config:
- 3 columns, 2 rows
- SQL card: `col-span-2` (row 1, cols 2–3)
- Stats card: `col-span-1` (row 2, col 1)
- All others: `col-span-1`

---

## 4. Full Component Code

```jsx
import { BentoGrid, BentoCard } from "@/components/magicui/bento-grid"
import { MagicCard } from "@/components/magicui/magic-card"
import { BorderBeam } from "@/components/magicui/border-beam"
import { BlurFade } from "@/components/magicui/blur-fade"
import Image from "next/image"

const features = [
  {
    id: "eda",
    eyebrow: "Core",
    title: "Exploratory analysis",
    description:
      "Profile datasets, detect outliers, analyze distributions, correlations, and missing data patterns — guided by John Tukey's EDA principles.",
    icon: "/icons/features/icon-eda.svg",
    iconBg: "#EEEDFE",
    dark: false,
    colSpan: 1,
  },
  {
    id: "sql",
    eyebrow: "Query",
    title: "SQL generation",
    description:
      "Write & execute analytical SQL with CTEs, window functions, cohort analysis, and funnel queries — powered by DuckDB.",
    icon: "/icons/features/icon-sql-dark.svg",
    iconBg: "rgba(255,255,255,0.08)",
    dark: true,
    colSpan: 2,
  },
  {
    id: "stats",
    eyebrow: "Stats",
    title: "Statistical tests",
    description:
      "Hypothesis testing, A/B analysis, regression — always reporting p-value, effect size, and confidence intervals.",
    icon: "/icons/features/icon-stats-dark.svg",
    iconBg: "rgba(255,255,255,0.08)",
    dark: true,
    colSpan: 1,
  },
  {
    id: "viz",
    eyebrow: "Visualize",
    title: "Interactive charts",
    description:
      "Auto-generate interactive charts following Edward Tufte's principles — maximize data-ink ratio, always pick the right chart type.",
    icon: "/icons/features/icon-visualizations.svg",
    iconBg: "#FAEEDA",
    dark: false,
    colSpan: 1,
  },
  {
    id: "cleaning",
    eyebrow: "Quality",
    title: "Data cleaning",
    description:
      "Structural fixes, deduplication, missing value treatment, and standardization — following a systematic pipeline.",
    icon: "/icons/features/icon-cleaning.svg",
    iconBg: "#E1F5EE",
    dark: false,
    colSpan: 1,
  },
]

export function FeaturesSection() {
  return (
    <section className="py-24 px-6 bg-[#f5f5f3]">

      {/* Section header */}
      <BlurFade delay={0}>
        <div className="text-center mb-12">
          <h2 className="text-3xl font-normal text-[#1a1a2e] tracking-tight mb-3">
            Built to cover your needs
          </h2>
          <p className="text-sm text-gray-400 max-w-md mx-auto leading-relaxed">
            Five specialist agents working together — EDA, visualizations,
            SQL, statistics, and data cleaning.
          </p>
        </div>
      </BlurFade>

      {/* Bento grid */}
      <div className="grid grid-cols-3 gap-2.5 max-w-5xl mx-auto">
        {features.map((feature, i) => (
          <BlurFade key={feature.id} delay={0.1 + i * 0.08}>
            <MagicCard
              className={[
                "relative overflow-hidden rounded-2xl p-6 cursor-pointer",
                "border transition-colors duration-200",
                feature.colSpan === 2 ? "col-span-2" : "col-span-1",
                feature.dark
                  ? "bg-[#26215C] border-[#3C3489] hover:border-[#7F77DD]"
                  : "bg-white border-black/7 hover:border-[#534AB7]/40",
              ].join(" ")}
              gradientColor={feature.dark ? "#534AB7" : "#EEEDFE"}
              gradientOpacity={0.15}
            >
              {/* BorderBeam on dark cards only */}
              {feature.dark && (
                <BorderBeam
                  size={80}
                  duration={3}
                  colorFrom="#EF9F27"
                  colorTo="#534AB7"
                />
              )}

              {/* Icon */}
              <div
                style={{ background: feature.iconBg }}
                className="w-10 h-10 rounded-xl flex items-center justify-center mb-4"
              >
                <Image
                  src={feature.icon}
                  width={22}
                  height={22}
                  alt={feature.title}
                />
              </div>

              {/* Eyebrow */}
              <p className={[
                "text-[10px] tracking-[0.1em] uppercase mb-2",
                feature.dark ? "text-[#7F77DD]" : "text-gray-400",
              ].join(" ")}>
                {feature.eyebrow}
              </p>

              {/* Amber accent line */}
              <div className="w-5 h-0.5 bg-[#EF9F27] rounded-full mb-3" />

              {/* Title */}
              <h3 className={[
                "text-sm font-medium mb-2",
                feature.dark ? "text-white" : "text-[#1a1a2e]",
              ].join(" ")}>
                {feature.title}
              </h3>

              {/* Description */}
              <p className={[
                "text-xs leading-relaxed",
                feature.dark ? "text-[#AFA9EC]" : "text-gray-400",
              ].join(" ")}>
                {feature.description}
              </p>
            </MagicCard>
          </BlurFade>
        ))}
      </div>
    </section>
  )
}
```

---

## 5. Magic UI Installs Needed

```bash
npx shadcn@latest add "https://magicui.design/r/bento-grid"
npx shadcn@latest add "https://magicui.design/r/magic-card"
npx shadcn@latest add "https://magicui.design/r/border-beam"
npx shadcn@latest add "https://magicui.design/r/blur-fade"
```

---

## 6. CSS Grid fix for col-span inside BlurFade

BlurFade wraps each card in a `<div>` — this breaks CSS grid col-span.
Fix by passing the span class to the wrapper div:

```jsx
<BlurFade
  key={feature.id}
  delay={0.1 + i * 0.08}
  className={feature.colSpan === 2 ? "col-span-2" : "col-span-1"}
>
  <MagicCard className="h-full ...">
    ...
  </MagicCard>
</BlurFade>
```

Also make sure the grid is on the parent `<div>`, not on `BentoGrid` —
use a plain `grid grid-cols-3 gap-2.5` div for full layout control.

---

## 7. Design Tokens Used

| Token | Value | Use |
|-------|-------|-----|
| Navy | `#26215C` | Dark card background |
| Purple | `#534AB7` | Light card hover border |
| Purple mid | `#7F77DD` | Dark card eyebrow text, hover border |
| Lavender | `#EEEDFE` | EDA icon bg, MagicCard gradient |
| Amber | `#EF9F27` | Accent line, BorderBeam, icon details |
| Amber bg | `#FAEEDA` | Visualizations icon bg |
| Teal bg | `#E1F5EE` | Stats + Cleaning icon bg |

---

## 8. What NOT to Change

- Do not use the old grid-pattern background on icons
- Do not use Lucide or any stock icon library for these features
- Do not add drop shadows to the cards
- Do not make all cards the same size — the asymmetric layout is intentional
- Do not add BorderBeam to white/light cards — only dark navy cards get it
- Do not change the icon SVG colors

---

*Anvaya — Ancient logic. Modern intelligence.*
