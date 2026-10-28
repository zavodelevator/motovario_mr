'use strict';
// node --test test/nmrv/model3d.test.js   (no WebGL, no dependencies; needs prototype/nmrv/data.json from the build step)
// The expectations are derived INDEPENDENTLY from the raw catalogue CSVs (data/raw/VSF), not from data.json.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ROOT = path.join(__dirname, '..', '..');
const VSF = path.join(ROOT, 'prototype', 'nmrv');
const RAW = path.join(ROOT, 'data', 'raw', 'VSF');
const M3 = require(path.join(VSF, 'src', 'model3d.js'));
const EN = require(path.join(VSF, 'src', 'engine.js'));
const data = require(path.join(VSF, 'data.json'));

function csv(file) {
  const text = fs.readFileSync(path.join(RAW, file), 'utf8');
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (q) { if (ch === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; } else cur += ch; }
    else if (ch === '"') q = true;
    else if (ch === ',') { row.push(cur); cur = ''; }
    else if (ch === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (ch !== '\r') cur += ch;
  }
  if (cur || row.length) { row.push(cur); rows.push(row); }
  const head = rows.shift();
  return rows.filter(r => r.length === head.length).map(r => Object.fromEntries(head.map((h, i) => [h, r[i]])));
}
const first = v => { const m = /-?\d+(?:[.,]\d+)?/.exec(String(v === undefined ? '' : v)); return m ? parseFloat(m[0].replace(',', '.')) : null; };

const housing = csv('dimensions_housing.csv').filter(r => r.variant === 'NMRV' || r.variant === 'NRV');
const motorRows = csv('motors_dimensions.csv');
const interfaceRows = csv('motor_interface.csv');
const inputFlange = csv('dimensions_motor_input_flange.csv');
const H = key => { const r = housing.find(x => x.size.replace(' ', '') === key); assert.ok(r, key); return r; };

// raw motor body / flange row for an IEC frame label used by the test (same labelling rule as the catalogue table keys)
const BODY_LABEL = { 56: null, 63: '063', 71: '071', 80: '080', 90: '90S', 100: '100', 112: '112', 132: '132L', 160: '160S' };
function rawMotor(frame, flange) {
  const body = motorRows.find(r => r.variant === 'motor_body' && r.size === BODY_LABEL[frame]);
  const fl = motorRows.find(r => r.variant === 'flange_' + flange && Number(r.size) === frame);
  return body && fl ? { body, fl } : null;
}
function motorLabel(frame) { return { 63: '63A', 71: '71B', 80: '80B', 90: '90S', 100: '100L', 112: '112M', 132: '132M', 160: '160S' }[frame] || String(frame); }

function expected(size, series, frame, flange) {
  const isNrv = series.startsWith('NRV'), key = (isNrv ? 'NRV' : 'NMRV') + size.slice(-3), h = H(key);
  const g = k => first(h[k]);
  const box = { min: [-g('G1') / 2, -g('H'), -g('G3')], max: [g('G1') / 2, g('R'), g('H1')] };
  if (isNrv) {
    box.min[2] = -(g('G3') + g('B')); box.max[2] = g('G2') + g('B');
  } else if (frame) {
    const m = rawMotor(frame, flange); if (!m) return null;
    const AC = first(m.body.AC), AD = first(m.body.AD), LB = first(m.body.LB), Y = first(m.body.Y) || 0, P = first(m.fl.P);
    let G = /PAM/.test(h.G) ? null : first(h.G);
    if (G === null) G = frame === 132 ? 185.5 : 168;     // NMRV110 p52 "185.5 (PAM 132) / 168 (PAM 080/112)"
    box.max[2] = G + LB;
    const xr = Math.max(g('G1') / 2, P / 2, AC / 2, Y / 2);
    box.min[0] = -xr; box.max[0] = xr;
    box.min[1] = Math.min(-g('H'), g('I') - Math.max(P, AC) / 2);
    const hasBox = first(m.body.X) !== null && first(m.body.Y) !== null && first(m.body.V) !== null;   // 160-280 table prints X only
    box.max[1] = Math.max(g('R'), hasBox ? g('I') + AD : g('I') + AC / 2, g('I') + P / 2);
  }
  return box;
}
function walk(o, fn, p) { if (Array.isArray(o)) o.forEach((v, i) => walk(v, fn, p + '[' + i + ']')); else if (o && typeof o === 'object') Object.keys(o).forEach(k => walk(o[k], fn, p + '.' + k)); else fn(o, p); }
function noNaN(spec) { walk(spec, (v, p) => { if (typeof v === 'number') assert.ok(Number.isFinite(v), 'non-finite ' + p); }, 'spec'); }

