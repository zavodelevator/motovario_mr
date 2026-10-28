#!/usr/bin/env python3
"""Screenshots (desktop 1400 and mobile 390) of simple, advanced and KP views -> prototype/nmrv/shots/. Run: python3 test/nmrv/shots.py"""
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
URL = (ROOT / "prototype" / "nmrv" / "index.html").as_uri()
OUT = ROOT / "prototype" / "nmrv" / "shots"
OUT.mkdir(exist_ok=True)


def run(b, w, h, tag):
    ctx = b.new_context(viewport={"width": w, "height": h}, locale="uk-UA")
    page = ctx.new_page()
    page.goto(URL)
    page.fill("#s_kw", "1.1"); page.fill("#s_n2", "47")
    page.wait_for_selector("#s_table tbody tr")
    page.locator("#s_table tbody tr").first.click()
    page.wait_for_selector("#s_det")
    page.screenshot(path=str(OUT / ("%s_simple.png" % tag)), full_page=True)
    page.click("#s_add")
    page.click("#mode_adv")
    page.fill("#f_torque", "120"); page.fill("#f_n2", "47")
    page.click("#btn_select"); page.wait_for_selector("#results .ct tbody tr")
    page.screenshot(path=str(OUT / ("%s_advanced.png" % tag)), full_page=True)
    page.click("#btn_demo"); page.uncheck("#p_draft"); page.fill("[data-p=number]", "MV-2026-0001")
    page.click("#btn_save"); page.wait_for_selector("#saved_list tbody tr")
    page.locator("#sec-quote").screenshot(path=str(OUT / ("%s_quote_saved.png" % tag)))
    page.click("#btn_kp"); page.wait_for_selector(".page", timeout=60000)
    page.wait_for_function("()=>[...document.querySelectorAll('.page img')].every(i=>i.complete)")
    pages = page.locator(".page")
    for i in range(min(2, pages.count())):
        pages.nth(i).screenshot(path=str(OUT / ("%s_kp_page%d.png" % (tag, i + 1))))
    ov = page.evaluate("()=>document.documentElement.scrollWidth-window.innerWidth")
    print(tag, "horizontal overflow px:", ov)
    ctx.close()


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    run(b, 1400, 1000, "desktop")
    run(b, 390, 800, "m390")
    b.close()
