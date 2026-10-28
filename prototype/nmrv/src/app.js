/* NMRV intermediate model: UI layer (forms, candidates, quote, saved quotes). Browser only.
 * Layers: data.json (catalogue) | engine.js (pure: selection, pricing, quote JSON) | app.js (this file: UI + CalcHost) | kp-template.js + kp.css (KP markup).
 * Everything the calculator needs from the surrounding system goes through CalcHost below. */

// ======================================================================== CalcHost
// Host adapter. Standalone default = localStorage (try/catch) + window.print. To embed into the Rails CRM (new_ax_crm) replace
// THIS ONE OBJECT (or set window.CalcHostOverride before this script runs; its methods replace the defaults) with fetch() calls to /api/v1.
// Contract (full text in docs/NMRV_MODEL.md):
//   getSeller()                 -> {name, short_name, edrpou, ipn, address, phone, email, site, iban, bank, mfo, dealer_statement} | {}
//   getManager()                -> {name, position, phone, email, office_name, office_contacts} | {}      (current CRM user)
//   getCustomerCandidates(q)    -> [{company:{code,name,edrpou,address}, person:{name,honorific,phone,email}}]   (CRM Company + Person)
//   getFxRate()                 -> number (UAH per EUR) | null
//   getPrice(articleKey)        -> {purchase_eur, margin_pct?} | null        null = "ціна за запитом"; stub returns null
//   saveQuote(quoteJson)        -> Promise<{id}>        (CRM: POST/PATCH, stored as CalculationRecord, calc_type 'motovario_nmrv')
//   loadQuotes()                -> Promise<quoteJson[]> (newest first)
//   deleteQuote(id)             -> Promise<void>
//   exportPdf(quoteJson)        -> Promise<void>        (standalone: window.print of the rendered KP)
// Synchronous getters are fed by data the host page already has (Rails view locals / Stimulus values); only I/O methods are async.
var CalcHost = (function () {
  var K_QUOTES = 'nmrv_quotes_v1', K_PROFILE = 'nmrv_profile_v1';
  function lsGet(k, dflt) { try { var s = window.localStorage.getItem(k); return s ? JSON.parse(s) : dflt; } catch (e) { return dflt; } }
  function lsSet(k, v) { try { window.localStorage.setItem(k, JSON.stringify(v)); return true; } catch (e) { return false; } }
  function quotes() { var o = lsGet(K_QUOTES, null); return o && Array.isArray(o.quotes) ? o.quotes : []; }
  function newId() { return 'q_' + Date.now().toString(36) + Math.random().toString(36).slice(2, 7); }
  var host = {
    getSeller: function () { return (lsGet(K_PROFILE, {}).seller) || {}; },
    getManager: function () { return (lsGet(K_PROFILE, {}).manager) || {}; },
    getCustomerCandidates: function (q) {
      var seen = {}, out = [];
      quotes().forEach(function (x) {
        var c = x.customer || {}; if (!c.name) return;
        var key = c.name + '|' + (c.edrpou || ''); if (seen[key]) return; seen[key] = 1;
        if (q && c.name.toLowerCase().indexOf(String(q).toLowerCase()) < 0) return;
        out.push({ company: { code: c.code, name: c.name, edrpou: c.edrpou, address: c.address }, person: x.contact || {} });
      });
      return out;
    },
    getFxRate: function () { return null; },
    getPrice: function (articleKey) { return null; },
    saveQuote: function (q) {
      var list = quotes(), now = new Date().toISOString(), copy = JSON.parse(JSON.stringify(q));
      copy.id = copy.id || newId(); copy.updated_at = now; copy.created_at = copy.created_at || now;
      var ix = list.findIndex(function (x) { return x.id === copy.id; });
      if (ix >= 0) list[ix] = copy; else list.push(copy);
      return lsSet(K_QUOTES, { v: 1, quotes: list }) ? Promise.resolve({ id: copy.id, updated_at: now }) : Promise.reject(new Error('storage_unavailable'));
    },
    loadQuotes: function () {
      return Promise.resolve(quotes().slice().sort(function (a, b) { return String(b.updated_at).localeCompare(String(a.updated_at)); }));
    },
    deleteQuote: function (id) {
      return lsSet(K_QUOTES, { v: 1, quotes: quotes().filter(function (x) { return x.id !== id; }) }) ? Promise.resolve() : Promise.reject(new Error('storage_unavailable'));
    },
    exportPdf: function (q) { window.print(); return Promise.resolve(); },
    // standalone-only convenience (a CRM host omits it: seller/manager come from the CRM)
    rememberProfile: function (p) { lsSet(K_PROFILE, p); }
  };
  if (window.CalcHostOverride) Object.keys(window.CalcHostOverride).forEach(function (k) { host[k] = window.CalcHostOverride[k]; });
  return host;
})();

