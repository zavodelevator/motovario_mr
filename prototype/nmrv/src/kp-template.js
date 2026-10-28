/* KP template (KP_SPEC.md): pure HTML-string rendering of the commercial proposal. No DOM access, no storage, no host calls.
 * NmrvKP.create(deps).build({ P, items, pricing }) -> HTML.   deps = { E, EN, D, IMGS, photoFor(c), modelPng(item) -> dataURL|null, conceptNote }
 * NmrvKP.util = shared formatting helpers (also used by the UI).
 * Swap this file (or the CSS) to restyle the KP for another company; the data contract is the quote JSON (docs/NMRV_MODEL.md). */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.NmrvKP = factory();
})(typeof self !== 'undefined' ? self : this, function () {
'use strict';
var NB = '\u202f';
function esc(s) { return String(s === null || s === undefined ? '' : s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
function has(v) { return v !== null && v !== undefined && v !== '' && !(typeof v === 'number' && !isFinite(v)); }
function fmt(x, dec) {
  if (!has(x)) return '';
  if (typeof x !== 'number') return String(x);
  var s = dec === undefined ? String(Math.round(x * 1000) / 1000) : x.toFixed(dec);
  var p = s.split('.'); var ip = p[0].replace(/\B(?=(\d{3})+(?!\d))/g, NB);
  return p[1] ? ip + ',' + p[1] : ip;
}
function pad2(n) { return String(n).padStart(2, '0'); }
function isoOf(d) { return d.getFullYear() + '-' + pad2(d.getMonth() + 1) + '-' + pad2(d.getDate()); }
function today() { return isoOf(new Date()); }
function dmy(iso) { if (!iso) return ''; var p = iso.split('-'); return p.length === 3 ? p[2] + '.' + p[1] + '.' + p[0] : iso; }
function addDays(iso, n) { var d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return isoOf(d); }
function bar(u) {
  var cls = u > 95 ? ' hot' : '';
  return '<div class="ubar' + cls + '"><i style="width:' + Math.min(100, Math.max(0, u)) + '%"></i></div><span class="unum">' + fmt(u, 1) + ' %</span>';
}
function typeName(c) { return c.kind === 'gearmotor' ? 'Черв\'ячний мотор-редуктор' : 'Черв\'ячний редуктор'; }
var util = { typeName: typeName, NB: NB, esc: esc, has: has, fmt: fmt, today: today, dmy: dmy, addDays: addDays, bar: bar };

function create(DEPS) {
  var E = DEPS.E, EN = DEPS.EN, D = DEPS.D, IMGS = DEPS.IMGS || {}, photoFor = DEPS.photoFor, CONCEPT_NOTE = DEPS.conceptNote || '';
  var CLASS_UK = EN.LOAD_CLASS_UK, CUR = null;
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
    var anyRef = CUR.items.some(function (i) { return has(i.customer_ref); });
    var priced = ctx.pi.priced;
    var h = '<table class="kt sum"><thead><tr><th class="c">Поз.</th><th class="c">Кількість</th><th>Опис</th>' + (anyRef ? '<th>Ваш № товару</th>' : '') +
      (priced ? '<th class="r">Ціна за од. з ПДВ, грн</th><th class="r">Сума з ПДВ, грн</th>' : '') + '</tr></thead><tbody>';
    items.forEach(function (it, k) {
      var ix = startIx + k;
      h += '<tr><td class="c">' + String(ix + 1).padStart(2, '0') + '</td><td class="c">' + it.qty + ' шт</td><td>' + esc(typeName(it.cand)) + '<div class="des">' + esc(it.cand.designation) + '</div></td>' +
        (anyRef ? '<td>' + esc(it.customer_ref) + '</td>' : '') +
        (priced ? '<td class="r">' + fmt(ctx.pi.list[ix].unit_gross_uah, 2) + '</td><td class="r">' + fmt(ctx.pi.list[ix].line_gross_kop / 100, 2) + '</td>' : '') + '</tr>';
    });
    return h + '</tbody></table>';
  }
  function totalsBlock(ctx) {
    if (!ctx.pi.priced) return '';
    var t = ctx.pi.totals;
    var W = (typeof Words !== 'undefined') ? Words : (typeof require === 'function' ? require('./words.js') : null);
    var words = W ? W.amountInWords(t.gross_kop / 100) : '';
    return '<table class="kt tot"><tbody><tr><td>Разом з ПДВ, грн</td><td class="r">' + fmt(t.gross_kop / 100, 2) + '</td></tr><tr><td>у т.ч. ПДВ 20 %, грн</td><td class="r">' + fmt(t.vat_kop / 100, 2) + '</td></tr><tr><td>Разом без ПДВ, грн</td><td class="r">' + fmt(t.net_kop / 100, 2) + '</td></tr></tbody></table>' + (words ? '<p class="small">Всього до сплати: <b>' + esc(words) + '</b>, у т.ч. ПДВ 20 %.</p>' : '');
  }
  function termsTable(ctx) {
    var P = ctx.P;
    var valid = addDays(P.date || today(), parseInt(P.validity_days, 10) || 30);
    var rows = [
      ['Умови оплати', esc(P.payment_terms)],
      ctx.pi.priced ? ['Ціни', 'Ціни вказано в гривнях з ПДВ 20 %, розраховано за курсом ' + fmt(ctx.pi.fx, 2) + ' грн/EUR на ' + esc(dmy(P.date || today())) + '. У разі зміни курсу більш ніж на 3 % ціна може бути переглянута.'] : null,
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
      (anyPrice ? '<span class="pp">' + fmt(anyPrice.unit_gross_uah, 2) + ' грн · ' + fmt(anyPrice.line_gross_kop / 100, 2) + ' грн</span>' : '') + '</div>';
    var h = bar1 + '<div class="imgrow">' +
      imgBlock(c, it, ph) +
      '<div class="basiscol">' + mark + '<div class="basis"><div class="bt">Вихідні дані підбору</div>' + rowsHtml(basis.map(function (b) { return [b[0], esc(b[1])]; })) + '</div></div></div>' +
      secBar('ТЕХНІЧНІ ДАНІ') +
      '<div class="two"><div><div class="coltitle">РЕДУКТОР</div>' + kvList(left) + '</div><div><div class="coltitle">' + motorTitle + '</div>' + motorBody + '</div></div>' +
      '<div class="posfoot">' + foot + '</div>';
    return h;
  }

  var PHOTO_NOTE = 'Колір і технічні характеристики можуть відрізнятися від показаних на зображенні. Технічна специфікація відповідає наведеним нижче даним.';
  function imgBlock(c, it, ph) {
    var png = DEPS.modelPng ? DEPS.modelPng(it) : null;
    if (png) {
      return '<div class="imgcol"><div class="imgbox m3"><img class="m3img" alt="' + esc(c.series) + ' 3D" src="' + png + '">' +
        (ph ? '<img class="thumb" alt="" src="' + ph.src + '">' : '') + '</div><p class="imgnote concept">' + esc(CONCEPT_NOTE) + '</p><p class="imgnote">' + esc(PHOTO_NOTE) + '</p></div>';
    }
    return ph ? '<div class="imgcol"><div class="imgbox"><img alt="' + esc(c.series) + '" src="' + ph.src + '"></div><p class="imgnote">' + esc(PHOTO_NOTE) + '</p></div>' : '';
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
    var h = secBar('ЗАВЕРШЕННЯ');
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

  // build({P, items, pricing}) -> HTML string. P = parties/terms form values, items = quote items, pricing = E-side priceItems() result.
  function build(input) {
    CUR = { items: input.items };
    var P = Object.assign({}, input.P);
    if (!P.date) P.date = today();
    var ctx = { P: P, pi: input.pricing };
    var pages = [];
    if (!CUR.items.length) return '<section class="page"><div class="pbody"><p>Додайте позиції до КП.</p></div></section>';
    var items = CUR.items, first = 5, rest = 8, chunks = [items.slice(0, first)];
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
  return { build: build };
}

return { create: create, util: util };
});
