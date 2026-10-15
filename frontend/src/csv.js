// The names of the columns we understand, and the other names people might use for them
const HEADER_ALIASES = {
  property: 'property_name',
  property_name: 'property_name',
  building: 'property_name',
  unit: 'unit_number',
  unit_number: 'unit_number',
  house: 'unit_number',
  house_no: 'unit_number',
  door: 'unit_number',
  unit_type: 'unit_type',
  type: 'unit_type',
  tenant: 'tenant_name',
  tenant_name: 'tenant_name',
  name: 'tenant_name',
  phone: 'phone',
  phone_number: 'phone',
  mobile: 'phone',
  tel: 'phone',
  id: 'id_number',
  id_number: 'id_number',
  rent: 'rent_amount',
  rent_amount: 'rent_amount',
  deposit: 'deposit_amount',
  deposit_amount: 'deposit_amount',
  owes: 'balance',
  balance: 'balance',
  arrears: 'balance',
  billing_from: 'billing_from',
  bill_from: 'billing_from',
  due_day: 'due_day',
  tenant_since: 'tenant_since',
  since: 'tenant_since',
}

// The columns that must be present
const REQUIRED = ['property_name', 'unit_number', 'tenant_name', 'phone', 'rent_amount']

// Friendly names for the required columns (used in messages)
export const COLUMN_LABELS = {
  property_name: 'property',
  unit_number: 'unit',
  tenant_name: 'tenant',
  phone: 'phone',
  rent_amount: 'rent',
}

// Turn a column heading like "Phone Number" into "phone_number"
function normalizeHeader(header) {
  return header
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '_')
    .replace(/^_|_$/g, '')
}

// Split pasted text into rows and cells (works for Excel pastes, commas, semicolons, and quoted cells)
export function parseTable(text) {
  // Tidy the line endings and remove a hidden mark Excel sometimes adds
  const clean = text.replace(/^\uFEFF/, '').replace(/\r\n?/g, '\n').trim()
  if (!clean) return []
  // Pick the separator from the first line: tab (Excel paste), then semicolon, then comma
  const firstLine = clean.split('\n')[0]
  const delimiter = ['\t', ';', ','].find((d) => firstLine.includes(d)) || ','
  const rows = []
  let row = []
  let cell = ''
  let inQuotes = false
  // Walk through the text one character at a time
  for (let i = 0; i < clean.length; i++) {
    const ch = clean[i]
    if (inQuotes) {
      if (ch === '"') {
        // Two quotes in a row mean one real quote
        if (clean[i + 1] === '"') {
          cell += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        cell += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === delimiter) {
      row.push(cell)
      cell = ''
    } else if (ch === '\n') {
      row.push(cell)
      rows.push(row)
      row = []
      cell = ''
    } else {
      cell += ch
    }
  }
  // Save the last cell and row
  row.push(cell)
  rows.push(row)
  // Ignore completely empty rows
  return rows.filter((r) => r.some((c) => c.trim() !== ''))
}

// Turn pasted text into rows of named values, and say which required columns are missing
export function rowsFromTable(text) {
  const table = parseTable(text)
  if (table.length === 0) return { rows: [], missing: [], unknown: [] }
  // Work out what each column is
  const headers = table[0].map((header) => HEADER_ALIASES[normalizeHeader(header)] || null)
  // Required columns that are not there
  const missing = REQUIRED.filter((key) => !headers.includes(key))
  // Columns we do not understand (they are ignored)
  const unknown = table[0].filter((header, i) => headers[i] === null && header.trim() !== '').map((header) => header.trim())
  // Build one object for each data row
  const rows = table.slice(1).map((cells) => {
    const row = {}
    headers.forEach((key, i) => {
      if (key) row[key] = (cells[i] ?? '').trim()
    })
    return row
  })
  return { rows, missing, unknown }
}

// Make the example file people can download and fill in
export function templateCsv(propertyName) {
  // The month after this one, written like 2026-11
  const next = new Date()
  next.setMonth(next.getMonth() + 1)
  const nextMonth = `${next.getFullYear()}-${String(next.getMonth() + 1).padStart(2, '0')}`
  return [
    'property,unit,unit_type,tenant,phone,rent,deposit,owes,billing_from,due_day,tenant_since,id_number',
    `${propertyName},A1,Bedsitter,Mercy Wambui,0711 000 111,6000,6000,0,${nextMonth},5,2023-02-10,`,
    `${propertyName},A2,1 Bedroom,Peter Kariuki,0722 000 222,9000,9000,4500,${nextMonth.slice(0, 5)}${String(new Date().getMonth() + 1).padStart(2, '0')},10,2024-06-01,`,
  ].join('\n')
}

// Save some text as a file on the person's computer
export function downloadText(filename, text) {
  const blob = new Blob([text], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}