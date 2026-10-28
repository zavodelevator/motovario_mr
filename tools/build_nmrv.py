#!/usr/bin/env python3
"""Build the NMRV-only intermediate model: prototype/nmrv/data.json + a single self-contained index.html.

Run:  python3 -I tools/build_nmrv.py
Reuses the extraction helpers of tools/build_prototype_data.py (VSF prototype stays untouched), then:
  * keeps NMRV / NMRV-P gearmotor rows only (NRV / NRV-P reducer rows are dropped from the bundle);
  * joins the catalogue reducer Mn2 (NRV table, same size / n1 / i) onto each gearmotor row at build time
    (fields mn2_tab / mn2_tab_pg) so Mn2 stays exactly the same as in the VSF prototype without shipping NRV rows;
  * drops every NRV size from weights, radial loads, dimensions and images.
No catalogue value is invented; missing values stay null (and are hidden in the UI).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
import build_prototype_data as bpd  # noqa: E402
from PIL import Image  # noqa: E402

OUT = ROOT / "prototype" / "nmrv"
SRC = OUT / "src"
IMG = OUT / "img"
bpd.IMG = IMG


def is_nrv(key):
    return "NRV" in key


def build_ratings_nmrv():
    bpd.FAMILIES = ["NMRV", "NMRV-P", "NRV", "NRV-P"]
    allr = bpd.build_ratings()
    red = {}
    for r in allr:
        if r["kind"] == "red" and r["p1"] and r["p1"] > 0:
            red["%s|%s|%s" % (r["size"], r["n1"], round(r["i"], 2))] = r
    nom = {2: 2800, 4: 1400, 6: 900}
    out = []
    for r in allr:
        if r["kind"] != "gm" or r["fam"] not in ("NMRV", "NMRV-P"):
            continue
        n1nom = nom.get(r["poles"])
        hit = red.get("%s|%s|%s" % (r["size"].replace("NMRV", "NRV"), n1nom, round(r["i"], 2)))
        r["mn2_tab"] = hit["t2"] if hit else None
        r["mn2_tab_pg"] = hit["pg"] if hit else None
        out.append(r)
    return out


def build_images_nmrv():
    IMG.mkdir(parents=True, exist_ok=True)
    p18, p19 = "VSF_NMRV_render_p18_1.png", "VSF_NMRV-P_render_p19_1.png"
    crops = {
        "NMRV": (p18, (270, 195, 480, 405), "nmrv.png", 18),
        "NMRV_comb": (p18, (270, 795, 500, 1010), "nmrv_comb.png", 18),
        "NMRV-P": (p19, (290, 260, 460, 425), "nmrvp.png", 19),
        "NMRV-P_comb": (p19, (265, 875, 480, 1045), "nmrvp_comb.png", 19),
    }
    photos = {}
    for key, (src, box, dst, pg) in crops.items():
        info = bpd.crop(src, box, dst)
        info["pg"] = pg
        photos[key] = info
    drawings = {}
    for key, src, dst, pg, cap in [
        ("NMRV", "VSF_NMRV_drawing_p52_1.png", "dim_nmrv.png", 52, "NMRV / NMRV-P 030-150"),
        ("NMRV025", "VSF_NMRV025_drawing_p51_1.png", "dim_nmrv025.png", 51, "NMRV 025"),
    ]:
        im = Image.open(bpd.RAW / "images" / src).convert("RGB")
        if max(im.size) > 1600:
            im.thumbnail((1600, 1600))
        im.save(IMG / dst, optimize=True)
        drawings[key] = {"file": dst, "src": src, "pg": pg, "caption": cap}
    return {"photos": photos, "drawings": drawings}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in IMG.glob("*.png"):
        f.unlink()
    ratings = build_ratings_nmrv()
    bpd.FAMILIES = ["NMRV", "NMRV-P"]
    dims, bores = bpd.build_dims()
    dims = {k: v for k, v in dims.items() if not is_nrv(k)}
    bores = {k: v for k, v in bores.items() if not is_nrv(k)}
    weights = {k: [{kk: vv for kk, vv in e.items() if kk != "variant"} for e in v]   # "variant" is a catalogue column label (mentions NRV), unused by the engine
               for k, v in bpd.build_weights().items() if not is_nrv(k)}
    radial = [r for r in bpd.build_radial() if not is_nrv(r["size"])]
    flanges = {k: v for k, v in bpd.build_input_flanges().items() if not is_nrv(k)}
    data = {
        "meta": {
            "series": "NMRV",
            "catalogue": "Каталог Motovario VSF (NMRV / NMRV-P)",
            "source": "data/raw/VSF",
            "pdf_page_offset": 2,
            "n1_nominal": {"2": 2800, "4": 1400, "6": 900},
            "counts": {"gm": len(ratings), "red": 0},
        },
        "ratings": ratings,
        "motors": bpd.build_motors(),
        "motor_interface": bpd.build_interface(),
        "flange_matrix": bpd.build_matrix(),
        "weights": weights,
        "lubrication": bpd.build_lub(),
        "service_factor": bpd.build_sf(),
        "radial": radial,
        "efficiency": bpd.build_eff(),
        "dimensions": dims,
        "shaft_bores": bores,
        "motor_dims": bpd.build_motor_dims(),
        "input_flanges": flanges,
        "solid_shafts": bpd.build_solid_shafts(),
        "images": build_images_nmrv(),
    }
    blob = json.dumps(data, ensure_ascii=False)
    assert "NRV" not in blob, "NRV leaked into the NMRV bundle"
    (OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    tpl = (SRC / "template.html").read_text(encoding="utf-8")
    parts = {n: (SRC / n).read_text(encoding="utf-8") for n in ("kp.css", "words.js", "engine.js", "kp-template.js", "app.js", "model3d.js")}
    imgmap = {f.name: bpd.data_uri(f) for f in sorted(IMG.glob("*.png"))}
    vend = OUT / "vendor"
    vendor = {"three": bpd.esm_to_function_body((vend / "three.module.min.js").read_text(encoding="utf-8"), "three"),
              "orbit": bpd.esm_to_function_body((vend / "OrbitControls.js").read_text(encoding="utf-8"), "orbit")}

    def js_json(o):
        return json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

    def js(t):
        return t.replace("</script", "<\\/script")

    html = tpl
    html = html.replace("/*{{CSS}}*/", parts["kp.css"])
    html = html.replace("/*{{ENGINE}}*/", js(parts["words.js"]) + "\n" + js(parts["engine.js"]))
    html = html.replace("/*{{KPTEMPLATE}}*/", js(parts["kp-template.js"]))
    html = html.replace("/*{{MODEL3D}}*/", js(parts["model3d.js"]))
    html = html.replace("/*{{VENDOR}}*/", "window.NMRV_VENDOR=" + js_json(vendor).replace("<!--", "<\\!--") + ";")
    html = html.replace("/*{{APP}}*/", js(parts["app.js"]))
    html = html.replace("/*{{DATA}}*/", "window.NMRV_DATA=" + js_json(data) + ";")
    html = html.replace("/*{{IMG}}*/", "window.NMRV_IMG=" + js_json(imgmap) + ";")
    (OUT / "index.html").write_text(html, encoding="utf-8")
    print("data.json  %d KB" % (len((OUT / "data.json").read_bytes()) // 1024))
    print("index.html %d KB" % (len(html.encode()) // 1024))
    print("rows: gearmotor %d" % len(ratings))


if __name__ == "__main__":
    main()
