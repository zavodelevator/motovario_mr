'use strict';
// node --test test/prototype/engine.test.js   (no dependencies; needs prototype/vsf/data.json from the build step)
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const VSF = path.join(__dirname, '..', '..', 'prototype', 'vsf');
const EN = require(path.join(VSF, 'src', 'engine.js'));
const data = require(path.join(VSF, 'data.json'));
const E = EN.createEngine(data);

const BASE = { load_class: 'B', hours_per_day: 8, starts_per_hour: 10, poles: 4, family: 'gm' };
const NOM = { 2: 2800, 4: 1400, 6: 900 };
function sel(o) { return E.select(Object.assign({}, BASE, o)); }

// deterministic PRNG
function lcg(seed) { let s = seed >>> 0; return () => ((s = (Math.imul(s, 1664525) + 1013904223) >>> 0) / 4294967296); }

test('data loaded and rows survive the data-defect filter', () => {
  assert.ok(data.ratings.length > 3000);
  assert.ok(E.rows.length > 3000);
  const dropRate = E.dropped.length / data.ratings.length;
  assert.ok(dropRate < 0.02, 'dropped ' + E.dropped.length + ' of ' + data.ratings.length);
  E.dropped.forEach(d => assert.ok(['n2_vs_n1_over_i', 'implied_n1_out_of_band', 'bad_row', 'no_mn2'].includes(d.reason)));
});

test('physical sanity: T2 ~ 9550*P/n2*eta for every ratings row used', () => {
  let robust = 0, all = 0;
  for (const r of E.rows) {
    if (!(r.p1 > 0)) continue;
    const eta = r.t2 * r.n2 / (9550 * r.p1);
    all++;
    assert.ok(eta > 0 && eta <= 1.0, `eta ${eta.toFixed(3)} out of (0,1] row ${r.id} ${r.size} i=${r.i} p1=${r.p1}`);
    // rounding-robust rows (Pn1 printed to 0.01 kW, n2 to 0.1 rpm): notes.md gate 2 => eta inside 0.3..0.95
    if (r.p1 >= 0.25 && r.n2 >= 5) {
      robust++;
      assert.ok(eta >= 0.3 && eta <= 0.95, `robust eta ${eta.toFixed(3)} row ${r.id} ${r.size} i=${r.i}`);
    }
  }
  assert.ok(robust > 1500 && all > robust);
});

test('n2 ~ n1/i for every row used (reducers 3 %, gearmotors within the slip band)', () => {
  let red = 0, gm = 0;
  for (const r of E.rows) {
    if (r.kind === 'red') {
      red++;
      if (r.n2 >= 5) assert.ok(Math.abs(r.n1 / r.i - r.n2) / r.n2 <= 0.03, `row ${r.id} ${r.size} i=${r.i}`);
    } else {
      gm++;
      if (r.n2 >= 10) { const q = r.n2 * r.i / NOM[r.poles]; assert.ok(q >= 0.85 && q <= 1.12, `row ${r.id}`); }
    }
  }
  assert.ok(red > 1500 && gm > 1500);
});

test('Mn2 matched from the reducer tables agrees with M2*fs within 15 %', () => {
  let t = 0, d = 0;
  for (const r of E.rows) {
    if (r.kind !== 'gm') continue;
    if (r.mn2_src === 'table') { t++; assert.ok(Math.abs(r.mn2 / (r.t2 * r.fs) - 1) <= 0.15); } else d++;
  }
  assert.ok(t > 1500, 'matched ' + t + ', derived ' + d);
});

