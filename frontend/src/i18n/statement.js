// statement.js - puts the lines of a tenant's statement into Kiswahili (no browser parts, so it can be tested)

const MONTHS_EN = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
const MONTHS_SW = ['Januari', 'Februari', 'Machi', 'Aprili', 'Mei', 'Juni', 'Julai', 'Agosti', 'Septemba', 'Oktoba', 'Novemba', 'Desemba']

// Lines that are always the same
const EXACT = {
  'M-Pesa payment': 'Malipo ya M-Pesa',
  'Cash payment': 'Malipo ya pesa taslimu',
  'Bank payment': 'Malipo ya benki',
  Rent: 'Kodi',
  Deposit: 'Amana',
  Water: 'Maji',
  Electricity: 'Umeme',
  'Wi-Fi': 'Wi-Fi',
  Other: 'Nyinginezo',
  'Balance brought forward': 'Salio lililohamishwa',
}

// Translate one line of a statement (anything we do not know stays as it is)
export function statementTitle(title, lang) {
  if (lang !== 'sw' || !title) return title
  if (EXACT[title]) return EXACT[title]
  let match = title.match(/^(\w+) rent$/)
  if (match && MONTHS_EN.includes(match[1])) return `Kodi ya ${MONTHS_SW[MONTHS_EN.indexOf(match[1])]}`
  match = title.match(/^Late fee: (\w+) (\d{4}) rent$/)
  if (match && MONTHS_EN.includes(match[1])) return `Faini ya kuchelewa: kodi ya ${MONTHS_SW[MONTHS_EN.indexOf(match[1])]} ${match[2]}`
  match = title.match(/^(Rent|Deposit|Water|Electricity|Wi-Fi|Other) · (\d{4}-\d{2})$/)
  if (match) return `${EXACT[match[1]]} · ${match[2]}`
  return title
}