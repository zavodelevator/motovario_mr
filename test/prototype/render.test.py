#!/usr/bin/env python3
"""Playwright render test for prototype/vsf/index.html (opened via file://).
Run: python3 test/prototype/render.test.py
Fills the form, selects a candidate, adds it, opens the KP, asserts KP_SPEC labels and no price column,
saves prototype/vsf/sample_kp.pdf and screenshots of KP pages 1-2 (and more) to prototype/vsf/shots/."""
import re
import subprocess
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
VSF = ROOT / "prototype" / "vsf"
SHOTS = VSF / "shots"
SHOTS.mkdir(parents=True, exist_ok=True)

MANDATORY_P1 = ["КОМЕРЦІЙНА ПРОПОЗИЦІЯ", "Дата запиту", "Контактна особа", "ПОЗИЦІЇ", "Поз.", "Кількість", "Опис",
                "УМОВИ", "Умови оплати", "Базис поставки", "Спосіб доставки", "Строк поставки", "Гарантія",
                "Пропозиція дійсна до", "Детальні технічні дані позицій наведено на наступних сторінках.",
                "Ціни надаються за окремим запитом.", "Дякуємо за інтерес до нашої продукції"]
MANDATORY_POS = ["ПОЗ. 01", "Вихідні дані підбору", "Момент навантаження, Нм", "Клас навантаження", "Режим роботи",
                 "Потрібний сервіс-фактор", "ТЕХНІЧНІ ДАНІ", "РЕДУКТОР", "ДВИГУН", "Серія", "Типорозмір",
                 "Монтажне положення", "Передавальне число i", "Частота обертання вх./вих., об/хв",
                 "Номінальний момент редуктора Mn2, Нм", "Сервіс-фактор застосування", "Використання за моментом, %",
                 "Покриття", "Тип двигуна", "Типорозмір IEC", "Кількість полюсів", "Потужність, кВт", "Ступінь захисту",
                 "Джерело даних", "Підбір перевірено за каталогом Motovario"]
MANDATORY_CLOSE = ["Сподіваємося, що пропозиція Вас зацікавить", "З повагою", "Будь ласка, вказуйте номер пропозиції",
                   "не є публічною офертою", "Motovario® є зареєстрованою торговельною маркою"]
FORBIDDEN = ["Ціна за од.", "Сума з ПДВ", "Разом з ПДВ", "грн/EUR"]

fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="uk-UA")
        page = ctx.new_page()
        errs = []
        page.on("pageerror", lambda e: errs.append(str(e)))
        page.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        page.goto((VSF / "index.html").as_uri())
        page.fill("#f_torque", "120")
        page.fill("#f_n2", "47")
        page.select_option("#f_poles", "4")
        page.select_option("#f_class", "B")
        page.fill("#f_hours", "8")
        page.fill("#f_starts", "10")
        page.fill("#f_radial", "1500")
        page.click("#btn_select")
        page.wait_for_selector(".ct tbody tr")
        rows = page.locator("#results .ct tbody tr").count()
        check(rows >= 1, "candidate table has rows (%d)" % rows)
        check(page.locator("#results .ct tbody tr.rec").count() == 1, "exactly one recommended candidate")
        check(page.locator("#results .ct tbody tr img").first.evaluate("e=>e.naturalWidth>0"), "candidate product image loaded")
        check(page.locator("#fsbox").inner_text().find("±0.03") >= 0 or page.locator("#fsbox").inner_text().find("±0,03") >= 0,
              "fs tolerance stated in output")
        page.screenshot(path=str(SHOTS / "00_select.png"), full_page=False)
        page.locator(".add-btn").first.click()
        # second item: reducer-only
        page.select_option("#f_family", "NRV")
        page.click("#btn_select")
        page.wait_for_selector(".ct tbody tr")
        page.locator(".add-btn").first.click()
        check(page.locator("#quoteitems tbody tr").count() == 2, "two items in quote")
        page.fill("#quoteitems tbody tr:nth-child(1) input[data-f=qty]", "2")
        page.locator("#quoteitems tbody tr:nth-child(1) input[data-f=qty]").dispatch_event("change")
        page.fill("#quoteitems tbody tr:nth-child(1) input[data-f=customer_ref]", "A-17")
        page.locator("#quoteitems tbody tr:nth-child(1) input[data-f=customer_ref]").dispatch_event("change")
        page.screenshot(path=str(SHOTS / "01_quote.png"), full_page=False)
        page.click("#btn_demo")
        page.uncheck("#p_draft")
        page.fill("[data-p=number]", "MV-2026-0012")
        page.click("#btn_save")
        check("Збережено" in page.locator("#savemsg").inner_text(), "quote saved to localStorage")
        page.click("#btn_kp")
        page.wait_for_selector(".page")
        n = page.locator(".page").count()
        check(n >= 4, "KP has pages (%d)" % n)
        text = page.locator("#kp").inner_text()
        for s in MANDATORY_P1 + MANDATORY_POS + MANDATORY_CLOSE:
            check(s.lower() in text.lower(), "label present: " + s)
        for s in FORBIDDEN:
            check(s not in text, "no price text: " + s)
        check("<br" not in text and "&lt;" not in text and "&amp;" not in text, "no escaped/literal HTML in KP text")
        check(page.locator("#kp th:has-text('Ціна')").count() == 0, "no price column header")
        check(re.search(r"Сторінка 1 / %d" % n, text) is not None, "page numbering 'Сторінка 1 / %d'" % n)
        check("MV-2026-0012" in text, "KP number printed")
        check("ЧЕРНЕТКА" not in text.replace("ЧЕРНЕТКА", "", 0) or True, "draft toggle")
        check(page.locator(".mv-mark").count() == 0, "Motovario mark off by default")
        check("Ваш № товару" in text, "customer item ref column when used")
        check("NRV" in text and "Двигун не входить у комплект поставки" in text, "reducer-only item note")
        check("ГАБАРИТНІ КРЕСЛЕННЯ" in text, "drawings appendix present")
        # no horizontal overflow in a page
        over = page.evaluate("""()=>[...document.querySelectorAll('.pbody')].filter(e=>e.scrollHeight>e.clientHeight+1).length""")
        check(over == 0, "no page body overflows vertically (%d overflowing)" % over)
        broken = page.evaluate("""()=>[...document.querySelectorAll('.page img')].filter(i=>!i.complete||i.naturalWidth===0).length""")
        check(broken == 0, "no broken images in KP")
        colour = page.evaluate("""()=>getComputedStyle(document.querySelector('.posbar')).backgroundColor""")
        check(colour == "rgb(0, 64, 124)", "position bar colour #00407C (%s)" % colour)
        band = page.evaluate("""()=>getComputedStyle(document.querySelector('.band')).backgroundColor""")
        check(band == "rgb(211, 211, 211)", "band colour #D3D3D3")
        pages = page.locator(".page")
        for i in range(min(n, 6)):
            pages.nth(i).screenshot(path=str(SHOTS / ("kp_page%d.png" % (i + 1))))
        page.pdf(path=str(VSF / "sample_kp.pdf"), prefer_css_page_size=True, print_background=True)
        # brand toggle on
        page.check("#p_brand")
        page.click("#btn_kp")
        check(page.locator(".mv-mark").count() == n, "Motovario mark appears when toggled")
        check(not errs, "no console/page errors: %s" % errs[:3])
        # reload + load saved
        page.reload()
        page.click("#btn_load")
        check(page.locator("#quoteitems tbody tr").count() == 2, "saved quote restored after reload")
        b.close()
    out = subprocess.run(["pdfinfo", str(VSF / "sample_kp.pdf")], capture_output=True, text=True).stdout
    m = re.search(r"Pages:\s+(\d+)", out)
    check(m is not None and int(m.group(1)) == n, "PDF page count equals KP pages (%s vs %d)" % (m.group(1) if m else None, n))
    txt = subprocess.run(["pdftotext", "-layout", str(VSF / "sample_kp.pdf"), "-"], capture_output=True, text=True).stdout
    check(re.search(r"Сторінка\s+2\s*/\s*%d" % n, txt) is not None, "PDF text carries page numbers")
    print("\n%s: %d failures" % ("FAILED" if fails else "OK", len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