const SIZES = ['030', '040', '050', '063', '075', '090', '110', '130', '150'];
const serOf = n => (parseInt(n, 10) >= 63 && parseInt(n, 10) <= 110 ? 'NMRV-P' : 'NMRV');

test('gearmotor spec bounding box = catalogue overall dims (+-1 mm), every size x motor frame x flange of the interface table', () => {
  let checked = 0; const sizesSeen = new Set();
  for (const n of SIZES) {
    const series = serOf(n), size = series + n;
    const ifaceSize = (series === 'NMRV-P' ? 'NMRV-P' : 'NMRV') + n;
    const combos = interfaceRows.filter(r => r.size === ifaceSize);
    assert.ok(combos.length, 'interface rows for ' + ifaceSize);
    for (const r of combos) {
      const frames = r.iec_frame.split('/').map(Number).filter(f => f >= 63);
      for (const frame of frames) {
        const spec = M3.buildModelSpec({ size, series, config: 'single' }, { frame: motorLabel(frame), poles: 4, flange: r.flange }, data, {});
        assert.ok(!spec.error, `${size} ${frame}${r.flange}: ${JSON.stringify(spec)}`);
        noNaN(spec);
        const exp = expected(size, series, frame, r.flange), b = M3.specBounds(spec);
        for (let k = 0; k < 3; k++) {
          assert.ok(Math.abs(b.min[k] - exp.min[k]) <= 1, `${size} ${frame}${r.flange} min[${k}] ${b.min[k]} vs ${exp.min[k]}`);
          assert.ok(Math.abs(b.max[k] - exp.max[k]) <= 1, `${size} ${frame}${r.flange} max[${k}] ${b.max[k]} vs ${exp.max[k]}`);
        }
        assert.deepEqual(spec.bbox.size.map(x => Math.round(x * 1e6)), b.size.map(x => Math.round(x * 1e6)));
        assert.equal(spec.status, 'concept'); assert.equal(spec.source, 'parametric-from-catalogue');
        checked++; sizesSeen.add(size);
      }
    }
  }
  assert.ok(sizesSeen.size >= 9, 'sizes ' + sizesSeen.size);
  assert.ok(checked >= 40, 'combinations ' + checked);
});

test('NRV / NRV-P are not supported in the NMRV-only model (no_dimensions)', () => {
  const spec = M3.buildModelSpec({ size: 'NRV040', series: 'NRV', config: 'single', kind: 'reducer' }, null, data, {});
  assert.equal(spec.error, 'no_dimensions'); assert.equal(spec.reason, 'series_not_supported');
});

