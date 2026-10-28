/* VSF selection engine (prototype). Pure functions, no DOM. UMD: browser global VSFEngine, node require().
 * Implements docs/ARCHITECTURE.md section 4 for the VSF worm data (NMRV / NMRV-P gearmotors, NRV / NRV-P reducers).
 * Inputs and outputs mirror Selection::Request / Result so the Rails port is a transcription.
 * No prices: priceHook(item) returns null, so the KP hides price columns (KP_SPEC section 6). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.VSFEngine = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var N1_NOM = { 2: 2800, 4: 1400, 6: 900 };
  var FS_TOLERANCE = 0.03;            // digitised nomogram accuracy (notes.md)
  var SF_HOURS_COLS = [2, 8, 16, 24];
  var FZ = { pinion: 1.1, chain: 1.4, vpulley: 1.7, flat: 2.5 };
  var LOAD_CLASS_UK = { A: 'A – рівномірне', B: 'B – помірні поштовхи', C: 'C – сильні поштовхи' };
  var FAMILY_ORDER = ['NMRV', 'NMRV-P', 'NRV', 'NRV-P'];
  var MODEL_VERSION = 'vsf-proto-1';

  // ------------------------------------------------------------------ helpers
  function round(x, d) { var m = Math.pow(10, d); return Math.round(x * m) / m; }
  function isNum(x) { return typeof x === 'number' && isFinite(x); }
  function relDev(a, b) { return (a - b) / b; }
  function ceilTo(x, step) { return round(Math.ceil(x / step - 1e-9) * step, 2); }
  function num(x) { return x === '' || x === null || x === undefined ? null : Number(x); }
  function spaced(size) {
    var m = /^(NMRV-P|NMRV|NRV-P|NRV)(.*)$/.exec(size);
    return m ? m[1] + ' ' + m[2] : size;
  }
  function fmtI(i) { return String(round(i, 2)); }
  function outputUnitNumber(size) { var m = /(\d{3})$/.exec(size); return m ? m[1] : null; }
  function inputUnit(row) {
    if (row.cfg === 'single') return row.size;
    var m = /^(NMRV-P|NMRV|NRV-P|NRV)(\d{3})\/(\d{3})$/.exec(row.size);
    if (!m) return null;
    var n = parseInt(m[2], 10);
    var fam = (m[1] === 'NMRV-P' || m[1] === 'NRV-P') && n >= 63 ? m[1] : m[1].replace('-P', '');
    return fam + m[2];
  }
  function weightKey(row) {
    if (row.cfg === 'single') return row.size;
    var m = /(\d{3})\/(\d{3})$/.exec(row.size);
    return m ? m[1] + '-' + m[2] : null;
  }
  function err(field, code, msg) { return { field: field, code: code, message_uk: msg }; }

  // ------------------------------------------------------------------ service factor
  // Grid: [{c,h,s,fs,pg}] digitised from the VSF nomogram (p.10). Hours: next tabulated column (conservative,
  // ARCH 4.3.3). Starts: clamp <5 to 5, linear interpolation between tabulated points, >100 hard error.
  function fsLookup(grid, cls, hours, starts) {
    if (['A', 'B', 'C'].indexOf(cls) < 0) return { error: err('load_class', 'load_class', 'Клас навантаження має бути A, B або C') };
    if (!isNum(hours) || hours <= 0 || hours > 24) return { error: err('hours_per_day', 'hours', 'Годин на добу: 0 < h ≤ 24') };
    if (!isNum(starts) || starts < 0 || starts > 100) return { error: err('starts_per_hour', 'starts', 'Пусків на годину: 0 ≤ s ≤ 100 (поза діаграмою каталогу)') };
    var hcol = null;
    for (var k = 0; k < SF_HOURS_COLS.length; k++) if (SF_HOURS_COLS[k] >= hours) { hcol = SF_HOURS_COLS[k]; break; }
    var pts = grid.filter(function (g) { return g.c === cls && g.h === hcol; }).sort(function (a, b) { return a.s - b.s; });
    if (!pts.length) return { error: err('service_factor', 'no_grid', 'Немає даних діаграми для цього режиму') };
    var s = Math.max(starts, pts[0].s), raw = null, i;
    for (i = 0; i < pts.length; i++) if (pts[i].s === s) { raw = pts[i].fs; break; }
    if (raw === null) {
      for (i = 0; i < pts.length - 1; i++) {
        if (s > pts[i].s && s < pts[i + 1].s) {
          raw = pts[i].fs + (pts[i + 1].fs - pts[i].fs) * (s - pts[i].s) / (pts[i + 1].s - pts[i].s);
          break;
        }
      }
    }
    return {
      fs_raw: round(raw, 4), fs_lookup: ceilTo(raw, 0.05), hours_col: hcol, starts_used: s,
      tolerance: FS_TOLERANCE, src_page: pts[0].pg,
      note_uk: 'Оцифровано з діаграми каталогу (с. ' + pts[0].pg + '), точність ±' + FS_TOLERANCE.toFixed(2) +
        '; значення округлено вгору до 0,05 (колонка ' + hcol + ' год/добу)'
    };
  }

  // ------------------------------------------------------------------ data preparation
  function createEngine(data) {
    var rows = [], dropped = [], byId = {}, redIdx = {}, sizeMeta = {}, motorIdx = {}, i;
    var warnDefs = {};

    // reducer index for Mn2 matching
    data.ratings.forEach(function (r) {
      if (r.kind === 'red' && r.p1 > 0) redIdx[r.size + '|' + r.n1 + '|' + round(r.i, 2)] = r;
    });
    data.motors.forEach(function (m) {
      var k = m.frame + '|' + m.poles + '|' + round(m.p, 3);
      (motorIdx[k] = motorIdx[k] || []).push(m);
    });

    data.ratings.forEach(function (r) {
      var o = Object.assign({}, r), reason = null;
      o.n1nom = o.kind === 'gm' ? N1_NOM[o.poles] : o.n1;
      if (!(o.i > 0) || !(o.n2 > 0)) reason = 'bad_row';
      else if (o.kind === 'red') {
        var dv = Math.abs(o.n1 / o.i - o.n2) / o.n2;
        if (dv > 0.03 && o.n2 >= 5) reason = 'n2_vs_n1_over_i';       // gate 3, printed value rounded/truncated in catalogue
      } else if (o.n2 >= 10) {
        var ratio = (o.n2 * o.i) / o.n1nom;
        if (ratio < 0.85 || ratio > 1.12) reason = 'implied_n1_out_of_band';
      }
      if (o.kind === 'gm') {
        var red = redIdx[spacedRedKey(o)];
        var derived = isNum(o.t2) && isNum(o.fs) ? o.t2 * o.fs : null;
        if (red && derived !== null && Math.abs(red.t2 / derived - 1) <= 0.15) {
          o.mn2 = red.t2; o.mn2_src = 'table'; o.mn2_pg = red.pg;
        } else if (derived !== null) {
          o.mn2 = derived; o.mn2_src = 'derived'; o.mn2_pg = o.pg;
        } else if (!reason) reason = 'no_mn2';
        o.m2 = o.t2;
      } else {
        o.mn2 = o.t2; o.mn2_src = 'table'; o.mn2_pg = o.pg; o.m2 = null;
      }
      if (reason) { dropped.push({ id: o.id, reason: reason }); return; }
      rows.push(o); byId[o.id] = o;
    });
    function spacedRedKey(g) { return g.size.replace('NMRV', 'NRV') + '|' + g.n1nom + '|' + round(g.i, 2); }

    // size ranks inside (family, config) by max Mn2
    var maxBy = {};
    rows.forEach(function (r) {
      var k = r.fam + '|' + r.cfg + '|' + r.size;
      maxBy[k] = Math.max(maxBy[k] || 0, r.mn2);
    });
    var groups = {};
    Object.keys(maxBy).forEach(function (k) {
      var p = k.split('|'); var g = p[0] + '|' + p[1];
      (groups[g] = groups[g] || []).push({ size: p[2], mx: maxBy[k] });
    });
    Object.keys(groups).forEach(function (g) {
      groups[g].sort(function (a, b) { return a.mx - b.mx || (a.size < b.size ? -1 : 1); })
        .forEach(function (s, idx) { sizeMeta[g + '|' + s.size] = { rank: idx + 1, max_mn2: s.mx }; });
    });
    rows.forEach(function (r) { r.size_rank = sizeMeta[r.fam + '|' + r.cfg + '|' + r.size].rank; });
    rows.sort(function (a, b) { return a.id - b.id; });

    function radialFor(row) {
      var n = outputUnitNumber(row.size);
      for (var k = 0; k < data.radial.length; k++) {
        var e = data.radial[k];
        if (e.shaft === 'output' && /NMRV NMRV-P/.test(e.size) && e.size.slice(-3) === n) return e;
      }
      return null;
    }
    function weightFor(row) {
      var ws = data.weights[weightKey(row)];
      if (!ws) return null;
      var w = ws.filter(function (x) { return !x.frame; })[0] || ws[0];
      return w ? { kg: w.kg, pg: w.pg } : null;
    }
    function lubFor(row, pos) {
      var l = data.lubrication[row.size];
      if (!l) return null;
      var key = pos === 'B6' || pos === 'B7' ? 'B6-B7' : pos;
      return l[key] ? { l: l[key].l, type: l[key].type, pg: l[key].pg, pos: pos } : null;
    }
    function effFor(row) {
      if (row.cfg !== 'single') return null;
      var e = data.efficiency[row.size.replace('-P', '')];
      var v = e && e[String(round(row.i, 2))];
      return v ? v : null;
    }
    function frameSize(f) { return parseInt(f, 10); }
    function ifaceFrames(entry) { return String(entry.frame).split('/').map(Number); }

    // motor fit for a gearmotor row. Returns {ok, motor, warns, fails, pages}
    function motorFit(row, req, forceFrame) {
      var out = { ok: true, warns: [], fails: [], motor: null, pages: [] };
      var opts = String(row.ms || '').split('/').filter(Boolean);
      var unit = inputUnit(row);
      var iface = data.motor_interface[unit] || null;
      var best = null, bestScore = -1, reasons = [];
      if (forceFrame) opts = opts.filter(function (o) { return o === forceFrame; });
      opts.forEach(function (opt) {
        var sz = frameSize(opt), flanges = [];
        if (iface) {
          iface.forEach(function (e) { if (ifaceFrames(e).indexOf(sz) >= 0) flanges.push(e); });
        }
        var feas = flanges.filter(function (e) {
          if (req.flange && req.flange !== 'any' && e.flange !== req.flange) return false;
          var mx = data.flange_matrix[unit + '|' + e.frame + '|' + e.flange];
          var st = mx && mx[String(round(row.i, 2))];
          return st !== 'no';
        });
        var mots = motorIdx[opt + '|' + row.poles + '|' + round(row.p1, 3)] || [];
        var score = (iface ? (feas.length ? 2 : 0) : 1) + (mots.length ? 1 : 0);
        if (iface && !feas.length) reasons.push(opt);
        if (score > bestScore) { bestScore = score; best = { opt: opt, flanges: flanges, feas: feas, mots: mots }; }
      });
      if (!best) { out.ok = false; out.fails.push('motor_fit'); return out; }
      if (iface && !best.feas.length) { out.ok = false; out.fails.push('motor_fit'); }
      if (!iface) out.warns.push('motor_interface_unknown');
      var pref = { TP: 0, TH: 1, TS: 2 };
      var types = best.mots.slice().sort(function (a, b) { return pref[a.type] - pref[b.type]; });
      var chosen = types[0] || null;
      var fl = (best.feas.length ? best.feas : best.flanges);
      var flangeNames = []; fl.forEach(function (e) { if (flangeNames.indexOf(e.flange) < 0) flangeNames.push(e.flange); });
      var pick = fl.filter(function (e) { return !req.flange || req.flange === 'any' || e.flange === req.flange; })[0] || fl[0] || null;
      var lowkey = pick && data.flange_matrix[unit + '|' + pick.frame + '|' + pick.flange];
      lowkey = lowkey && lowkey[String(round(row.i, 2))];
      if (lowkey === 'warn') out.warns.push('flange_out_of_warranty');
      if (lowkey === 'lowkey') out.warns.push('flange_low_profile_key');
      out.motor = {
        frame: best.opt, alt_frames: opts.filter(function (o) { return o !== best.opt; }),
        poles: row.poles, p_kw: row.p1,
        line: chosen ? chosen.type : null, ie: chosen ? chosen.ie : null,
        in_motor_table: !!chosen, flanges: flangeNames,
        flange: pick ? pick.flange : null, flange_P: pick ? pick.P : null, bore_mm: pick ? pick.bore : null,
        iec_frame_label: pick ? pick.frame : null
      };
      if (!chosen) out.warns.push('motor_not_in_motor_table');
      if (chosen) out.pages.push(chosen.pg);
      if (pick) out.pages.push(pick.pg);
      return out;
    }

    // ------------------------------------------------------------ request normalisation
    function normalise(req0) {
      var req = {}, errors = [], warnings = [];
      Object.keys(req0 || {}).forEach(function (k) { req[k] = req0[k]; });
      ['load_torque_nm', 'load_power_kw', 'n2_rpm', 'ratio', 'hours_per_day', 'starts_per_hour', 'fs_min',
        'radial_load_n', 'radial_x_mm', 'element_diameter_mm', 'peak_torque_nm', 'ambient_c', 'n2_tolerance_pct',
        'ratio_tolerance_pct'].forEach(function (k) { req[k] = num(req[k]); });
      req.poles = req.poles === 'any' ? 'any' : (num(req.poles) || 4);
      req.family = req.family || 'gm';
      if (req.hours_per_day === null) req.hours_per_day = 8;
      if (req.starts_per_hour === null) req.starts_per_hour = 5;
      req.mounting_position = req.mounting_position || 'B3';
      req.flange = req.flange || 'any';
      var T = req.load_torque_nm, P = req.load_power_kw;
      if (T === null && P === null) errors.push(err('load_torque_nm', 'load_required', 'Вкажіть момент навантаження (Нм) або потужність (кВт)'));
      if (T !== null && !(T > 0 && T <= 120000)) errors.push(err('load_torque_nm', 'torque_range', 'Момент: 0 < T ≤ 120000 Нм'));
      if (P !== null && !(P > 0 && P <= 90)) errors.push(err('load_power_kw', 'power_range', 'Потужність: 0 < P ≤ 90 кВт'));
      var n1nom = req.poles === 'any' ? null : N1_NOM[req.poles];
      if (req.poles !== 'any' && !n1nom) errors.push(err('poles', 'poles', 'Кількість полюсів: 2, 4 або 6'));
      if (req.n2_rpm === null && req.ratio === null) errors.push(err('n2_rpm', 'speed_required', 'Вкажіть частоту на виході (об/хв) або передавальне число'));
      if (req.n2_rpm !== null && !(req.n2_rpm >= 0.1 && req.n2_rpm <= 1500)) errors.push(err('n2_rpm', 'n2_range', 'Частота на виході: 0,1…1500 об/хв'));
      if (req.n2_rpm !== null && n1nom && req.n2_rpm >= n1nom) errors.push(err('n2_rpm', 'n2_ge_n1', 'Частота на виході має бути менша за вхідну (' + n1nom + ')'));
      if (req.ratio !== null && !(req.ratio >= 1 && req.ratio <= 2700)) errors.push(err('ratio', 'ratio_range', 'Передавальне число: 1…2700'));
      if (req.n2_rpm !== null && req.ratio !== null && n1nom && Math.abs(n1nom / req.ratio - req.n2_rpm) / req.n2_rpm > 0.03)
        errors.push(err('ratio', 'n2_ratio_mismatch', 'n2 і i суперечать одне одному (n1/i = ' + round(n1nom / req.ratio, 2) + ' об/хв)'));
      if (req.n2_rpm !== null && (req.n2_rpm < 1 || req.n2_rpm > 500)) warnings.push('n2_unusual');
      if (!(req.hours_per_day > 0 && req.hours_per_day <= 24)) errors.push(err('hours_per_day', 'hours', 'Годин на добу: 0 < h ≤ 24'));
      if (!(req.starts_per_hour >= 0 && req.starts_per_hour <= 100)) errors.push(err('starts_per_hour', 'starts', 'Пусків на годину: 0…100'));
      else if (req.starts_per_hour > 30) warnings.push('starts_gt_30');
      if (req.fs_min !== null && !(req.fs_min >= 0.7 && req.fs_min <= 3.0)) errors.push(err('fs_min', 'fs_range', 'Сервіс-фактор вручну: 0,7…3,0'));
      else if (req.fs_min !== null && req.fs_min < 1) warnings.push('fs_lt_1');
      if (req.n2_tolerance_pct !== null && !(req.n2_tolerance_pct >= 0 && req.n2_tolerance_pct <= 20)) errors.push(err('n2_tolerance_pct', 'tol', 'Допуск за швидкістю: 0…20 %'));
      if (req.ratio_tolerance_pct !== null && !(req.ratio_tolerance_pct >= 0 && req.ratio_tolerance_pct <= 10)) errors.push(err('ratio_tolerance_pct', 'tol', 'Допуск за i: 0…10 %'));
      if (req.ambient_c !== null && !(req.ambient_c >= -40 && req.ambient_c <= 60)) errors.push(err('ambient_c', 'ambient', 'Температура: -40…+60 °C'));
      if (req.radial_load_n !== null && req.radial_load_n < 0) errors.push(err('radial_load_n', 'radial', 'Радіальне навантаження ≥ 0'));
      if (req.element && req.element !== 'none' && !(req.element_diameter_mm > 0)) errors.push(err('element_diameter_mm', 'element_d', 'Вкажіть діаметр елемента передачі'));
      // derive T / n2
      var n2t = req.n2_rpm, mode = req.n2_rpm !== null ? 'n2' : 'ratio';
      if (n2t === null && req.ratio !== null) {
        if (n1nom) n2t = n1nom / req.ratio;
        else { n2t = N1_NOM[4] / req.ratio; warnings.push('poles_any_assumed_4p_for_power'); }
      }
      if (T === null && P !== null && n2t) T = 9550 * P / n2t;
      else if (T !== null && P !== null && n2t && Math.abs(9550 * P / n2t - T) / T > 0.10)
        errors.push(err('load_power_kw', 'tp_mismatch', 'T і P не узгоджені: 9550·P/n2 = ' + round(9550 * P / n2t, 1) + ' Нм, задано ' + T + ' Нм'));
      req._T = T; req._n2t = n2t; req._mode = mode; req._n1nom = n1nom;
      return { req: req, errors: errors, warnings: warnings };
    }

    function requiredFs(req) {
      var d = fsLookup(data.service_factor, req.load_class, req.hours_per_day, req.starts_per_hour);
      if (d.error) return { error: d.error };
      var res = { lookup: d, fs_lookup: d.fs_lookup, source: 'series_chart', source_uk: 'за діаграмою каталогу', warnings: [] };
      var fs = d.fs_lookup;
      if (req.fs_min !== null) {
        if (req.fs_override) { fs = req.fs_min; res.source = 'manual'; res.source_uk = 'задано вручну'; res.warnings.push('fs_overridden'); }
        else if (req.fs_min > fs) { fs = req.fs_min; res.source = 'manual'; res.source_uk = 'задано вручну'; }
      }
      res.fs_req = fs;
      return res;
    }

    // ------------------------------------------------------------ per-row evaluation (select + verify)
    function evaluateRow(row, ctx, opts) {
      opts = opts || {};
      var req = ctx.req, T = req._T, fails = [], warns = [], checks = {};
      function chk(name, status, code) { checks[name] = status; if (status === 'fail') fails.push(code || name); }
      var isGm = row.kind === 'gm';
      // A1 family
      var famOk = ctx.famSet[row.fam];
      chk('family', famOk ? 'pass' : 'fail');
      // A2 poles
      var polesOk = req.poles === 'any' ? (isGm || [2800, 1400, 900].indexOf(row.n1) >= 0) : (isGm ? row.poles === req.poles : row.n1 === req._n1nom);
      chk('poles', polesOk ? 'pass' : 'fail');
      // A3 speed
      var dev, devKind;
      if (req._mode === 'ratio') { dev = relDev(row.i, req.ratio); devKind = 'ratio'; }
      else { dev = relDev(row.n2, req._n2t); devKind = 'n2'; }
      var tol = (devKind === 'ratio' ? (req.ratio_tolerance_pct === null ? 3 : req.ratio_tolerance_pct) : ctx.n2tol) / 100;
      chk('speed', Math.abs(dev) <= tol + 1e-12 ? 'pass' : 'fail');
      // A4 motor not overloaded
      if (isGm) chk('motor_torque', row.m2 >= T ? 'pass' : 'fail');
      // A5 gear strength incl. duty
      var mn2req = T * ctx.fs.fs_req;
      chk('gear_torque', row.mn2 >= mn2req - 1e-9 ? 'pass' : 'fail');
      // radial load
      var radial = radialFor(row), fre = null, fr2allowed = row.fr2 || (radial && radial.frmax) || null, frWarn = null;
      if (req.radial_load_n !== null && req.radial_load_n > 0) fre = req.radial_load_n;
      else if (req.element && req.element !== 'none' && req.element_diameter_mm > 0)
        fre = 2000 * T * FZ[req.element] / req.element_diameter_mm;
      if (fre !== null) {
        var allowed = fr2allowed;
        if (allowed === null) { warns.push('fr_unknown'); chk('radial', 'warn'); }
        else {
          if (req.radial_x_mm !== null && radial) allowed = Math.min(allowed * radial.a / (radial.b + req.radial_x_mm), radial.frmax || allowed);
          else { warns.push('fr_mid_shaft_only'); }
          fr2allowed = allowed;
          chk('radial', fre <= allowed ? 'pass' : 'fail');
        }
      }
      // peak torque
      if (req.peak_torque_nm !== null && req.peak_torque_nm > 0) chk('peak', req.peak_torque_nm <= 2 * row.mn2 ? 'pass' : 'fail');
      // motor fit / brake
      var mf = null;
      if (isGm) {
        mf = motorFit(row, req, opts.motorFrame);
        chk('motor_fit', mf.ok ? 'pass' : 'fail');
        warns = warns.concat(mf.warns);
        if (row.brk && !req.brake) chk('brake_only', 'fail');
        else if (row.brk) warns.push('brake_motor_only');
      }
      // reducer-only: required input power (informational) and motor hint
      var pin = null, eta = null, motorHint = null;
      if (!isGm) {
        if (row.p1 > 0) {
          eta = row.mn2 * row.n2 / (9550 * row.p1);
          eta = Math.min(0.98, Math.max(0.5, eta));
          pin = T * row.n2 / (9550 * eta);
          warns.push('eta_implied');
          var cands = data.motors.filter(function (m) { return (req.poles === 'any' || m.poles === req.poles) && m.p >= pin; })
            .sort(function (a, b) { return a.p - b.p || ({ TP: 0, TH: 1, TS: 2 }[a.type] - { TP: 0, TH: 1, TS: 2 }[b.type]); });
          if (cands.length) motorHint = { p_kw: cands[0].p, line: cands[0].type, ie: cands[0].ie };
        }
      }
      // soft checks
      warns.push('thermal_not_verified');
      if (isGm && row.mn2_src === 'derived') warns.push('mn2_derived');
      if (req.ambient_c !== null && (req.ambient_c < -5 || req.ambient_c > 40)) warns.push('ambient_out_of_range');
      if (req.starts_per_hour > 30) warns.push('starts_gt_30');
      if (req.hoisting) warns.push('worm_hoisting');
      if (req.output === 'solid') {
        var n = outputUnitNumber(row.size);
        var has = data.solid_shafts.some(function (s) { return String(parseInt(s.size, 10)) === String(parseInt(n, 10)); });
        if (!has) warns.push('solid_shaft_not_tabulated');
      }
      if (ctx.n2widened) warns.push('n2_tol_widened');
      if (req.poles === 'any' && !isGm) warns.push('reducer_n1_nominal_tables_only');
      var uniq = []; warns.forEach(function (w) { if (uniq.indexOf(w) < 0) uniq.push(w); });
      warns = uniq;

      var w = weightFor(row), lub = lubFor(row, req.mounting_position), eff = effFor(row);
      var pages = [row.pg];
      if (row.mn2_src === 'table' && row.mn2_pg !== row.pg) pages.push(row.mn2_pg);
      if (mf) pages = pages.concat(mf.pages);
      if (radial) pages.push(radial.pg);
      if (w) pages.push(w.pg);
      if (lub) pages.push(lub.pg);
      pages.push(ctx.fs.lookup.src_page);
      var seen = {}; pages = pages.filter(function (p) { if (seen[p]) return false; seen[p] = 1; return true; }).sort(function (a, b) { return a - b; });

      var util = mn2req / row.mn2 * 100;
      var cand = {
        row_id: row.id, key: row.kind + row.id,
        designation: spaced(row.size) + ' i=' + fmtI(row.i) + (mf && mf.motor ? ' ' + mf.motor.frame + ' ' + String(row.p1).replace('.', ',') + 'кВт ' + row.poles + 'P' : ' n1=' + row.n1) + ' ' + req.mounting_position,
        series: row.fam, size: row.size, size_spaced: spaced(row.size), config: row.cfg, kind: isGm ? 'gearmotor' : 'reducer',
        stages: row.cfg === 'combined' ? 2 : 1,
        i: row.i, n1: isGm ? row.n1nom : row.n1, n1_implied: isGm ? row.n1i : null, n2: row.n2,
        dev_kind: devKind, dev_pct: round(dev * 100, 2),
        n2_dev_pct: round(relDev(row.n2, req._n2t) * 100, 2),
        motor: mf ? mf.motor : null, motor_hint: motorHint, p1_kw: row.p1,
        m2_nm: row.m2, mn2_nm: row.mn2, mn2_source: row.mn2_src,
        fs_catalogue: isGm ? row.fs : null, fs_req: ctx.fs.fs_req, fs_app: round(row.mn2 / T, 2),
        utilisation_gear_pct: round(util, 1),
        utilisation_motor_pct: isGm ? round(T / row.m2 * 100, 1) : null,
        t2_req_nm: round(mn2req, 1),
        fr2_allowed_n: fr2allowed, fr2_applied_n: fre !== null ? round(fre, 0) : null,
        fr2_catalogue_n: row.fr2, fr1_n: row.fr1,
        p_in_req_kw: pin !== null ? round(pin, 3) : null, eta_implied: eta !== null ? round(eta, 3) : null,
        mass_kg: w ? w.kg : null, lubrication: lub, eta_catalogue: eff,
        size_rank: row.size_rank, brake_motor_only: !!row.brk,
        warnings: warns, checks: checks, fails: fails,
        src_page: row.pg, src_pages: pages
      };
      cand.image_key = imageKey(row);
      return cand;
    }

    function imageKey(row) {
      return row.fam + (row.cfg === 'combined' ? '_comb' : '');
    }

    function buildCtx(norm, fs, widen) {
      var req = norm.req, famSet = {};
      var fam = req.family;
      var list = fam === 'any' ? FAMILY_ORDER : fam === 'gm' ? ['NMRV', 'NMRV-P'] : (fam === 'NRV' ? ['NRV', 'NRV-P'] : Array.isArray(fam) ? fam : [fam]);
      list.forEach(function (f) { famSet[f] = true; });
      var base = req.n2_tolerance_pct === null ? 5 : req.n2_tolerance_pct;
      return { req: req, fs: fs, famSet: famSet, famOrder: list, n2tol: widen ? 10 : base, n2widened: !!widen };
    }

    // ------------------------------------------------------------ select
    function select(req0) {
      var norm = normalise(req0);
      var result = {
        engine_version: MODEL_VERSION, dataset: data.meta.catalogue, errors: norm.errors, warnings: norm.warnings.slice(),
        candidates: [], recommended_index: null, request: null, fs: null, no_candidate: null, dropped_rows: dropped.length
      };
      if (norm.errors.length) return result;
      var req = norm.req;
      var fs = requiredFs(req);
      if (fs.error) { result.errors.push(fs.error); return result; }
      result.warnings = result.warnings.concat(fs.warnings);
      result.fs = {
        fs_req: fs.fs_req, fs_lookup: fs.fs_lookup, source: fs.source, source_uk: fs.source_uk,
        tolerance: FS_TOLERANCE, note_uk: fs.lookup.note_uk, fs_raw: fs.lookup.fs_raw, hours_col: fs.lookup.hours_col,
        starts_used: fs.lookup.starts_used, src_page: fs.lookup.src_page
      };
      result.request = { T_load_nm: round(req._T, 2), n2_target_rpm: round(req._n2t, 3), mode: req._mode, poles: req.poles, t2_req_nm: round(req._T * fs.fs_req, 2) };

      function run(widen) {
        var ctx = buildCtx(norm, fs, widen);
        var ok = [], rejected = [];
        rows.forEach(function (row) {
          var c = evaluateRow(row, ctx, {});
          if (c.fails.length === 0) ok.push(c);
          else rejected.push(c);
        });
        return { ctx: ctx, ok: ok, rejected: rejected };
      }
      var r = run(false);
      if (!r.ok.length && req._mode === 'n2' && req.n2_tolerance_pct === null) {
        var r2 = run(true);
        if (r2.ok.length) { r = r2; result.warnings.push('n2_tol_widened'); }
      }
      var ok = r.ok;
      // one candidate per (size, i, poles): the smallest adequate motor; the others become alternatives
      var grp = {}, order = [];
      ok.forEach(function (c) {
        var k = c.size + '|' + c.n1 + '|' + c.i + '|' + (c.motor ? c.motor.poles : '');
        if (!grp[k]) { grp[k] = []; order.push(k); }
        grp[k].push(c);
      });
      var best = {};
      order.forEach(function (k) {
        var g = grp[k].slice().sort(function (x, y) { return x.p1_kw - y.p1_kw || x.row_id - y.row_id; });
        g[0].motor_alternatives = g.slice(1).map(function (h) {
          return { row_id: h.row_id, frame: h.motor && h.motor.frame, p_kw: h.p1_kw, m2_nm: h.m2_nm, utilisation_motor_pct: h.utilisation_motor_pct };
        });
        best[k] = g[0];
      });
      ok = order.map(function (k) { return best[k]; });
      if (!ok.length) {
        result.no_candidate = explainEmpty(r.rejected, r.ctx);
        return result;
      }
      // smallest adequate size + next size up, per (family, config) group
      var byGroup = {};
      ok.forEach(function (c) { var g = c.series + '|' + c.config; (byGroup[g] = byGroup[g] || []).push(c); });
      var kept = [];
      Object.keys(byGroup).forEach(function (g) {
        var ranks = []; byGroup[g].forEach(function (c) { if (ranks.indexOf(c.size_rank) < 0) ranks.push(c.size_rank); });
        ranks.sort(function (a, b) { return a - b; });
        var keep = ranks.slice(0, 2);
        byGroup[g].forEach(function (c) { if (keep.indexOf(c.size_rank) >= 0) { c.alternative = c.size_rank !== keep[0]; kept.push(c); } });
      });
      var famPref = {}; r.ctx.famOrder.forEach(function (f, ix) { famPref[f] = (req.family === 'any' || req.family === 'NRV' || req.family === 'gm') ? 0 : ix; });
      kept.sort(function (a, b) {
        return (famPref[a.series] - famPref[b.series]) ||
          (a.mn2_nm - b.mn2_nm) ||
          (Math.abs(a.dev_pct) - Math.abs(b.dev_pct)) ||
          ((a.motor ? a.motor.p_kw : a.p1_kw) - (b.motor ? b.motor.p_kw : b.p1_kw)) ||
          ((a.mass_kg === null ? 1e9 : a.mass_kg) - (b.mass_kg === null ? 1e9 : b.mass_kg)) ||
          (a.designation < b.designation ? -1 : a.designation > b.designation ? 1 : 0) ||
          (a.row_id - b.row_id);
      });
      if (req.family === 'any' || Array.isArray(req.family)) {
        // order across families is the preference order above; keep it deterministic
      }
      result.candidates = kept.slice(0, req.limit || 10);
      result.candidates.forEach(function (c, ix) { c.recommended = ix === 0; c.band = band(c.utilisation_gear_pct); });
      result.recommended_index = 0;
      return result;
    }

    function band(u) { return u >= 85 ? 'tight' : u < 50 ? 'oversized' : 'ok'; }

    function explainEmpty(rejected, ctx) {
      var pass12 = rejected.filter(function (c) { return c.checks.family === 'pass' && c.checks.poles === 'pass' && c.checks.speed === 'pass'; });
      var counts = {};
      rejected.forEach(function (c) { c.fails.forEach(function (f) { counts[f] = (counts[f] || 0) + 1; }); });
      var ranking = Object.keys(counts).map(function (k) { return { check: k, rows: counts[k] }; })
        .sort(function (a, b) { return b.rows - a.rows || (a.check < b.check ? -1 : 1); });
      var nearest = pass12.slice().sort(function (a, b) {
        return (a.fails.length - b.fails.length) || (b.mn2_nm - a.mn2_nm) || (a.row_id - b.row_id);
      }).slice(0, 3).map(function (c) { return { designation: c.designation, mn2_nm: c.mn2_nm, m2_nm: c.m2_nm, fails: c.fails, src_page: c.src_page }; });
      var reason;
      if (!pass12.length) reason = 'Немає рядків каталогу з потрібною швидкістю / кількістю полюсів у вибраному сімействі (допуск ' + ctx.n2tol + ' % за n2).';
      else {
        var mx = Math.max.apply(null, pass12.map(function (c) { return c.mn2_nm; }));
        reason = 'Для потрібної швидкості максимальний Mn2 у каталозі ' + round(mx, 0) + ' Нм; потрібно ' + round(ctx.req._T * ctx.fs.fs_req, 0) +
          ' Нм (T·fs). Найчастіше не проходить: ' + (ranking[0] ? ranking[0].check : '-') + '.';
      }
      return { code: 'no_candidate', reason_uk: reason, ranking: ranking, nearest_rejected: nearest };
    }

    // ------------------------------------------------------------ manual override (verify mode)
    function overrideOptions() {
      // size -> ratios -> motor variants; used by the UI dropdowns
      var out = {};
      rows.forEach(function (r) {
        var o = out[r.size] = out[r.size] || { size: r.size, kind: r.kind, fam: r.fam, rows: [] };
        o.rows.push({ id: r.id, i: r.i, n1: r.n1nom, n2: r.n2, p1: r.p1, ms: r.ms, poles: r.poles, kind: r.kind });
      });
      return out;
    }
    function verify(req0, rowId, motorFrame) {
      var norm = normalise(req0);
      var row = byId[rowId];
      var res = { errors: norm.errors, candidate: null, status: null, failures: [] };
      if (!row) { res.errors.push(err('row', 'row_not_found', 'Рядок каталогу не знайдено')); return res; }
      if (norm.errors.length) return res;
      var fs = requiredFs(norm.req);
      if (fs.error) { res.errors.push(fs.error); return res; }
      var ctx = buildCtx(norm, fs, false);
      ctx.famSet[row.fam] = true;
      var c = evaluateRow(row, ctx, { motorFrame: motorFrame || null });
      c.verify = true;
      res.candidate = c; res.failures = c.fails.slice(); res.fs = fs;
      res.status = c.fails.length ? 'failed_overridden' : (c.warnings.length ? 'warnings' : 'passed');
      // warnings that are only informational do not downgrade "passed" to "warnings" in the KP wording
      return res;
    }

    // ------------------------------------------------------------ KP technical snapshot (KP_SPEC section 4)
    function hsCode(c) {
      if (!c.motor) return null;
      if (c.motor.p_kw <= 7.5) return '8501 52 20 00';
      if (c.motor.p_kw <= 37) return '8501 52 30 00';
      return null;
    }
    function techSnapshot(c, req, extra) {
      extra = extra || {};
      var T = req._T !== undefined ? req._T : req.load_torque_nm;
      var hollow = (data.shaft_bores['NMRV' + outputUnitNumber(c.size)] || []);
      var solid = data.solid_shafts.filter(function (s) { return String(parseInt(s.size, 10)) === String(parseInt(outputUnitNumber(c.size), 10)); })[0];
      var outShaft = null;
      if (req.output === 'solid' && solid) outShaft = 'Ø' + String(solid.d).replace(/\s*h6/, '') + ' мм (опція, вихідний вал зі шпонкою)';
      else if (hollow.length) outShaft = 'порожнистий, Ø' + hollow.map(function (h) { return h.D; }).join(' / ') + ' мм H8 (на вибір)';
      var versionMap = { foot: 'на лапах (корпус з лапами)', flange: 'фланцеве (вихідний фланець)', torque_arm: 'насадне з моментним важелем' };
      var snap = {
        gear: {
          series: c.series + ' – черв\'ячна' + (c.series === 'NMRV-P' ? ' (NMRVpower)' : c.series === 'NRV-P' ? ' (NRVpower)' : ''),
          size: c.size_spaced,
          stages: c.stages,
          version: versionMap[req.version || 'foot'] || null,
          output_shaft: outShaft,
          mounting_position: req.mounting_position,
          terminal_box_position: extra.terminal_box || null,
          i: c.i,
          n1_n2: c.n1 + ' / ' + c.n2,
          m2: c.m2_nm,
          mn2: c.mn2_nm,
          fs_catalogue: c.fs_catalogue,
          fs_app: c.fs_app,
          utilisation: c.utilisation_gear_pct,
          fr2: c.fr2_allowed_n,
          lubricant: c.lubrication ? (c.lubrication.type.replace(/,.*$/, '') + ', ' + String(c.lubrication.l).replace('.', ',') + ' л' + (/for life/.test(c.lubrication.type) ? ' (на весь термін служби)' : '')) : null,
          paint: 'RAL 5010 (синій), епоксидно-поліефірне',
          thermal: null,
          options: extra.options || null,
          eta_catalogue: c.eta_catalogue ? c.eta_catalogue.dyn : null,
          fr1: c.kind === 'reducer' ? c.fr1_n : null
        },
        motor: null, mass_kg: c.mass_kg, hs_code: extra.hs_code !== undefined ? extra.hs_code : hsCode(c),
        source: 'Каталог Motovario VSF, с. ' + c.src_page + (c.src_pages.length > 1 ? ' (також ' + c.src_pages.filter(function (p) { return p !== c.src_page; }).join(', ') + ')' : '')
      };
      if (c.kind === 'gearmotor' && c.motor) {
        snap.motor = {
          type: c.motor.line ? c.motor.line + ' – ' + c.motor.ie : null,
          frame: c.motor.frame, poles: c.motor.poles, p_kw: c.motor.p_kw,
          n_rpm: null,
          voltage: c.motor.p_kw <= 3 ? '230/400 Δ/Y' : '400/690 Δ/Y',
          frequency: 50, ie_class: c.motor.ie, ip: 'IP55', insulation: 'F', duty: 'S1',
          brake: req.brake ? 'так' : null, i_n: null, cos_phi: null, eta: null,
          flange: c.motor.flange ? c.motor.flange + (c.motor.flange_P ? ' Ø' + c.motor.flange_P : '') : null
        };
      } else {
        snap.reducer_note = 'Двигун не входить у комплект поставки; вхідний вал (редуктор NRV)';
        if (c.motor_hint) snap.motor_hint = c.motor_hint;
      }
      return snap;
    }

    // ------------------------------------------------------------ simple mode (power kW + output rpm)
    // selectSimple({p_kw, n2_rpm, poles?, family?, min_fs?, tol_pct?, limit?}) -> plain JSON. Gearmotor rows only (no
    // brake-only rows). fs = Mn2 / M2 from the catalogue row. Nothing is invented: a variant needs i, M2 and fs.
    var SIMPLE_DUTY = { load_class: 'B', hours_per_day: 8, starts_per_hour: 10 };
    function fmtKw(p) { return String(p).replace('.', ','); }
    function housingNo(size) { var n = outputUnitNumber(size); return n ? parseInt(n, 10) : 9999; }
    function simpleFamilies(f) { return f === 'NMRV' ? ['NMRV'] : f === 'NMRV-P' ? ['NMRV-P'] : ['NMRV', 'NMRV-P']; }
    function selectSimple(p0) {
      p0 = p0 || {};
      var P = num(p0.p_kw), N2 = num(p0.n2_rpm), minFs = num(p0.min_fs), limit = num(p0.limit) || 12;
      var poles = p0.poles === undefined || p0.poles === null || p0.poles === '' || p0.poles === 'any' ? 'any' : num(p0.poles);
      var fam = p0.family === 'NMRV' || p0.family === 'NMRV-P' ? p0.family : 'all';
      if (minFs === null) minFs = 1.0;
      var out = {
        engine_version: MODEL_VERSION, status: 'ok', errors: [], request: { p_kw: P, n2_rpm: N2, poles: poles, family: fam, min_fs: minFs },
        power: null, tol_pct: null, widened: false, variants: [], excluded_by_fs: 0, hint_uk: null, suggestions: { powers: [], speeds: [], powers_for_speed: [] },
        duty_defaults: SIMPLE_DUTY
      };
      if (P === null || N2 === null) { out.status = 'incomplete'; return out; }
      if (!(P > 0 && P <= 90)) out.errors.push(err('p_kw', 'power_range', 'Потужність двигуна: 0 < P ≤ 90 кВт'));
      if (!(N2 >= 0.1 && N2 <= 1500)) out.errors.push(err('n2_rpm', 'n2_range', 'Частота на виході: 0,1…1500 об/хв'));
      if (poles !== 'any' && !N1_NOM[poles]) out.errors.push(err('poles', 'poles', 'Кількість полюсів: 2, 4 або 6'));
      if (!(minFs >= 0.5 && minFs <= 3)) out.errors.push(err('min_fs', 'fs_range', 'Мінімальний сервіс-фактор: 0,5…3'));
      if (out.errors.length) { out.status = 'error'; return out; }
      var famSet = simpleFamilies(fam);
      var pool = rows.filter(function (r) {
        return r.kind === 'gm' && !r.brk && famSet.indexOf(r.fam) >= 0 && (poles === 'any' || r.poles === poles) && isNum(r.m2) && r.m2 > 0 && isNum(r.mn2) && isNum(r.i) && r.i > 0;
      });
      var powers = []; pool.forEach(function (r) { if (powers.indexOf(r.p1) < 0) powers.push(r.p1); });
      powers.sort(function (a, b) { return a - b; });
      var up = powers.filter(function (p) { return p >= P - 1e-9; });
      if (!up.length) {
        out.status = 'empty';
        out.suggestions.powers = powers.slice(-4);
        out.hint_uk = 'У каталозі немає двигунів потужністю ' + fmtKw(P) + ' кВт і більше для вибраних умов. Максимальна потужність: ' + fmtKw(powers[powers.length - 1]) + ' кВт.';
        return out;
      }
      var matched = up[0], exact = Math.abs(matched - P) < 1e-6;
      out.power = { typed: P, matched: matched, exact: exact, next: up.slice(exact ? 1 : 1, 5), lower: powers.filter(function (p) { return p < matched; }).slice(-2) };
      out.suggestions.powers = (exact ? [] : [matched]).concat(up.slice(1, 5)).concat(exact ? powers.filter(function (p) { return p < matched; }).slice(-2) : []);
      function gather(pw, tol) {
        var inP = pool.filter(function (r) { return Math.abs(r.p1 - pw) < 1e-9; });
        var near = inP.filter(function (r) { return Math.abs(r.n2 - N2) / N2 <= tol / 100 + 1e-12; });
        var byFs = near.filter(function (r) { return r.mn2 / r.m2 >= minFs - 1e-9; });
        return { inP: inP, near: near, ok: byFs };
      }
      var tol = p0.tol_pct === undefined || p0.tol_pct === null || p0.tol_pct === '' ? 5 : num(p0.tol_pct);
      var g = gather(matched, tol);
      if (g.ok.length < 3 && tol < 10 && (p0.tol_pct === undefined || p0.tol_pct === null || p0.tol_pct === '')) {
        var g2 = gather(matched, 10);
        if (g2.ok.length > g.ok.length) { g = g2; tol = 10; out.widened = true; }
      }
      out.tol_pct = tol;
      out.excluded_by_fs = g.near.length - g.ok.length;
      // one entry per (size, config, i, poles, power): keep the first row id (the catalogue has duplicates only for motor frames)
      var seen = {}, list = [];
      g.ok.slice().sort(function (a, b) { return a.id - b.id; }).forEach(function (r) {
        var k = r.size + '|' + r.cfg + '|' + r.i + '|' + r.poles + '|' + r.p1;
        if (!seen[k]) { seen[k] = 1; list.push(r); }
      });
      list.forEach(function (r) { r._fs = r.mn2 / r.m2; });
      list.sort(function (a, b) {
        return (housingNo(a.size) - housingNo(b.size)) || ((a.cfg === 'single' ? 0 : 1) - (b.cfg === 'single' ? 0 : 1)) ||
          (Math.abs(a._fs - minFs) - Math.abs(b._fs - minFs)) || (Math.abs(a.n2 - N2) - Math.abs(b.n2 - N2)) ||
          (a.fam < b.fam ? -1 : a.fam > b.fam ? 1 : 0) || (a.id - b.id);
      });
      if (!list.length) {
        out.status = 'empty';
        var sp = {}; g.inP.forEach(function (r) { if (r.mn2 / r.m2 >= minFs - 1e-9) sp[round(r.n2, 1)] = 1; });
        var speeds = Object.keys(sp).map(Number).sort(function (a, b) { return Math.abs(a - N2) - Math.abs(b - N2) || a - b; }).slice(0, 6).sort(function (a, b) { return a - b; });
        out.suggestions.speeds = speeds;
        powers.forEach(function (pw) { if (pw !== matched && gather(pw, tol).ok.length) out.suggestions.powers_for_speed.push(pw); });
        out.suggestions.powers_for_speed.sort(function (a, b) { return Math.abs(a - matched) - Math.abs(b - matched) || a - b; });
        out.suggestions.powers_for_speed = out.suggestions.powers_for_speed.slice(0, 5).sort(function (a, b) { return a - b; });
        out.hint_uk = 'Для ' + fmtKw(matched) + ' кВт немає варіантів із n2 ' + fmt0(N2) + ' об/хв ±' + tol + ' %' + (out.excluded_by_fs ? ' і сервіс-фактором ≥ ' + String(round(minFs, 2)).replace('.', ',') + ' (відсіяно за fs: ' + out.excluded_by_fs + ')' : '') + '.' +
          (speeds.length ? ' Для цієї потужності є швидкості: ' + speeds.map(fmt0).join(', ') + ' об/хв.' : '') +
          (out.suggestions.powers_for_speed.length ? ' Для цієї швидкості є потужності: ' + out.suggestions.powers_for_speed.map(fmtKw).join(', ') + ' кВт.' : '');
        return out;
      }
      var total = list.length;
      list = list.slice(0, limit);
      out.total_found = total;
      out.variants = list.map(function (r) {
        var req = Object.assign({ load_torque_nm: r.m2, n2_rpm: r.n2, poles: r.poles, family: r.fam, mounting_position: 'B3', version: 'foot', output: 'hollow' }, SIMPLE_DUTY);
        var v = verify(req, r.id, null), c = v.candidate;
        var fs = r.mn2 / r.m2;
        return {
          row_id: r.id, key: 'gm' + r.id,
          designation: spaced(r.size) + ' i=' + fmtI(r.i) + (c && c.motor ? ' ' + c.motor.frame : '') + ' ' + fmtKw(r.p1) + 'кВт ' + r.poles + 'P',
          series: r.fam, size: r.size, size_spaced: spaced(r.size), config: r.cfg, stages: r.cfg === 'combined' ? 2 : 1,
          i: r.i, poles: r.poles, n1: N1_NOM[r.poles], n2: r.n2, dev_pct: round(relDev(r.n2, N2) * 100, 1),
          p_kw: r.p1, motor: c ? c.motor : null, m2_nm: r.m2, mn2_nm: r.mn2, mn2_source: r.mn2_src,
          fs: round(fs, 2), fs_catalogue: isNum(r.fs) ? r.fs : null, fs_band: fs >= 1.25 ? 'green' : fs >= 1.0 ? 'amber' : 'red',
          mass_kg: c ? c.mass_kg : null, image_key: c ? c.image_key : imageKey(r), src_page: r.pg, src_pages: c ? c.src_pages : [r.pg],
          cand: c, housing_no: housingNo(r.size)
        };
      });
      out.status = 'ok';
      return out;
    }
    function fmt0(x) { return String(round(x, 1)).replace('.', ','); }

    // ------------------------------------------------------------ misc
    function priceHook(item) { return null; }   // D1: no prices yet; KP hides price columns when every hook is null

    function designationList() {
      var seen = {}, out = [];
      rows.forEach(function (r) { if (!seen[r.size]) { seen[r.size] = 1; out.push(r.size); } });
      return out;
    }

    return {
      version: MODEL_VERSION, rows: rows, rowById: function (id) { return byId[id] || null; }, dropped: dropped,
      normalise: normalise, requiredFs: requiredFs, select: select, selectSimple: selectSimple, verify: verify, overrideOptions: overrideOptions,
      techSnapshot: techSnapshot, priceHook: priceHook, sizeMeta: sizeMeta, designationList: designationList,
      fsLookup: function (c, h, s) { return fsLookup(data.service_factor, c, h, s); },
      data: data
    };
  }

  var engineCache = typeof WeakMap === 'function' ? new WeakMap() : null;
  function selectSimple(params, data) {
    var e = engineCache && engineCache.get(data);
    if (!e) { e = createEngine(data); if (engineCache) engineCache.set(data, e); }
    return e.selectSimple(params);
  }

  return {
    createEngine: createEngine, selectSimple: selectSimple, fsLookup: fsLookup, N1_NOM: N1_NOM, FS_TOLERANCE: FS_TOLERANCE, LOAD_CLASS_UK: LOAD_CLASS_UK,
    FAMILY_ORDER: FAMILY_ORDER, spaced: spaced, inputUnit: inputUnit, outputUnitNumber: outputUnitNumber
  };
});
