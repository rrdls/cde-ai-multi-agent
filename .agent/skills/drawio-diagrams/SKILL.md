---
name: draw.io Diagram Generator
description: How to create formal draw.io (.drawio) diagrams programmatically using Python with proper shapes, colors, legends, and academic styling
---

# draw.io Diagram Generator Skill

Generate professional draw.io (`.drawio`) diagrams programmatically via Python scripts. Designed for academic/scientific contexts where formal notation, color-coded sections, and data-flow examples are required.

## Design Principles

1. **No code-level details** in labels. Use conceptual/scientific descriptions of what happens, not function names or implementation specifics.
2. **Concrete examples** at every data stage. Show real values flowing through the pipeline.
3. **Formal shapes** with a legend explaining each type.
4. **Color-coded sections** to visually group related steps.
5. **Horizontal flow** (left→right) within each section, sections stacked vertically.

## Shape Vocabulary

Use these draw.io shapes consistently. Each has a distinct semantic meaning:

| Shape | draw.io style key | Use for |
|---|---|---|
| **Document** | `shape=document` | Input/output files (PDF, CSV, XLSX, JSONL) |
| **Rounded Rectangle** | `rounded=1;arcSize=20` | Processing / transformation steps |
| **Double-bar Process** | `shape=process` | LLM calls or external API invocations |
| **Cylinder** | `shape=cylinder3` | Databases, vector stores, persistent storage |
| **Hexagon** | `shape=hexagon;perimeter=hexagonPerimeter2` | Knowledge bases, ontologies, taxonomies |
| **Note** (folded corner) | `shape=note` | Data with concrete example (monospace font) |

## Color Palette

Assign one color pair (fill + stroke) per logical section. Use draw.io's default palette for compatibility:

| Section | Fill | Stroke | Use |
|---|---|---|---|
| Blue | `#dae8fc` | `#6c8ebf` | Data ingestion / seeding |
| Green | `#d5e8d4` | `#82b366` | Pre-processing / chunking |
| Purple | `#e1d5e7` | `#9673a6` | Main pipeline / inference |
| Orange/Yellow | `#fff2cc` | `#d6b656` | LLM calls, knowledge bases |
| Pink/Red | `#f8cecc` | `#b85450` | Databases, search, fallback paths |
| Gray | `#f5f5f5` | `#666666` | Data/example boxes |

Process boxes within a section use a **slightly darker** variant of the section color (e.g., `#bdd7ee` instead of `#dae8fc` for blue processes).

## Python Generator Structure

Create a Python script at `diagrams/generate_<name>.py` that outputs a `.drawio` file.

### Required Components

```python
import html as _html
from pathlib import Path

# 1. ID generator
_id = 0
def uid():
    global _id; _id += 1; return f"n{_id}"

# 2. Style templates (one per shape type)
def _doc_style(fill, stroke):
    return (f"shape=document;whiteSpace=wrap;html=1;boundedLbl=1;"
            f"backgroundOutline=1;fillColor={fill};strokeColor={stroke};"
            f"fontSize=11;align=center;verticalAlign=middle;")

def _proc_style(fill, stroke):
    return (f"rounded=1;whiteSpace=wrap;html=1;arcSize=20;"
            f"fillColor={fill};strokeColor={stroke};"
            f"fontSize=11;align=center;verticalAlign=middle;")

def _data_style():
    return ("shape=note;whiteSpace=wrap;html=1;backgroundOutline=1;size=15;"
            "fillColor=#f5f5f5;strokeColor=#666666;fontSize=10;"
            "align=left;verticalAlign=middle;"
            "fontFamily=Courier New;spacingLeft=8;spacingRight=6;")

def _llm_style():
    return ("shape=process;whiteSpace=wrap;html=1;backgroundOutline=1;"
            "fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;"
            "align=center;verticalAlign=middle;fontStyle=1;")

def _db_style():
    return ("shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;"
            "backgroundOutline=1;size=12;fillColor=#f8cecc;"
            "strokeColor=#b85450;fontSize=11;"
            "align=center;verticalAlign=middle;")

def _hex_style():
    return ("shape=hexagon;perimeter=hexagonPerimeter2;"
            "whiteSpace=wrap;html=1;fixedSize=1;"
            "fillColor=#fff2cc;strokeColor=#d6b656;fontSize=11;"
            "align=center;verticalAlign=middle;")

# 3. Cell builder (handles XML + HTML escaping)
def esc(t): return _html.escape(str(t))

def cell(cid, style, x, y, w, h, label, parent="1"):
    label = label.replace("\n", "<br>")
    return (f'        <mxCell id="{cid}" value="{esc(label)}" '
            f'style="{style}" vertex="1" parent="{parent}">\n'
            f'          <mxGeometry x="{x}" y="{y}" width="{w}" '
            f'height="{h}" as="geometry" />\n'
            f'        </mxCell>\n')

# 4. Edge builder
def _edge_style(color="#333333", sw=1.5, dashed=False):
    d = "dashed=1;dashPattern=8 8;" if dashed else ""
    return (f"edgeStyle=orthogonalEdgeStyle;rounded=1;"
            f"orthogonalLoop=1;jettySize=auto;html=1;"
            f"strokeColor={color};strokeWidth={sw};{d}"
            f"endArrow=blockThin;endFill=1;")

def edge(eid, src, tgt, style):
    return (f'        <mxCell id="{eid}" style="{style}" edge="1" '
            f'source="{src}" target="{tgt}" parent="1">\n'
            f'          <mxGeometry relative="1" as="geometry" />\n'
            f'        </mxCell>\n')
```