(function () {
  'use strict';
  var D = window.NMRV_DATA, IMGS = window.NMRV_IMG || {}, EN = window.NmrvEngine, M3 = window.NmrvModel3D, KPT = window.NmrvKP;
  var E = EN.createEngine(D);
  var U = KPT.util, esc = U.esc, has = U.has, fmt = U.fmt, today = U.today, dmy = U.dmy, typeName = U.typeName, bar = U.bar;
  var state = { items: [], cands: [], raw: null, nextId: 1, overrideTarget: null, ov: null, pngCache: {}, quoteId: null, createdAt: null };

  function $(id) { return document.getElementById(id); }

  var WARN = {
    thermal_not_verified: 'Тепловий розрахунок не виконано: у каталозі немає даних Pth для VSF',
    mn2_derived: 'Mn2 обчислено як M2·fs (немає відповідного рядка таблиці редукторів)',
    fr_mid_shaft_only: 'Fr2 за каталогом (середина вала); для точки x вкажіть відстань від буртика',
    fr_unknown: 'Допустиме радіальне навантаження невідоме',
    eta_implied: 'ККД оцінено за таблицею редуктора (Mn2·n2/9550·Pn1)',
    n2_tol_widened: 'Допуск за n2 автоматично розширено до 10 %',
    brake_motor_only: 'Цей двигун доступний лише в гальмівному виконанні',
    motor_interface_unknown: 'Для вхідного вузла немає таблиці фланців двигуна; сумісність не перевірено',
    motor_not_in_motor_table: 'Двигуна немає в таблиці потужностей каталогу (с. 69); тип/клас не показано',
    flange_out_of_warranty: 'Каталог: для цієї комбінації фланця й i не використовувати поза гарантією',
    flange_low_profile_key: 'Для фланця двигуна потрібна шпонка низького профілю',
    worm_hoisting: 'Черв\'ячна пара: не покладайтеся на самогальмування в підйомних механізмах',
    ambient_out_of_range: 'Температура поза -5…+40 °C: уточніть у техслужби Motovario',
    starts_gt_30: 'Понад 30 пусків/год: перевірте допустиму кількість пусків двигуна',
    solid_shaft_not_tabulated: 'Для цього типорозміру суцільний вихідний вал у каталозі не наведено',
    fs_overridden: 'Сервіс-фактор замінено вручну',
    fs_lt_1: 'Сервіс-фактор менший за 1,0',
    n2_unusual: 'Незвичайна частота на виході (<1 або >500 об/хв)',
    poles_any_assumed_4p_for_power: 'Для переведення потужності в момент прийнято n1 = 1400 об/хв',
    reducer_n1_nominal_tables_only: 'Для редукторів використано лише таблиці 2800/1400/900 об/хв'
  };
  var CHECK_UK = {
    family: 'інше сімейство', poles: 'інша кількість полюсів / частота входу', speed: 'швидкість або i поза допуском',
    motor_torque: 'момент двигуна M2 менший за момент навантаження', gear_torque: 'Mn2 менший за T·fs',
    radial: 'радіальне навантаження перевищує допустиме', peak: 'піковий момент більший за 2·Mn2',
    motor_fit: 'двигун не стикується з редуктором (фланець / співвідношення)', brake_only: 'двигун лише з гальмом'
  };
  var CLASS_UK = EN.LOAD_CLASS_UK;

  // ------------------------------------------------------------------ form
  function readForm() {
    var v = function (id) { return $(id).value; };
    return {
      load_torque_nm: v('f_torque'), load_power_kw: v('f_power'), load_class: v('f_class'),
      hours_per_day: v('f_hours'), starts_per_hour: v('f_starts'), fs_min: v('f_fsmin'), fs_override: $('f_fsover').checked,
      n2_rpm: v('f_n2'), ratio: v('f_ratio'), poles: v('f_poles'), family: v('f_family'),
      n2_tolerance_pct: v('f_tol'), brake: $('f_brake').checked,
      mounting_position: v('f_mount'), output: v('f_output'), version: v('f_version'), flange: v('f_flange'),
      hoisting: $('f_hoist').checked,
      radial_load_n: v('f_radial'), element: v('f_elem'), element_diameter_mm: v('f_elemd'), radial_x_mm: v('f_radx'),
      peak_torque_nm: v('f_peak'), ambient_c: v('f_ambient'), qty: v('f_qty')
    };
  }
  function resetForm() {
    ['f_torque', 'f_power', 'f_n2', 'f_ratio', 'f_fsmin', 'f_tol', 'f_radial', 'f_elemd', 'f_radx', 'f_peak', 'f_ambient'].forEach(function (id) { $(id).value = ''; });
    $('f_hours').value = 8; $('f_starts').value = 10; $('f_qty').value = 1;
    $('errors').innerHTML = ''; $('results').innerHTML = ''; $('fsbox').innerHTML = '';
  }

  function warnChips(list) {
    return list.map(function (w) { return '<span class="chip" title="' + esc(w) + '">' + esc(WARN[w] || w) + '</span>'; }).join('');
  }
  function photoFor(c) {
    var p = D.images.photos[c.image_key] || null;
    return p && IMGS[p.file] ? { src: IMGS[p.file], pg: p.pg } : null;
  }
  // ------------------------------------------------------------------ concept 3D (model3d.js; catalogue dimensions only)
  var CONCEPT_NOTE = M3 ? M3.CONCEPT_NOTE : 'Ілюстрація, концептуальна модель; розміри — за каталогом Motovario';
  var threeLib = null;
  function getThree() {           // lazy: the 700 KB library is evaluated only on the first 3D use
    if (threeLib !== null) return threeLib || null;
    try {
      var V = window.NMRV_VENDOR, T = new Function(V.three)();
      threeLib = { THREE: T, OrbitControls: new Function('THREE', V.orbit)(T) };
    } catch (e) { threeLib = false; if (window.console) console.warn('3D library unavailable: ' + e.message); }
    return threeLib || null;
  }
  function specFor(c, req) {
    if (!M3) return { error: 'no_dimensions', reason: 'model3d_missing' };
    return M3.buildModelSpec(c, c.motor, D, { mounting: req && req.mounting_position, version: req && req.version });
  }
  function modelKey(it) {
    var c = it.cand;
    return [c.series, c.size, c.config, c.motor ? c.motor.frame + '|' + c.motor.flange + '|' + c.motor.poles : '-', it.req && it.req.version].join('/');
  }
  function threeBtn(c, req) {
    var sp = specFor(c, req);
    return sp.error ? '<button type="button" class="btn small m3d-btn" disabled title="3D недоступне: немає каталожних розмірів (' + esc(sp.reason || '') + ')">3D</button>'
      : '<button type="button" class="btn small m3d-btn" title="Концептуальна 3D-модель за каталожними розмірами">3D</button>';
  }
  var viewer = null, m3dCtx = null;
  function close3d() {
    if (viewer) { viewer.dispose(); viewer = null; }
    $('m3d-view').innerHTML = '';
    $('m3d').hidden = true; m3dCtx = null;
  }
  function open3d(c, req) {
    m3dCtx = { c: c, req: req };
    var spec = specFor(c, req), view = $('m3d-view'), ph = photoFor(c);
    $('m3d-title').textContent = c.designation;
    $('m3d-pos').value = (spec.mount && spec.mount.pos) || req.mounting_position || 'B3';
    $('m3d-wire').checked = false;
    $('m3d').hidden = false;
    var fallback = function (why) {
      view.innerHTML = '<div class="m3d-fb">' + (ph ? '<img alt="" src="' + ph.src + '">' : '') + '<p class="muted">' + esc(why) + ' Показано фото з каталогу.</p></div>';
      $('m3d-info').textContent = '';
    };
    if (spec.error) { fallback('3D-модель недоступна: немає каталожних розмірів (' + (spec.reason || '') + (spec.missing && spec.missing.length ? ': ' + spec.missing.join(', ') : '') + ').'); return; }
    var tp = getThree();
    if (!tp) { fallback('3D-бібліотека не завантажилась.'); return; }
    viewer = M3.createViewer(view, spec, tp.THREE, tp.OrbitControls);
    if (!viewer) { fallback('WebGL недоступний у цьому браузері.'); return; }
    viewer.setMounting($('m3d-pos').value);
    var b = spec.bbox.size;
    $('m3d-info').textContent = 'Габарити моделі за каталогом (B3), мм: довжина ' + fmt(b[2], 0) + ' × ширина ' + fmt(b[0], 0) + ' × висота ' + fmt(b[1], 0) + '. ' + CONCEPT_NOTE + '. Джерело: каталог, с. ' + spec.src_pages.join(', ') + '.';
  }
  // KP image: fixed isometric render (B3 frame) of the concept model, cached per unit; PNG data URL 1200x900
  function prepareModelImages(items) {
    var todo = items.filter(function (it) { return !(modelKey(it) in state.pngCache); });
    if (!todo.length) return null;
    return todo.reduce(function (p, it) {
      return p.then(function () {
        return new Promise(function (res) {
          setTimeout(function () {
            var png = null;
            try {
              var spec = specFor(it.cand, it.req);
              var tp = !spec.error && getThree();
              if (tp) png = M3.renderSpecToPng(spec, tp.THREE, { width: 1200, height: 900, mounting: 'B3' });
            } catch (e) { png = null; if (window.console) console.warn('3D render failed: ' + e.message); }
            state.pngCache[modelKey(it)] = png;
            res();
          }, 0);
        });
      });
    }, Promise.resolve());
  }

  function motorOptionsHtml(c, idx) {
    if (!c.motor) return c.kind === 'reducer' ? '<span class="muted">без двигуна</span>' + (c.motor_hint ? '<div class="sub">двигун ≥ ' + fmt(c.motor_hint.p_kw) + ' кВт (' + c.motor_hint.line + ')</div>' : '') : '';
    var m = c.motor;
    var desc = m.frame + ' · ' + fmt(m.p_kw) + ' кВт · ' + m.poles + 'p' + (m.line ? ' · ' + m.line + ' ' + m.ie : '') + (m.flange ? ' · ' + m.flange : '');
    var opts = c._opts || [];
    if (opts.length > 1) {
      return '<select class="motsel" data-idx="' + idx + '">' + opts.map(function (o) {
        return '<option value="' + o.row_id + '|' + esc(o.frame) + '"' + (o.row_id === c.row_id && o.frame === m.frame ? ' selected' : '') + '>' + esc(o.frame) + ' · ' + fmt(o.p_kw) + ' кВт</option>';
      }).join('') + '</select><div class="sub">' + esc(desc) + '</div>';
    }
    return esc(desc);
  }

  function renderErrors(res) {
    var el = $('errors');
    if (!res.errors.length) { el.innerHTML = ''; return; }
    el.innerHTML = '<ul>' + res.errors.map(function (e) { return '<li>' + esc(e.message_uk) + '</li>'; }).join('') + '</ul>';
  }
  function renderFs(res) {
    var el = $('fsbox');
    if (!res.fs) { el.innerHTML = ''; return; }
    var f = res.fs, r = res.request;
    el.innerHTML = '<div class="fsbox"><b>Потрібний сервіс-фактор fs = ' + fmt(f.fs_req, 2) + '</b> (' + esc(f.source_uk) + '). ' +
      'Момент навантаження ' + fmt(r.T_load_nm, 1) + ' Нм; потрібний Mn2 = T·fs = <b>' + fmt(r.t2_req_nm, 1) + ' Нм</b>; ціль n2 ≈ ' + fmt(r.n2_target_rpm, 2) + ' об/хв.' +
      '<div class="sub">' + esc(f.note_uk) + '. Сирe значення з діаграми: ' + fmt(f.fs_raw, 2) + '.</div>' +
      (res.warnings.length ? '<div>' + warnChips(res.warnings) + '</div>' : '') + '</div>';
  }
  function renderCands() {
    var el = $('results'), res = state.res;
    if (!res) { el.innerHTML = ''; return; }
    if (res.no_candidate) {
      var nc = res.no_candidate;
      el.innerHTML = '<div class="nocand"><b>Підходящих варіантів немає.</b> ' + esc(nc.reason_uk) +
        (nc.nearest_rejected.length ? '<div class="sub">Найближчі відхилені: ' + nc.nearest_rejected.map(function (n) {
          return esc(n.designation) + ' (Mn2 ' + fmt(n.mn2_nm) + ' Нм; не пройшли: ' + n.fails.map(function (f) { return CHECK_UK[f] || f; }).join(', ') + '; с. ' + n.src_page + ')';
        }).join('; ') + '</div>' : '') + '</div>';
      return;
    }
    if (!state.cands.length) { el.innerHTML = ''; return; }
    var h = '<div class="tw"><table class="ct"><thead><tr><th></th><th>Позначення</th><th>i</th><th>n2, об/хв</th><th>Двигун</th><th>M2 двиг., Нм</th><th>Mn2, Нм</th><th>fs кат. / заст.</th><th>Використання за моментом</th><th>Fr2 доп., Н</th><th>Стор.</th><th></th></tr></thead><tbody>';
    state.cands.forEach(function (c, idx) {
      var ph = photoFor(c);
      var warns = c.warnings.filter(function (w) { return w !== 'thermal_not_verified' || true; });
      var bandTxt = c.band === 'tight' ? '<span class="chip warn">впритул</span>' : c.band === 'oversized' ? '<span class="chip info">завеликий запас</span>' : '';
      h += '<tr class="' + (c.recommended ? 'rec' : '') + (c.alternative ? ' alt' : '') + '" data-idx="' + idx + '">' +
        '<td class="ph">' + (ph ? '<img alt="" src="' + ph.src + '">' : '') + '<div>' + threeBtn(c, state.raw) + '</div></td>' +
        '<td><b>' + esc(c.designation) + '</b>' + (c.recommended ? ' <span class="chip ok">рекомендовано</span>' : '') + (c.alternative ? ' <span class="chip info">наступний типорозмір</span>' : '') + bandTxt +
        '<div class="sub">' + esc(c.series) + (c.config === 'combined' ? ' · двоступінчастий' : '') + ' · ' + (c.kind === 'gearmotor' ? 'мотор-редуктор' : 'редуктор') + (c.mass_kg !== null ? ' · редуктор ' + fmt(c.mass_kg) + ' кг' : '') + '</div>' +
        '<div class="chips">' + warnChips(warns) + '</div></td>' +
        '<td class="r">' + fmt(c.i, 2) + '</td><td class="r">' + fmt(c.n2) + '<div class="sub">' + (c.n2_dev_pct > 0 ? '+' : '') + fmt(c.n2_dev_pct, 1) + ' %</div></td>' +
        '<td>' + motorOptionsHtml(c, idx) + '</td>' +
        '<td class="r">' + (c.m2_nm !== null ? fmt(c.m2_nm) : '') + '</td>' +
        '<td class="r">' + fmt(c.mn2_nm) + '<div class="sub">' + (c.mn2_source === 'table' ? 'таблиця' : 'M2·fs') + '</div></td>' +
        '<td class="r">' + (c.fs_catalogue !== null ? fmt(c.fs_catalogue, 1) : '–') + ' / ' + fmt(c.fs_app, 2) + '</td>' +
        '<td class="u">' + bar(c.utilisation_gear_pct) + (c.utilisation_motor_pct !== null ? '<div class="sub">двигун ' + fmt(c.utilisation_motor_pct, 0) + ' %</div>' : '') + '</td>' +
        '<td class="r">' + (c.fr2_allowed_n !== null ? fmt(c.fr2_allowed_n, 0) : '') + (c.fr2_applied_n !== null ? '<div class="sub">задано ' + fmt(c.fr2_applied_n, 0) + '</div>' : '') + '</td>' +
        '<td class="pg">' + c.src_pages.join(', ') + '</td>' +
        '<td><button type="button" class="btn small add-btn" data-idx="' + idx + '">Додати до КП</button></td></tr>';
    });
    h += '</tbody></table></div><p class="hint">Показано до 10 варіантів: найменший придатний типорозмір і наступний за ним. «Стор.» — сторінки PDF-каталогу VSF (друкована = PDF − 2).</p>';
    el.innerHTML = h;
  }

  function doSelect() {
    var raw = readForm(); state.raw = raw;
    var res = E.select(raw);
    state.res = res;
    renderErrors(res); renderFs(res);
    state.cands = res.candidates.map(function (c) {
      var opts = [{ row_id: c.row_id, frame: c.motor ? c.motor.frame : null, p_kw: c.p1_kw }]
        .concat((c.motor_alternatives || []).map(function (a) { return { row_id: a.row_id, frame: a.frame, p_kw: a.p_kw }; }));
      c._opts = opts; return c;
    });
    renderCands();
  }

  // ------------------------------------------------------------------ quote
  function verifStatus(c) { return c.fails && c.fails.length ? 'failed_overridden' : 'passed'; }

  function addItem(cand, raw, opts) {
    opts = opts || {};
    var norm = E.normalise(raw);
    var it = {
      id: state.nextId++, qty: Math.max(1, Math.min(999, parseInt(raw.qty, 10) || 1)),
      raw: raw, req: norm.req, cand: JSON.parse(JSON.stringify(cand)),
      override: !!opts.override, reason: opts.reason || '', customer_ref: '', terminal_box: '', options: '', hs_code: null
    };
    delete it.cand._opts;
    it.status = verifStatus(it.cand);
    state.items.push(it);
    renderQuote();
    return it;
  }

  function renderQuote() {
    var el = $('quoteitems');
    if (!state.items.length) { el.innerHTML = '<p class="muted">Позицій ще немає. Підберіть привід і натисніть «Додати до КП».</p>'; return; }
    var pr = pricing();
    var h = '<div class="tw"><table class="ct qt"><thead><tr><th>Поз.</th><th>Опис</th><th>К-сть</th><th>Ваш № товару</th><th>Клемна коробка</th><th>Опції</th><th>Код УКТ ЗЕД</th>' + (pr.priced ? '<th>Ціна з ПДВ, грн</th>' : '') + '<th></th></tr></thead><tbody>';
    state.items.forEach(function (it, ix) {
      var c = it.cand;
      var hs = it.hs_code !== null ? it.hs_code : (E.techSnapshot(c, it.req, {}).hs_code || '');
      h += '<tr data-id="' + it.id + '"><td>' + String(ix + 1).padStart(2, '0') + '</td><td><b>' + esc(c.designation) + '</b><div class="sub">' + typeName(c) +
        (it.override ? ' · <span class="chip warn">вручну</span>' : '') +
        (it.status === 'failed_overridden' ? ' <span class="chip warn">перевірку не пройдено: ' + esc(c.fails.map(function (f) { return CHECK_UK[f] || f; }).join(', ')) + '</span>' : '') + '</div>' +
        (it.override ? '<input class="reason" data-f="reason" placeholder="причина ручного вибору" value="' + esc(it.reason) + '">' : '') + '</td>' +
        '<td><input class="qty" data-f="qty" type="number" min="1" max="999" value="' + it.qty + '"></td>' +
        '<td><input data-f="customer_ref" value="' + esc(it.customer_ref) + '"></td>' +
        '<td><input data-f="terminal_box" value="' + esc(it.terminal_box) + '" placeholder="напр. 0 / 90"></td>' +
        '<td><input data-f="options" value="' + esc(it.options) + '" placeholder="напр. суцільний вал"></td>' +
        '<td><input data-f="hs_code" value="' + esc(hs) + '"></td>' +
        (pr.priced ? '<td class="r nw">' + fmt(pr.list[ix].unit_gross_uah, 2) + '<div class="sub">∑ ' + fmt(pr.list[ix].line_gross_kop / 100, 2) + '</div></td>' : '') + '<td class="nw">' + threeBtn(c, it.req) + ' <button type="button" class="btn small ov-btn">Вручну…</button> <button type="button" class="btn small rm-btn" title="Видалити">×</button></td></tr>';
    });
    h += '</tbody></table></div>';
    el.innerHTML = h;
  }

  // ------------------------------------------------------------------ manual override dialog
  function ovSizes() {
    var o = E.overrideOptions(), order = EN.FAMILY_ORDER;
    return Object.keys(o).sort(function (a, b) {
      var fa = order.indexOf(o[a].fam), fb = order.indexOf(o[b].fam);
      return fa - fb || (o[a].rows[0].kind < o[b].rows[0].kind ? -1 : 1) || (a < b ? -1 : 1);
    }).map(function (k) { return o[k]; });
  }
  function ovFill() {
    var sizes = ovSizes();
    state.ov = { sizes: sizes };
    $('o_size').innerHTML = sizes.map(function (s) { return '<option value="' + esc(s.size) + '">' + esc(EN.spaced(s.size)) + (s.kind === 'red' ? ' (редуктор)' : '') + '</option>'; }).join('');
    ovSizeChange();
  }
  function ovCurrentSize() { var sz = $('o_size').value; return state.ov.sizes.filter(function (s) { return s.size === sz; })[0]; }
  function ovSizeChange() {
    var s = ovCurrentSize(), seen = {}, is = [];
    s.rows.forEach(function (r) { var k = r.i + '|' + r.n1; if (!seen[k]) { seen[k] = 1; is.push(r); } });
    is.sort(function (a, b) { return a.i - b.i || a.n1 - b.n1; });
    $('o_i').innerHTML = is.map(function (r) { return '<option value="' + r.i + '|' + r.n1 + '">' + fmt(r.i, 2) + (s.kind === 'red' ? ' (n1 ' + r.n1 + ')' : '') + '</option>'; }).join('');
    ovIChange();
  }
  function ovIChange() {
    var s = ovCurrentSize(), p = $('o_i').value.split('|'), i = Number(p[0]), n1 = Number(p[1]);
    var rows = s.rows.filter(function (r) { return r.i === i && r.n1 === n1; }).sort(function (a, b) { return a.poles - b.poles || a.p1 - b.p1; });
    $('o_row').innerHTML = rows.map(function (r) { return '<option value="' + r.id + '">' + (r.kind === 'gm' ? fmt(r.p1) + ' кВт · ' + r.poles + 'p · ' + esc(r.ms) : 'Pn1 ' + fmt(r.p1) + ' кВт · n1 ' + r.n1 + ' · n2 ' + fmt(r.n2)) + '</option>'; }).join('');
    ovRowChange();
  }
  function ovRowChange() {
    var id = Number($('o_row').value), r = E.rowById(id);
    var opts = r && r.ms ? String(r.ms).split('/') : [];
    $('o_frame').innerHTML = opts.length ? opts.map(function (f) { return '<option>' + esc(f) + '</option>'; }).join('') : '<option value="">–</option>';
    $('o_frame').disabled = !opts.length;
    $('o_result').innerHTML = '';
  }
  function ovVerify() {
    var raw = readForm();
    var res = E.verify(raw, Number($('o_row').value), $('o_frame').value || null);
    var el = $('o_result');
    if (res.errors.length) { el.innerHTML = '<div class="errors"><ul>' + res.errors.map(function (e) { return '<li>' + esc(e.message_uk) + '</li>'; }).join('') + '</ul></div>'; return null; }
    var c = res.candidate;
    var st = res.status === 'failed_overridden'
      ? '<div class="nocand"><b>Перевірку не пройдено:</b> ' + res.failures.map(function (f) { return esc(CHECK_UK[f] || f); }).join('; ') + '. Потрібна причина ручного вибору.</div>'
      : '<div class="fsbox"><b>Перевірку пройдено.</b> Використання за моментом ' + fmt(c.utilisation_gear_pct, 1) + ' %, fs застосування ' + fmt(c.fs_app, 2) + '.</div>';
    el.innerHTML = st + '<div>' + warnChips(c.warnings) + '</div>';
    state.ov.last = { res: res, raw: raw };
    return state.ov.last;
  }
  function ovOpen(targetId) {
    state.overrideTarget = targetId || null;
    ovFill(); $('o_reason').value = ''; $('override-dlg').hidden = false;
  }
  function ovAdd() {
    var l = ovVerify(); if (!l) return;
    var failed = l.res.status === 'failed_overridden', reason = $('o_reason').value.trim();
    if (failed && !reason) { $('o_reason').focus(); $('o_reason').classList.add('bad'); return; }
    $('o_reason').classList.remove('bad');
    if (state.overrideTarget) {
      var it = state.items.filter(function (x) { return x.id === state.overrideTarget; })[0];
      if (it) { it.cand = JSON.parse(JSON.stringify(l.res.candidate)); it.req = E.normalise(l.raw).req; it.raw = l.raw; it.override = true; it.reason = reason; it.status = verifStatus(it.cand); }
      renderQuote();
    } else addItem(l.res.candidate, l.raw, { override: true, reason: reason });
    $('override-dlg').hidden = true;
  }

  // ------------------------------------------------------------------ parties
  var DEFAULT_PARTIES = {
    payment_terms: '50 % попередня оплата, 50 % протягом 10 днів від дати повідомлення про готовність товару до відвантаження.',
    incoterms: 'DAP', delivery_method: 'Транспортний перевізник', lead_time: '6–7 тижнів',
    lead_cond: 'Строк поставки відраховується з моменту отримання передоплати та повного технічного погодження.',
    warranty: '12 місяців з дня відвантаження', unpriced_note: 'Ціни надаються за окремим запитом.', validity_days: '30'
  };
  var DEMO_PARTIES = {
    seller_name: 'ТОВ «Зразок-Привід» (вигадані дані)', seller_short: 'ТОВ «Зразок-Привід»', seller_edrpou: '00000000', seller_ipn: 'платник ПДВ',
    seller_address: 'м. Київ, вул. Прикладна, 1', seller_phone: '+380 44 000 00 00', seller_email: 'sales@example.invalid', seller_site: 'www.example.invalid',
    seller_iban: 'UA00 0000 0000 0000 0000 0000 00000', seller_bank: 'АТ «Зразок-банк»', seller_mfo: '000000',
    customer_code: '10001', customer_name: 'ТОВ «Тестовий замовник»', customer_edrpou: '11111111', customer_address: 'м. Харків, вул. Тестова, 5',
    contact_name: 'Іван Петренко', contact_honorific: 'Пан', contact_phone: '+380 50 000 00 00', contact_email: 'ivan@example.invalid',
    mgr_name: 'Олена Коваленко', mgr_position: 'менеджер з продажу', mgr_phone: '+380 44 000 00 01', mgr_email: 'olena@example.invalid',
    office_name: 'Відділ приводної техніки', office_contacts: '+380 44 000 00 02 · office@example.invalid',
    delivery_place: 'Київ'
  };
  function partyInputs() { return [].slice.call(document.querySelectorAll('[data-p]')); }
  function readParties() {
    var p = {};
    partyInputs().forEach(function (e) { p[e.getAttribute('data-p')] = e.value; });
    p.brand = $('p_brand').checked; p.draft = $('p_draft').checked;
    return p;
  }
  function fillParties(p) {
    partyInputs().forEach(function (e) { var k = e.getAttribute('data-p'); if (p[k] !== undefined) e.value = p[k]; });
    if (p.brand !== undefined) $('p_brand').checked = !!p.brand;
    if (p.draft !== undefined) $('p_draft').checked = !!p.draft;
  }
  var SELLER_MAP = { seller_name: 'name', seller_short: 'short_name', seller_edrpou: 'edrpou', seller_ipn: 'ipn', seller_address: 'address', seller_phone: 'phone',
    seller_email: 'email', seller_site: 'site', seller_iban: 'iban', seller_bank: 'bank', seller_mfo: 'mfo', dealer_statement: 'dealer_statement' };
  var MGR_MAP = { mgr_name: 'name', mgr_position: 'position', mgr_phone: 'phone', mgr_email: 'email', office_name: 'office_name', office_contacts: 'office_contacts' };
  function mapped(src, map) { var o = {}; Object.keys(map).forEach(function (k) { if (src && has(src[map[k]])) o[k] = src[map[k]]; }); return o; }
  function profileFromForm() {
    var P = readParties(), seller = {}, manager = {};
    Object.keys(SELLER_MAP).forEach(function (k) { seller[SELLER_MAP[k]] = P[k] || ''; });
    Object.keys(MGR_MAP).forEach(function (k) { manager[MGR_MAP[k]] = P[k] || ''; });
    return { seller: seller, manager: manager };
  }
  function initParties() {
    var p = Object.assign({}, DEFAULT_PARTIES, { date: today(), request_date: today() }, mapped(CalcHost.getSeller(), SELLER_MAP), mapped(CalcHost.getManager(), MGR_MAP));
    fillParties(p);
    var fx = CalcHost.getFxRate(); if (fx > 0) $('p_fx').value = fx;
    fillCustomerPicker();
    ['seller', 'manager'].forEach(function (k) { /* profile persisted on change, see init() */ });
  }
  function fillCustomerPicker() {
    var list = CalcHost.getCustomerCandidates('') || [];
    state.custs = list;
    $('cust_pick').innerHTML = '<option value="">– вибрати (' + list.length + ') –</option>' + list.map(function (c, ix) {
      return '<option value="' + ix + '">' + esc(c.company.name + (c.company.edrpou ? ' · ' + c.company.edrpou : '') + (c.person && c.person.name ? ' · ' + c.person.name : '')) + '</option>';
    }).join('');
  }
  function pickCustomer() {
    var c = (state.custs || [])[Number($('cust_pick').value)]; if (!c) return;
    var co = c.company || {}, pe = c.person || {};
    fillParties({ customer_code: co.code || '', customer_name: co.name || '', customer_edrpou: co.edrpou || '', customer_address: co.address || '',
      contact_name: pe.name || '', contact_honorific: pe.honorific || '', contact_phone: pe.phone || '', contact_email: pe.email || '' });
  }

  // ------------------------------------------------------------------ KP rendering
  // ------------------------------------------------------------------ pricing, quote JSON, KP
  var kp = KPT.create({
    E: E, EN: EN, D: D, IMGS: IMGS, photoFor: photoFor, conceptNote: CONCEPT_NOTE,
    modelPng: function (it) { return state.pngCache[modelKey(it)] || null; }
  });
  function fxRate() {
    var f = parseFloat(String($('p_fx').value).replace(',', '.'));
    if (f > 0) return f;
    var h = CalcHost.getFxRate();
    return h > 0 ? h : null;
  }
  // priced only when fx > 0 and CalcHost.getPrice() answers for EVERY position (engine.priceItems)
  function pricing() {
    return EN.priceItems(state.items, function (k) { return CalcHost.getPrice(k); }, fxRate());
  }
  function collectQuote() {
    var pr = pricing();
    var items = state.items.map(function (it) {
      return Object.assign({}, it, { tech: E.techSnapshot(it.cand, it.req, { terminal_box: it.terminal_box || null, options: it.options || null, hs_code: it.hs_code === null ? undefined : (it.hs_code || null) }) });
    });
    return EN.buildQuote({ id: state.quoteId, created_at: state.createdAt, parties: readParties(), items: items, fx: fxRate(), pricing: pr });
  }
  function renderKpNow() {
    var P = readParties(); if (!P.date) P.date = today();
    $('kp').innerHTML = kp.build({ P: P, items: state.items, pricing: pricing() });
    $('kp').classList.add('on');
    document.body.classList.add('has-kp');
    $('sec-kp').scrollIntoView({ behavior: 'auto', block: 'start' });
  }
  // sync when every model image is cached (or no 3D), otherwise render the 3D PNGs first (async), then build the KP
  function renderKp() {
    var pend = M3 ? prepareModelImages(state.items) : null;
    if (!pend) { renderKpNow(); return Promise.resolve(); }
    msg('Готуємо 3D-зображення для КП…');
    return pend.then(function () { msg(''); renderKpNow(); });
  }
  function buildKp() {
    var P = readParties(); if (!P.date) P.date = today();
    return kp.build({ P: P, items: state.items, pricing: pricing() });
  }

  // ------------------------------------------------------------------ save / load / saved quotes (through CalcHost)
  function msg(t) { $('savemsg').textContent = t; }
  function saveQuote() {
    var q = collectQuote();
    return CalcHost.saveQuote(q).then(function (r) {
      if (r && r.id) state.quoteId = r.id;
      if (!state.createdAt) state.createdAt = q.created_at || (r && r.updated_at) || new Date().toISOString();
      msg('Збережено (' + state.items.length + ' поз.)');
      return refreshSaved();
    }).catch(function () { msg('Не вдалося зберегти: сховище недоступне'); });
  }
  function restoreQuote(q) {
    state.items = (q.items || []).map(function (i, ix) {
      var req = E.normalise(i.request || {}).req;
      return { id: ix + 1, qty: i.qty, raw: i.request, req: req, cand: i.candidate, override: !!i.override, reason: i.reason || '', status: i.status || 'passed',
        customer_ref: i.customer_ref || '', terminal_box: i.terminal_box || '', options: i.options || '', hs_code: i.hs_code === undefined ? null : i.hs_code };
    });
    state.nextId = state.items.length + 1; state.quoteId = q.id || null; state.createdAt = q.created_at || null;
    fillParties(EN.partiesFromQuote(q));
    $('p_fx').value = q.fx_eur_uah || '';
    renderQuote(); $('kp').innerHTML = ''; $('kp').classList.remove('on'); document.body.classList.remove('has-kp');
  }
  function newQuote() {
    state.items = []; state.nextId = 1; state.quoteId = null; state.createdAt = null;
    var keep = readParties();   // seller / manager / terms stay, customer and number reset
    ['customer_code', 'customer_name', 'customer_edrpou', 'customer_address', 'contact_name', 'contact_honorific', 'contact_phone', 'contact_email', 'number'].forEach(function (k) { keep[k] = ''; });
    keep.date = today(); keep.request_date = today(); keep.draft = true;
    fillParties(keep);
    renderQuote(); $('kp').innerHTML = ''; $('kp').classList.remove('on'); document.body.classList.remove('has-kp'); msg('');
  }
  function savedTitle(q) {
    return (q.number || 'ЧЕРНЕТКА') + ' · ' + ((q.customer && q.customer.name) || 'без замовника');
  }
  function refreshSaved() {
    return CalcHost.loadQuotes().then(function (list) {
      state.saved = list; $('saved_n').textContent = list.length;
      if (!list.length) { $('saved_list').innerHTML = '<p class="muted">Збережених КП немає.</p>'; return; }
      $('saved_list').innerHTML = '<div class="tw"><table class="ct sv"><thead><tr><th>КП</th><th>Позиції</th><th>Сума з ПДВ, грн</th><th>Оновлено</th><th></th></tr></thead><tbody>' +
        list.map(function (q) {
          return '<tr data-qid="' + esc(q.id) + '"><td><b>' + esc(savedTitle(q)) + '</b>' + (q.id === state.quoteId ? ' <span class="chip ok">відкрито</span>' : '') +
            '<div class="sub">' + esc((q.items || []).map(function (i) { return i.designation; }).slice(0, 3).join(', ')) + '</div></td>' +
            '<td class="r">' + (q.items || []).length + '</td><td class="r">' + (q.totals ? fmt(q.totals.gross_uah, 2) : '<span class="muted">за запитом</span>') + '</td>' +
            '<td class="nw">' + esc(String(q.updated_at || '').slice(0, 16).replace('T', ' ')) + '</td>' +
            '<td class="nw"><button type="button" class="btn small sv-open">Відкрити</button> <button type="button" class="btn small sv-dup">Дублювати</button> <button type="button" class="btn small sv-del" title="Видалити">×</button></td></tr>';
        }).join('') + '</tbody></table></div>';
    }).catch(function () { $('saved_list').innerHTML = '<p class="muted">Список недоступний.</p>'; });
  }
  function savedAction(e) {
    var tr = e.target.closest('tr[data-qid]'); if (!tr) return;
    var id = tr.getAttribute('data-qid'), q = (state.saved || []).filter(function (x) { return x.id === id; })[0]; if (!q) return;
    if (e.target.closest('.sv-open')) { restoreQuote(q); msg('Відкрито: ' + savedTitle(q)); refreshSaved(); }
    else if (e.target.closest('.sv-dup')) {
      var copy = JSON.parse(JSON.stringify(q)); copy.id = null; copy.created_at = null; copy.number = null; copy.draft = true; copy.status = 'draft';
      CalcHost.saveQuote(copy).then(function () { msg('Дубль створено (чернетка, без номера)'); return refreshSaved(); });
    } else if (e.target.closest('.sv-del')) {
      if (!window.confirm('Видалити збережене КП «' + savedTitle(q) + '»?')) return;
      CalcHost.deleteQuote(id).then(function () { if (state.quoteId === id) { state.quoteId = null; } msg('Видалено'); return refreshSaved(); });
    }
  }


  // ------------------------------------------------------------------ simple mode (power + output rpm)
  var MODE_KEY = 'nmrv_mode_v1';
  var sm = { res: null, sel: null, assume: { load_class: 'B', hours: 8, starts: 10, torque: null }, timer: null, added: false };
  function kw(p) { return fmt(p); }
  function dimsOf(v) {
    if (v._dims !== undefined) return v._dims;
    var d = null;
    try {
      var sp = M3 && v.cand ? M3.buildModelSpec(v.cand, v.cand.motor, D, { mounting: 'B3' }) : null;
      if (sp && !sp.error && sp.bbox) d = { l: sp.bbox.size[2], w: sp.bbox.size[0], h: sp.bbox.size[1], pages: sp.src_pages };
    } catch (e) { d = null; }
    v._dims = d; return d;
  }
  function dimsTxt(d) { return d ? fmt(d.l, 0) + '×' + fmt(d.w, 0) + '×' + fmt(d.h, 0) : ''; }
  function readSimple() {
    return { p_kw: $('s_kw').value, n2_rpm: $('s_n2').value, poles: $('s_poles').value, family: $('s_family').value, min_fs: $('s_minfs').value };
  }
  function chipsFor(list, attr, unit) {
    return list.map(function (x) { return '<button type="button" class="chipbtn" data-' + attr + '="' + x + '">' + fmt(x) + ' ' + unit + '</button>'; }).join('');
  }
  function doSimple() {
    var r = EN.selectSimple(readSimple(), D);
    sm.res = r; sm.sel = null; $('s_detail').innerHTML = '';
    var msg = $('s_msg'), el = $('s_results'); el.innerHTML = '';
    if (r.status === 'incomplete') { msg.innerHTML = '<p class="muted">Введіть потужність двигуна (кВт) і потрібні оберти на виході (об/хв) — варіанти з\'являться автоматично.</p>'; return; }
    if (r.status === 'error') { msg.innerHTML = '<div class="errors"><ul>' + r.errors.map(function (e) { return '<li>' + esc(e.message_uk) + '</li>'; }).join('') + '</ul></div>'; return; }
    var h = '';
    if (r.power && !r.power.exact) {
      h += '<div class="fsbox">' + esc(fmt(r.request.p_kw)) + ' кВт — не стандартна потужність двигуна з каталогу. Показано найближчу більшу: <b>' + esc(kw(r.power.matched)) + ' кВт</b>. Інші стандартні потужності: ' +
        chipsFor(r.power.next, 'kw', 'кВт') + '</div>';
    }
    if (r.status === 'empty') {
      h += '<div class="nocand"><b>Підходящих варіантів немає.</b> ' + esc(r.hint_uk) + '<div>' +
        (r.suggestions.speeds.length ? 'Швидкості: ' + chipsFor(r.suggestions.speeds, 'rpm', 'об/хв') + ' ' : '') +
        (r.suggestions.powers_for_speed.length ? 'Потужності: ' + chipsFor(r.suggestions.powers_for_speed, 'kw', 'кВт') : '') +
        (!r.suggestions.speeds.length && !r.suggestions.powers_for_speed.length && r.suggestions.powers.length ? chipsFor(r.suggestions.powers, 'kw', 'кВт') : '') + '</div></div>';
      msg.innerHTML = h; return;
    }
    h += '<div class="fsbox">Знайдено варіантів: <b>' + r.total_found + '</b>' + (r.total_found > r.variants.length ? ' (показано перші ' + r.variants.length + ')' : '') +
      '. Допуск за обертами ±' + r.tol_pct + ' %' + (r.widened ? ' (розширено з 5 %: за 5 % було менше 3 варіантів)' : '') + '; сервіс-фактор ≥ ' + fmt(r.request.min_fs, 2) +
      (r.excluded_by_fs ? '; відсіяно за сервіс-фактором: ' + r.excluded_by_fs : '') + '.</div>';
    msg.innerHTML = h;
    var t = '<div class="tw"><table class="ct st" id="s_table"><thead><tr><th>Варіант</th><th>Двигун, об/хв</th><th>Передавальне число i</th><th>Габаритний розмір редуктора<small>Д×Ш×В, мм</small></th><th>Сервіс-фактор</th><th>Момент на виході M2, Нм</th></tr></thead><tbody>';
    r.variants.forEach(function (v, ix) {
      var ph = photoFor(v), d = dimsOf(v), m = v.motor;
      t += '<tr tabindex="0" role="button" aria-label="Показати параметри: ' + esc(v.designation) + '" data-ix="' + ix + '">' +
        '<td><div class="vr">' + (ph ? '<img alt="" src="' + ph.src + '">' : '') + '<div><b>' + esc(v.designation) + '</b><div class="sub">' + esc(v.series) + (v.config === 'combined' ? ' · двоступінчастий' : '') +
        ' · <u>Показати параметри</u></div></div></div></td>' +
        '<td class="r"><b>' + fmt(v.n1) + '</b><div class="sub">' + (m ? esc(m.frame) + ' · ' : '') + kw(v.p_kw) + ' кВт · ' + v.poles + 'p</div></td>' +
        '<td class="r">' + fmt(v.i, 2) + '<div class="sub">n2 ' + fmt(v.n2) + ' (' + (v.dev_pct > 0 ? '+' : '') + fmt(v.dev_pct, 1) + ' %)</div></td>' +
        '<td class="r">' + (d ? dimsTxt(d) : '<span class="muted">–</span>') + '</td>' +
        '<td class="r"><span class="fsb ' + v.fs_band + '">' + fmt(v.fs, 2) + '</span></td>' +
        '<td class="r">' + fmt(v.m2_nm) + '</td></tr>';
    });
    t += '</tbody></table></div><p class="hint">Порядок: найменший придатний типорозмір, далі сервіс-фактор найближчий до мінімального, далі відхилення за обертами. Сервіс-фактор = Mn2 / M2 з каталогу: зелений ≥ 1,25; бурштиновий 1,0–1,25; червоний &lt; 1,0 (лише коли мінімум знижено). Габарити — з концептуальної 3D-моделі за каталожними розмірами, у положенні B3, разом з двигуном; для двоступінчастих і NMRV 025 даних немає. Клік або Enter по рядку — повні параметри.</p>';
    el.innerHTML = t;
  }
  function simpleRaw(v) {
    var a = sm.assume, T = a.torque === null ? v.m2_nm : a.torque;
    return { load_torque_nm: T, n2_rpm: v.n2, poles: v.poles, family: v.series, load_class: a.load_class, hours_per_day: a.hours, starts_per_hour: a.starts,
      mounting_position: 'B3', output: 'hollow', version: 'foot', flange: 'any', qty: $('s_qty').value };
  }
  function selectSimpleRow(ix) {
    var v = sm.res.variants[ix]; sm.sel = ix; sm.added = false; sm.assume.torque = null;
    [].forEach.call(document.querySelectorAll('#s_table tbody tr'), function (tr) { tr.classList.toggle('sel', Number(tr.getAttribute('data-ix')) === ix); });
    renderDetail();
    $('s_detail').scrollIntoView({ block: 'nearest' });
  }
  function renderDetail() {
    var v = sm.res.variants[sm.sel], a = sm.assume, raw = simpleRaw(v);
    var ver = E.verify(raw, v.row_id, v.motor ? v.motor.frame : null);
    if (ver.errors.length) { $('s_detail').innerHTML = '<div class="errors"><ul>' + ver.errors.map(function (e) { return '<li>' + esc(e.message_uk) + '</li>'; }).join('') + '</ul></div>'; return; }
    var c = ver.candidate, req = E.normalise(raw).req, snap = E.techSnapshot(c, req, {}), g = snap.gear, m = snap.motor, d = dimsOf(v);
    var failed = c.fails.length > 0;
    sm.cur = { cand: c, raw: raw, failed: failed, ver: ver };
    var left = [['Серія', g.series], ['Типорозмір', g.size], ['Кількість ступенів', g.stages], ['Виконання', g.version], ['Вихідний вал', g.output_shaft],
      ['Передавальне число i', fmt(g.i, 2)], ['Частота обертання вх./вих., об/хв', String(g.n1_n2).replace(/(\d)\.(\d)/g, '$1,$2')],
      ['Момент на виході M2, Нм', fmt(g.m2)], ['Номінальний момент Mn2, Нм', fmt(g.mn2)],
      ['Сервіс-фактор каталожний (Mn2/M2)', fmt(v.fs, 2)], ['Сервіс-фактор каталожний fs (таблиця)', has(g.fs_catalogue) ? fmt(g.fs_catalogue, 1) : null],
      ['Сервіс-фактор застосування (Mn2/T)', fmt(g.fs_app, 2) + ' (потрібно ' + fmt(ver.fs.fs_req, 2) + ')'], ['Використання за моментом, %', fmt(g.utilisation, 1)],
      ['Допустиме радіальне навантаження Fr2, Н', fmt(g.fr2, 0)], ['Мастило / кількість', g.lubricant], ['Покриття', g.paint],
      ['ККД черв\'ячної пари (каталог)', has(g.eta_catalogue) ? fmt(g.eta_catalogue, 2) : null], ['Маса редуктора нетто, кг (без двигуна і мастила)', has(snap.mass_kg) ? fmt(snap.mass_kg) : null],
      ['Габарити Д×Ш×В, мм (3D, з двигуном)', d ? dimsTxt(d) : null]].filter(function (r) { return has(r[1]); });
    var right = m ? [['Тип двигуна', m.type], ['Типорозмір IEC', m.frame], ['Кількість полюсів', m.poles], ['Потужність, кВт', fmt(m.p_kw)], ['Напруга, В / схема', m.voltage], ['Частота мережі, Гц', m.frequency],
      ['Клас енергоефективності', m.ie_class], ['Ступінь захисту', m.ip], ['Клас ізоляції', m.insulation], ['Режим роботи', m.duty], ['Фланець', m.flange]].filter(function (r) { return has(r[1]); }) : [];
    function kvs(list) { return list.map(function (r) { return '<div class="kv"><span class="k">' + esc(r[0]) + '</span><span class="v">' + esc(r[1]) + '</span></div>'; }).join(''); }
    var warn = failed ? '<div class="nocand">За припущеннями застосування нижче перевірку не пройдено: ' + c.fails.map(function (f) { return esc(CHECK_UK[f] || f); }).join('; ') + '. У КП позиція буде позначена.</div>'
      : '<div class="fsbox">Перевірку за припущеннями застосування пройдено.</div>';
    var h = '<div class="sdet" id="s_det" tabindex="-1"><h3>' + esc(v.designation) + '</h3>' +
      '<div class="assum"><b>Припущення для сервіс-фактора застосування</b> (змініть за потреби; для підбору не використовуються)' +
      '<div class="agrid"><label>Клас навантаження <select id="a_class"><option value="A">A</option><option value="B">B</option><option value="C">C</option></select></label>' +
      '<label>Годин на добу <input id="a_hours" type="number" step="any" value="' + a.hours + '"></label>' +
      '<label>Пусків на годину <input id="a_starts" type="number" step="any" value="' + a.starts + '"></label>' +
      '<label>Момент навантаження T, Нм <input id="a_torque" type="number" step="any" value="' + (a.torque === null ? round1(v.m2_nm) : a.torque) + '"></label></div>' +
      '<div class="sub">За замовчуванням T = M2 (двигун навантажений повністю). ' + esc(ver.fs.lookup.note_uk) + '</div></div>' + warn +
      '<div class="two2"><div><div class="coltitle">Редуктор</div>' + kvs(left) + '</div><div><div class="coltitle">' + (m ? 'Двигун' : 'Двигун') + '</div>' + kvs(right) +
      '<div class="coltitle">Джерело</div>' + kvs([['Сторінки каталогу', c.src_pages.join(', ')]]) + '</div></div>' +
      '<div class="actions"><button type="button" class="btn primary" id="s_add">Додати до КП</button>' +
      threeBtn(c, req).replace('class="btn small m3d-btn"', 'class="btn m3d-btn" id="s_3d"') +
      '<button type="button" class="btn" id="s_toadv">Перейти до складного підбору з цими даними</button><span class="hint" id="s_addmsg"></span></div></div>';
    $('s_detail').innerHTML = h;
    $('a_class').value = a.load_class;
  }
  function round1(x) { return Math.round(x * 10) / 10; }
  function addSimple() {
    if (!sm.cur) return;
    var cur = sm.cur, opts = {};
    if (cur.failed) { opts.override = true; opts.reason = 'Простий підбір: сервіс-фактор застосування ' + fmt(cur.cand.fs_app, 2) + ' менший за потрібний ' + fmt(cur.ver.fs.fs_req, 2) + ' (клас ' + cur.raw.load_class + ', ' + cur.raw.hours_per_day + ' год/добу, ' + cur.raw.starts_per_hour + ' пусків/год)'; }
    addItem(cur.cand, cur.raw, opts);
    $('s_addmsg').textContent = 'Додано до КП (поз. ' + state.items.length + ')';
  }
  function toAdvanced() {
    if (!sm.cur) return;
    var raw = sm.cur.raw, v = sm.res.variants[sm.sel];
    setMode('adv');
    $('f_torque').value = raw.load_torque_nm === undefined ? '' : round1(raw.load_torque_nm); $('f_power').value = '';
    $('f_n2').value = sm.res.request.n2_rpm; $('f_ratio').value = '';
    $('f_poles').value = String(v.poles); $('f_family').value = v.series;
    $('f_class').value = raw.load_class; $('f_hours').value = raw.hours_per_day; $('f_starts').value = raw.starts_per_hour; $('f_qty').value = raw.qty || 1;
    doSelect();
    $('sec-select').scrollIntoView({ block: 'start' });
  }
  function setMode(mode) {
    var simple = mode !== 'adv';
    $('simple').hidden = !simple; $('sec-select').hidden = simple;
    $('mode_simple').classList.toggle('on', simple); $('mode_adv').classList.toggle('on', !simple);
    $('mode_simple').setAttribute('aria-pressed', String(simple)); $('mode_adv').setAttribute('aria-pressed', String(!simple));
    $('mode_hint').textContent = simple ? 'Простий: лише потужність двигуна і потрібні оберти на виході.' : 'Складний: повна форма підбору за моментом, режимом роботи, навантаженнями.';
    document.body.setAttribute('data-mode', simple ? 'simple' : 'adv');
    try { localStorage.setItem(MODE_KEY, simple ? 'simple' : 'adv'); } catch (e) { /* storage unavailable */ }
  }
  function initSimple() {
    var mode = 'simple';
    try { if (localStorage.getItem(MODE_KEY) === 'adv') mode = 'adv'; } catch (e) { /* ignore */ }
    setMode(mode);
    $('mode_simple').addEventListener('click', function () { setMode('simple'); });
    $('mode_adv').addEventListener('click', function () { setMode('adv'); });
    $('sform').addEventListener('submit', function (e) { e.preventDefault(); doSimple(); });
    ['s_kw', 's_n2', 's_minfs'].forEach(function (id) { $(id).addEventListener('input', function () { clearTimeout(sm.timer); sm.timer = setTimeout(doSimple, 250); }); });
    ['s_poles', 's_family'].forEach(function (id) { $(id).addEventListener('change', doSimple); });
    $('s_msg').addEventListener('click', function (e) {
      var b = e.target.closest('.chipbtn'); if (!b) return;
      if (b.hasAttribute('data-kw')) $('s_kw').value = b.getAttribute('data-kw');
      if (b.hasAttribute('data-rpm')) $('s_n2').value = b.getAttribute('data-rpm');
      doSimple();
    });
    var tbl = $('s_results');
    tbl.addEventListener('click', function (e) { var tr = e.target.closest('tr[data-ix]'); if (tr) selectSimpleRow(Number(tr.getAttribute('data-ix'))); });
    tbl.addEventListener('keydown', function (e) {
      var tr = e.target.closest && e.target.closest('tr[data-ix]');
      if (tr && e.target === tr && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); selectSimpleRow(Number(tr.getAttribute('data-ix'))); }
    });
    var det = $('s_detail');
    det.addEventListener('click', function (e) {
      if (e.target.closest('#s_add')) addSimple();
      else if (e.target.closest('#s_toadv')) toAdvanced();
      else { var b = e.target.closest('.m3d-btn'); if (b && !b.disabled && sm.cur) open3d(sm.cur.cand, E.normalise(sm.cur.raw).req); }
    });
    det.addEventListener('change', function (e) {
      var id = e.target.id; if (id.indexOf('a_') !== 0) return;
      var a = sm.assume;
      a.load_class = $('a_class').value; a.hours = Number($('a_hours').value) || 8; a.starts = $('a_starts').value === '' ? 10 : Number($('a_starts').value);
      var tv = Number($('a_torque').value); a.torque = tv > 0 ? tv : null;
      renderDetail();
    });
  }

  // ------------------------------------------------------------------ wiring
  function init() {
    initParties();
    initSimple();
    $('selform').addEventListener('submit', function (e) { e.preventDefault(); doSelect(); });
    $('btn_reset').addEventListener('click', resetForm);
    $('results').addEventListener('click', function (e) {
      var b = e.target.closest('.add-btn'); if (!b) return;
      var c = state.cands[Number(b.getAttribute('data-idx'))];
      addItem(c, state.raw || readForm());
      b.textContent = 'Додано ✓';
    });
    $('results').addEventListener('change', function (e) {
      if (!e.target.classList.contains('motsel')) return;
      var idx = Number(e.target.getAttribute('data-idx')), p = e.target.value.split('|');
      var old = state.cands[idx];
      var res = E.verify(state.raw, Number(p[0]), p[1]);
      if (res.candidate) {
        var c = res.candidate; c._opts = old._opts; c.recommended = old.recommended; c.alternative = old.alternative; c.band = old.utilisation_gear_pct >= 85 ? 'tight' : old.utilisation_gear_pct < 50 ? 'oversized' : 'ok';
        state.cands[idx] = c; renderCands();
      }
    });
    $('quoteitems').addEventListener('change', function (e) {
      var f = e.target.getAttribute('data-f'); if (!f) return;
      var id = Number(e.target.closest('tr').getAttribute('data-id'));
      var it = state.items.filter(function (x) { return x.id === id; })[0]; if (!it) return;
      if (f === 'qty') it.qty = Math.max(1, Math.min(999, parseInt(e.target.value, 10) || 1));
      else it[f] = e.target.value;
    });
    $('quoteitems').addEventListener('click', function (e) {
      var tr = e.target.closest('tr'); if (!tr) return;
      var id = Number(tr.getAttribute('data-id'));
      if (e.target.closest('.rm-btn')) { state.items = state.items.filter(function (x) { return x.id !== id; }); renderQuote(); }
      else if (e.target.closest('.ov-btn')) ovOpen(id);
    });
    $('btn_manual').addEventListener('click', function () { ovOpen(null); });
    $('results').addEventListener('click', function (e) {
      var b = e.target.closest('.m3d-btn'); if (!b || b.disabled) return;
      var idx = Number(b.closest('tr').getAttribute('data-idx'));
      open3d(state.cands[idx], state.raw ? E.normalise(state.raw).req : {});
    });
    $('quoteitems').addEventListener('click', function (e) {
      var b = e.target.closest('.m3d-btn'); if (!b || b.disabled) return;
      var id = Number(b.closest('tr').getAttribute('data-id'));
      var it = state.items.filter(function (x) { return x.id === id; })[0];
      if (it) open3d(it.cand, it.req);
    });
    $('m3d-close').addEventListener('click', close3d);
    $('m3d').addEventListener('click', function (e) { if (e.target === $('m3d')) close3d(); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape' && !$('m3d').hidden) close3d(); });
    $('m3d-pos').addEventListener('change', function () { if (viewer) viewer.setMounting($('m3d-pos').value); });
    $('m3d-wire').addEventListener('change', function () { if (viewer) viewer.setWireframe($('m3d-wire').checked); });
    $('o_size').addEventListener('change', ovSizeChange); $('o_i').addEventListener('change', ovIChange); $('o_row').addEventListener('change', ovRowChange);
    $('o_check').addEventListener('click', ovVerify); $('o_add').addEventListener('click', ovAdd);
    $('o_cancel').addEventListener('click', function () { $('override-dlg').hidden = true; });
    $('btn_save').addEventListener('click', saveQuote);
    $('btn_new').addEventListener('click', newQuote);
    $('saved_list').addEventListener('click', savedAction);
    $('cust_pick').addEventListener('change', pickCustomer);
    $('p_fx').addEventListener('input', renderQuote);
    $('parties').addEventListener('change', function (e) {
      var k = e.target.getAttribute('data-p');
      if (k && (SELLER_MAP[k] || MGR_MAP[k]) && CalcHost.rememberProfile) CalcHost.rememberProfile(profileFromForm());
    });
    $('btn_demo').addEventListener('click', function () { fillParties(DEMO_PARTIES); });
    $('btn_kp').addEventListener('click', renderKp);
    $('btn_print').addEventListener('click', function () { renderKp().then(function () { return CalcHost.exportPdf(collectQuote()); }); });
  }
  window.__nmrv = { E: E, state: state, buildKp: buildKp, collectQuote: collectQuote, saveQuote: saveQuote, refreshSaved: refreshSaved, CalcHost: CalcHost, pricing: pricing, fmt: fmt, getViewer: function () { return viewer; }, specFor: specFor, getThree: getThree, simple: sm, setMode: setMode };
  init();
  refreshSaved();
})();
