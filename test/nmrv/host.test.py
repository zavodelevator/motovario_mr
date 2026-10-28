#!/usr/bin/env python3
"""Playwright test: CalcHost adapter swap, price handling and saved quotes. Run: python3 test/nmrv/host.test.py
All customer/seller/price data below is FAKE and lives only in this test."""
import re
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent.parent
URL = (ROOT / "prototype" / "nmrv" / "index.html").as_uri()
fails = []


def check(cond, msg):
    print(("PASS " if cond else "FAIL ") + msg)
    if not cond:
        fails.append(msg)


FAKE_HOST = """
window.__saved = []; window.__payloads = []; window.__calls = [];
window.CalcHostOverride = {
  getSeller: () => ({ name: 'ТОВ «Фейк-Продавець»', short_name: 'Фейк-Продавець', edrpou: '99999999' }),
  getManager: () => ({ name: 'Фейк Менеджер', position: 'менеджер', email: 'm@example.invalid' }),
  getCustomerCandidates: () => [{ company: { code: 'C-1', name: 'ТОВ «Фейк-Клієнт»', edrpou: '88888888', address: 'м. Тест' }, person: { name: 'Петро Фейк', honorific: 'Пан', phone: '+380000000000', email: 'p@example.invalid' } }],
  getFxRate: () => 40,
  getPrice: (key) => { window.__calls.push(key); return { purchase_eur: 100, margin_pct: 10 }; },
  saveQuote: (q) => { window.__payloads.push(JSON.parse(JSON.stringify(q))); const c = JSON.parse(JSON.stringify(q)); c.id = 'crm-77'; window.__saved = window.__saved.filter(x => x.id !== c.id).concat([c]); return Promise.resolve({ id: 'crm-77' }); },
  loadQuotes: () => Promise.resolve(window.__saved.slice()),
  deleteQuote: (id) => { window.__saved = window.__saved.filter(x => x.id !== id); return Promise.resolve(); },
  exportPdf: (q) => { window.__pdf = q; return Promise.resolve(); }
};
"""


def add_first_candidate(page):
    page.fill("#s_kw", "1.1")
    page.fill("#s_n2", "47")
    page.wait_for_selector("#s_table tbody tr")
    page.locator("#s_table tbody tr").first.click()
    page.click("#s_add")


