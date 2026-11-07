// Tests for the offline rules and the way waiting changes are shown (no browser needed)

import test from 'node:test'
import assert from 'node:assert/strict'
import { isCacheable, isGuarded, matchQueueable } from '../src/offline/rules.js'
import { mergeBodies, overlayInspections, overlayRepairs, overlayWork } from '../src/offline/overlay.js'

test('only the safe requests can wait on the phone', () => {
  assert.equal(matchQueueable('POST', '/maintenance').kind, 'repair')
  assert.equal(matchQueueable('POST', '/maintenance').key, true)
  assert.equal(matchQueueable('PUT', '/maintenance/5').kind, 'repair_update')
  assert.equal(matchQueueable('PUT', '/inspections/items/12').merge, true)
  assert.equal(matchQueueable('POST', '/inspections/3/photos').multipart, true)
  assert.equal(matchQueueable('PUT', '/work/units/9/status').kind, 'unit_status')
  // Money, accounts and everything else are never saved for later
  for (const [method, path] of [
    ['POST', '/payments'],
    ['POST', '/leases/1/payments'],
    ['POST', '/mpesa/stk-push'],
    ['DELETE', '/payments/3'],
    ['POST', '/auth/login'],
    ['POST', '/account/change-password'],
    ['POST', '/tenants'],
    ['GET', '/maintenance'],
    ['POST', '/inspections/3/finalize'],
  ]) {
    assert.equal(matchQueueable(method, path), null, `${method} ${path}`)
  }
})

test('locking a checklist always needs the server', () => {
  assert.equal(isGuarded('POST', '/inspections/3/finalize'), true)
  assert.equal(isGuarded('POST', '/inspections/3/photos'), false)
})

test('the phone remembers only the pages it needs', () => {
  for (const path of ['/auth/me', '/setup/status', '/work/properties', '/maintenance', '/maintenance?status=open', '/inspections/lease/4']) {
    assert.equal(isCacheable(path), true, path)
  }
  for (const path of ['/payments', '/properties', '/tenants', '/portal/home', '/account/export', '/admin/overview']) {
    assert.equal(isCacheable(path), false, path)
  }
})

test('a newer rating replaces the older one but keeps other fields', () => {
  assert.deepEqual(mergeBodies({ condition: 'good', note: 'ok' }, { condition: 'poor' }), { condition: 'poor', note: 'ok' })
  assert.deepEqual(mergeBodies(null, { note: 'x' }), { note: 'x' })
})

// A checklist as the server sends it
const checklist = () => ({
  move_in: {
    id: 7,
    items: [
      { id: 1, condition: null, note: null, photos: [] },
      { id: 2, condition: 'good', note: null, photos: [] },
    ],
    general_photos: [],
  },
  move_out: null,
})

test('waiting ratings, notes and photos show on a checklist', () => {
  const original = checklist()
  const entries = [
    { id: 'a', kind: 'item', status: 'pending', path: '/inspections/items/1', body: { condition: 'poor', note: 'Cracked' } },
    { id: 'b', kind: 'photo', status: 'pending', path: '/inspections/7/photos', fields: { item_id: '2' }, createdAt: 1700000000000 },
    { id: 'c', kind: 'photo', status: 'pending', path: '/inspections/7/photos', fields: {}, createdAt: 1700000001000 },
  ]
  const shown = overlayInspections(original, entries)
  assert.equal(shown.move_in.items[0].condition, 'poor')
  assert.equal(shown.move_in.items[0].note, 'Cracked')
  assert.equal(shown.move_in.items[1].photos[0].id, 'local-b')
  assert.equal(shown.move_in.general_photos[0].id, 'local-c')
  // The saved copy is not changed
  assert.equal(original.move_in.items[0].condition, null)
  assert.equal(original.move_in.items[1].photos.length, 0)
})

test('changes that failed are not shown as if they had happened', () => {
  const entries = [{ id: 'a', kind: 'item', status: 'failed', path: '/inspections/items/1', body: { condition: 'poor' } }]
  assert.equal(overlayInspections(checklist(), entries).move_in.items[0].condition, null)
})

test('a waiting unit status shows on the caretaker home', () => {
  const home = [{ units: [{ unit_id: 5, status: 'vacant' }, { unit_id: 6, status: 'vacant' }] }]
  const entries = [{ id: 'a', kind: 'unit_status', status: 'pending', path: '/work/units/5/status', body: { status: 'maintenance' } }]
  const shown = overlayWork(home, entries)
  assert.equal(shown[0].units[0].status, 'maintenance')
  assert.equal(shown[0].units[1].status, 'vacant')
  assert.equal(home[0].units[0].status, 'vacant')
})

test('a waiting repair update shows in the list', () => {
  const list = { items: [{ id: 3, status: 'open' }, { id: 4, status: 'open' }] }
  const entries = [{ id: 'a', kind: 'repair_update', status: 'pending', path: '/maintenance/3', body: { status: 'done' } }]
  const shown = overlayRepairs(list, entries)
  assert.equal(shown.items[0].status, 'done')
  assert.equal(shown.items[1].status, 'open')
})