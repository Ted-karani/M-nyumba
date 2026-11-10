// translate.js - turns an English text into another language (no browser parts, so it can be tested)

// Look the English text up in a dictionary. If it is not there, show the English. Fill in {name} style blanks.
export function translate(dictionary, key, vars) {
  const text = (dictionary && dictionary[key]) || key
  if (!vars) return text
  return text.replace(/\{(\w+)\}/g, (whole, name) => (name in vars ? String(vars[name]) : whole))
}