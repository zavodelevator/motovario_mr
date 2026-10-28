/* VSF prototype UI: form, candidates, quote, KP preview (KP_SPEC). Browser only; the engine is in engine.js. */
(function () {
  'use strict';
  var D = window.VSF_DATA, IMGS = window.VSF_IMG || {}, EN = window.VSFEngine;
  var E = EN.createEngine(D);
  var NB = ' ';
  var state = { items: [], cands: [], raw: null, nextId: 1, overrideTarget: null, ov: null };

  function $(id) { return document.getElementById(id); }
  function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
  function has(v) { return v !== null && v !== undefined && v !== '' && !(typeof v === 'number' && !isFinite(v)); }
  function fmt(x, dec) {
    if (!has(x)) return '';
    if (typeof x !== 'number') return String(x);
    var s = dec === undefined ? String(Math.round(x * 1000) / 1000) : x.toFixed(dec);
    var p = s.split('.'); var ip = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, NB);
    return p[1] ? ip + ',' + p[1] : ip;
  }
  function today() { var d = new Date(); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }
  function dmy(iso) { if (!iso) return ''; var p = iso.split('-'); return p.length === 3 ? p[2] + '.' + p[1] + '.' + p[0] : iso; }
  function addDays(iso, n) { var d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0'); }

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
  function bar(u) {
    var cls = u > 95 ? ' hot' : '';
    return '<div class="ubar' + cls + '"><i style="width:' + Math.min(100, Math.max(0, u)) + '%"></i></div><span class="unum">' + fmt(u, 1) + ' %</span>';
  }
  function photoFor(c) {
    var p = D.images.photos[c.image_key] || null;
    return p && IMGS[p.file] ? { src: IMGS[p.file], pg: p.pg } : null;
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
        '<td class="ph">' + (ph ? '<img alt="" src="' + ph.src + '">' : '') + '</td>' +
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
  function typeName(c) { return c.kind === 'gearmotor' ? 'Черв\'ячний мотор-редуктор' : 'Черв\'ячний редуктор'; }
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
    var h = '<div class="tw"><table class="ct qt"><thead><tr><th>Поз.</th><th>Опис</th><th>К-сть</th><th>Ваш № товару</th><th>Клемна коробка</th><th>Опції</th><th>Код УКТ ЗЕД</th><th></th></tr></thead><tbody>';
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
        '<td class="nw"><button type="button" class="btn small ov-btn">Вручну…</button> <button type="button" class="btn small rm-btn" title="Видалити">×</button></td></tr>';
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
  function initParties() {
    var p = Object.assign({}, DEFAULT_PARTIES, { date: today(), request_date: today() });
    fillParties(p);
  }

  // ------------------------------------------------------------------ KP rendering
  function priceInfo() {
    var res = state.items.map(function (it) { return E.priceHook({ cand: it.cand, qty: it.qty, req: it.req }); });
    var priced = res.length > 0 && res.every(function (r) { return r !== null && r !== undefined; });
    return { priced: priced, list: res };
  }
  function rowsHtml(list) {
    return list.filter(function (r) { return has(r[1]); }).map(function (r) {
      return '<div class="kv"><span class="k">' + esc(r[0]) + '</span><span class="v">' + r[1] + '</span></div>';
    }).join('');
  }
  function T(v) { return esc(v); }

  function pageWrap(inner, ctx, idx, total) {
    var P = ctx.P, num = P.draft || !P.number ? 'ЧЕРНЕТКА' : P.number;
    var logos = '<div class="logos"><span class="seller-name">' + esc(P.seller_short || P.seller_name || '') + '</span>' +
      (P.brand ? '<span class="mv-mark" title="Знак Motovario (текстовий; графічний логотип відсутній у даних)">motovario<small>a TECO Group company</small></span>' : '') + '</div>';
    var foot = '<div class="fcols"><div>' + [P.seller_name, P.seller_edrpou ? 'ЄДРПОУ ' + P.seller_edrpou : '', P.seller_ipn].filter(has).map(esc).join('<br>') + '</div>' +
      '<div>' + [P.seller_address, P.seller_phone, P.seller_email, P.seller_site].filter(has).map(esc).join('<br>') + '</div>' +
      '<div>' + [P.seller_iban ? 'IBAN ' + P.seller_iban : '', P.seller_bank, P.seller_mfo ? 'МФО ' + P.seller_mfo : ''].filter(has).map(esc).join('<br>') + '</div>' +
      '<div class="fpage">№ ' + esc(num) + ' · Сторінка ' + (idx + 1) + ' / ' + total + '</div></div>';
    return '<section class="page' + (P.draft ? ' draft' : '') + '">' + logos +
      '<div class="crumb">Motovario ∕ Мотор-редуктори ∕ Комерційна пропозиція</div>' +
      '<div class="band"><span class="band-t">КОМЕРЦІЙНА ПРОПОЗИЦІЯ</span><span class="band-tab">№ ' + esc(num) + ' · ' + esc(dmy(P.date)) + '</span></div>' +
      '<div class="pbody">' + inner + '</div><footer class="foot">' + foot + '</footer></section>';
  }
  function secBar(t) { return '<div class="secbar"><span>' + esc(t) + '</span></div>'; }

  function summaryTable(items, startIx, ctx) {
    var anyRef = state.items.some(function (i) { return has(i.customer_ref); });
    var priced = ctx.pi.priced;
    var h = '<table class="kt sum"><thead><tr><th class="c">Поз.</th><th class="c">Кількість</th><th>Опис</th>' + (anyRef ? '<th>Ваш № товару</th>' : '') +
      (priced ? '<th class="r">Ціна за од. з ПДВ, грн</th><th class="r">Сума з ПДВ, грн</th>' : '') + '</tr></thead><tbody>';
    items.forEach(function (it, k) {
      var ix = startIx + k;
      h += '<tr><td class="c">' + String(ix + 1).padStart(2, '0') + '</td><td class="c">' + it.qty + ' шт</td><td>' + esc(typeName(it.cand)) + '<div class="des">' + esc(it.cand.designation) + '</div></td>' +
        (anyRef ? '<td>' + esc(it.customer_ref) + '</td>' : '') +
        (priced ? '<td class="r">' + fmt(ctx.pi.list[ix].unit_gross_uah, 2) + '</td><td class="r">' + fmt(ctx.pi.list[ix].unit_gross_uah * it.qty, 2) + '</td>' : '') + '</tr>';
    });
    return h + '</tbody></table>';
  }
  function totalsBlock(ctx) {
    if (!ctx.pi.priced) return '';
    var gross = 0; ctx.pi.list.forEach(function (p, ix) { gross += p.unit_gross_uah * state.items[ix].qty; });
    var vat = gross - gross / 1.2;
    return '<table class="kt tot"><tbody><tr><td>Разом з ПДВ, грн</td><td class="r">' + fmt(gross, 2) + '</td></tr><tr><td>у т.ч. ПДВ 20 %, грн</td><td class="r">' + fmt(vat, 2) + '</td></tr><tr><td>Разом без ПДВ, грн</td><td class="r">' + fmt(gross - vat, 2) + '</td></tr></tbody></table>';
  }
  function termsTable(ctx) {
    var P = ctx.P;
    var valid = addDays(P.date || today(), parseInt(P.validity_days, 10) || 30);
    var rows = [
      ['Умови оплати', esc(P.payment_terms)],
      ctx.pi.priced ? ['Ціни', 'Ціни вказано в гривнях з ПДВ 20 %.'] : null,
      ['Базис поставки', esc([P.incoterms, P.delivery_place].filter(has).join(' ')) + (has(P.incoterms) ? ', Incoterms® 2020' : '')],
      ['Спосіб доставки', esc(P.delivery_method)],
      ['Строк поставки', esc(P.lead_time) + (has(P.lead_cond) ? '<div class="note">' + esc(P.lead_cond) + '</div>' : '')],
      ['Гарантія', esc(P.warranty)],
      ['Пропозиція дійсна до', esc(dmy(valid))]
    ].filter(Boolean).filter(function (r) { return has(r[1]) && r[1] !== ''; });
    return '<table class="kt terms"><tbody>' + rows.map(function (r) { return '<tr><td class="lab">' + r[0] + '</td><td>' + r[1] + '</td></tr>'; }).join('') + '</tbody></table>' +
      '<p class="small">Детальні технічні дані позицій наведено на наступних сторінках.</p>';
  }

  function firstPage(ctx, rowsHere, startIx, showTerms, cont) {
    var P = ctx.P, h = '';
    if (!cont) {
      var meta = [P.customer_code ? ['№ клієнта', P.customer_code] : null, ['Дата запиту', dmy(P.request_date || P.date)]].filter(Boolean);
      h += '<div class="parties"><div class="pl">' +
        '<div class="oneliner">' + esc([P.seller_name, P.seller_address].filter(has).join(', ')) + '</div>' +
        '<div class="addr"><b>' + esc(P.customer_name) + '</b>' + (P.customer_edrpou ? '<br>ЄДРПОУ ' + esc(P.customer_edrpou) : '') + (P.customer_address ? '<br>' + esc(P.customer_address).replace(/\n/g, '<br>') : '') +
        (P.contact_name ? '<br>' + esc((P.contact_honorific ? P.contact_honorific + ' ' : '') + P.contact_name) : '') +
        (P.contact_phone || P.contact_email ? '<br><span class="grey">' + esc([P.contact_phone, P.contact_email].filter(has).join(' · ')) + '</span>' : '') + '</div>' +
        '<div class="meta">' + meta.map(function (m) { return '<span class="k">' + m[0] + ':</span> <b>' + esc(m[1]) + '</b>'; }).join('<br>') + '</div></div>' +
        '<div class="pr">' + (P.mgr_name ? '<div class="blk"><b>Контактна особа</b><br><b>' + esc(P.mgr_name) + '</b><br>' + esc(P.mgr_position || '') + '<br><span class="grey">' + [P.mgr_phone, P.mgr_email].filter(has).map(esc).join('<br>') + '</span></div>' : '') +
        (P.office_name ? '<div class="blk"><b>' + esc(P.office_name) + '</b><br><span class="grey">' + esc(P.office_contacts || '') + '</span></div>' : '') + '</div></div>';
      var gr = (P.contact_name ? esc(P.contact_name) + ', дякуємо' : 'Дякуємо') + ' за інтерес до нашої продукції. Ми підготували пропозицію на основі Вашого запиту.';
      h += '<p class="greet">' + gr + '</p>';
    }
    h += secBar('ПОЗИЦІЇ' + (cont ? ' (продовження)' : '')) + summaryTable(rowsHere, startIx, ctx);
    if (showTerms) {
      h += totalsBlock(ctx);
      if (!ctx.pi.priced && has(ctx.P.unpriced_note)) h += '<p class="unpriced">' + esc(ctx.P.unpriced_note) + '</p>';
      h += secBar('УМОВИ') + termsTable(ctx);
    }
    return h;
  }

  function positionPage(it, ix, ctx) {
    var c = it.cand, req = it.req;
    var snap = E.techSnapshot(c, req, { terminal_box: it.terminal_box || null, options: it.options || null, hs_code: it.hs_code === null ? undefined : (it.hs_code || null) });
    var g = snap.gear, m = snap.motor, qty = it.qty;
    var ph = photoFor(c);
    var failed = it.status === 'failed_overridden';
    var mark = failed
      ? '<div class="vmark bad">Позицію задано вручну; перевірку за каталогом не пройдено' + (it.reason ? ': ' + esc(it.reason) : '') + '</div>'
      : '<div class="vmark">✓ Підбір перевірено за каталогом Motovario</div>';
    var basis = [];
    var T = req._T;
    basis.push(['Момент навантаження, Нм', fmt(T, 1)]);
    if (has(req.load_power_kw)) basis.push(['Потужність навантаження, кВт', fmt(req.load_power_kw)]);
    if (req._mode === 'n2') basis.push(['Потрібна частота на виході, об/хв', fmt(req.n2_rpm)]);
    else basis.push(['Потрібне передавальне число', fmt(req.ratio, 2)]);
    basis.push(['Клас навантаження', CLASS_UK[req.load_class] || req.load_class]);
    basis.push(['Режим роботи', fmt(req.hours_per_day) + ' год/добу, ' + fmt(req.starts_per_hour) + ' пусків/год']);
    var fsInfo = E.requiredFs(req);
    basis.push(['Потрібний сервіс-фактор', fmt(fsInfo.fs_req, 2) + ' (' + fsInfo.source_uk + (fsInfo.source === 'series_chart' ? '; ±' + fmt(EN.FS_TOLERANCE, 2) : '') + ')']);
    if (c.fr2_applied_n !== null) basis.push(['Радіальне навантаження на вихідний вал, Н', fmt(c.fr2_applied_n, 0)]);
    if (has(req.ambient_c) && req.ambient_c !== 25) basis.push(['Температура довкілля, °C', fmt(req.ambient_c)]);

    function kvList(arr) { return rowsHtml(arr); }
    var utilCell = bar(g.utilisation);
    var left = [
      ['Серія', T2(g.series)], ['Типорозмір', T2(g.size)], ['Кількість ступенів', T2(g.stages)], ['Виконання', T2(g.version)],
      ['Вихідний вал', T2(g.output_shaft)], ['Монтажне положення', T2(g.mounting_position)], ['Положення клемної коробки', T2(g.terminal_box_position)],
      ['Передавальне число i', fmt(g.i, 2)], ['Частота обертання вх./вих., об/хв', T2(String(g.n1_n2).replace(/(\d)\.(\d)/g, '$1,$2'))],
      ['Крутний момент на виході M2, Нм', fmt(g.m2)], ['Номінальний момент редуктора Mn2, Нм', fmt(g.mn2)],
      ['Сервіс-фактор (каталожний) fs', has(g.fs_catalogue) ? fmt(g.fs_catalogue, 1) : null], ['Сервіс-фактор застосування', fmt(g.fs_app, 2)],
      ['Використання за моментом, %', '<span class="nw">' + utilCell + '</span>'],
      ['Допустиме радіальне навантаження Fr2, Н', fmt(g.fr2, 0)],
      c.kind === 'reducer' ? ['Радіальне навантаження на вхідний вал Fr1, Н', fmt(c.fr1_n, 0)] : null,
      ['Мастило / кількість, л', T2(g.lubricant)], ['Покриття', T2(g.paint)], ['Термічна потужність Pth, кВт', has(g.thermal) ? fmt(g.thermal) : null],
      ['ККД черв\'ячної пари (каталог, при 1400 об/хв)', has(g.eta_catalogue) ? fmt(g.eta_catalogue, 2) : null],
      ['Опції', T2(g.options)]
    ].filter(Boolean);
    function T2(v) { return has(v) ? esc(v) : null; }
    var right = [];
    var motorTitle = 'ДВИГУН', motorBody = '';
    if (m) {
      right = [['Тип двигуна', T2(m.type)], ['Типорозмір IEC', T2(m.frame)], ['Кількість полюсів', T2(m.poles)], ['Потужність, кВт', fmt(m.p_kw)],
        ['Номінальна частота обертання, об/хв', has(m.n_rpm) ? fmt(m.n_rpm) : null], ['Напруга, В / схема', T2(m.voltage)], ['Частота мережі, Гц', T2(m.frequency)],
        ['Клас енергоефективності', T2(m.ie_class)], ['Ступінь захисту', T2(m.ip)], ['Клас ізоляції', T2(m.insulation)], ['Режим роботи', T2(m.duty)],
        ['Гальмо', T2(m.brake)], ['Номінальний струм, А', has(m.i_n) ? fmt(m.i_n) : null], ['cos φ', has(m.cos_phi) ? fmt(m.cos_phi) : null],
        ['ККД, %', has(m.eta) ? fmt(m.eta) : null], ['Фланець', T2(m.flange)]];
      motorBody = kvList(right);
    } else {
      motorBody = '<p class="note2">' + esc(snap.reducer_note || '') + '</p>' + (snap.motor_hint ? '<p class="note2">Орієнтовно потрібний двигун не менше ' + fmt(snap.motor_hint.p_kw) + ' кВт.</p>' : '');
    }
    var mass = has(snap.mass_kg) ? fmt(snap.mass_kg) + ' кг/шт · ' + fmt(Math.round(snap.mass_kg * qty * 10) / 10) + ' кг/поз. (без двигуна і мастила)' : null;
    var hs = snap.hs_code;
    var foot = rowsHtml([['Маса редуктора нетто, прибл.', mass], ['Код УКТ ЗЕД', hs ? esc(hs) : null], ['Джерело даних', esc(snap.source)]]);
    var anyPrice = ctx.pi.priced ? ctx.pi.list[ix] : null;
    var bar1 = '<div class="posbar"><span class="pn">ПОЗ. ' + String(ix + 1).padStart(2, '0') + '</span><span>' + qty + ' шт</span><span>' + esc(typeName(c)) + '</span><b class="pd">' + esc(c.designation) + '</b>' +
      (anyPrice ? '<span class="pp">' + fmt(anyPrice.unit_gross_uah, 2) + ' грн · ' + fmt(anyPrice.unit_gross_uah * qty, 2) + ' грн</span>' : '') + '</div>';
    var h = bar1 + '<div class="imgrow">' +
      (ph ? '<div class="imgcol"><div class="imgbox"><img alt="' + esc(c.series) + '" src="' + ph.src + '"></div><p class="imgnote">Колір і технічні характеристики можуть відрізнятися від показаних на зображенні. Технічна специфікація відповідає наведеним нижче даним.</p></div>' : '') +
      '<div class="basiscol">' + mark + '<div class="basis"><div class="bt">Вихідні дані підбору</div>' + rowsHtml(basis.map(function (b) { return [b[0], esc(b[1])]; })) + '</div></div></div>' +
      secBar('ТЕХНІЧНІ ДАНІ') +
      '<div class="two"><div><div class="coltitle">РЕДУКТОР</div>' + kvList(left) + '</div><div><div class="coltitle">' + motorTitle + '</div>' + motorBody + '</div></div>' +
      '<div class="posfoot">' + foot + '</div>';
    return h;
  }

  function drawingKey(c) {
    if (c.config !== 'single') return null;
    var n = EN.outputUnitNumber(c.size);
    var isNrv = c.series.indexOf('NRV') === 0;
    var dimKey = (isNrv ? 'NRV' : 'NMRV') + n;
    var drw = isNrv ? D.images.drawings.NRV : (c.size === 'NMRV025' ? D.images.drawings.NMRV025 : D.images.drawings.NMRV);
    return { drw: drw, dimKey: dimKey, dims: D.dimensions[dimKey] || null };
  }
  function drawingPage(it, ix) {
    var dk = drawingKey(it.cand);
    if (!dk || !IMGS[dk.drw.file]) return null;
    var h = secBar('ГАБАРИТНІ КРЕСЛЕННЯ') + '<div class="dwhead">ПОЗ. ' + String(ix + 1).padStart(2, '0') + ' · <b>' + esc(it.cand.designation) + '</b></div>' +
      '<div class="dwbox"><img alt="" src="' + IMGS[dk.drw.file] + '"></div><p class="small">' + esc(dk.drw.caption) + ' (каталог, с. ' + dk.drw.pg + ')</p>';
    if (dk.dims) {
      var keys = Object.keys(dk.dims.dims);
      var cells = keys.map(function (k) { return '<td class="sy">' + esc(k) + '</td><td class="vl">' + esc(String(dk.dims.dims[k]).replace(/\n/g, ' ').replace('.', ',')) + '</td>'; });
      var per = 6, trs = '';
      for (var a = 0; a < cells.length; a += per) {
        var chunk = cells.slice(a, a + per); while (chunk.length < per) chunk.push('<td></td><td></td>');
        trs += '<tr>' + chunk.join('') + '</tr>';
      }
      h += '<div class="dimt"><b>' + esc(dk.dimKey.replace(/(NMRV|NRV)/, '$1 ')) + ' · розміри, мм</b> (с. ' + dk.dims.pg + ')</div><table class="kt dims"><tbody>' + trs + '</tbody></table>';
    }
    h += '<p class="small">Розміри, мм. Креслення не є робочим; остаточні розміри за даними виробника.</p>';
    return h;
  }

  function closingPage(ctx) {
    var P = ctx.P, num = P.draft || !P.number ? 'ЧЕРНЕТКА' : P.number;
    var allRed = state.items.length && state.items.every(function (i) { return i.cand.kind === 'reducer' && has(i.cand.mass_kg); });
    var mass = null;
    if (allRed) { mass = 0; state.items.forEach(function (i) { mass += i.cand.mass_kg * i.qty; }); }
    var h = secBar('ЗАВЕРШЕННЯ');
    if (mass !== null) h += '<p><span class="k">Загальна маса нетто, прибл.:</span> <b>' + fmt(Math.round(mass * 10) / 10) + ' кг</b></p>';
    h += totalsBlock(ctx);
    h += '<p class="closing">Сподіваємося, що пропозиція Вас зацікавить. Будемо раді відповісти на запитання.</p>' +
      '<p class="sign">З повагою,<br><b>' + esc(P.mgr_name || '') + '</b>' + (P.mgr_position ? '<br>' + esc(P.mgr_position) : '') + (P.seller_short ? '<br>' + esc(P.seller_short) : '') + '</p>' +
      '<p>Будь ласка, вказуйте номер пропозиції <b>' + esc(num) + '</b> у листуванні.</p>';
    var disc = ['Підбір виконано на підставі наданих Вами даних про застосування. Просимо перевірити їх повноту і правильність; за зміни умов експлуатації підбір потребує перегляду.',
      'Технічні дані наведено за технічними каталогами Motovario; виробник може змінювати характеристики без попереднього повідомлення. Зображення не є зобов\'язальними.',
      'Ця комерційна пропозиція не є публічною офертою.',
      'Motovario® є зареєстрованою торговельною маркою Motovario S.p.A. (TECO Group).'];
    if (has(P.dealer_statement)) disc.push(P.dealer_statement);
    h += '<div class="disc">' + disc.map(function (d, i) { return '<p>' + (i + 1) + '. ' + esc(d) + '</p>'; }).join('') + '</div>';
    return h;
  }

  function buildKp() {
    var P = readParties();
    if (!P.date) P.date = today();
    var ctx = { P: P, pi: priceInfo() };
    var pages = [];
    if (!state.items.length) {
      return '<section class="page"><div class="pbody"><p>Додайте позиції до КП.</p></div></section>';
    }
    // page 1 + continuation pages
    var items = state.items, first = 5, rest = 8, chunks = [items.slice(0, first)];
    for (var a = first; a < items.length; a += rest) chunks.push(items.slice(a, a + rest));
    var start = 0;
    chunks.forEach(function (ch, k) {
      pages.push(firstPage(ctx, ch, start, k === chunks.length - 1, k > 0));
      start += ch.length;
    });
    items.forEach(function (it, ix) { pages.push(positionPage(it, ix, ctx)); });
    items.forEach(function (it, ix) { var d = drawingPage(it, ix); if (d) pages.push(d); });
    pages.push(closingPage(ctx));
    return pages.map(function (p, i) { return pageWrap(p, ctx, i, pages.length); }).join('');
  }
  function renderKp() {
    $('kp').innerHTML = buildKp();
    $('kp').classList.add('on');
    document.body.classList.add('has-kp');
    $('sec-kp').scrollIntoView({ behavior: 'auto', block: 'start' });
  }

  // ------------------------------------------------------------------ save / load
  var LS_KEY = 'vsf_quote_v1';
  function msg(t) { $('savemsg').textContent = t; }
  function saveQuote() {
    try {
      localStorage.setItem(LS_KEY, JSON.stringify({ v: 1, items: state.items, nextId: state.nextId, parties: readParties(), form: readForm() }));
      msg('Збережено в цьому браузері (' + state.items.length + ' поз.)');
    } catch (e) { msg('Не вдалося зберегти: сховище браузера недоступне'); }
  }
  function loadQuote() {
    try {
      var s = localStorage.getItem(LS_KEY);
      if (!s) { msg('Збереженого КП немає'); return; }
      var o = JSON.parse(s);
      state.items = o.items || []; state.nextId = o.nextId || 1;
      if (o.parties) fillParties(o.parties);
      renderQuote(); msg('Завантажено: ' + state.items.length + ' поз.');
    } catch (e) { msg('Не вдалося завантажити збережене КП'); }
  }

  // ------------------------------------------------------------------ wiring
  function init() {
    initParties();
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
    $('o_size').addEventListener('change', ovSizeChange); $('o_i').addEventListener('change', ovIChange); $('o_row').addEventListener('change', ovRowChange);
    $('o_check').addEventListener('click', ovVerify); $('o_add').addEventListener('click', ovAdd);
    $('o_cancel').addEventListener('click', function () { $('override-dlg').hidden = true; });
    $('btn_save').addEventListener('click', saveQuote); $('btn_load').addEventListener('click', loadQuote);
    $('btn_clear').addEventListener('click', function () { state.items = []; renderQuote(); $('kp').innerHTML = ''; msg(''); });
    $('btn_demo').addEventListener('click', function () { fillParties(DEMO_PARTIES); });
    $('btn_kp').addEventListener('click', renderKp);
    $('btn_print').addEventListener('click', function () { renderKp(); window.print(); });
  }
  window.__vsf = { E: E, state: state, buildKp: buildKp, fmt: fmt };
  init();
})();
