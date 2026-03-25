---
description: How to create standalone HTML slide presentations for academic defenses and qualification exams with premium light design
---

# Academic HTML Slide Presentations

Create self-contained, single-file HTML slide presentations designed for **academic contexts** (qualification exams, thesis defenses, conference talks). Extends the base html-slides skill with institutional elements, larger typography for projectors, progress indicators, and structured academic slide sequences.

## Output

A single `.html` file. Place it next to the content being presented (e.g., `slides/slides-academic.html`).

## Design System

### Color Palette (CSS Custom Properties)

```css
:root {
  --bg: #f8f9fc;
  --surface: #ffffff;
  --border: #e2e5ef;
  --text: #1e293b;
  --muted: #64748b;
  --accent: #7c3aed;
  --accent-light: #6d28d9;
  --green: #059669;
  --amber: #d97706;
  --rose: #e11d48;
  --blue: #2563eb;
}
```

### Typography (projector-optimized)

- **Font**: `Inter` from Google Fonts (weights: 300, 400, 600, 700, 800)
- **Code font**: `JetBrains Mono` or `Fira Code` (monospace fallback)
- **h1**: 3.5rem, weight 800, gradient text (`accent-light` → `blue`)
- **h2**: 2.5rem, weight 700, `accent-light` color
- **Body/li**: 1.4rem, line-height 1.7, `muted` color
- **`<strong>`**: `text` color (dark), weight 600
- **`<code>`**: `surface` background, `border` border, `green` text, 6px border-radius

> All sizes are intentionally larger than the base skill for readability at 3-5m distance from a projector.

### Slide Container

```css
.slide-inner {
  max-width: 1100px;  /* wider than base (960px) */
}
```

### Layout: 16:9 Forced Aspect Ratio

Slides use a fixed 16:9 container to ensure consistent rendering on any projector:

```css
.slide {
  display: none;
  justify-content: center;
  align-items: center;
  height: 100vh;
  width: 100vw;
  padding: 3rem 5rem;
}
```

## Academic-Specific Components

### Progress Bar

A thin bar at the top of every slide indicating presentation progress:

```css
.progress-bar {
  position: fixed;
  top: 0;
  left: 0;
  height: 4px;
  background: linear-gradient(90deg, var(--accent), var(--blue));
  transition: width 0.4s ease;
  z-index: 20;
}
```

Updated via JS on each slide change:

```js
function updateProgress() {
  const pct = ((cur + 1) / slides.length) * 100;
  document.getElementById('progress').style.width = pct + '%';
}
```

### Institutional Header (Title Slide Only)

The first slide includes university/program info:

```html
<p class="institution">Universidade XYZ — Programa de Pós-Graduação em ...</p>
```

```css
.institution {
  font-size: 1rem;
  color: var(--muted);
  letter-spacing: 0.05em;
  margin-bottom: 2rem;
  text-transform: uppercase;
  font-weight: 600;
}
```

### Author & Advisor Block

```html
<div class="author-block">
  <p><strong>Mestrando:</strong> Nome do Aluno</p>
  <p><strong>Orientador:</strong> Prof. Dr. Nome</p>
  <p>Fevereiro 2026</p>
</div>
```

```css
.author-block {
  margin-top: 2rem;
  font-size: 1.1rem;
  color: var(--muted);
}
.author-block p { margin: 0.3rem 0; }
```

### Section Divider Slide

Used to separate major sections (Introdução, Metodologia, Resultados, etc.):

```html
<div class="slide" id="s-section">
  <div class="slide-inner" style="text-align:center;">
    <p class="section-label">Parte 2</p>
    <h1 style="font-size:3rem;">Metodologia</h1>
  </div>
</div>
```

```css
.section-label {
  font-size: 1rem;
  text-transform: uppercase;
  letter-spacing: 0.15em;
  color: var(--muted);
  font-weight: 700;
  margin-bottom: 0.5rem;
}
```

### Citation Inline

For referencing within slides:

```html
<span class="cite">(Silva et al., 2024)</span>
```

```css
.cite {
  font-size: 0.9em;
  color: var(--muted);
  font-style: italic;
}
```

### References Slide

Final slide with formatted references:

```html
<ul class="references">
  <li>SILVA, A. B. et al. Título do artigo. <em>Revista</em>, v. 1, p. 1-10, 2024.</li>
</ul>
```

```css
.references {
  list-style: none;
  padding-left: 0;
}
.references li {
  font-size: 1rem;
  color: var(--text);
  padding: 0.4rem 0;
  padding-left: 1.6rem;
  text-indent: -1.6rem;
  line-height: 1.5;
}
.references li::before { content: none; }
```

## Reusable Components (inherited from base skill)

All components from the base `html-slides` skill apply here:
- **Pipeline/Flow Diagram** (`.pipeline`, `.step-box`) — arrows via SVG overlay (see below)
- **Highlight Box** (`.highlight-box`)
- **Two-Column Layout** (`.two-col`, `.col`)
- **Tag Badges** (`.tags`, `.tag`)
- **Custom Bullet Lists** (`▸` marker)

With one modification: cards (`.step-box`, `.col`) get subtle `box-shadow: 0 2px 8px rgba(0,0,0,0.06)`.

### SVG Arrow Overlay (standard for all diagrams)

**All arrows** in diagrams (vertical, horizontal, cross-lane, loop) MUST use an SVG overlay positioned on top of the diagram container. Do NOT use CSS pseudo-elements or div-based arrows.

#### Structure

