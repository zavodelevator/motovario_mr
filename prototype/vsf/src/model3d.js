/* VSF concept 3D model (ADR 'concept-3d', owner decision 2026-10-28).
 *
 * A PARAMETRIC model of the selected NMRV / NMRV-P / NRV / NRV-P gearmotor generated ONLY from catalogue dimension
 * tables (data/raw/VSF dimensions_housing, dimensions_shaft_bore, motors_dimensions). No external model files.
 * Status: concept. Every KP image made from it carries the footnote CONCEPT_NOTE. All KP numbers (dimensions, torque,
 * mass) come from catalogue data, never from this geometry.
 *
 * Two layers:
 *   buildModelSpec(rowOrCandidate, motor, data, opts)  PURE. Returns a plain JSON spec of primitives, or
 *                                                      {error:'no_dimensions', reason, missing:[...]}.
 *   specToThree(spec, THREE)                           browser: spec -> THREE.Group (+ renderSpecToPng, createViewer).
 * UMD: browser global VSFModel3D, node require() (tests use buildModelSpec / specBounds / MOUNTS only).
 *
 * ------------------------------------------------------------------------------------------------------------------
 * Frame of the spec ("B3 frame", mm): X = output (hollow) shaft axis, Y = up (feet at -Y), Z = worm / motor axis,
 * motor towards +Z, output axis at the origin. The mounting position is a rigid rotation applied on top (spec.mount).
 *
 * SYMBOL -> GEOMETRY MAP (catalogue symbols, drawings p52 NMRV/NMRV-P and p56 NRV/NRV-P; motor drawing p66):
 *   I            centre distance: worm/motor axis is at Y = +I (above the output axis in B3)
 *   H            output axis -> base (feet bottom): housing/lugs bottom at Y = -H
 *   R            output axis -> top of housing: housing top at Y = +R
 *   L            overall housing width across X (foot width): housing box X = +-L/2
 *   H1           output axis -> housing end face along the worm axis: housing box Z = +-H1
 *   G3           output axis -> bearing cover face (non-motor side): cap on Z in [-G3, -H1]
 *   G            output axis -> outer face of the motor input flange (NMRV): motor mounting face at Z = +G
 *   G2, B, D1    NRV: input shaft on the motor side from Z = G2, length B, diameter D1; the other shaft from -G3, length B
 *   G1, N1       overall hollow-shaft length / half: spigots and hollow shaft end at X = +-G1/2 (= +-N1)
 *   N            spigot diameter (h8) of the output faces (tube from X = +-L/2 to +-G1/2)
 *   M, KE        four tapped holes on pitch circle M, 45 deg positions, on both output faces (dark marks, thread dia KE)
 *   K            distance between the foot holes across X: hole centres at X = +-K/2
 *   A1           distance between the foot holes along Z: hole centres at Z = +-A1/2
 *   V            output axis -> foot hole line: holes at Y = -V, hole dia O (dark marks on the lug end faces)
 *   S, S1, P, Q, W, b1/t1/f1   not drawn (hole sizes of the ears, 45 deg flange outline, key of the input shaft, f1 thread)
 *   D (H8), b, t  hollow-shaft bore diameter (first tabulated bore) and keyway width / depth (t = bore bottom -> key top)
 *   Pm            gearbox input flange diameter = motor flange P (checked equal in the tests), gearbox flange plate on Z [G-LA, G]
 *   --- motor (p66-67), motor axis at Y=I ---
 *   LB            motor mounting face -> end of fan cover:  body ends at Z = G + LB
 *   LA, P, M, S, T  motor flange: plate thickness LA on Z [G, G+LA], diameter P, holes on pitch circle M, dia S (B5/B14 per candidate)
 *   AC            motor body diameter,  AD axis -> top of terminal box (top at Y = I + AD)
 *   X, Y          terminal box length (along Z) and width (across X);  V(motor) mounting face -> terminal box centre
 *
 * STYLE parameters that are NOT catalogue dimensions (decorative, they never leave the envelope given by the symbols above):
 *   edge radii of boxes, hollow-shaft hub diameter (1.6 x bore), adapter cone radii, motor fin pitch/thickness/core radius,
 *   fan-cover length (22 % of the motor body), terminal-box lower overlap. Listed in spec.style.
 * ASSUMPTIONS (listed in spec.assumptions when they were used):
 *   - NMRV-P / NRV-P use the NMRV / NRV housing table (the catalogue prints one table "NMRV / NMRV-P", p52; "NRV / NRV-P", p56).
 *   - Range values ("90 - 95", "164 - 170", "82 - 85") -> lower bound.
 *   - NMRV 110 G depends on the PAM (p52: 185.5 PAM 132; 168 PAM 080/112): frame 132 -> 185.5, frames 80..112 -> 168.
 *   - Motor frame 132M/MA/MB use the table row 132L (the table has only 132S / 132L).
 *   - Terminal box on top (+Y); mounting-position rotations follow IEC 60034-7 viewed from the motor drive end for B6 / B7
 *     (V5 = motor up, V6 = motor down confirmed on the catalogue picture p24).
 *   - Output flange / torque-arm executions are not tabulated (p73-75 not extracted): the standard foot housing is drawn
 *     for them too, only the foot-hole marks are dropped for 'flange'.
 * Not supported -> {error:'no_dimensions'}: NMRV025 (drawing only), combined / pre-stage units, SW / ISW, motor frames without table row.
 */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.VSFModel3D = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var CONCEPT_NOTE = 'Ілюстрація, концептуальна модель; розміри — за каталогом Motovario';
  var COLORS = { body: 0x1F4E8C, motor: 0x8b929a, fan: 0x5f666e, fin: 0x9aa1a9, steel: 0xc3c9d0, dark: 0x15191e, tbox: 0x7b828a };

  // mounting position -> rigid rotation local -> world (row-major 3x3), see header for the conventions
  var MOUNTS = {
    B3: [1, 0, 0, 0, 1, 0, 0, 0, 1],
    B8: [-1, 0, 0, 0, -1, 0, 0, 0, 1],
    B6: [0, -1, 0, 1, 0, 0, 0, 0, 1],
    B7: [0, 1, 0, -1, 0, 0, 0, 0, 1],
    V5: [1, 0, 0, 0, 0, 1, 0, -1, 0],
    V6: [1, 0, 0, 0, 0, -1, 0, 1, 0]
  };
  function mulV(m, v) { return [m[0] * v[0] + m[1] * v[1] + m[2] * v[2], m[3] * v[0] + m[4] * v[1] + m[5] * v[2], m[6] * v[0] + m[7] * v[1] + m[8] * v[2]]; }
  function r3(v) { return v.map(function (x) { return Math.round(x * 1e6) / 1e6 + 0; }); }

  // ------------------------------------------------------------------ catalogue value helpers
  function pnum(v) {                       // number | "90 - 95" | "M6*11" | "9.5" -> number (first number found) or null
    if (typeof v === 'number') return isFinite(v) ? v : null;
    if (v === null || v === undefined || v === '') return null;
    var m = /-?\d+(?:[.,]\d+)?/.exec(String(v));
    return m ? parseFloat(m[0].replace(',', '.')) : null;
  }
  function isRange(v) { return typeof v === 'string' && /\d\s*-\s*\d/.test(v); }
  function nodims(reason, missing) { return { error: 'no_dimensions', reason: reason, missing: missing || [] }; }

  // motor frame label ("90S", "100LA", "63A", "132MB", "160MA") -> row of data.motor_dims.bodies
  function motorBody(data, frame, poles, assumptions) {
    var md = data && data.motor_dims;
    if (!md || !frame) return null;
    var m = /^(\d{2,3})([A-Z]*)/.exec(String(frame));
    if (!m) return null;
    var n = parseInt(m[1], 10), suf = m[2] || '', keys;
    if (n <= 80) keys = [('00' + n).slice(-3)];
    else if (n === 90) keys = [suf.charAt(0) === 'L' ? '90L' : '90S'];
    else if (n === 100 || n === 112) keys = [String(n)];
    else if (n === 132) {
      if (suf.charAt(0) === 'S') keys = ['132S'];
      else { keys = ['132L']; assumptions.push('motor frame ' + frame + ' -> table row 132L'); }
    } else keys = [String(n) + (suf.charAt(0) || 'S'), String(n) + 'M', String(n) + 'S', String(n) + 'L'];
    var rows = [];
    for (var ki = 0; ki < keys.length && !rows.length; ki++) rows = md.bodies.filter(function (b) { return b.frame === keys[ki]; });
    if (!rows.length) return null;
    var byPoles = rows.filter(function (b) { return b.poles && String(b.poles).split('-').indexOf(String(poles)) >= 0; });
    var row = byPoles[0] || rows[0];
    return row;
  }
  function motorFlange(data, flange, frame) {
    var n = parseInt(/^(\d{2,3})/.exec(String(frame))[1], 10);
    var key = ('00' + n).slice(-3);
    var f = data.motor_dims.flanges[flange] || {};
    return f[key] || null;
  }

  // ------------------------------------------------------------------ spec builder (pure)
  function buildModelSpec(c, motor, data, opts) {
    opts = opts || {};
    try {
      return build(c, motor, data, opts);
    } catch (e) {
      return nodims('exception: ' + e.message);
    }
  }

  function build(c, motor, data, opts) {
    var mount = MOUNTS[opts.mounting] ? opts.mounting : 'B3';
    var version = opts.version || 'foot';
    if (!c || !c.size || !data || !data.dimensions) return nodims('no_input');
    if (c.config && c.config !== 'single') return nodims('combined_or_prestage_unit');
    var series = c.series || '';
    if (['NMRV', 'NMRV-P', 'NRV', 'NRV-P'].indexOf(series) < 0) return nodims('series_not_supported', [series]);
    var isNrv = series.indexOf('NRV') === 0;
    var nm = /(\d{3})$/.exec(c.size);
    if (!nm) return nodims('size');
    var key = (isNrv ? 'NRV' : 'NMRV') + nm[1];
    var ent = data.dimensions[key];
    if (!ent) return nodims('housing_table_missing', [key]);
    var assumptions = [], pages = [ent.pg];
    if (series.indexOf('-P') > 0) assumptions.push(series + ' drawn with the ' + (isNrv ? 'NRV' : 'NMRV') + ' ' + nm[1] + ' housing table (one table for both series in the catalogue)');

    var d = {}, raw = ent.dims;
    var need = ['I', 'H', 'R', 'L', 'H1', 'G1', 'G3', 'N', 'K', 'V', 'A1', 'O', 'M', 'KE'];
    if (isNrv) need = need.concat(['G2', 'D1', 'B']);
    var missing = [];
    need.forEach(function (k) {
      var v = pnum(raw[k]);
      if (v === null) missing.push(k); else { d[k] = v; if (isRange(raw[k])) assumptions.push('range ' + k + ' = "' + raw[k] + '" -> lower bound'); }
    });
    var bores = (data.shaft_bores && data.shaft_bores[key]) || [];
    var bore = bores.filter(function (b) { return pnum(b.D) !== null; })[0];
    if (!bore) missing.push('D (shaft bore)');
    if (missing.length) return nodims('housing_dimension_missing', missing);
    var D = pnum(bore.D), bk = pnum(bore.b), bt = pnum(bore.t);
    pages.push(bore.pg);

    // ---- motor (NMRV / NMRV-P gearmotor)
    var mot = null, Gv = null;
    if (!isNrv && motor && motor.frame) {
      var body = motorBody(data, motor.frame, motor.poles, assumptions);
      if (!body) return nodims('motor_frame_not_tabulated', [String(motor.frame)]);
      var flName = motor.flange === 'B14' ? 'B14' : 'B5';
      var fl = motorFlange(data, flName, motor.frame);
      var mm = ['AC', 'AD', 'LB'].filter(function (k) { return pnum(body[k]) === null; });
      if (mm.length) return nodims('motor_dimension_missing', mm.map(function (k) { return k + ' (motor ' + body.frame + ')'; }));
      if (!fl || pnum(fl.P) === null || pnum(fl.LA) === null || pnum(fl.M) === null) return nodims('motor_flange_not_tabulated', [flName + ' ' + motor.frame]);
      mot = { frame: body.frame, flange: flName, AC: pnum(body.AC), AD: pnum(body.AD), LB: pnum(body.LB), X: pnum(body.X), Y: pnum(body.Y), V: pnum(body.V),
        P: pnum(fl.P), LA: pnum(fl.LA), M: pnum(fl.M), S: pnum(fl.S) || 6 };
      pages.push(body.pg, fl.pg);
      // gearbox flange G
      Gv = pnum(raw.G);
      if (Gv === null && ent.G_pam && ent.G_pam.length) {
        var fn = parseInt(/^(\d+)/.exec(String(motor.frame))[1], 10);
        var hit = ent.G_pam.filter(function (g) { return fn >= g.from && fn <= g.to; })[0];
        if (!hit) return nodims('housing_G_for_frame_missing', ['G (frame ' + motor.frame + ')']);
        Gv = hit.G; assumptions.push('G = ' + hit.G + ' for PAM ' + hit.label + ' (catalogue p52)');
      }
      if (Gv === null) return nodims('housing_dimension_missing', ['G']);
      d.G = Gv;
    }

    var parts = [], add = function (p) { parts.push(p); return p; };
    var I = d.I, H = d.H, R = d.R, L = d.L, H1 = d.H1, G1 = d.G1, G3 = d.G3, N = d.N;
    var cap_r = Math.max(6, Math.min(R - I, I) * 0.9);

    // housing: main box from the foot-hole line up to R, four corner lugs below
    var rb = Math.min(0.1 * L, 11);
    add({ t: 'box', id: 'housing', mat: 'body', c: [0, (R - d.V) / 2, 0], s: [L, R + d.V, 2 * H1], r: rb });
    var lx0 = d.K - L / 2, lx1 = L / 2, lz0 = d.A1 - H1, lz1 = H1;
    var lugTop = -d.V + (H - d.V);
    if (lx1 > lx0 && lz1 > lz0 && lugTop > -H) {
      [-1, 1].forEach(function (sx) { [-1, 1].forEach(function (sz) {
        add({ t: 'box', id: 'lug', mat: 'body', c: [sx * (lx0 + lx1) / 2, (-H + lugTop) / 2, sz * (lz0 + lz1) / 2], s: [lx1 - lx0, lugTop + H, lz1 - lz0], r: 1.5 });
      }); });
    }
    if (version !== 'flange') {
      [-1, 1].forEach(function (sx) { [-1, 1].forEach(function (sz) {
        add({ t: 'mark', id: 'foot_hole_z', mat: 'dark', c: [sx * d.K / 2, -d.V, sz * H1], ax: 'z', sign: sz, r: d.O / 2 });
        add({ t: 'mark', id: 'foot_hole_x', mat: 'dark', c: [sx * L / 2, -d.V, sz * d.A1 / 2], ax: 'x', sign: sx, r: d.O / 2 });
      }); });
    }

    // output (hollow-shaft) faces: spigot tube + hollow shaft tube + keyway + four tapped holes
    var hubR = Math.min(D / 2 * 1.6, N / 2 - 1);
    var spLen = G1 / 2 - L / 2;
    [-1, 1].forEach(function (sx) {
      add({ t: 'tube', id: 'spigot', mat: 'body', c: [sx * (L / 2 + spLen / 2), 0, 0], ax: 'x', r: N / 2, ri: hubR, len: spLen });
      [45, 135, 225, 315].forEach(function (a) {
        var ar = a * Math.PI / 180;
        add({ t: 'mark', id: 'face_hole', mat: 'dark', c: [sx * L / 2, d.M / 2 * Math.sin(ar), d.M / 2 * Math.cos(ar)], ax: 'x', sign: sx, r: Math.max(2, d.KE / 2) });
      });
    });
    add({ t: 'tube', id: 'hollow_shaft', mat: 'steel', c: [0, 0, 0], ax: 'x', r: hubR, ri: D / 2, len: G1 });
    if (bk !== null && bt !== null && bt > D) {
      add({ t: 'box', id: 'keyway', mat: 'dark', c: [0, bt / 2, 0], s: [G1, bt - D, bk], r: 0 });
    }

    // worm side
    if (!isNrv) {
      add({ t: 'cyl', id: 'cap', mat: 'body', c: [0, I, -(H1 + G3) / 2], ax: 'z', r: cap_r, len: G3 - H1 });
    } else {
      add({ t: 'cyl', id: 'cap', mat: 'body', c: [0, I, -(H1 + G3) / 2], ax: 'z', r: cap_r, len: G3 - H1 });
      add({ t: 'cyl', id: 'cap', mat: 'body', c: [0, I, (H1 + d.G2) / 2], ax: 'z', r: cap_r, len: d.G2 - H1 });
      add({ t: 'cyl', id: 'input_shaft', mat: 'steel', c: [0, I, -G3 - d.B / 2], ax: 'z', r: d.D1 / 2, len: d.B });
      add({ t: 'cyl', id: 'input_shaft', mat: 'steel', c: [0, I, d.G2 + d.B / 2], ax: 'z', r: d.D1 / 2, len: d.B });
    }

    if (mot) {
      // adapter cone + gearbox input flange plate
      var Pm = mot.P, la = mot.LA;
      var coneLen = Gv - la - H1;
      if (coneLen > 1) add({ t: 'cyl', id: 'adapter', mat: 'body', c: [0, I, H1 + coneLen / 2], ax: 'z', r: cap_r, r2: Math.min(Pm / 2 * 0.72, Math.max(cap_r, Pm / 2 * 0.6)), len: coneLen });
      add({ t: 'flange', id: 'gear_flange', mat: 'body', c: [0, I, Gv - la / 2], ax: 'z', r: Pm / 2, len: la, holes: { n: 4, pcd: mot.M, d: mot.S, a0: 45 } });
      // motor
      add({ t: 'flange', id: 'motor_flange', mat: 'motor', c: [0, I, Gv + la / 2], ax: 'z', r: Pm / 2, len: la, holes: { n: 4, pcd: mot.M, d: mot.S, a0: 45 } });
      var zb0 = Gv + la, zEnd = Gv + mot.LB, bodyLen = zEnd - zb0;
      var fanLen = bodyLen * 0.22, zFan = zEnd - fanLen, coreLen = zFan - zb0;
      var rCore = mot.AC / 2 * 0.94, rFin = mot.AC / 2;
      add({ t: 'cyl', id: 'motor_core', mat: 'motor', c: [0, I, zb0 + coreLen / 2], ax: 'z', r: rCore, len: coreLen });
      var nFin = Math.max(4, Math.min(24, Math.round(coreLen / (mot.AC * 0.16)))), pitch = coreLen / nFin;
      for (var i = 0; i < nFin; i++) add({ t: 'cyl', id: 'motor_fin', mat: 'fin', c: [0, I, zb0 + pitch * (i + 0.5)], ax: 'z', r: rFin, len: pitch * 0.42 });
      add({ t: 'cyl', id: 'fan_cover', mat: 'fan', c: [0, I, zFan + fanLen / 2], ax: 'z', r: rFin, r2: rFin * 0.93, len: fanLen });
      var tbBot = mot.AC / 2 * 0.7;
      if (mot.X === null || mot.Y === null || mot.V === null) assumptions.push('terminal box not drawn: X / Y / V not tabulated for motor frame ' + mot.frame + ' (catalogue p67)');
      else add({ t: 'box', id: 'terminal_box', mat: 'tbox', c: [0, I + (tbBot + mot.AD) / 2, Gv + mot.V], s: [mot.Y, mot.AD - tbBot, mot.X], r: 3 });
    }

    var spec = {
      version: 1, status: 'concept', source: 'parametric-from-catalogue', note_uk: CONCEPT_NOTE,
      series: series, size: c.size, kind: isNrv ? 'reducer' : (mot ? 'gearmotor' : 'gearbox'),
      variant: version, units: 'mm',
      frame: { x: 'output shaft axis', y: 'up (feet at -Y)', z: 'worm / motor axis, motor at +Z' },
      mount: { pos: mount, rot: MOUNTS[mount].slice(), outputAxis: r3(mulV(MOUNTS[mount], [1, 0, 0])), wormAxis: r3(mulV(MOUNTS[mount], [0, 0, 1])), feetDir: r3(mulV(MOUNTS[mount], [0, -1, 0])) },
      axes: { output: [1, 0, 0], worm: [0, 0, 1], up: [0, 1, 0] },
      dims_used: d, motor_used: mot, bore: { D: D, b: bk, t: bt },
      parts: parts, src_pages: pages.filter(function (p, ix, a) { return p && a.indexOf(p) === ix; }).sort(function (a, b) { return a - b; }),
      style: ['edge radii', 'hollow-shaft hub dia 1.6 x bore', 'adapter cone radii', 'motor core 0.9 x AC with fins', 'fan cover 22 % of motor body', 'terminal box lower overlap 0.7 x AC/2'],
      assumptions: assumptions
    };
    if (version === 'torque_arm') spec.assumptions.push('torque arm not tabulated (catalogue p74-75 not extracted): not drawn');
    if (version === 'flange') spec.assumptions.push('output flange execution not tabulated (catalogue p73 not extracted): standard housing drawn');
    var b = specBounds(spec);
    spec.bbox = { min: b.min, max: b.max, size: b.size };
    for (var k = 0; k < 3; k++) if (!isFinite(b.min[k]) || !isFinite(b.max[k])) return nodims('nan_bounds');
    return spec;
  }

  // ------------------------------------------------------------------ bounds (local B3 frame)
  var AX = { x: 0, y: 1, z: 2 };
  function partExtent(p) {
    var a = AX[p.ax || 'z'], lo = [0, 0, 0], hi = [0, 0, 0], i;
    if (p.t === 'box') { for (i = 0; i < 3; i++) { lo[i] = p.c[i] - p.s[i] / 2; hi[i] = p.c[i] + p.s[i] / 2; } return [lo, hi]; }
    if (p.t === 'mark') return null;
    var rr = Math.max(p.r, p.r2 || 0);
    for (i = 0; i < 3; i++) {
      var h = i === a ? p.len / 2 : rr;
      lo[i] = p.c[i] - h; hi[i] = p.c[i] + h;
    }
    return [lo, hi];
  }
  function specBounds(spec) {
    var min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    spec.parts.forEach(function (p) {
      var e = partExtent(p); if (!e) return;
      for (var i = 0; i < 3; i++) { if (e[0][i] < min[i]) min[i] = e[0][i]; if (e[1][i] > max[i]) max[i] = e[1][i]; }
    });
    return { min: min, max: max, size: [max[0] - min[0], max[1] - min[1], max[2] - min[2]] };
  }
  function worldBounds(spec, pos) {
    var rot = MOUNTS[pos || spec.mount.pos] || MOUNTS.B3, b = specBounds(spec);
    var min = [Infinity, Infinity, Infinity], max = [-Infinity, -Infinity, -Infinity];
    for (var i = 0; i < 8; i++) {
      var w = mulV(rot, [i & 1 ? b.max[0] : b.min[0], i & 2 ? b.max[1] : b.min[1], i & 4 ? b.max[2] : b.min[2]]);
      for (var k = 0; k < 3; k++) { if (w[k] < min[k]) min[k] = w[k]; if (w[k] > max[k]) max[k] = w[k]; }
    }
    return { min: min, max: max, size: [max[0] - min[0], max[1] - min[1], max[2] - min[2]] };
  }

  // ------------------------------------------------------------------ three.js layer (browser)
  function roundedBoxGeometry(THREE, sx, sy, sz, r, k) {
    r = Math.max(0, Math.min(r, sx / 2 - 1e-3, sy / 2 - 1e-3, sz / 2 - 1e-3));
    if (r < 0.05) return new THREE.BoxGeometry(sx, sy, sz);
    k = k || 4;
    function coords(e) {
      var a = [], j;
      for (j = 0; j <= k; j++) a.push(-e / 2 + r * j / k);
      for (j = 0; j <= k; j++) a.push(e / 2 - r + r * j / k);
      return a;
    }
    var cs = [coords(sx), coords(sy), coords(sz)], half = [sx / 2, sy / 2, sz / 2];
    var pos = [], nor = [], idx = [], vcount = 0;
    function face(axis, sign) {
      var u = (axis + 1) % 3, v = (axis + 2) % 3, nu = cs[u].length, nv = cs[v].length, base = vcount, i, j;
      for (j = 0; j < nv; j++) for (i = 0; i < nu; i++) {
        var p = [0, 0, 0]; p[axis] = sign * half[axis]; p[u] = cs[u][i]; p[v] = cs[v][j];
        var q = [0, 0, 0], n = [0, 0, 0], len;
        for (var t = 0; t < 3; t++) { var inner = half[t] - r; q[t] = Math.max(-inner, Math.min(inner, p[t])); n[t] = p[t] - q[t]; }
        len = Math.sqrt(n[0] * n[0] + n[1] * n[1] + n[2] * n[2]) || 1;
        for (t = 0; t < 3; t++) { n[t] /= len; p[t] = q[t] + n[t] * r; }
        pos.push(p[0], p[1], p[2]); nor.push(n[0], n[1], n[2]); vcount++;
      }
      // winding: (u x v) must point along sign * axis
      var cu = [0, 0, 0], cv = [0, 0, 0]; cu[u] = 1; cv[v] = 1;
      var cr = [cu[1] * cv[2] - cu[2] * cv[1], cu[2] * cv[0] - cu[0] * cv[2], cu[0] * cv[1] - cu[1] * cv[0]];
      var flip = cr[axis] * sign < 0;
      for (j = 0; j < nv - 1; j++) for (i = 0; i < nu - 1; i++) {
        var a = base + j * nu + i, b = a + 1, c = a + nu, d = c + 1;
        if (flip) idx.push(a, c, b, b, c, d); else idx.push(a, b, c, b, d, c);
      }
    }
    face(0, 1); face(0, -1); face(1, 1); face(1, -1); face(2, 1); face(2, -1);
    var g = new THREE.BufferGeometry();
    g.setAttribute('position', new THREE.Float32BufferAttribute(pos, 3));
    g.setAttribute('normal', new THREE.Float32BufferAttribute(nor, 3));
    g.setIndex(idx);
    return g;
  }
  function orient(g, ax, kind) {   // kind 'cyl' (built along Y) or 'ext' (built along +Z, centred)
    if (kind === 'cyl') { if (ax === 'z') g.rotateX(Math.PI / 2); else if (ax === 'x') g.rotateZ(-Math.PI / 2); }
    else { if (ax === 'x') g.rotateY(Math.PI / 2); else if (ax === 'y') g.rotateX(-Math.PI / 2); }
    return g;
  }
  function ringGeometry(THREE, ro, ri, len, holes) {
    var sh = new THREE.Shape(); sh.absarc(0, 0, ro, 0, Math.PI * 2, false);
    if (ri > 0) { var hp = new THREE.Path(); hp.absarc(0, 0, ri, 0, Math.PI * 2, true); sh.holes.push(hp); }
    if (holes) for (var i = 0; i < holes.n; i++) {
      var a = (holes.a0 + i * 360 / holes.n) * Math.PI / 180, hp2 = new THREE.Path();
      hp2.absarc(holes.pcd / 2 * Math.cos(a), holes.pcd / 2 * Math.sin(a), holes.d / 2, 0, Math.PI * 2, true); sh.holes.push(hp2);
    }
    var g = new THREE.ExtrudeGeometry(sh, { depth: len, bevelEnabled: false, curveSegments: 40 });
    g.translate(0, 0, -len / 2);
    return g;
  }

  function specToThree(spec, THREE) {
    var group = new THREE.Group(), mats = {}, geos = [], meshes = [];
    function mat(name) {
      if (mats[name]) return mats[name];
      var m;
      if (name === 'dark') m = new THREE.MeshStandardMaterial({ color: COLORS.dark, roughness: 0.9, metalness: 0, polygonOffset: true, polygonOffsetFactor: -2, polygonOffsetUnits: -2 });
      else if (name === 'steel') m = new THREE.MeshStandardMaterial({ color: COLORS.steel, roughness: 0.32, metalness: 0.85 });
      else if (name === 'body') m = new THREE.MeshStandardMaterial({ color: COLORS.body, roughness: 0.48, metalness: 0.12 });
      else m = new THREE.MeshStandardMaterial({ color: COLORS[name] || 0x888888, roughness: 0.55, metalness: 0.25 });
      mats[name] = m; return m;
    }
    spec.parts.forEach(function (p) {
      var g, ax = p.ax || 'z';
      if (p.t === 'box') g = roundedBoxGeometry(THREE, p.s[0], p.s[1], p.s[2], p.r || 0, 4);
      else if (p.t === 'cyl') g = orient(new THREE.CylinderGeometry(p.r2 !== undefined ? p.r2 : p.r, p.r, p.len, 56, 1), ax, 'cyl');
      else if (p.t === 'tube') g = orient(ringGeometry(THREE, p.r, p.ri, p.len, null), ax, 'ext');
      else if (p.t === 'flange') g = orient(ringGeometry(THREE, p.r, 0, p.len, p.holes), ax, 'ext');
      else if (p.t === 'mark') {
        g = new THREE.CircleGeometry(p.r, 28);
        var a = p.ax;
        if (a === 'x') g.rotateY(p.sign > 0 ? Math.PI / 2 : -Math.PI / 2);
        else if (a === 'y') g.rotateX(p.sign > 0 ? -Math.PI / 2 : Math.PI / 2);
        else if (p.sign < 0) g.rotateY(Math.PI);
      }
      if (!g) return;
      var m = new THREE.Mesh(g, mat(p.mat));
      m.position.set(p.c[0], p.c[1], p.c[2]);
      if (p.t === 'mark') { var o = 0.12; m.position[p.ax] += p.sign * o; }
      m.castShadow = p.t !== 'mark' && p.id !== 'motor_fin' && p.id !== 'keyway'; m.receiveShadow = false;
      m.userData.partId = p.id;
      group.add(m); geos.push(g); meshes.push(m);
    });
    var mount = new THREE.Group();
    mount.matrixAutoUpdate = false;
    function setMounting(pos) {
      var r = MOUNTS[pos] || MOUNTS.B3;
      mount.matrix.set(r[0], r[1], r[2], 0, r[3], r[4], r[5], 0, r[6], r[7], r[8], 0, 0, 0, 0, 1);
      mount.matrixWorldNeedsUpdate = true; mount.updateMatrixWorld(true);
    }
    mount.add(group);
    setMounting(spec.mount.pos);
    return {
      group: mount,
      setMounting: setMounting,
      setWireframe: function (on) { Object.keys(mats).forEach(function (k) { mats[k].wireframe = !!on; }); },
      box: function () { return new THREE.Box3().setFromObject(mount); },
      dispose: function () { geos.forEach(function (g) { g.dispose(); }); Object.keys(mats).forEach(function (k) { mats[k].dispose(); }); }
    };
  }

  function studio(THREE, renderer, scene, box) {
    scene.background = new THREE.Color(0xffffff);
    scene.add(new THREE.HemisphereLight(0xffffff, 0xc9d1da, 1.05));
    var key = new THREE.DirectionalLight(0xffffff, 1.9);
    var size = box.getSize(new THREE.Vector3()), ctr = box.getCenter(new THREE.Vector3()), rad = size.length() / 2;
    key.position.set(ctr.x + rad * 1.2, ctr.y + rad * 2.2, ctr.z + rad * 1.0);
    key.target.position.copy(ctr); scene.add(key.target);
    key.castShadow = true; key.shadow.mapSize.set(1024, 1024);
    var sc = key.shadow.camera; sc.left = -rad * 1.6; sc.right = rad * 1.6; sc.top = rad * 1.6; sc.bottom = -rad * 1.6; sc.near = 0.1; sc.far = rad * 8;
    key.shadow.bias = -0.0008; key.shadow.normalBias = 1.2;
    scene.add(key);
    var fill = new THREE.DirectionalLight(0xdfe8f5, 0.7); fill.position.set(ctr.x - rad * 1.5, ctr.y + rad * 0.6, ctr.z - rad * 1.2); fill.target.position.copy(ctr); scene.add(fill, fill.target);
    var floor = new THREE.Mesh(new THREE.PlaneGeometry(rad * 8, rad * 8), new THREE.ShadowMaterial({ opacity: 0.16 }));
    floor.rotation.x = -Math.PI / 2; floor.position.set(ctr.x, box.min.y - 0.4, ctr.z); floor.receiveShadow = true;
    scene.add(floor);
    renderer.shadowMap.enabled = true; renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    return floor;
  }

  // fixed isometric-style view for the KP image
  var ISO_DIR = [1.0, 0.52, -0.62];
  function renderSpecToPng(spec, THREE, o) {
    o = o || {};
    var W = o.width || 1200, Hh = o.height || 900, canvas = document.createElement('canvas');
    canvas.width = W; canvas.height = Hh;
    var renderer;
    try { renderer = new THREE.WebGLRenderer({ canvas: canvas, antialias: true, preserveDrawingBuffer: true }); } catch (e) { return null; }
    if (!renderer.getContext()) return null;
    renderer.setPixelRatio(1); renderer.setSize(W, Hh, false);
    var scene = new THREE.Scene(), obj = specToThree(spec, THREE);
    if (o.mounting) obj.setMounting(o.mounting);
    scene.add(obj.group); scene.updateMatrixWorld(true);
    var box = obj.box(), floor = studio(THREE, renderer, scene, box);
    var ctr = box.getCenter(new THREE.Vector3()), rad = box.getSize(new THREE.Vector3()).length() / 2;
    var dd = o.dir || ISO_DIR, dir = new THREE.Vector3(dd[0], dd[1], dd[2]).normalize();
    var cam = new THREE.OrthographicCamera(-1, 1, 1, -1, 0.1, rad * 10);
    cam.position.copy(ctr).addScaledVector(dir, rad * 4); cam.up.set(0, 1, 0); cam.lookAt(ctr); cam.updateMatrixWorld(true);
    // fit: project the 8 box corners into camera space
    var inv = cam.matrixWorldInverse, mnx = 1e9, mxx = -1e9, mny = 1e9, mxy = -1e9;
    for (var i = 0; i < 8; i++) {
      var v = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).applyMatrix4(inv);
      mnx = Math.min(mnx, v.x); mxx = Math.max(mxx, v.x); mny = Math.min(mny, v.y); mxy = Math.max(mxy, v.y);
    }
    var cx = (mnx + mxx) / 2, cy = (mny + mxy) / 2, hw = (mxx - mnx) / 2, hh = (mxy - mny) / 2, asp = W / Hh, m = 1.12;
    var hx = Math.max(hw * m, hh * m * asp), hy = hx / asp;
    cam.left = cx - hx; cam.right = cx + hx; cam.top = cy + hy; cam.bottom = cy - hy; cam.updateProjectionMatrix();
    renderer.render(scene, cam);
    var url = canvas.toDataURL('image/png');
    obj.dispose(); floor.geometry.dispose(); floor.material.dispose(); renderer.dispose();
    if (renderer.forceContextLoss) renderer.forceContextLoss();
    return url;
  }

  // smallest camera distance (along dir from ctr) at which the 8 corners of the world box stay inside the view
  function fitCamera(THREE, cam, ctr, dir, box, rad) {
    var d = rad * 1.2, i, k;
    for (k = 0; k < 80; k++) {
      cam.position.copy(ctr).addScaledVector(dir, d); cam.lookAt(ctr); cam.updateMatrixWorld(true); cam.updateProjectionMatrix();
      var ok = true;
      for (i = 0; i < 8 && ok; i++) {
        var v = new THREE.Vector3(i & 1 ? box.max.x : box.min.x, i & 2 ? box.max.y : box.min.y, i & 4 ? box.max.z : box.min.z).project(cam);
        if (Math.abs(v.x) > 0.9 || Math.abs(v.y) > 0.9) ok = false;
      }
      if (ok) break;
      d *= 1.05;
    }
    cam.near = Math.max(0.1, d - rad * 1.5); cam.far = d + rad * 4; cam.updateProjectionMatrix();
    return d;
  }

  // interactive viewer: lazy WebGL context, full dispose()
  function createViewer(container, spec, THREE, OrbitControls, o) {
    o = o || {};
    var w = container.clientWidth || 640, h = container.clientHeight || 480, renderer;
    try { renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: false }); } catch (e) { return null; }
    if (!renderer.getContext()) return null;
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1)); renderer.setSize(w, h);
    container.appendChild(renderer.domElement);
    var scene = new THREE.Scene(), obj = specToThree(spec, THREE);
    scene.add(obj.group); scene.updateMatrixWorld(true);
    var box = obj.box(), floor = studio(THREE, renderer, scene, box);
    var ctr = box.getCenter(new THREE.Vector3()), rad = box.getSize(new THREE.Vector3()).length() / 2;
    var cam = new THREE.PerspectiveCamera(32, w / h, rad / 50, rad * 40);
    var dir = new THREE.Vector3(ISO_DIR[0], ISO_DIR[1], ISO_DIR[2]).normalize();
    fitCamera(THREE, cam, ctr, dir, box, rad);
    var controls = new OrbitControls(cam, renderer.domElement);
    controls.target.copy(ctr); controls.enableDamping = false; controls.update();
    var dead = false, raf = 0;
    function draw() { raf = 0; if (!dead) renderer.render(scene, cam); }
    function req() { if (!raf && !dead) raf = requestAnimationFrame(draw); }
    controls.addEventListener('change', req);
    function resize() {
      var ww = container.clientWidth || w, hh = container.clientHeight || h;
      renderer.setSize(ww, hh); cam.aspect = ww / hh; cam.updateProjectionMatrix(); req();
    }
    window.addEventListener('resize', resize);
    function refit() {
      scene.updateMatrixWorld(true);
      var b = obj.box(), c = b.getCenter(new THREE.Vector3());
      floor.position.set(c.x, b.min.y - 0.4, c.z);
      controls.target.copy(c); fitCamera(THREE, cam, c, dir, b, rad); controls.update(); req();
    }
    req();
    return {
      renderer: renderer, canvas: renderer.domElement, scene: scene, camera: cam,
      setMounting: function (pos) { obj.setMounting(pos); refit(); },
      setWireframe: function (on) { obj.setWireframe(on); req(); },
      redraw: function () { renderer.render(scene, cam); },
      dispose: function () {
        dead = true; if (raf) cancelAnimationFrame(raf);
        window.removeEventListener('resize', resize); controls.dispose();
        obj.dispose(); floor.geometry.dispose(); floor.material.dispose();
        renderer.dispose(); if (renderer.forceContextLoss) renderer.forceContextLoss();
        if (renderer.domElement.parentNode) renderer.domElement.parentNode.removeChild(renderer.domElement);
      }
    };
  }

  return {
    CONCEPT_NOTE: CONCEPT_NOTE, MOUNTS: MOUNTS, COLORS: COLORS, ISO_DIR: ISO_DIR,
    buildModelSpec: buildModelSpec, specBounds: specBounds, worldBounds: worldBounds,
    specToThree: specToThree, renderSpecToPng: renderSpecToPng, createViewer: createViewer, roundedBoxGeometry: roundedBoxGeometry
  };
});