def fake_host_checks(b):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="uk-UA")
    ctx.add_init_script(FAKE_HOST)
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL)
    check(page.input_value("[data-p=seller_name]") == "ТОВ «Фейк-Продавець»", "seller prefilled from host.getSeller()")
    check(page.input_value("[data-p=mgr_name]") == "Фейк Менеджер", "manager prefilled from host.getManager()")
    check(page.input_value("#p_fx") == "40", "fx field prefilled from host.getFxRate()")
    check(page.locator("#cust_pick option").count() == 2, "customer picker lists host.getCustomerCandidates()")
    page.select_option("#cust_pick", "0")
    check(page.input_value("[data-p=customer_name]") == "ТОВ «Фейк-Клієнт»" and page.input_value("[data-p=contact_name]") == "Петро Фейк"
          and page.input_value("[data-p=customer_edrpou]") == "88888888", "picking a candidate fills Company + Person fields")
    add_first_candidate(page)
    check(page.locator("#quoteitems thead th:has-text('Ціна')").count() == 1, "price column appears in the quote table when host gives prices")
    keys = page.evaluate("()=>window.__calls")
    check(len(keys) > 0 and all(re.match(r"^NMRV(-P)?\\|NMRV(-P)?\\d{3}\\|i[\\d.]+\\|", k) for k in keys), "getPrice() asked with articleKey strings: %s" % keys[:1])
    page.fill("#quoteitems tbody tr input[data-f=qty]", "3")
    page.locator("#quoteitems tbody tr input[data-f=qty]").dispatch_event("change")
    page.click("#btn_save")
    page.wait_for_function("()=>window.__payloads.length===1")
    q = page.evaluate("()=>window.__payloads[0]")
    check(q["schema"] == "motovario_nmrv_quote/1" and q["currency"] == "UAH" and q["vat_pct"] == 20, "saveQuote payload: schema/currency/vat")
    check(q["priced"] is True and q["fx_eur_uah"] == 40, "payload priced with fx 40")
    it = q["items"][0]
    check(it["qty"] == 3 and it["price"]["unit_gross_uah"] % 3 == 0 and it["price"]["unit_gross_uah"] > 0, "item price is whole UAH divisible by 3 (%s)" % it["price"]["unit_gross_uah"])
    check(it["price"]["unit_gross_uah"] == 5280, "fixture 100 EUR +10 % x 40 x 1.2 = 5280")
    check(q["totals"]["gross_uah"] == 5280 * 3 and abs(q["totals"]["net_uah"] + q["totals"]["vat_uah"] - q["totals"]["gross_uah"]) < 0.005, "totals gross/net/vat consistent")
    check(q["customer"]["name"] == "ТОВ «Фейк-Клієнт»" and q["contact"]["name"] == "Петро Фейк" and q["seller"]["edrpou"] == "99999999", "payload carries customer, contact, seller")
    check(set(["request", "candidate", "tech", "article_key", "designation"]).issubset(it.keys()), "item carries request + candidate + tech snapshot")
    stored = page.evaluate("()=>{try{return localStorage.getItem('nmrv_quotes_v1')}catch(e){return 'x'}}")
    check(stored is None, "default localStorage store untouched when the host is replaced")
    check(page.evaluate("()=>window.__nmrv.state.quoteId") == "crm-77", "id returned by the host is adopted")
    check(page.locator("#saved_list tbody tr").count() == 1, "saved list comes from host.loadQuotes()")
    page.click("#btn_kp")
    page.wait_for_selector(".page", timeout=60000)
    text = page.locator("#kp").inner_text()
    for s in ["Ціна за од. з ПДВ, грн", "Сума з ПДВ, грн", "Разом з ПДВ, грн", "у т.ч. ПДВ 20 %, грн", "Разом без ПДВ, грн", "грн/EUR"]:
        check(s in text, "priced KP shows: " + s)
    check("Ціни надаються за окремим запитом" not in text, "no 'prices on request' note when priced")
    check("Всього до сплати:" in text and "гривень 00 копійок" in text, "priced KP shows amount in words")
    check("15" in text.replace("\\u202f", "").replace(" ", "") and "840,00" in text, "line total 15 840,00 printed")
    page.click("#btn_print")
    page.wait_for_function("()=>!!window.__pdf")
    check(page.evaluate("()=>window.__pdf.items.length") == 1, "exportPdf(quoteJson) called through the host")
    # delete through the host
    page.once("dialog", lambda d: d.accept())
    page.locator("#saved_list .sv-del").first.click()
    page.wait_for_function("()=>window.__saved.length===0")
    check(page.locator("#saved_list tbody tr").count() == 0, "delete goes through host.deleteQuote()")
    check(not errs, "no page errors: %s" % errs[:2])
    ctx.close()


def stub_host_checks(b):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="uk-UA")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL)
    page.fill("#p_fx", "41.5")
    add_first_candidate(page)
    check(page.locator("#quoteitems thead th:has-text('Ціна')").count() == 0, "stub getPrice()=null: no price column even with fx set")
    page.click("#btn_kp")
    page.wait_for_selector(".page", timeout=60000)
    text = page.locator("#kp").inner_text()
    check("Ціни надаються за окремим запитом." in text and "Сума з ПДВ" not in text and "Разом з ПДВ" not in text and "грн/EUR" not in text, "stub: KP unpriced, note printed, no price text")
    check("Всього до сплати" not in text, "stub: no amount in words when unpriced")
    q = page.evaluate("()=>window.__nmrv.collectQuote()")
    check(q["priced"] is False and q["totals"] is None and q["items"][0]["price"] is None, "stub: quote JSON priced=false, totals null")
    ctx.close()


