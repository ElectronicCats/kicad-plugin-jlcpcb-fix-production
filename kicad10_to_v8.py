#!/usr/bin/env python3
"""Convert a KiCad 10 .kicad_pcb (format version 20260206) to KiCad 8
compatible syntax (version 20240108) so external importers (EasyEDA Pro)
can read the routing.

Changes applied:
  - version/generator_version -> 8.0
  - Layer table renumbered to the v8 scheme (F.Cu=0 ... B.Cu=31, user 32+)
  - Rebuilds the numbered net table (net N "name") after (setup)
  - (net "name") -> (net N [name]) depending on context (pad/zone/track/via)
  - Strips v9/v10-only tokens: tenting/covering/plugging/capping/filling in
    setup, point, units inside footprints, embedded_fonts,
    duplicate_pad_numbers_are_jumpers

CLI usage:  kicad10_to_v8.py input.kicad_pcb output.kicad_pcb
As module:  from kicad10_to_v8 import convert_text
"""
import re

V8_LAYER_NUM = {
    "F.Cu": 0, "In1.Cu": 1, "In2.Cu": 2, "In3.Cu": 3, "In4.Cu": 4,
    "B.Cu": 31,
    "B.Adhes": 32, "F.Adhes": 33, "B.Paste": 34, "F.Paste": 35,
    "B.SilkS": 36, "F.SilkS": 37, "B.Mask": 38, "F.Mask": 39,
    "Dwgs.User": 40, "Cmts.User": 41, "Eco1.User": 42, "Eco2.User": 43,
    "Edge.Cuts": 44, "Margin": 45, "B.CrtYd": 46, "F.CrtYd": 47,
    "B.Fab": 48, "F.Fab": 49,
    "User.1": 50, "User.2": 51, "User.3": 52, "User.4": 53,
}

STRIP_BLOCKS = {"tenting", "covering", "plugging"}
STRIP_BLOCKS_ANYWHERE = {"point"}
STRIP_LINES_IN_SETUP = {"capping", "filling"}
STRIP_LINES_ANYWHERE = {"embedded_fonts", "duplicate_pad_numbers_are_jumpers"}

NET_RE = re.compile(r'^(\s*)\(net "((?:[^"\\]|\\.)*)"\)\s*$')
OPEN_TOK_RE = re.compile(r"^\s*\((\w+)")


def _balance(s):
    """Count parentheses outside of strings."""
    n = 0
    in_str = False
    prev = ""
    for c in s:
        if in_str:
            if c == '"' and prev != "\\":
                in_str = False
        else:
            if c == '"':
                in_str = True
            elif c == "(":
                n += 1
            elif c == ")":
                n -= 1
        prev = c
    return n


def convert_text(text):
    """Return (converted_text, net_count)."""
    lines = text.splitlines()

    # Collect net names in order of appearance
    nets = {}
    for ln in lines:
        m = NET_RE.match(ln)
        if m:
            name = m.group(2)
            if name not in nets:
                nets[name] = len(nets) + 1  # 0 reserved for ""

    out = []
    stack = []          # open block tokens
    skip_depth = None   # depth of block being discarded (v10-only blocks)

    for ln in lines:
        b = _balance(ln)
        tok_m = OPEN_TOK_RE.match(ln)
        tok = tok_m.group(1) if tok_m else None

        # skipping a v10-only block
        if skip_depth is not None:
            if b > 0 and tok:
                stack.append(tok)
            elif b < 0:
                for _ in range(-b):
                    if stack:
                        stack.pop()
                if len(stack) <= skip_depth:
                    skip_depth = None
            continue

        in_setup = "setup" in stack
        in_footprint = bool(stack) and stack[-1] == "footprint"

        if tok in STRIP_LINES_ANYWHERE and b == 0:
            continue
        if in_setup and tok in STRIP_LINES_IN_SETUP and b == 0:
            continue
        if ((in_setup and tok in STRIP_BLOCKS) or tok in STRIP_BLOCKS_ANYWHERE
                or (in_footprint and tok == "units")) and b > 0:
            skip_depth = len(stack)
            stack.append(tok)
            continue

        # version/generator line
        if tok == "version" and len(stack) == 1:
            out.append(re.sub(r"\d+", "20240108", ln))
            continue
        if tok == "generator_version" and len(stack) == 1:
            out.append(re.sub(r'"[^"]*"', '"8.0"', ln))
            continue

        # renumber layer table (top-level "layers" block)
        if stack and stack[-1] == "layers" and len(stack) == 2 and b == 0:
            m = re.match(r'^(\s*)\((\d+) ("([^"]+)".*)\)\s*$', ln)
            if m:
                num = V8_LAYER_NUM.get(m.group(4))
                if num is not None:
                    out.append("%s(%d %s)" % (m.group(1), num, m.group(3)))
                    continue
            out.append(ln)
            continue

        # (net "x") -> numbered form depending on context
        m = NET_RE.match(ln)
        if m and stack:
            indent, name = m.group(1), m.group(2)
            num = nets[name]
            ctx = stack[-1]
            if ctx == "pad":
                out.append('%s(net %d "%s")' % (indent, num, name))
            elif ctx == "zone":
                out.append("%s(net %d)" % (indent, num))
                out.append('%s(net_name "%s")' % (indent, name))
            else:  # segment, via, arc
                out.append("%s(net %d)" % (indent, num))
            if b > 0 and tok:
                stack.append(tok)
            elif b < 0:
                for _ in range(-b):
                    if stack:
                        stack.pop()
            continue

        out.append(ln)

        # insert the net table right after (setup) closes
        closed_setup = b < 0 and stack and stack[-1] == "setup" and len(stack) == 2

        if b > 0 and tok:
            stack.append(tok)
        elif b < 0:
            for _ in range(-b):
                if stack:
                    stack.pop()

        if closed_setup and nets:
            out.append('\t(net 0 "")')
            for name, num in sorted(nets.items(), key=lambda kv: kv[1]):
                out.append('\t(net %d "%s")' % (num, name))

    result = "\n".join(out) + "\n"
    if _balance(result) != 0:
        raise ValueError("unbalanced parentheses in output")
    return result, len(nets)


if __name__ == "__main__":
    import sys
    src, dst = sys.argv[1], sys.argv[2]
    text = open(src, encoding="utf-8").read()
    converted, nnets = convert_text(text)
    open(dst, "w", encoding="utf-8").write(converted)
    print("OK: %d nets numbered -> %s" % (nnets, dst))