test('fsLookup: grid points, interpolation, clamping, hour columns, errors', () => {
  const g = data.service_factor;
  const pt = (c, h, s) => g.find(x => x.c === c && x.h === h && x.s === s).fs;
  let r = E.fsLookup('B', 8, 10);
  assert.equal(r.fs_raw, pt('B', 8, 10));
  assert.equal(r.fs_lookup, 1.25);
  assert.equal(r.tolerance, 0.03);
  assert.match(r.note_uk, /±0\.03/);
  // starts below 5 clamp to 5
  assert.equal(E.fsLookup('B', 8, 1).fs_raw, pt('B', 8, 5));
  assert.equal(E.fsLookup('B', 8, 0).fs_raw, pt('B', 8, 5));
  // between 10 and 20 -> linear
  const a = pt('B', 8, 10), b = pt('B', 8, 20);
  assert.ok(Math.abs(E.fsLookup('B', 8, 15).fs_raw - (a + b) / 2) < 1e-3);
  // exact top of chart
  assert.equal(E.fsLookup('C', 8, 100).fs_raw, pt('C', 8, 100));
  // hours: smallest tabulated column >= input
  assert.equal(E.fsLookup('A', 1, 5).hours_col, 2);
  assert.equal(E.fsLookup('A', 2, 5).hours_col, 2);
  assert.equal(E.fsLookup('A', 2.5, 5).hours_col, 8);
  assert.equal(E.fsLookup('A', 9, 5).hours_col, 16);
  assert.equal(E.fsLookup('A', 24, 5).hours_col, 24);
  // monotone in class, hours and starts
  for (const h of [2, 8, 16, 24]) for (const s of [5, 12, 37, 100]) {
    assert.ok(E.fsLookup('A', h, s).fs_raw <= E.fsLookup('B', h, s).fs_raw);
    assert.ok(E.fsLookup('B', h, s).fs_raw <= E.fsLookup('C', h, s).fs_raw);
  }
  // rounding is upward to 0.05
  for (const c of 'ABC') for (const s of [5, 7, 33, 61, 99]) {
    const q = E.fsLookup(c, 8, s);
    assert.ok(q.fs_lookup >= q.fs_raw - 1e-9 && q.fs_lookup - q.fs_raw < 0.05 + 1e-9);
    assert.ok(Math.abs(q.fs_lookup * 20 - Math.round(q.fs_lookup * 20)) < 1e-9);
  }
  // errors
  assert.ok(E.fsLookup('B', 8, 101).error);
  assert.ok(E.fsLookup('B', 25, 10).error);
  assert.ok(E.fsLookup('B', 0, 10).error);
  assert.ok(E.fsLookup('D', 8, 10).error);
});

test('manual fs: raises, ignored when lower, replaces with fs_override', () => {
  const base = sel({ load_torque_nm: 50, n2_rpm: 47 });
  assert.equal(base.fs.fs_req, 1.25);
  assert.equal(sel({ load_torque_nm: 50, n2_rpm: 47, fs_min: 1.6 }).fs.fs_req, 1.6);
  assert.equal(sel({ load_torque_nm: 50, n2_rpm: 47, fs_min: 1.0 }).fs.fs_req, 1.25);
  const o = sel({ load_torque_nm: 50, n2_rpm: 47, fs_min: 1.0, fs_override: true });
  assert.equal(o.fs.fs_req, 1.0);
  assert.ok(o.warnings.includes('fs_overridden'));
  assert.ok(sel({ load_torque_nm: 50, n2_rpm: 47, fs_min: 5 }).errors.length);
});

test('validation: required fields and ranges', () => {
  assert.ok(sel({}).errors.length >= 2);
  assert.ok(sel({ load_torque_nm: -1, n2_rpm: 47 }).errors.some(e => e.code === 'torque_range'));
  assert.ok(sel({ load_torque_nm: 10, n2_rpm: 1400, poles: 4 }).errors.some(e => e.code === 'n2_ge_n1'));
  assert.ok(sel({ load_torque_nm: 10, n2_rpm: 47, ratio: 10 }).errors.some(e => e.code === 'n2_ratio_mismatch'));
  assert.ok(sel({ load_torque_nm: 100, load_power_kw: 2, n2_rpm: 47 }).errors.some(e => e.code === 'tp_mismatch'));
  assert.ok(sel({ load_torque_nm: 10, n2_rpm: 47, starts_per_hour: 120 }).errors.length);
});

test('selection monotonicity: a bigger load never yields a smaller recommended size', () => {
  let checked = 0;
  for (const poles of [2, 4, 6]) for (const fam of ['gm', 'NMRV-P', 'NRV']) {
    const rnd = lcg(poles * 7 + fam.length);
    const n2 = [14, 23, 47, 93, 140, 9.3][Math.floor(rnd() * 6)] * (poles === 2 ? 2 : poles === 6 ? 0.64 : 1);
    let prev = 0, none = false;
    for (let T = 2; T <= 900; T *= 1.35) {
      const r = sel({ poles, family: fam, load_torque_nm: T, n2_rpm: n2 });
      if (r.no_candidate) { none = true; continue; }
      assert.ok(!none, 'candidates reappeared after no_candidate at T=' + T);
      const c = r.candidates[0];
      assert.ok(c.mn2_nm >= prev - 1e-9, `T=${T}: mn2 ${c.mn2_nm} < previous ${prev}`);
      prev = c.mn2_nm; checked++;
    }
  }
  assert.ok(checked > 40);
});