def saved_quotes_checks(b):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="uk-UA")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL)
    check(page.locator("#saved_list tbody tr").count() == 0 and page.inner_text("#saved_n") == "0", "no saved quotes initially")
    page.fill("[data-p=customer_name]", "ТОВ «Тест-1»")
    page.fill("[data-p=seller_name]", "ТОВ «Тест-Продавець»")
    add_first_candidate(page)
    page.click("#btn_save")
    page.wait_for_selector("#saved_list tbody tr")
    check(page.locator("#saved_list tbody tr").count() == 1 and "Тест-1" in page.locator("#saved_list").inner_text(), "save adds a row with the customer name")
    id1 = page.evaluate("()=>window.__nmrv.state.quoteId")
    page.click("#btn_save")   # save again = update, not a second row
    page.wait_for_timeout(300)
    check(page.locator("#saved_list tbody tr").count() == 1, "saving the same quote again updates it (still 1 row)")
    page.locator("#saved_list .sv-dup").first.click()
    page.wait_for_function("()=>document.querySelectorAll('#saved_list tbody tr').length===2")
    check(page.locator("#saved_list tbody tr").count() == 2, "duplicate creates a second row")
    ids = page.evaluate("()=>window.__nmrv.CalcHost.loadQuotes().then(l=>l.map(x=>x.id))")
    check(len(set(ids)) == 2, "duplicate has a new id")
    dup = page.evaluate("()=>window.__nmrv.CalcHost.loadQuotes().then(l=>l.find(x=>x.id!==window.__nmrv.state.quoteId))")
    check(dup["draft"] is True and dup["number"] is None and len(dup["items"]) == 1, "duplicate is a draft without a number, items kept")
    # new quote, then open the first one
    page.click("#btn_new")
    check(page.locator("#quoteitems tbody tr").count() == 0 and page.input_value("[data-p=customer_name]") == "", "new quote clears items and customer")
    check(page.input_value("[data-p=seller_name]") == "ТОВ «Тест-Продавець»", "new quote keeps the seller")
    page.locator("#saved_list tr[data-qid='%s'] .sv-open" % id1).click()
    check(page.locator("#quoteitems tbody tr").count() == 1 and page.input_value("[data-p=customer_name]") == "ТОВ «Тест-1»", "open restores items and parties")
    page.click("#btn_kp")
    page.wait_for_selector(".page", timeout=60000)
    check("ПОЗ. 01" in page.locator("#kp").inner_text(), "KP renders from a restored quote")
    # persistence across reload
    page.reload()
    page.wait_for_selector("#saved_list tbody tr")
    check(page.locator("#saved_list tbody tr").count() == 2, "saved quotes survive reload")
    check(page.locator("#cust_pick option").count() == 2, "customer picker offers the saved customer (standalone getCustomerCandidates)")
    check(page.input_value("[data-p=seller_name]") == "ТОВ «Тест-Продавець»", "seller profile remembered by the standalone host")
    # delete (dismiss first, then accept)
    page.once("dialog", lambda d: d.dismiss())
    page.locator("#saved_list .sv-del").first.click()
    check(page.locator("#saved_list tbody tr").count() == 2, "delete dismissed: nothing removed")
    page.once("dialog", lambda d: d.accept())
    page.locator("#saved_list .sv-del").first.click()
    page.wait_for_function("()=>document.querySelectorAll('#saved_list tbody tr').length===1")
    check(page.locator("#saved_list tbody tr").count() == 1, "delete removes a row")
    check(not errs, "no page errors: %s" % errs[:2])
    ctx.close()


def no_storage_checks(b):
    ctx = b.new_context(viewport={"width": 1400, "height": 1000}, locale="uk-UA")
    ctx.add_init_script("Object.defineProperty(window,'localStorage',{get(){throw new Error('blocked')}});")
    page = ctx.new_page()
    errs = []
    page.on("pageerror", lambda e: errs.append(str(e)))
    page.goto(URL)
    add_first_candidate(page)
    check(page.locator("#quoteitems tbody tr").count() == 1, "storage blocked: calculator still works")
    page.click("#btn_save")
    page.wait_for_function("()=>document.querySelector('#savemsg').textContent.length>0")
    check("Не вдалося зберегти" in page.inner_text("#savemsg"), "storage blocked: save reports an error instead of crashing")
    check(not errs, "no uncaught page errors: %s" % errs[:2])
    ctx.close()


def main():
    with sync_playwright() as p:
        b = p.chromium.launch()
        fake_host_checks(b)
        stub_host_checks(b)
        saved_quotes_checks(b)
        no_storage_checks(b)
        b.close()
    print("\n%s: %d failures" % ("FAILED" if fails else "OK", len(fails)))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
