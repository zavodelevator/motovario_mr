'use strict';
// node --test test/nmrv/pricing.test.js
// Pricing rounding, price-hook semantics, quote JSON shape and the CalculationRecord mapping. Prices below are FAKE test fixtures.
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const NM = path.join(__dirname, '..', '..', 'prototype', 'nmrv');
const EN = require(path.join(NM, 'src', 'engine.js'));
const data = require(path.join(NM, 'data.json'));
const E = EN.createEngine(data);

const BASE = { load_class: 'B', hours_per_day: 8, starts_per_hour: 10, poles: 4, family: 'gm', load_torque_nm: 40, n2_rpm: 47, mounting_position: 'B3', output: 'hollow', version: 'foot', flange: 'any' };
function cands() { return E.select(BASE).candidates.slice(0, 2); }
function items() { return cands().map((c, i) => ({ cand: c, qty: i + 2, raw: BASE, req: E.normalise(BASE).req })); }

test('ceilTo3: result is always divisible by 3 and minimal', () => {
  assert.equal(EN.ceilTo3(122500), 122502);
  assert.equal(EN.ceilTo3(122502), 122502);
  assert.equal(EN.ceilTo3(1), 3);
  assert.equal(EN.ceilTo3(3), 3);
  for (let n = 1; n < 2000; n++) { const r = EN.ceilTo3(n); assert.equal(r % 3, 0); assert.ok(r >= n && r - n < 3); }
});

test('priceUnit: purchase * (1+margin) * fx * (1+VAT), ceil to whole UAH, then up to a multiple of 3', () => {
  let u = EN.priceUnit(100, { margin_pct: 10, fx: 40 });          // 5280 exactly
  assert.equal(u.unit_gross_uah, 5280);
  u = EN.priceUnit(123.45, { margin_pct: 0, fx: 41.5 });           // 6147.81 -> 6148 -> 6150
  assert.equal(u.unit_gross_uah, 6150);
  assert.equal(u.unit_net_kop, 512500);                            // 615000 / 1.2
  assert.equal(u.unit_vat_kop, 102500);
  assert.equal(u.unit_net_kop + u.unit_vat_kop, u.unit_gross_uah * 100);
  assert.equal(EN.priceUnit(100, { fx: 40 }).unit_gross_uah, 4800); // float noise (4800.000000000001) must not push to 4803
});

test('priceUnit: invalid inputs give null (no price, never NaN)', () => {
  assert.equal(EN.priceUnit(0, { fx: 40 }), null);
  assert.equal(EN.priceUnit(100, { fx: 0 }), null);
  assert.equal(EN.priceUnit(100, {}), null);
  assert.equal(EN.priceUnit(-5, { fx: 40 }), null);
});

test('priceItems: the stub host (getPrice -> null) leaves the quote unpriced', () => {
  const r = EN.priceItems(items(), () => null, 40);
  assert.equal(r.priced, false); assert.equal(r.totals, null); assert.equal(r.fx, null);
  assert.ok(r.list.every(x => x === null));
});

test('priceItems: no fx -> unpriced even when prices exist', () => {
  assert.equal(EN.priceItems(items(), () => ({ purchase_eur: 100 }), null).priced, false);
  assert.equal(EN.priceItems(items(), () => ({ purchase_eur: 100 }), 0).priced, false);
});

test('priceItems: one position without a price -> whole quote unpriced (no half-priced KP)', () => {
  const its = items(); let n = 0;
  const r = EN.priceItems(its, () => (n++ === 0 ? { purchase_eur: 100 } : null), 40);
  assert.equal(r.priced, false); assert.equal(r.totals, null);
});

test('priceItems: fake fixture prices every position, lines and totals are consistent and divisible by 3 UAH', () => {
  const its = items();
  const fixture = { [EN.articleKey(its[0].cand)]: { purchase_eur: 100, margin_pct: 10 }, [EN.articleKey(its[1].cand)]: { purchase_eur: 123.45 } };
  const r = EN.priceItems(its, k => fixture[k] || null, 40);
  assert.equal(r.priced, true); assert.equal(r.fx, 40);
  r.list.forEach((u, ix) => {
    assert.equal(u.unit_gross_uah % 3, 0);
    assert.equal(u.line_gross_kop, u.unit_gross_uah * 100 * its[ix].qty);
    assert.equal((u.line_gross_kop / 100) % 3, 0, 'line stays divisible by 3 UAH');
  });
  const g = r.list.reduce((a, u) => a + u.line_gross_kop, 0);
  assert.equal(r.totals.gross_kop, g);
  assert.equal(r.totals.net_kop + r.totals.vat_kop, g);
  assert.ok(Math.abs(r.totals.vat_kop - g * 0.2 / 1.2) <= its.length + 1, 'VAT ~ gross/6');
});

