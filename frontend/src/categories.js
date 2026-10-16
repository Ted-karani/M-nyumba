// The kinds of expense, and the words we show for them
export const EXPENSE_CATEGORIES = [
  { key: 'caretaker', label: 'Caretaker pay' },
  { key: 'security', label: 'Security' },
  { key: 'cleaning', label: 'Cleaning and garbage' },
  { key: 'taxes', label: 'Taxes and levies' },
  { key: 'insurance', label: 'Insurance' },
  { key: 'licences', label: 'Licences and permits' },
  { key: 'utilities', label: 'Common area bills' },
  { key: 'supplies', label: 'Supplies' },
  { key: 'other', label: 'Other' },
]

// Get the words for a kind (or the kind itself if we do not know it)
export function categoryLabel(key) {
  const found = EXPENSE_CATEGORIES.find((category) => category.key === key)
  return found ? found.label : key
}