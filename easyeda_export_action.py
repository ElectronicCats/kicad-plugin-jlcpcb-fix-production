"""pcbnew action plugin: exports a copy of the board in KiCad 8 syntax
compatible with the EasyEDA Pro importer (keeps the routing) and creates
the zip ready to import.
"""
import os
import zipfile

import pcbnew

try:
    import wx
except ImportError:
    wx = None

from .kicad10_to_v8 import convert_text


def _notify(msg, error=False):
    if wx:
        style = wx.OK | (wx.ICON_ERROR if error else wx.ICON_INFORMATION)
        wx.MessageBox(msg, "Export for EasyEDA", style)


class EasyEDAExportPlugin(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Export EasyEDA-compatible copy"
        self.category = "Export"
        self.description = (
            "Converts the saved .kicad_pcb to KiCad 8 syntax so EasyEDA Pro "
            "imports the routing, and generates the import zip"
        )
        self.show_toolbar_button = True
        icon = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon):
            self.icon_file_name = icon

    def Run(self):
        board = pcbnew.GetBoard()
        src = board.GetFileName()
        if not src or not os.path.exists(src):
            _notify("Save the board before exporting.", error=True)
            return

        base = os.path.splitext(os.path.basename(src))[0]
        out_dir = os.path.join(os.path.dirname(src), "easyeda-import")

        try:
            text = open(src, encoding="utf-8").read()
            converted, nnets = convert_text(text)
        except Exception as exc:  # noqa: BLE001 - reported to the user
            _notify("Conversion error:\n%s" % exc, error=True)
            return

        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, base + ".kicad_pcb")
        with open(dst, "w", encoding="utf-8") as fh:
            fh.write(converted)

        zpath = os.path.join(out_dir, base + "-easyeda-import.zip")
        pro = os.path.splitext(src)[0] + ".kicad_pro"
        with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(dst, base + ".kicad_pcb")
            if os.path.exists(pro):
                z.write(pro, base + ".kicad_pro")

        _notify(
            "Conversion OK (%d nets renumbered).\n\n"
            "PCB: %s\nZip for EasyEDA Pro: %s\n\n"
            "Note: the last SAVED version of the board is converted."
            % (nnets, dst, zpath)
        )