test('hollow-shaft bore, spigot and foot-hole marks use the catalogue symbols', () => {
  const spec = M3.buildModelSpec({ size: 'NMRV-P063', series: 'NMRV-P', config: 'single' }, { frame: '90S', poles: 4, flange: 'B5' }, data, { version: 'foot' });
  const h = H('NMRV063'), sh = csv('dimensions_shaft_bore.csv').find(r => r.size === 'NMRV 063' && r.variant === 'NMRV');
  const hs = spec.parts.find(p => p.id === 'hollow_shaft');
  assert.equal(hs.ax, 'x'); assert.equal(hs.ri * 2, Number(sh['D H8'])); assert.equal(hs.len, first(h.G1));
  const sp = spec.parts.filter(p => p.id === 'spigot'); assert.equal(sp.length, 2); sp.forEach(p => assert.equal(p.r * 2, first(h.N)));
  const holes = spec.parts.filter(p => p.id === 'foot_hole_z'); assert.equal(holes.length, 4);
  holes.forEach(p => { assert.equal(Math.abs(p.c[0]), first(h.K) / 2); assert.equal(p.c[1], -first(h.V)); assert.equal(Math.abs(p.c[2]), first(h.H1)); assert.equal(p.r * 2, first(h.O)); });
  const fh = spec.parts.filter(p => p.id === 'face_hole'); assert.equal(fh.length, 8);
  fh.forEach(p => assert.ok(Math.abs(Math.hypot(p.c[1], p.c[2]) - first(h.M) / 2) < 1e-6));
  const tb = spec.parts.find(p => p.id === 'terminal_box'), mb = motorRows.find(r => r.size === '90S' && r.variant === 'motor_body');
  assert.equal(tb.s[0], first(mb.Y)); assert.equal(tb.s[2], first(mb.X));
  assert.equal(tb.c[2], first(h.G) + first(mb.V));
  // flange variant drops foot-hole marks; torque arm documented as not tabulated
  const fl = M3.buildModelSpec({ size: 'NMRV040', series: 'NMRV', config: 'single' }, null, data, { version: 'flange' });
  assert.equal(fl.parts.filter(p => p.id === 'foot_hole_z').length, 0);
  const ta = M3.buildModelSpec({ size: 'NMRV040', series: 'NMRV', config: 'single' }, null, data, { version: 'torque_arm' });
  assert.ok(ta.assumptions.some(a => /torque arm/.test(a)));
});

test('NMRV 110: G depends on the PAM (frame 132 -> 185.5, frames 80..112 -> 168); range values use the lower bound', () => {
  const s132 = M3.buildModelSpec({ size: 'NMRV-P110', series: 'NMRV-P', config: 'single' }, { frame: '132S', poles: 4, flange: 'B5' }, data, {});
  const s112 = M3.buildModelSpec({ size: 'NMRV-P110', series: 'NMRV-P', config: 'single' }, { frame: '112M', poles: 4, flange: 'B5' }, data, {});
  assert.equal(s132.dims_used.G, 185.5); assert.equal(s112.dims_used.G, 168);
  assert.ok(s112.assumptions.some(a => /PAM/.test(a)));
  assert.ok(s112.assumptions.some(a => /"82 - 85" -> lower bound/.test(a)));
  assert.equal(s112.dims_used.V, 82); assert.equal(s112.dims_used.A1, 164);
});