```html
<div class="diagram-wrapper" style="position:relative;">
  <svg class="svg-overlay" id="svgOverlay">
    <defs>
      <marker id="arrowGray" markerWidth="8" markerHeight="5"
              refX="7" refY="2.5" orient="auto">
        <polygon points="0 0, 8 2.5, 0 5" fill="#64748b"/>
      </marker>
    </defs>
  </svg>
  <div class="diagram" id="diagram">
    <!-- step boxes with unique IDs -->
  </div>
</div>
```

```css
.svg-overlay {
  position: absolute;
  top: 0; left: 0;
  width: 100%; height: 100%;
  pointer-events: none;
  z-index: 10;
}
```

#### JS: compute positions and draw arrows

```js
function drawAllArrows() {
  const svg = document.getElementById('svgOverlay');
  const wrapper = document.querySelector('.diagram-wrapper');
  const wr = wrapper.getBoundingClientRect();
  svg.setAttribute('width', wr.width);
  svg.setAttribute('height', wr.height);
  svg.setAttribute('viewBox', `0 0 ${wr.width} ${wr.height}`);
  svg.querySelectorAll('path').forEach(el => el.remove());

  function r(id) {
    const b = document.getElementById(id).getBoundingClientRect();
    return {
      top: b.top - wr.top, bottom: b.bottom - wr.top,
      left: b.left - wr.left, right: b.right - wr.left,
      cx: b.left - wr.left + b.width / 2,
      cy: b.top - wr.top + b.height / 2,
    };
  }

  function arrow(d, color, dash, marker) {
    const p = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    p.setAttribute('d', d);
    p.setAttribute('fill', 'none');
    p.setAttribute('stroke', color);
    p.setAttribute('stroke-width', '2');
    if (dash) p.setAttribute('stroke-dasharray', dash);
    p.setAttribute('marker-end', marker);
    svg.appendChild(p);
  }

  // Gap offset so arrows don't touch box borders
  const gap = 6;

  // Vertical (within lane): bottom-center → top-center
  const a = r('from'), b = r('to');
  arrow(`M ${a.cx} ${a.bottom + gap} L ${a.cx} ${b.top - gap}`,
        '#64748b', null, 'url(#arrowGray)');

  // Cross-lane (L-shaped): right-center → left-center
  const mid = (a.right + b.left) / 2;
  arrow(`M ${a.right + gap} ${a.cy} L ${mid} ${a.cy} L ${mid} ${b.cy} L ${b.left - gap} ${b.cy}`,
        '#64748b', '6 3', 'url(#arrowGray)');

  // Loop (right side, going up):
  const loopX = a.right + 24;
  arrow(`M ${a.right + gap} ${a.cy} L ${loopX} ${a.cy} L ${loopX} ${b.cy} L ${b.right + gap} ${b.cy}`,
        '#d97706', '4 3', 'url(#arrowAmber)');
}
window.addEventListener('load', drawAllArrows);
window.addEventListener('resize', drawAllArrows);
```

#### Arrow types

| Type | Style | Use case |
|------|-------|----------|
| **Vertical** | Solid, gray | Sequential steps within a lane |
| **Cross-lane** | Dashed `6 3`, gray | Connecting steps across different lanes |
| **Loop** | Dashed `4 3`, amber | Feedback/retry loops (e.g., fixer → validator) |

#### Rules

- Every `<div class="step">` MUST have a unique `id` attribute
- Gap between steps within a lane (`gap` on `.lane`) MUST be `≥ 2.25rem` so vertical arrows have visible shaft
- Gap between lanes (`gap` on `.diagram`) should be `≥ 2.5rem` to give cross-lane arrows room
- Always call `drawAllArrows()` on both `load` and `resize`
- Use `<marker>` definitions matching the arrow color

## Navigation

Same as base skill (keyboard arrows + buttons), plus progress bar update:

```js
function show(i) {
  slides[cur].classList.remove('active');
  cur = (i + slides.length) % slides.length;
  slides[cur].classList.add('active');
  counter.textContent = `${cur + 1} / ${slides.length}`;
  updateProgress();
}
```

## Slide Composition Guidelines

### Recommended Academic Slide Sequence

1. **Title slide**: institution, title (`h1`), subtitle, author/advisor block, date
2. **Outline/Sumário slide**: numbered list of sections
3. **Section divider**: "Parte 1 — Introdução"
4. **Problem/Motivation slides**: contextualize the research gap
5. **Section divider**: "Parte 2 — Metodologia"  
6. **Architecture/Method slides**: pipeline diagrams, two-col comparisons
7. **Section divider**: "Parte 3 — Resultados (Parciais)"
8. **Results slides**: metrics, tables, highlight-boxes for key findings
9. **Section divider**: "Parte 4 — Conclusões"
10. **Conclusions + Next Steps slide**
11. **References slide**
12. **Thank you / Q&A slide**

### Content Rules

- **Qualification exams**: 15-25 slides (20min presentation typical)
- **Thesis defenses**: 25-40 slides (30-40min)
- **Conference talks**: 10-15 slides (15min)
- **One idea per slide**: never overload
- **Use inline citations** (`<span class="cite">`) when referencing work
- **Bold key terms** with `<strong>` for contrast
- **No walls of text**: max 4-5 bullets per list, 1 line each
- **Diagrams over text**: prefer pipeline/flow diagrams whenever possible

## Como Abrir

After creating the `.html` file, open it in the user's default browser:

```bash
xdg-open path/to/slides.html
```

### Do NOT

- Use external CSS frameworks (Tailwind, Bootstrap)
- Use default browser fonts
- Add more than 40 slides for any academic presentation
- Cram multiple ideas into one slide
- Use the browser_subagent to preview
- Skip section dividers in presentations with 15+ slides
