// overlay.js - puts the changes that are still waiting to be sent on top of what the server last told us
// (plain functions with no browser parts, so they can be tested)

// Join two waiting changes for the same thing: the newer values win
export function mergeBodies(older, newer) {
  return { ...(older || {}), ...(newer || {}) }
}

// The number inside an address like /inspections/items/12
function idFrom(path, pattern) {
  const match = path.match(pattern)
  return match ? Number(match[1]) : null
}

const ITEM = /^\/inspections\/items\/(\d+)$/
const PHOTO = /^\/inspections\/(\d+)\/photos$/
const UNIT = /^\/work\/units\/(\d+)\/status$/
const REPAIR = /^\/maintenance\/(\d+)$/

// Only changes that have not failed are shown as if they had happened
const waiting = (entries) => entries.filter((entry) => entry.status === 'pending')

// A checklist screen: ratings, notes and photos that are still waiting
export function overlayInspections(data, entries) {
  const copy = JSON.parse(JSON.stringify(data))
  const inspections = [copy.move_in, copy.move_out].filter(Boolean)
  for (const entry of waiting(entries)) {
    if (entry.kind === 'item') {
      const id = idFrom(entry.path, ITEM)
      for (const inspection of inspections) {
        const item = (inspection.items || []).find((row) => row.id === id)
        if (!item) continue
        if (entry.body && 'condition' in entry.body) item.condition = entry.body.condition
        if (entry.body && 'note' in entry.body) item.note = entry.body.note
      }
    }
    if (entry.kind === 'photo') {
      const inspection = inspections.find((row) => row.id === idFrom(entry.path, PHOTO))
      if (!inspection) continue
      const fields = entry.fields || {}
      const photo = {
        id: `local-${entry.id}`,
        item_id: fields.item_id ? Number(fields.item_id) : null,
        caption: fields.caption || null,
        created_at: new Date(entry.createdAt).toISOString().slice(0, -1),
      }
      const item = photo.item_id ? (inspection.items || []).find((row) => row.id === photo.item_id) : null
      if (item) {
        item.photos = item.photos || []
        item.photos.push(photo)
      } else {
        inspection.general_photos = inspection.general_photos || []
        inspection.general_photos.push(photo)
      }
    }
  }
  return copy
}

// A caretaker's home screen: unit status changes that are still waiting
export function overlayWork(data, entries) {
  const copy = JSON.parse(JSON.stringify(data))
  const properties = Array.isArray(copy) ? copy : copy.properties || []
  for (const entry of waiting(entries)) {
    if (entry.kind !== 'unit_status' || !entry.body) continue
    const id = idFrom(entry.path, UNIT)
    for (const property of properties) {
      for (const unit of property.units || []) {
        if ((unit.unit_id ?? unit.id) === id && 'status' in entry.body) unit.status = entry.body.status
      }
    }
  }
  return copy
}

// The repairs list: updates that are still waiting
export function overlayRepairs(data, entries) {
  const copy = JSON.parse(JSON.stringify(data))
  const rows = Array.isArray(copy) ? copy : copy.items || []
  for (const entry of waiting(entries)) {
    if (entry.kind !== 'repair_update' || !entry.body) continue
    const id = idFrom(entry.path, REPAIR)
    const row = rows.find((item) => item.id === id)
    if (row) Object.assign(row, entry.body)
  }
  return copy
}