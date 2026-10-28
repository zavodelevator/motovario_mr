#!/usr/bin/env python3
"""Build the VSF prototype: data.json + img/ + a single self-contained index.html.

Run:  python3 -I tools/build_prototype_data.py
Reads data/raw/VSF/*, writes under prototype/vsf/ only.
No catalogue value is invented; missing values stay null (and are hidden in the UI).
"""
import base64
import csv
import json
import math
import os
import re
import sys
from pathlib import Path

import pandas as pd
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw" / "VSF"
OUT = ROOT / "prototype" / "vsf"
SRC = OUT / "src"
IMG = OUT / "img"

FAMILIES = ["NMRV", "NMRV-P", "NRV", "NRV-P"]


def nn(v):
    """pandas NaN -> None, numpy -> python."""
    if v is None:
        return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
        if isinstance(v, float) and math.isnan(v):
            return None
    return v


def num(v):
    v = nn(v)
    if v is None:
        return None
    f = float(v)
    return int(f) if f == int(f) and abs(f) < 1e9 else f


def read(name):
    return pd.read_csv(RAW / name, dtype=str, keep_default_na=False, na_values=[""])


def build_ratings():
    r = read("ratings.csv")
    r = r[r["family"].isin(FAMILIES)]
    rows = []
    for idx, x in r.iterrows():
        gm = x["variant"] == "gearmotor"
        rows.append({
            "id": int(idx),
            "kind": "gm" if gm else "red",
            "fam": x["family"],
            "cfg": x["config"],
            "size": x["size"],
            "n1": num(x["n1_rpm"]),
            "p1": num(x["p1_kw"]),
            "i": num(x["i"]),
            "n2": num(x["n2_rpm"]),
            "t2": num(x["t2_nm"]),
            "fs": num(x["fs"]),
            "fr2": num(x["fr2_n"]),
            "fr1": num(x["fr1_n"]),
            "mf": [int(t) for t in x["motor_frames"].split(";")] if nn(x["motor_frames"]) else None,
            "ms": nn(x["motor_size"]),
            "poles": num(x["poles"]),
            "n1i": num(x["n1_implied_rpm"]),
            "brk": 1 if nn(x["brake_motor_only"]) else 0,
            "pg": int(x["src_page"]),
        })
    return rows


def build_motors():
    m = read("motors.csv")
    out = []
    for _, x in m.iterrows():
        out.append({"type": x["motor_type"], "frame": x["frame"], "poles": num(x["poles"]),
                    "p": num(x["power_kw"]), "ie": nn(x["efficiency_class"]), "pg": int(x["src_page"])})
    return out


def build_interface():
    m = read("motor_interface.csv")
    out = {}
    for _, x in m.iterrows():
        out.setdefault(x["size"], []).append({
            "frame": x["iec_frame"], "flange": x["flange"], "bore": num(x["bore_mm"]),
            "N": num(x["N_mm"]), "M": num(x["M_mm"]), "P": num(x["P_mm"]), "pg": int(x["src_page"])})
    return out


def build_matrix():
    m = read("extra_motor_flange_ratio_matrix.csv")
    out = {}
    for _, x in m.iterrows():
        k = "%s|%s|%s" % (x["size"], x["iec_frame"], x["flange"])
        st = x["status"]
        code = {"feasible": "ok", "not feasible": "no", "not to be used (out of warranty)": "warn",
                "feasible (low profile key supplied)": "lowkey"}.get(st)
        if code is None:
            continue
        out.setdefault(k, {})["%g" % float(x["i"])] = code
    return out


def build_weights():
    w = read("weights.csv")
    out = {}
    for _, x in w.iterrows():
        out.setdefault(x["size"], []).append({"kg": num(x["mass_kg"]), "variant": x["variant"],
                                              "frame": nn(x["motor_frame"]), "pg": int(x["src_page"])})
    return out