### Shortcut Helpers

Wrap the primitives into convenient one-liners that return `(id, xml_string)`:

```python
def doc(x, y, w, h, label, fill, stroke):
    i = uid(); return i, cell(i, _doc_style(fill, stroke), x, y, w, h, label)

def proc(x, y, w, h, label, fill, stroke):
    i = uid(); return i, cell(i, _proc_style(fill, stroke), x, y, w, h, label)

def data(x, y, w, h, label):
    i = uid(); return i, cell(i, _data_style(), x, y, w, h, label)

def llm(x, y, w, h, label):
    i = uid(); return i, cell(i, _llm_style(), x, y, w, h, label)

def db(x, y, w, h, label):
    i = uid(); return i, cell(i, _db_style(), x, y, w, h, label)

def hexbox(x, y, w, h, label):
    i = uid(); return i, cell(i, _hex_style(), x, y, w, h, label)

def arr(src, tgt, color="#333333", sw=1.5, dashed=False):
    i = uid(); return edge(i, src, tgt, _edge_style(color, sw, dashed))
```

### Section Background

Use a dashed rounded rectangle at low opacity as a section container:

```python
def _section_style(fill, stroke):
    return (f"rounded=1;whiteSpace=wrap;html=1;arcSize=5;"
            f"dashed=1;dashPattern=5 5;fillColor={fill};"
            f"strokeColor={stroke};fontSize=14;fontStyle=1;"
            f"align=left;verticalAlign=top;spacingLeft=10;"
            f"spacingTop=5;opacity=40;")
```

### Label Formatting

Use HTML inside labels for rich formatting:
- `<b>Title</b>` for box titles (bold)
- `<br>` for line breaks (convert `\n` → `<br>`)
- `<font size="2">smaller text</font>` for detail text
- `<i>italic</i>` for emphasis
- `<font color='#6c8ebf'>■</font>` for color swatches in legend

### Building the Diagram

Use an accumulator pattern:

```python
def build():
    cells = ""

    def a(id_xml_pair):
        nonlocal cells
        if isinstance(id_xml_pair, tuple):
            cells += id_xml_pair[1]
            return id_xml_pair[0]
        else:
            cells += id_xml_pair
            return None

    # Add elements
    my_box = a(doc(40, 80, 180, 80, "<b>Input File</b>\nCSV format", "#dae8fc", "#6c8ebf"))
    my_proc = a(proc(280, 85, 170, 70, "<b>Transform</b>\nNormalization", "#bdd7ee", "#6c8ebf"))
    a(arr(my_box, my_proc, "#6c8ebf"))
    # ... more elements ...

    return cells
```

### XML Assembly

```python
def main():
    cells = build()
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<mxfile host="app.diagrams.net" type="device">
  <diagram name="Diagram Name" id="diagram-id">
    <mxGraphModel dx="2800" dy="2000" grid="1" gridSize="10"
        guides="1" tooltips="1" connect="1" arrows="1" fold="1"
        page="0" pageScale="1" pageWidth="5000" pageHeight="4000"
        math="0" shadow="0">
      <root>
        <mxCell id="0" />
        <mxCell id="1" parent="0" />
{cells}
      </root>
    </mxGraphModel>
  </diagram>
</mxfile>"""
    Path("output.drawio").write_text(xml, encoding="utf-8")
```

Set `page="0"` for infinite canvas (recommended for large diagrams).

## Layout Guidelines

### Positioning

- **Section backgrounds**: Start at `y=20`, increment by section height + 30px gap
- **Element rows**: Within a section, each row starts at section_y + offset
- **Horizontal spacing**: ~60px gap between elements
- **Standard sizes**:
  - Document shapes: 160-200 × 70-80
  - Process boxes: 170-240 × 65-80
  - Data/example notes: 250-310 × 75-100
  - LLM calls: 190 × 65
  - Database cylinders: 230-260 × 100-150
  - Hexagons (knowledge base): 280-320 × 200-280

### Legend (mandatory)

Always include a legend section at the bottom of the diagram with:
1. One instance of each shape type used, with its semantic meaning
2. Color swatch legend explaining each section's color
3. Arrow type legend (solid = data flow, dashed = reference/lookup)

## Reference Implementation

See `diagrams/generate_chain_drawio.py` for a complete working example with:
- 3 color-coded sections (Seed, Chunker, Chain Pipeline)
- All 6 shape types in use
- Concrete data examples at every stage
- Complete legend
- ~100 elements total
