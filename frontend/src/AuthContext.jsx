// Import the React tools we need
import { createContext, useContext, useEffect, useState } from 'react'
// Import all the functions from our api file
import * as api from './api'

// Make a shared box that any screen can read from
const AuthContext = createContext(null)

// This wraps the whole app and holds the login information
export function AuthProvider({ children }) {
  // The logged-in user (or nothing)
  const [user, setUser] = useState(null)
  // True while we check if a saved token is still good
  const [loading, setLoading] = useState(true)

  // When the app first opens, check for a saved token
  useEffect(() => {
    // No token means nobody is logged in, so we are done checking
    if (!api.getToken()) {
      setLoading(false)
      return
    }
    // Ask the backend who the token belongs to
    api
      .getMe()
      .then(setUser)
      // If the token is expired or fake, throw it away
      .catch(() => api.clearToken())
      // Either way, we are done checking
      .finally(() => setLoading(false))
  }, [])

  // Log in, save the token, then load the user's details
  async function signIn(email, password) {
    const data = await api.login(email, password)
    api.saveToken(data.access_token)
    setUser(await api.getMe())
  }

  // Create an account, then log in straight away
  async function signUp(form) {
    await api.register(form)
    await signIn(form.email, form.password)
  }

  // Log out: forget the token and the user
  function signOut() {
    api.clearToken()
    setUser(null)
  }

  // Share these with every screen
  return (
    <AuthContext.Provider value={{ user, loading, signIn, signUp, signOut }}>
      {children}
    </AuthContext.Provider>
  )
}

// A shortcut so screens can write useAuth() to get the login information
export const useAuth = () => useContext(AuthContext)