test('error path: missing dimensions -> {error:"no_dimensions"} (UI falls back to the catalogue photo)', () => {
  const ok = { size: 'NMRV050', series: 'NMRV', config: 'single' };
  assert.equal(M3.buildModelSpec({ size: 'NMRV025', series: 'NMRV', config: 'single' }, null, data, {}).error, 'no_dimensions'); // drawing only (p51)
  assert.equal(M3.buildModelSpec({ size: 'NMRV063/150', series: 'NMRV-P', config: 'combined' }, null, data, {}).error, 'no_dimensions');
  assert.equal(M3.buildModelSpec({ size: 'SW063', series: 'SW', config: 'single' }, null, data, {}).error, 'no_dimensions');
  assert.equal(M3.buildModelSpec(ok, { frame: '56A', poles: 4, flange: 'B14' }, data, {}).error, 'no_dimensions');   // motor frame 56 not tabulated
  assert.equal(M3.buildModelSpec(null, null, data, {}).error, 'no_dimensions');
  // delete one symbol at a time from a copy of the data: every needed symbol must be reported
  for (const k of ['I', 'H', 'R', 'L', 'H1', 'G1', 'G3', 'N', 'K', 'V', 'A1', 'O', 'M', 'G']) {
    const d2 = JSON.parse(JSON.stringify(data)); delete d2.dimensions.NMRV050.dims[k];
    const r = M3.buildModelSpec(ok, { frame: '71B', poles: 4, flange: 'B5' }, d2, {});
    assert.equal(r.error, 'no_dimensions', 'missing ' + k); assert.ok(r.missing.length >= 1, 'reports missing for ' + k);
  }
  const d3 = JSON.parse(JSON.stringify(data)); delete d3.shaft_bores.NMRV050;
  assert.equal(M3.buildModelSpec(ok, null, d3, {}).error, 'no_dimensions');
  const d4 = JSON.parse(JSON.stringify(data)); d4.dimensions.NMRV050.dims.H1 = 'abc';
  assert.equal(M3.buildModelSpec(ok, null, d4, {}).error, 'no_dimensions');
  const d5 = JSON.parse(JSON.stringify(data)); d5.motor_dims.bodies = d5.motor_dims.bodies.filter(b => b.frame !== '071');
  assert.equal(M3.buildModelSpec(ok, { frame: '71B', poles: 4, flange: 'B5' }, d5, {}).error, 'no_dimensions');
});

test('mounting-position transform: rigid, output shaft axis consistent for B3 B6 B7 B8 V5 V6', () => {
  const spec0 = M3.buildModelSpec({ size: 'NMRV-P075', series: 'NMRV-P', config: 'single' }, { frame: '80B', poles: 4, flange: 'B5' }, data, {});
  const local = M3.specBounds(spec0).size.slice().sort((a, b) => a - b);
  const det = m => m[0] * (m[4] * m[8] - m[5] * m[7]) - m[1] * (m[3] * m[8] - m[5] * m[6]) + m[2] * (m[3] * m[7] - m[4] * m[6]);
  const mul = (m, v) => [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2], m[6] * v[0] + m[7] * v[1] + m[8] * v[2]];
  const near = (a, b) => a.every((x, i) => Math.abs(x - b[i]) < 1e-9);
  const expectOut = { B3: [1, 0, 0], B8: [-1, 0, 0], B6: [0, 1, 0], B7: [0, -1, 0], V5: [1, 0, 0], V6: [1, 0, 0] };
  const expectFeet = { B3: [0, -1, 0], B8: [0, 1, 0], V5: [0, 0, 1], V6: [0, 0, -1] };
  for (const pos of ['B3', 'B6', 'B7', 'B8', 'V5', 'V6']) {
    const spec = M3.buildModelSpec({ size: 'NMRV-P075', series: 'NMRV-P', config: 'single' }, { frame: '80B', poles: 4, flange: 'B5' }, data, { mounting: pos });
    const R = spec.mount.rot;
    assert.equal(spec.mount.pos, pos); assert.ok(Math.abs(det(R) - 1) < 1e-12, pos + ' det');
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {            // R R^T = I
      let s = 0; for (let k = 0; k < 3; k++) s += R[i * 3 + k] * R[j * 3 + k];
      assert.ok(Math.abs(s - (i === j ? 1 : 0)) < 1e-12, pos + ' orthonormal');
    }
    // the hollow shaft stays on the local X axis in every position; its world axis is R * X and equals the declared output axis
    const hs = spec.parts.find(p => p.id === 'hollow_shaft');
    assert.equal(hs.ax, 'x');
    assert.ok(near(mul(R, [1, 0, 0]), spec.mount.outputAxis), pos + ' output axis');
    assert.ok(near(spec.mount.outputAxis, expectOut[pos]), pos + ' output axis value ' + spec.mount.outputAxis);
    assert.ok(Math.abs(spec.mount.outputAxis[0] * spec.mount.wormAxis[0] + spec.mount.outputAxis[1] * spec.mount.wormAxis[1] + spec.mount.outputAxis[2] * spec.mount.wormAxis[2]) < 1e-12, 'axes perpendicular');
    if (pos === 'V5') assert.ok(near(spec.mount.wormAxis, [0, 1, 0]), 'V5 motor up');
    if (pos === 'V6') assert.ok(near(spec.mount.wormAxis, [0, -1, 0]), 'V6 motor down');
    if (expectFeet[pos]) assert.ok(near(spec.mount.feetDir, expectFeet[pos]), pos + ' feet');
    else assert.equal(spec.mount.feetDir[1], 0, pos + ' feet horizontal (wall mounting)');
    const wb = M3.worldBounds(spec, pos).size.slice().sort((a, b) => a - b);          // rigid: same box up to axis permutation
    wb.forEach((v, i) => assert.ok(Math.abs(v - local[i]) < 1e-9, pos + ' box'));
    // geometry (local frame) is identical for all positions: only spec.mount differs
    assert.deepEqual(spec.parts, spec0.parts);
  }
  assert.equal(M3.buildModelSpec({ size: 'NMRV040', series: 'NMRV', config: 'single' }, null, data, { mounting: 'XX' }).mount.pos, 'B3');
});