test('every returned candidate satisfies A4, A5, radial and carries src_page (random requests)', () => {
  const rnd = lcg(12345);
  let reqs = 0, cands = 0;
  for (let k = 0; k < 150; k++) {
    const poles = [2, 4, 6][Math.floor(rnd() * 3)];
    const req = {
      poles, family: ['gm', 'NMRV', 'NMRV-P', 'NRV', 'any'][Math.floor(rnd() * 5)], load_class: 'ABC'[Math.floor(rnd() * 3)],
      hours_per_day: [2, 8, 16, 24][Math.floor(rnd() * 4)], starts_per_hour: 5 + Math.floor(rnd() * 90),
      load_torque_nm: Math.round(Math.exp(Math.log(2) + rnd() * Math.log(600)) * 10) / 10,
      n2_rpm: Math.round(NOM[poles] / [5, 7.5, 10, 15, 20, 30, 40, 60, 80, 100][Math.floor(rnd() * 10)])
    };
    if (rnd() < 0.3) req.radial_load_n = Math.round(rnd() * 3000);
    const r = E.select(req); reqs++;
    if (r.errors.length || r.no_candidate) continue;
    const T = r.request.T_load_nm;
    for (const c of r.candidates) {
      cands++;
      assert.ok(c.mn2_nm >= T * r.fs.fs_req - 0.05, 'A5 ' + c.designation);
      if (c.kind === 'gearmotor') assert.ok(c.m2_nm >= T - 1e-9, 'A4 ' + c.designation);
      assert.ok(c.fs_app >= r.fs.fs_req - 0.01, 'fs_app');
      assert.ok(Number.isInteger(c.src_page) && c.src_page > 0 && c.src_pages.includes(c.src_page));
      if (c.fr2_applied_n !== null) assert.ok(c.fr2_applied_n <= c.fr2_allowed_n + 1e-9, 'radial');
      assert.ok(c.utilisation_gear_pct <= 100.5);
      assert.equal(c.checks.gear_torque, 'pass');
    }
  }
  assert.ok(reqs === 150 && cands > 100, 'candidates checked: ' + cands);
});

test('negative mutation: x10 load changes the recommendation or yields no_candidate', () => {
  const rnd = lcg(99); let n = 0;
  for (let k = 0; k < 20; k++) {
    const T = 5 + rnd() * 60;
    const a = sel({ load_torque_nm: T, n2_rpm: 47 }), b = sel({ load_torque_nm: T * 10, n2_rpm: 47 });
    assert.ok(a.candidates.length);
    if (!b.candidates.length) { assert.ok(b.no_candidate); n++; continue; }
    assert.notEqual(b.candidates[0].designation, a.candidates[0].designation); n++;
  }
  assert.equal(n, 20);
});

test('no_candidate carries a reason and nearest rejected rows', () => {
  const r = sel({ load_torque_nm: 5000, n2_rpm: 47 });
  assert.ok(r.no_candidate && r.no_candidate.reason_uk.length > 10);
  assert.ok(r.no_candidate.nearest_rejected.length > 0 && r.no_candidate.nearest_rejected.length <= 3);
  assert.equal(r.candidates.length, 0);
});

test('ratio input vs speed input vs power input are equivalent for a catalogue row', () => {
  const row = E.rows.find(r => r.kind === 'gm' && r.size === 'NMRV-P075' && r.poles === 4 && r.i === 30 && r.p1 === 0.75);
  assert.ok(row, 'row exists');
  const T = 60;
  const byRatio = sel({ load_torque_nm: T, ratio: row.i });
  const bySpeed = sel({ load_torque_nm: T, n2_rpm: row.n2 });
  const nTarget = NOM[4] / row.i;
  const bySpeedNom = sel({ load_torque_nm: T, n2_rpm: nTarget });
  assert.equal(byRatio.request.n2_target_rpm, round3(nTarget));
  for (const r of [byRatio, bySpeed, bySpeedNom]) {
    assert.ok(r.candidates.some(c => c.size === row.size && c.i === row.i), 'row present');
  }
  assert.equal(byRatio.candidates[0].designation, bySpeedNom.candidates[0].designation);
  // power input: P = T*n2/9550 gives the same load
  const P = T * nTarget / 9550;
  const byPower = sel({ load_power_kw: P, n2_rpm: nTarget });
  assert.ok(Math.abs(byPower.request.T_load_nm - T) < 0.01);
  assert.equal(byPower.candidates[0].designation, bySpeedNom.candidates[0].designation);
  // both T and P given and consistent
  assert.equal(sel({ load_torque_nm: T, load_power_kw: P, n2_rpm: nTarget }).errors.length, 0);
});
function round3(x) { return Math.round(x * 1000) / 1000; }

