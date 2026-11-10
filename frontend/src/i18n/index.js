// index.js - the language the person chose, and the function that turns English texts into it

// Import the React tool for reading something that changes outside React
import { useSyncExternalStore } from 'react'
// Import our own files
import { sw } from './sw'
import { translate } from './translate'

const KEY = 'estateloom_lang'

// The first language: the one the person chose before, or Kiswahili if their phone is set to it
function firstLanguage() {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'sw' || saved === 'en') return saved
  } catch {
    // Not being able to read the saved choice is fine
  }
  return (navigator.language || '').toLowerCase().startsWith('sw') ? 'sw' : 'en'
}

let language = firstLanguage()
document.documentElement.lang = language
const listeners = new Set()

export const getLang = () => language

// Change the language, remember it, and tell the screens
export function setLang(next) {
  if (next !== 'en' && next !== 'sw') return
  language = next
  document.documentElement.lang = next
  try {
    localStorage.setItem(KEY, next)
  } catch {
    // Not being able to save the choice is fine
  }
  listeners.forEach((listener) => listener())
}

const subscribe = (listener) => {
  listeners.add(listener)
  return () => listeners.delete(listener)
}

// Turn an English text into the chosen language (the English is the fallback)
export function t(key, vars) {
  return language === 'sw' ? translate(sw, key, vars) : translate(null, key, vars)
}

// For screens: gives the function, and makes the screen redraw when the language changes
export function useT() {
  useSyncExternalStore(subscribe, getLang)
  return t
}