test('gearbox input flange Pm (dimensions_motor_input_flange) equals the motor flange P used for the plates', () => {
  let n = 0;
  for (const r of inputFlange) {
    const fl = r.variant.endsWith('B14') ? 'B14' : 'B5';
    if (!r.variant.startsWith('NMRV')) continue;
    const key = ('000' + r.size).slice(-3), mf = data.motor_dims.flanges[fl][key];
    if (!mf) continue;                       // 056 (motors table starts at 063)
    assert.equal(mf.P, Number(r.Pm), r.variant + ' ' + r.size); n++;
  }
  assert.ok(n >= 12);
});

test('engine candidates: every NMRV / NRV single-stage candidate gives a finite spec or a documented no_dimensions', () => {
  const E = EN.createEngine(data);
  const base = { load_class: 'B', hours_per_day: 8, starts_per_hour: 10, poles: 4, family: 'gm', mounting_position: 'B3' };
  let specs = 0, errs = new Set();
  for (const [T, n2, fam] of [[120, 47, 'gm'], [20, 60, 'gm'], [600, 20, 'gm'], [8, 100, 'gm'], [120, 47, 'NMRV-P'], [400, 30, 'NMRV']]) {
    const res = E.select(Object.assign({}, base, { load_torque_nm: T, n2_rpm: n2, family: fam }));
    for (const c of res.candidates) {
      const s = M3.buildModelSpec(c, c.motor, data, { mounting: 'B3', version: 'foot' });
      if (s.error) { errs.add(s.reason + ':' + c.size); continue; }
      noNaN(s); specs++;
      assert.ok(s.src_pages.length >= 1 && (!c.motor || s.src_pages.length >= 2));
    }
  }
  assert.ok(specs >= 10, 'specs ' + specs);
  console.log('# specs', specs, 'no_dimensions:', [...errs].join(', ') || 'none');
});


test('motor frames 160-280 (catalogue p67, no X/Y/V): spec is built without a terminal box, documented', () => {
  const s = M3.buildModelSpec({ size: 'NMRV150', series: 'NMRV', config: 'single' }, { frame: '160L', poles: 4, flange: 'B5' }, data, {});
  assert.ok(!s.error, JSON.stringify(s)); noNaN(s);
  assert.equal(s.parts.filter(p => p.id === 'terminal_box').length, 0);
  assert.ok(s.assumptions.some(a => /terminal box not drawn/.test(a)));
  const mb = motorRows.find(r => r.size === '160L' && r.variant === 'motor_body_160-280');
  assert.ok(Math.abs(M3.specBounds(s).max[2] - (first(H('NMRV150').G) + first(mb.LB))) < 1e-6);
});