test('deterministic ordering: repeated runs and shuffled input rows give identical output', () => {
  const req = { load_torque_nm: 45, n2_rpm: 47, family: 'any' };
  const a = JSON.stringify(sel(req)), b = JSON.stringify(sel(req));
  assert.equal(a, b);
  const shuffled = Object.assign({}, data, { ratings: data.ratings.slice().reverse() });
  const E2 = EN.createEngine(shuffled);
  const r2 = E2.select(Object.assign({}, BASE, req));
  assert.deepEqual(r2.candidates.map(c => c.designation), sel(req).candidates.map(c => c.designation));
  assert.deepEqual(r2.candidates.map(c => c.row_id), sel(req).candidates.map(c => c.row_id));
});

test('priceHook returns null (KP hides price columns)', () => {
  assert.equal(E.priceHook({}), null);
});

test('motor fit: gearmotor candidates carry frame, poles, power and a flange from motor_interface', () => {
  const r = sel({ load_torque_nm: 40, n2_rpm: 47 });
  const c = r.candidates[0];
  assert.ok(c.motor && c.motor.frame && c.motor.poles === 4 && c.motor.p_kw > 0);
  assert.ok(['B5', 'B14'].includes(c.motor.flange));
  const b14 = sel({ load_torque_nm: 40, n2_rpm: 47, flange: 'B14' });
  b14.candidates.forEach(x => assert.equal(x.motor.flange, 'B14'));
});

test('brake-only motors are excluded unless a brake is requested', () => {
  const brakeRows = E.rows.filter(r => r.brk);
  assert.ok(brakeRows.length > 0);
  const r = brakeRows[0];
  const T = Math.min(r.m2 * 0.9, r.mn2 / 1.25 * 0.9);
  const without = E.verify(Object.assign({}, BASE, { poles: r.poles, load_torque_nm: T, n2_rpm: r.n2, brake: false }), r.id);
  assert.ok(without.failures.includes('brake_only'));
  const withB = E.verify(Object.assign({}, BASE, { poles: r.poles, load_torque_nm: T, n2_rpm: r.n2, brake: true }), r.id);
  assert.ok(!withB.failures.includes('brake_only'));
});

test('manual override verify: passes for a good row, failed_overridden for an overloaded one', () => {
  const row = E.rows.find(r => r.kind === 'gm' && r.size === 'NMRV050' && r.poles === 4 && r.i === 20);
  const ok = E.verify(Object.assign({}, BASE, { load_torque_nm: 20, n2_rpm: row.n2 }), row.id);
  assert.ok(ok.candidate && ok.status !== 'failed_overridden', JSON.stringify(ok.failures));
  const bad = E.verify(Object.assign({}, BASE, { load_torque_nm: 2000, n2_rpm: row.n2 }), row.id);
  assert.equal(bad.status, 'failed_overridden');
  assert.ok(bad.failures.includes('gear_torque'));
  assert.ok(E.verify(BASE, -5).errors.length);
});

test('radial load check rejects an overload and applies Frx at distance x', () => {
  const ok = sel({ load_torque_nm: 40, n2_rpm: 47, radial_load_n: 500 });
  assert.ok(ok.candidates.length);
  const huge = sel({ load_torque_nm: 40, n2_rpm: 47, radial_load_n: 90000 });
  assert.ok(huge.no_candidate);
  const mid = sel({ load_torque_nm: 40, n2_rpm: 47, radial_load_n: 1000 }).candidates[0];
  const atX = sel({ load_torque_nm: 40, n2_rpm: 47, radial_load_n: 1000, radial_x_mm: 60 }).candidates[0];
  assert.ok(atX.fr2_allowed_n < mid.fr2_allowed_n || atX.size !== mid.size);
  assert.ok(mid.warnings.includes('fr_mid_shaft_only'));
});