def build_lub():
    w = read("lubrication.csv")
    out = {}
    for _, x in w.iterrows():
        out.setdefault(x["size"], {})[x["mounting_position"]] = {
            "l": num(x["oil_l"]), "type": x["oil_type"], "pg": int(x["src_page"])}
    return out


def build_sf():
    w = read("service_factor.csv")
    return [{"c": x["load_class"], "h": num(x["hours_per_day"]), "s": num(x["starts_per_hour"]),
             "fs": num(x["fs"]), "pg": int(x["src_page"])} for _, x in w.iterrows()]


def build_radial():
    w = read("radial_load_params.csv")
    return [{"size": x["size"], "shaft": x["shaft"], "a": num(x["a_mm"]), "b": num(x["b_mm"]),
             "frmax": num(x["fr_max_n"]), "pg": int(x["src_page"])} for _, x in w.iterrows()]


def build_eff():
    w = read("extra_mesh_efficiency.csv")
    out = {}
    for _, x in w.iterrows():
        k = x["size"].replace(" ", "")
        out.setdefault(k, {})["%g" % float(x["i"])] = {"dyn": num(x["eta_dyn_1400"]), "stat": num(x["eta_static"]),
                                                       "pg": int(x["src_page"])}
    return out


def build_dims():
    h = read("dimensions_housing.csv")
    h = h[h["variant"].isin(["NMRV", "NRV"])]
    out = {}
    for _, x in h.iterrows():
        d = {}
        for c in h.columns:
            if c in ("series", "size", "variant", "src_page"):
                continue
            v = nn(x[c])
            if v is None:
                continue
            if c == "G" and "PAM" in str(v):
                continue  # NMRV110 G has two values tied to PAM; do not guess (see notes.md)
            d[c.replace(" j6", "")] = v
        out[x["size"].replace(" ", "")] = {"variant": x["variant"], "dims": d, "pg": int(x["src_page"])}
    b = read("dimensions_shaft_bore.csv")
    bores = {}
    for _, x in b.iterrows():
        if x["variant"] not in ("NMRV", "NRV"):
            continue
        bores.setdefault(x["size"].replace(" ", ""), []).append(
            {"D": num(x["D H8"]), "b": num(x["b"]), "t": num(x["t"]), "pg": int(x["src_page"])})
    return out, bores


def build_solid_shafts():
    s = read("extra_low_speed_shafts.csv")
    return [{"size": x["size"], "variant": x["variant"], "d": x["d"], "B": x["B"], "L": x["L"], "pg": int(x["src_page"])}
            for _, x in s.iterrows()]


def crop(src_name, box, dst_name, scale=3):
    im = Image.open(RAW / "images" / src_name).convert("RGB")
    c = im.crop(box)
    c = c.resize((c.width * scale, c.height * scale), Image.LANCZOS)
    pad = 24
    canvas = Image.new("RGB", (c.width + 2 * pad, c.height + 2 * pad), "white")
    canvas.paste(c, (pad, pad))
    canvas.save(IMG / dst_name, optimize=True)
    return {"file": dst_name, "src": src_name, "w": canvas.width, "h": canvas.height}


