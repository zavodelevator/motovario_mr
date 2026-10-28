/* Amount in words for UAH (Ukrainian). Pure function, no DOM. UMD: browser global Words, node require().
 * amountInWords(amount) -> 'Одна тисяча двісті тридцять чотири гривні 50 копійок'.
 * Integer hryvnias, kopecks always shown as two digits. Returns '' for non-finite, negative or > 999999999.99. */
(function (root, factory) {
  if (typeof module === 'object' && module.exports) module.exports = factory();
  else root.Words = factory();
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  var ONES_M = ['', 'один', 'два', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять'];
  var ONES_F = ['', 'одна', 'дві', 'три', 'чотири', 'п\'ять', 'шість', 'сім', 'вісім', 'дев\'ять'];
  var TEENS = ['десять', 'одинадцять', 'дванадцять', 'тринадцять', 'чотирнадцять', 'п\'ятнадцять', 'шістнадцять', 'сімнадцять', 'вісімнадцять', 'дев\'ятнадцять'];
  var TENS = ['', '', 'двадцять', 'тридцять', 'сорок', 'п\'ятдесят', 'шістдесят', 'сімдесят', 'вісімдесят', 'дев\'яносто'];
  var HUNDREDS = ['', 'сто', 'двісті', 'триста', 'чотириста', 'п\'ятсот', 'шістсот', 'сімсот', 'вісімсот', 'дев\'ятсот'];
  var MAX_HRN = 999999999;

  // 0..999 in words; fem = feminine units (одна/дві) for thousands and hryvnia triads.
  function triad(n, fem) {
    var words = [];
    var h = Math.floor(n / 100), t = Math.floor((n % 100) / 10), u = n % 10;
    if (h) words.push(HUNDREDS[h]);
    if (t === 1) words.push(TEENS[u]);
    else {
      if (t) words.push(TENS[t]);
      if (u) words.push(fem ? ONES_F[u] : ONES_M[u]);
    }
    return words.join(' ');
  }

  // forms = [nominative singular, genitive singular, genitive plural]; 11-14 always genitive plural.
  function plural(n, forms) {
    var d100 = n % 100, d10 = n % 10;
    if (d100 >= 11 && d100 <= 14) return forms[2];
    if (d10 === 1) return forms[0];
    if (d10 >= 2 && d10 <= 4) return forms[1];
    return forms[2];
  }

  function pad2(n) { return (n < 10 ? '0' : '') + n; }

  function amountInWords(amount) {
    if (typeof amount !== 'number' || !isFinite(amount) || amount < 0) return '';
    var cents = Math.round(amount * 100);
    var hrn = Math.floor(cents / 100), kop = cents % 100;
    if (hrn > MAX_HRN) return '';

    var mln = Math.floor(hrn / 1000000), tys = Math.floor(hrn / 1000) % 1000, rest = hrn % 1000;
    var parts = [];
    if (mln) parts.push(triad(mln, false), plural(mln, ['мільйон', 'мільйони', 'мільйонів']));
    if (tys) parts.push(triad(tys, true), plural(tys, ['тисяча', 'тисячі', 'тисяч']));
    if (rest) parts.push(triad(rest, true));
    if (!parts.length) parts.push('нуль');

    var words = parts.join(' ') + ' ' + plural(hrn, ['гривня', 'гривні', 'гривень']) +
      ' ' + pad2(kop) + ' ' + plural(kop, ['копійка', 'копійки', 'копійок']);
    return words.charAt(0).toUpperCase() + words.slice(1);
  }

  return { amountInWords: amountInWords };
});
