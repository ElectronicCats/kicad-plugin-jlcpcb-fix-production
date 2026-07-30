#!/usr/bin/env python3
"""Build the PCM zip (KiCad Plugin and Content Manager, 'Install from File')."""
import json
import os
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_FILES = ["__init__.py", "easyeda_export_action.py", "kicad10_to_v8.py", "icon.png"]

version = json.load(open(os.path.join(HERE, "metadata.json")))["versions"][0]["version"]
out = os.path.join(HERE, "dist", "kicad-plugin-jlcpcb-fix-production-%s-pcm.zip" % version)
os.makedirs(os.path.dirname(out), exist_ok=True)

with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    z.write(os.path.join(HERE, "metadata.json"), "metadata.json")
    z.write(os.path.join(HERE, "resources", "icon.png"), "resources/icon.png")
    for f in PLUGIN_FILES:
        z.write(os.path.join(HERE, f), "plugins/" + f)

print(out)