def build_images():
    """Catalogue renders are montages (several units per PNG): crop single units out of
    p18 (NMRV) and p19 (NMRV-P). Series-level photos, no per-size photos exist in the catalogue."""
    IMG.mkdir(parents=True, exist_ok=True)
    p18 = "VSF_NMRV_render_p18_1.png"
    p19 = "VSF_NMRV-P_render_p19_1.png"
    crops = {
        "NMRV": (p18, (270, 195, 480, 405), "nmrv.png", 18),
        "NRV": (p18, (290, 515, 470, 690), "nrv.png", 18),
        "NMRV_comb": (p18, (270, 795, 500, 1010), "nmrv_comb.png", 18),
        "NRV_comb": (p18, (260, 1150, 460, 1355), "nrv_comb.png", 18),
        "NMRV-P": (p19, (290, 260, 460, 425), "nmrvp.png", 19),
        "NRV-P": (p19, (310, 575, 450, 725), "nrvp.png", 19),
        "NMRV-P_comb": (p19, (265, 875, 480, 1045), "nmrvp_comb.png", 19),
        "NRV-P_comb": (p19, (280, 1225, 465, 1370), "nrvp_comb.png", 19),
    }
    photos = {}
    for key, (src, box, dst, pg) in crops.items():
        info = crop(src, box, dst)
        info["pg"] = pg
        photos[key] = info
    drawings = {}
    for key, src, dst, pg, cap in [
        ("NMRV", "VSF_NMRV_drawing_p52_1.png", "dim_nmrv.png", 52, "NMRV / NMRV-P 030-150"),
        ("NMRV025", "VSF_NMRV025_drawing_p51_1.png", "dim_nmrv025.png", 51, "NMRV 025"),
        ("NRV", "VSF_NRV_drawing_p56_1.png", "dim_nrv.png", 56, "NRV / NRV-P 030-150"),
    ]:
        im = Image.open(RAW / "images" / src).convert("RGB")
        if max(im.size) > 1600:
            im.thumbnail((1600, 1600))
        im.save(IMG / dst, optimize=True)
        drawings[key] = {"file": dst, "src": src, "pg": pg, "caption": cap}
    # service-factor nomogram for reference in the UI
    im = Image.open(RAW / "images" / "VSF_general_diagram_p10_1.png").convert("RGB")
    im.save(IMG / "sf_nomogram.png", optimize=True)
    drawings["SF"] = {"file": "sf_nomogram.png", "src": "VSF_general_diagram_p10_1.png", "pg": 10,
                      "caption": "Діаграма сервіс-фактора"}
    return {"photos": photos, "drawings": drawings}


def data_uri(path):
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ratings = build_ratings()
    dims, bores = build_dims()
    data = {
        "meta": {
            "series": "VSF",
            "catalogue": "Каталог Motovario VSF (NMRV), 328 с. PDF",
            "edition": None,
            "source": "data/raw/VSF",
            "pdf_page_offset": 2,
            "n1_nominal": {"2": 2800, "4": 1400, "6": 900},
            "counts": {"gm": sum(1 for r in ratings if r["kind"] == "gm"),
                       "red": sum(1 for r in ratings if r["kind"] == "red")},
        },
        "ratings": ratings,
        "motors": build_motors(),
        "motor_interface": build_interface(),
        "flange_matrix": build_matrix(),
        "weights": build_weights(),
        "lubrication": build_lub(),
        "service_factor": build_sf(),
        "radial": build_radial(),
        "efficiency": build_eff(),
        "dimensions": dims,
        "shaft_bores": bores,
        "solid_shafts": build_solid_shafts(),
        "images": build_images(),
    }
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    # ---- inline everything into index.html
    tpl = (SRC / "template.html").read_text(encoding="utf-8")
    css = (SRC / "kp.css").read_text(encoding="utf-8")
    engine = (SRC / "engine.js").read_text(encoding="utf-8")
    app = (SRC / "app.js").read_text(encoding="utf-8")
    imgmap = {}
    for f in sorted(IMG.glob("*.png")):
        imgmap[f.name] = data_uri(f)

    def js_json(o):
        return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    html = tpl
    html = html.replace("/*{{CSS}}*/", css)
    html = html.replace("/*{{ENGINE}}*/", engine.replace("</script", "<\\/script"))
    html = html.replace("/*{{APP}}*/", app.replace("</script", "<\\/script"))
    html = html.replace("/*{{DATA}}*/", "window.VSF_DATA=" + js_json(data) + ";")
    html = html.replace("/*{{IMG}}*/", "window.VSF_IMG=" + js_json(imgmap) + ";")
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("data.json  %d KB" % (len((OUT / "data.json").read_bytes()) // 1024))
    print("index.html %d KB" % (len(html.encode()) // 1024))
    print("rows: gearmotor %d, reducer %d" % (data["meta"]["counts"]["gm"], data["meta"]["counts"]["red"]))


if __name__ == "__main__":
    sys.exit(main())
