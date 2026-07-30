# kicad-easyeda-export

A KiCad (pcbnew) action plugin that exports a copy of your board in a format
the **EasyEDA Pro** importer can fully read — **including the routing** —
plus a zip ready to import.

Use case: you design in KiCad but need the project inside EasyEDA Pro, e.g.
for JLCPCB's **full-color silkscreen** service, which only accepts fabrication
files exported from EasyEDA Pro.

## The problem it solves

Importing a KiCad 9/10 board into EasyEDA Pro appears to work — footprints
and board outline show up — but **all tracks, vias and copper zones are
silently dropped**.

The root cause is a file-format change. Up to KiCad 8, every `.kicad_pcb`
contained a numbered net table, and every copper item referenced its net by
number:

```lisp
(net 12 "+3.3V")          ; net table entry, in the board header
...
(segment
  (start 147.374 93.98)
  (end 147.374 90.88)
  (width 0.2)
  (layer "F.Cu")
  (net 12))               ; track references the net by NUMBER
```

KiCad 10 (format version `20260206`) removed the numbered net table entirely.
Tracks, vias, pads and zones now reference nets **by name**:

```lisp
(segment
  ...
  (net "+3.3V"))          ; by NAME — no numbered table exists anymore
```

EasyEDA Pro's importer (officially supporting up to KiCad 5.x formats, in
practice tolerant up to ~v8/v9) expects the numbered form. When it hits
`(net "+3.3V")` where it expects an integer, it fails to parse the copper
item and skips it — footprints survive, routing doesn't.

## What the plugin does

It rewrites the board file into KiCad 8 syntax (format `20240108`), without
touching your original file:

- Rebuilds the numbered net table and converts every `(net "name")` reference
  back to `(net N)` / `(net N "name")` depending on context (track, via,
  zone, pad).
- Renumbers the layer table to the v8 scheme (`F.Cu=0 … B.Cu=31`).
- Strips KiCad 9/10-only tokens that older parsers reject (`point` markers,
  `units` blocks in footprints, `tenting`/`covering`/`plugging` setup blocks,
  `embedded_fonts`, `duplicate_pad_numbers_are_jumpers`).

Everything electrical is preserved: on a real 4-layer, 79-net, 465-track
board, the converted copy passes KiCad's DRC with **0 unconnected pads**, and
Gerbers plotted from it are byte-identical to the original's for tracks,
pads, drills, mask, silkscreen and outline (only zone-fill polygon emission
differs in form, not geometry).

## Installation

### Via the Plugin and Content Manager (recommended)

1. Download the `*-pcm.zip` from the [latest release](https://github.com/ElectronicCats/kicad-plugin-jlcpcb-fix-production/releases).
2. In KiCad: **Tools → Plugin and Content Manager → Install from File…** and
   pick the zip.

To build the zip yourself: `python3 make_pcm_package.py` (output in `dist/`).

### Manual

Clone this repository into your KiCad plugins directory:

- **Linux:** `~/.local/share/kicad/<version>/scripting/plugins/`
- **macOS:** `~/Documents/KiCad/<version>/scripting/plugins/`
- **Windows:** `%USERPROFILE%\Documents\KiCad\<version>\scripting\plugins\`

where `<version>` is e.g. `10.0`. For example on Linux:

```sh
mkdir -p ~/.local/share/kicad/10.0/scripting/plugins
cd ~/.local/share/kicad/10.0/scripting/plugins
git clone <this-repo-url> kicad_easyeda_export
```

Restart pcbnew (or Tools → External Plugins → Refresh Plugins).

## Usage

1. Open your board in pcbnew and **save it** (the plugin converts the file on
   disk).
2. Click **Tools → External Plugins → "Export EasyEDA-compatible copy"** (or
   the toolbar button).
3. Next to your project you get an `easyeda-import/` folder containing:
   - `<board>.kicad_pcb` — the converted board
   - `<board>-easyeda-import.zip` — board + project file, ready to import
4. In [EasyEDA Pro](https://pro.easyeda.com): File → Import → KiCad, pick the
   zip, and verify the routing is there.

The converter is also usable standalone, without KiCad:

```sh
python3 kicad10_to_v8.py input.kicad_pcb output.kicad_pcb
```

## Full-color silkscreen at JLCPCB (why you'd want this)

JLCPCB's full-color silkscreen can only be ordered with Gerbers exported
from EasyEDA Pro. The workflow:

1. Export from KiCad with this plugin, import the zip into EasyEDA Pro.
2. Settings → PCB/Footprint → General → enable **"Use JLC color silkscreen
   technology"**.
3. Place → Image to add your PNG/SVG artwork (tick "original quality").
4. Export → PCB Fabrication File (Gerber) with the Silkscreen option ticked,
   and order at JLCPCB.

## Limitations

- One-way: KiCad → EasyEDA. Don't round-trip edits back.
- EasyEDA Pro rebuilds copper zone fills on import — review them afterwards.
- The stripped v10 tokens are cosmetic/metadata, but if your board depends on
  KiCad 10-only features (e.g. multi-unit footprints), review the import.
- Always cross-check the imported board against KiCad's own Gerbers before
  ordering.