// ---------------------------------------------------------------- golden cases derived from catalogue rows
// For a catalogue row r: T = floor(min(M2, Mn2/fs_req)) is the largest load it carries. The case is "golden" when no
// row of a smaller size (same family, same poles, n2 within 5 %) can carry that T; then r's size must be recommended.
function capacity(r, fsReq) { return Math.min(r.kind === 'gm' ? r.m2 : Infinity, r.mn2 / fsReq); }
function goldenCases() {
  const fsReq = E.requiredFs(E.normalise(Object.assign({}, BASE, { load_torque_nm: 1, n2_rpm: 10 })).req).fs_req;
  const out = [];
  const gm = E.rows.filter(r => r.kind === 'gm' && r.cfg === 'single' && r.n2 >= 10 && !r.brk && r.poles === 4);
  const seen = new Set();
  for (const r of gm) {
    const key = r.fam + r.size; if (seen.has(key)) continue;
    const T = Math.floor(capacity(r, fsReq)); if (T < 3) continue;
    const peers = E.rows.filter(s => s.kind === 'gm' && s.fam === r.fam && s.cfg === 'single' && s.poles === r.poles && !s.brk &&
      Math.abs(s.n2 - r.n2) / r.n2 <= 0.05);
    const smaller = peers.filter(s => s.size_rank < r.size_rank);
    if (smaller.some(s => capacity(s, fsReq) >= T)) continue;
    if (peers.some(s => s.size_rank === r.size_rank && s.i !== r.i && capacity(s, fsReq) >= T && s.mn2 < r.mn2)) continue;
    seen.add(key); out.push({ r, T, fsReq });
  }
  return out;
}
test('golden: >= 6 cases derived from catalogue rows return that size as the smallest adequate one', () => {
  const cases = goldenCases();
  assert.ok(cases.length >= 6, 'derived cases: ' + cases.length);
  let n = 0;
  for (const { r, T } of cases) {
    const res = sel({ load_torque_nm: T, n2_rpm: r.n2, poles: r.poles, family: r.fam });
    assert.ok(res.candidates.length, `${r.size} i=${r.i} T=${T}`);
    const rec = res.candidates[0];
    assert.equal(rec.size, r.size, `${r.size} i=${r.i} T=${T} -> ${rec.designation}`);
    const hit = res.candidates.find(c => c.size === r.size && c.i === r.i);
    assert.ok(hit, 'row i present');
    assert.ok(hit.row_id === r.id || (hit.motor_alternatives || []).some(a => a.row_id === r.id), 'row id reachable');
    assert.equal(hit.mn2_nm >= T * res.fs.fs_req - 0.05, true);
    assert.ok(hit.src_page > 0);
    n++;
  }
  console.log('golden cases checked: ' + n + ' (' + cases.slice(0, 8).map(c => c.r.size + ' i=' + c.r.i + ' T=' + c.T).join('; ') + ')');
});

test('golden: pinned catalogue rows match the CSV values (guards the extractor output)', () => {
  const pins = [
    { size: 'NMRV050', i: 100, p1: 0.12, poles: 4, n2: 13, m2: 43, fs: 1.3, fr2: 4280, page: 89 },
    { size: 'NMRV-P075', i: 30, p1: 1.5, poles: 4, n2: 47, m2: 236, fs: 1.0, fr2: 4421, page: 149 },
  ];
  for (const p of pins) {
    const r = E.rows.find(x => x.kind === 'gm' && x.size === p.size && x.i === p.i && x.p1 === p.p1 && x.poles === p.poles);
    assert.ok(r, p.size + ' i=' + p.i);
    assert.equal(r.n2, p.n2); assert.equal(r.t2, p.m2); assert.equal(r.fs, p.fs); assert.equal(r.fr2, p.fr2); assert.equal(r.pg, p.page);
  }
});

test('reducer-only (NRV) candidates have no motor block and a motor power hint', () => {
  const r = sel({ load_torque_nm: 40, n2_rpm: 47, family: 'NRV' });
  assert.ok(r.candidates.length);
  r.candidates.forEach(c => { assert.equal(c.kind, 'reducer'); assert.equal(c.motor, null); assert.ok(c.p_in_req_kw > 0); });
});

test('techSnapshot omits null fields and states the catalogue source', () => {
  const r = sel({ load_torque_nm: 40, n2_rpm: 47 });
  const c = r.candidates[0];
  const snap = E.techSnapshot(c, E.normalise(Object.assign({}, BASE, { load_torque_nm: 40, n2_rpm: 47 })).req, {});
  assert.equal(snap.motor.n_rpm, null);      // catalogue has no motor rpm: hidden by the renderer
  assert.ok(snap.source.includes('с. ' + c.src_page));
  assert.equal(snap.motor.frequency, 50);
});
