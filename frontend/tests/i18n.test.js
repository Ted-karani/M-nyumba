// Tests for the Kiswahili translations (no browser needed)

import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { sw } from '../src/i18n/sw.js'
import { statementTitle } from '../src/i18n/statement.js'
import { translate } from '../src/i18n/translate.js'

const src = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', 'src')

// The screens that use translations
const FILES = [
  'pages/Login.jsx',
  'pages/PortalHome.jsx',
  'pages/PortalRepairs.jsx',
  'pages/PortalNotices.jsx',
  'pages/PortalAccount.jsx',
  'components/TenantGate.jsx',
  'components/MpesaPrompt.jsx',
  'components/RepairPhotos.jsx',
  'components/Layout.jsx',
  'components/OfflineBar.jsx',
]
// Menu names that are translated by the menu itself, not by a call in a screen
const FROM_THE_MENU = ['My rent', 'Problems']

// Find every English text given to the translate function in a screen
function keysIn(file) {
  const text = readFileSync(path.join(src, file), 'utf8')
  const found = []
  for (const match of text.matchAll(/\bt\(\s*(['"])((?:\\.|(?!\1)[^\\])*)\1/g)) found.push(match[2].replace(/\\(['"\\])/g, '$1'))
  return found
}

const placeholders = (text) => [...text.matchAll(/\{(\w+)\}/g)].map((match) => match[1]).sort()

test('every English text in the screens has a Kiswahili text', () => {
  const missing = []
  for (const file of FILES) for (const key of keysIn(file)) if (!(key in sw)) missing.push(`${file}: ${key}`)
  assert.deepEqual(missing, [])
})

test('every Kiswahili text is used by a screen (so a typo in a key is caught)', () => {
  const used = new Set(FROM_THE_MENU)
  for (const file of FILES) keysIn(file).forEach((key) => used.add(key))
  assert.deepEqual(Object.keys(sw).filter((key) => !used.has(key)), [])
})

test('the blanks in braces are the same in both languages, and no text is empty', () => {
  for (const [english, swahili] of Object.entries(sw)) {
    assert.ok(swahili.trim().length > 0, english)
    assert.deepEqual(placeholders(swahili), placeholders(english), english)
  }
})

test('a text that is not in the dictionary stays English, and blanks are filled in', () => {
  assert.equal(translate(sw, 'A text nobody translated'), 'A text nobody translated')
  assert.equal(translate(sw, 'Welcome, {name}', { name: 'Grace' }), 'Karibu, Grace')
  assert.equal(translate(null, 'Welcome, {name}', { name: 'Grace' }), 'Welcome, Grace')
  assert.equal(translate(sw, 'Show all ({count})', { count: 12 }), 'Onyesha zote (12)')
  assert.equal(translate(sw, 'Balance {amount}'), 'Salio {amount}')
})

test('statement lines are translated, and anything unknown stays as it is', () => {
  assert.equal(statementTitle('October rent', 'sw'), 'Kodi ya Oktoba')
  assert.equal(statementTitle('M-Pesa payment', 'sw'), 'Malipo ya M-Pesa')
  assert.equal(statementTitle('Cash payment', 'sw'), 'Malipo ya pesa taslimu')
  assert.equal(statementTitle('Balance brought forward', 'sw'), 'Salio lililohamishwa')
  assert.equal(statementTitle('Late fee: October 2026 rent', 'sw'), 'Faini ya kuchelewa: kodi ya Oktoba 2026')
  assert.equal(statementTitle('Water · 2026-10', 'sw'), 'Maji · 2026-10')
  assert.equal(statementTitle('Water: 12 units', 'sw'), 'Water: 12 units')
  assert.equal(statementTitle('October rent', 'en'), 'October rent')
  assert.equal(statementTitle('Something else entirely', 'sw'), 'Something else entirely')
})