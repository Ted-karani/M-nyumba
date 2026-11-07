// Import the React tool for reading something that changes outside React
import { useSyncExternalStore } from 'react'
// Import our own files
import { getState, subscribe } from './engine'

// Gives a screen the current offline state, and refreshes it when it changes
export function useOfflineState() {
  return useSyncExternalStore(subscribe, getState)
}