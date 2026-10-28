'use strict';
// node --test test/nmrv/words.test.js   (no dependencies)
const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const { amountInWords } = require(path.join(__dirname, '..', '..', 'prototype', 'nmrv', 'src', 'words.js'));

const CASES = [
  [0, 'Нуль гривень 00 копійок'],
  [1, 'Одна гривня 00 копійок'],
  [2, 'Дві гривні 00 копійок'],
  [5, 'П\'ять гривень 00 копійок'],
  [11, 'Одинадцять гривень 00 копійок'],
  [12, 'Дванадцять гривень 00 копійок'],
  [14, 'Чотирнадцять гривень 00 копійок'],
  [21, 'Двадцять одна гривня 00 копійок'],
  [22, 'Двадцять дві гривні 00 копійок'],
  [100, 'Сто гривень 00 копійок'],
  [101, 'Сто одна гривня 00 копійок'],
  [111, 'Сто одинадцять гривень 00 копійок'],
  [1000, 'Одна тисяча гривень 00 копійок'],
  [2000, 'Дві тисячі гривень 00 копійок'],
  [5000, 'П\'ять тисяч гривень 00 копійок'],
  [11000, 'Одинадцять тисяч гривень 00 копійок'],
  [12000, 'Дванадцять тисяч гривень 00 копійок'],
  [21000, 'Двадцять одна тисяча гривень 00 копійок'],
  [22000, 'Двадцять дві тисячі гривень 00 копійок'],
  [101000, 'Сто одна тисяча гривень 00 копійок'],
  [1000000, 'Один мільйон гривень 00 копійок'],
  [2000000, 'Два мільйони гривень 00 копійок'],
  [5000000, 'П\'ять мільйонів гривень 00 копійок'],
  [999999999.99, 'Дев\'ятсот дев\'яносто дев\'ять мільйонів дев\'ятсот дев\'яносто дев\'ять тисяч дев\'ятсот дев\'яносто дев\'ять гривень 99 копійок'],
  [0.01, 'Нуль гривень 01 копійка'],
  [0.02, 'Нуль гривень 02 копійки'],
  [0.05, 'Нуль гривень 05 копійок'],
  [0.21, 'Нуль гривень 21 копійка'],
  [0.11, 'Нуль гривень 11 копійок'],
  [1234.5, 'Одна тисяча двісті тридцять чотири гривні 50 копійок'],
  [0.999, 'Одна гривня 00 копійок'],
];

for (const [input, expected] of CASES) {
  test(`amountInWords(${input}) -> "${expected}"`, () => {
    assert.strictEqual(amountInWords(input), expected);
  });
}

test('negative amount returns empty string', () => {
  assert.strictEqual(amountInWords(-1), '');
  assert.strictEqual(amountInWords(-0.01), '');
});

test('NaN returns empty string', () => {
  assert.strictEqual(amountInWords(NaN), '');
});

test('Infinity returns empty string', () => {
  assert.strictEqual(amountInWords(Infinity), '');
  assert.strictEqual(amountInWords(-Infinity), '');
});

test('amount above 999999999.99 returns empty string', () => {
  assert.strictEqual(amountInWords(1e9), '');
  assert.strictEqual(amountInWords(1000000000.01), '');
});

test('non-number input returns empty string', () => {
  assert.strictEqual(amountInWords('100'), '');
  assert.strictEqual(amountInWords(undefined), '');
});