test('articleKey: stable, unique per candidate, built from catalogue identity only', () => {
  const cs = E.select(BASE).candidates;
  const keys = cs.map(EN.articleKey);
  assert.equal(new Set(keys).size, keys.length);
  keys.forEach(k => assert.match(k, /^NMRV(-P)?\|NMRV(-P)?\d{3}\|i[\d.]+\|(single|comb)\|/));
  assert.equal(EN.articleKey(cs[0]), EN.articleKey(JSON.parse(JSON.stringify(cs[0]))));
});

const PARTIES = { seller_name: 'ТОВ «Тест»', seller_short: 'Тест', customer_name: 'ТОВ «Замовник»', customer_edrpou: '12345678', contact_name: 'Іван Тест', mgr_name: 'Менеджер',
  payment_terms: '100 %', incoterms: 'DAP', date: '2026-10-28', validity_days: '30', number: '', draft: true, brand: false };

test('buildQuote: documented shape (docs/NMRV_MODEL.md), unpriced', () => {
  const q = EN.buildQuote({ id: null, parties: PARTIES, items: items(), fx: null, pricing: EN.priceItems(items(), () => null, null) });
  assert.equal(q.schema, 'motovario_nmrv_quote/1');
  assert.equal(q.currency, 'UAH'); assert.equal(q.vat_pct, 20);
  assert.equal(q.priced, false); assert.equal(q.totals, null); assert.equal(q.fx_eur_uah, null);
  assert.equal(q.number, null); assert.equal(q.draft, true);
  ['seller', 'customer', 'contact', 'manager', 'terms'].forEach(k => assert.equal(typeof q[k], 'object'));
  assert.equal(q.customer.name, 'ТОВ «Замовник»');
  assert.equal(q.items.length, 2);
  q.items.forEach((i, ix) => {
    assert.equal(i.pos, ix + 1); assert.ok(i.qty >= 1); assert.ok(i.article_key); assert.ok(i.designation);
    assert.equal(typeof i.request, 'object'); assert.equal(typeof i.candidate, 'object'); assert.equal(i.price, null);
  });
  JSON.parse(JSON.stringify(q));
});

test('buildQuote: priced quote carries per-item prices and UAH totals (fake fixture)', () => {
  const its = items();
  const pr = EN.priceItems(its, () => ({ purchase_eur: 100, margin_pct: 10 }), 40);
  const q = EN.buildQuote({ id: 'q1', parties: PARTIES, items: its, fx: 40, pricing: pr });
  assert.equal(q.priced, true); assert.equal(q.fx_eur_uah, 40);
  assert.equal(q.items[0].price.unit_gross_uah, 5280);
  assert.equal(q.totals.gross_uah, 5280 * (2 + 3));
  assert.equal(q.totals.net_uah + q.totals.vat_uah, q.totals.gross_uah);
});

test('quoteToRecord: CalculationRecord fields (calc_type, description, params, result_data, price)', () => {
  const its = items();
  const unp = EN.quoteToRecord(EN.buildQuote({ parties: PARTIES, items: its, pricing: EN.priceItems(its, () => null, null) }));
  assert.deepEqual(Object.keys(unp).sort(), ['calc_type', 'description', 'params', 'price', 'result_data']);
  assert.equal(unp.calc_type, 'motovario_nmrv'); assert.equal(unp.price, null);
  assert.ok(unp.description.includes('NMRV'));
  assert.equal(unp.params.items.length, 2); assert.ok(unp.params.items[0].request && unp.params.items[0].article_key);
  assert.ok(!('candidate' in unp.params.items[0]), 'params = inputs only, results live in result_data');
  assert.equal(unp.result_data.items[0].designation, its[0].cand.designation);
  const pr = EN.priceItems(its, () => ({ purchase_eur: 100 }), 40);
  const priced = EN.quoteToRecord(EN.buildQuote({ parties: PARTIES, items: its, fx: 40, pricing: pr }));
  assert.equal(priced.price, 4800 * 5);
  assert.equal(priced.result_data.totals.gross_uah, priced.price);
});

test('partiesFromQuote is the inverse of the party part of buildQuote', () => {
  const q = EN.buildQuote({ parties: PARTIES, items: items(), pricing: EN.priceItems(items(), () => null, null) });
  const back = EN.partiesFromQuote(q);
  ['seller_name', 'seller_short', 'customer_name', 'customer_edrpou', 'contact_name', 'mgr_name', 'payment_terms', 'incoterms', 'date'].forEach(k => assert.equal(back[k], PARTIES[k], k));
  assert.equal(back.draft, true); assert.equal(back.validity_days, '30');
});
