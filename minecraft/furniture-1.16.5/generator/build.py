"""Builds the resource pack (Minecraft Java 1.16.5) and preview images.

    python3 build.py            # all models
    python3 build.py furn_dresser_wood
"""
import json
import os
import sys
import zipfile

from PIL import Image

from models_furniture import MODELS
from render import render, sheet, slot_preview

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PACK = os.path.join(ROOT, "resourcepack")
PREV = os.path.join(ROOT, "previews")
DIST = os.path.join(ROOT, "dist")
PACK_NAME = "zona_furniture_1.16.5"


def write_pack_meta(icon=None):
    os.makedirs(PACK, exist_ok=True)
    meta = {"pack": {"pack_format": 6, "description": "§6Zona furniture §7(1.16.5)"}}
    with open(os.path.join(PACK, "pack.mcmeta"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    if icon is not None:
        icon.convert("RGBA").resize((128, 128), Image.LANCZOS).save(os.path.join(PACK, "pack.png"))


def write_overrides():
    """1.16.5 way of adding custom models: overrides with custom_model_data on paper."""
    ov = [{"predicate": {"custom_model_data": cmd}, "model": f"zona_item:item/{name}"}
          for name, (_, cmd, _) in sorted(MODELS.items(), key=lambda kv: kv[1][1])]
    data = {"parent": "minecraft:item/generated", "textures": {"layer0": "minecraft:item/paper"}, "overrides": ov}
    path = os.path.join(PACK, "assets", "minecraft", "models", "item")
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, "paper.json"), "w", encoding="utf-8") as fh:
        fh.write("{\n")
        fh.write('\t"parent": "minecraft:item/generated",\n')
        fh.write('\t"textures": {"layer0": "minecraft:item/paper"},\n')
        fh.write('\t"overrides": [\n')
        for i, o in enumerate(ov):
            fh.write("\t\t" + json.dumps(o) + ("," if i < len(ov) - 1 else "") + "\n")
        fh.write("\t]\n}\n")
    return data


def build_one(name):
    fn, cmd, title = MODELS[name]
    m = fn()
    m.build()
    m.auto_display()
    m.write(PACK)
    os.makedirs(PREV, exist_ok=True)
    gui = m.display["gui"]["rotation"]
    views = [
        render(m, rotation=gui, size=420),
        render(m, rotation=(20, 155, 0), size=420),
        render(m, rotation=(10, 180, 0), size=420),
        render(m, rotation=(30, 30, 0), size=420),
    ]
    sh = sheet(views, 4)
    sh.save(os.path.join(PREV, f"{name}.png"))
    views[0].save(os.path.join(PREV, f"{name}_gui.png"))
    slot_preview(m).save(os.path.join(PREV, f"{name}_slot.png"))
    print(f"{name}: {len(m.elements)} elements, texture {m.S}x{m.S}, CMD {cmd} ({title})")
    return m, views[0]


def make_zip():
    os.makedirs(DIST, exist_ok=True)
    out = os.path.join(DIST, PACK_NAME + ".zip")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for base, _, files in os.walk(PACK):
            for f in sorted(files):
                full = os.path.join(base, f)
                z.write(full, os.path.relpath(full, PACK))
    return out


def main(argv):
    names = argv or list(MODELS)
    icon = None
    for n in names:
        _, gui = build_one(n)
        icon = icon or gui
    write_pack_meta(icon)
    write_overrides()
    print("zip:", make_zip())


if __name__ == "__main__":
    main(sys.argv[1:])
