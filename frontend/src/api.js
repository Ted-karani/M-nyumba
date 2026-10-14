// The address of our backend
const API_URL = 'http://127.0.0.1:8000'
// The name we save the login token under in the browser
const TOKEN_KEY = 'mnyumba_token'

// Read the saved token (or nothing if there is none)
export const getToken = () => localStorage.getItem(TOKEN_KEY)
// Save a token in the browser
export const saveToken = (token) => localStorage.setItem(TOKEN_KEY, token)
// Remove the token (this is what logging out does)
export const clearToken = () => localStorage.removeItem(TOKEN_KEY)

// Turn whatever error the backend sent into one readable sentence
function errorMessage(data, status) {
  // Simple errors come as plain text, like "Wrong email or password"
  if (data && typeof data.detail === 'string') return data.detail
  // Form errors come as a list, so we read the first one
  if (data && Array.isArray(data.detail) && data.detail.length > 0) {
    const first = data.detail[0]
    // Find which field the error is about (the last part of "loc")
    const field = first.loc && first.loc.length > 1 ? first.loc[first.loc.length - 1] : null
    // Tidy up the message text
    const message = (first.msg || 'Invalid input').replace('Value error, ', '')
    // Show "field: message" when we know the field
    return field ? `${String(field).replace(/_/g, ' ')}: ${message}` : message
  }
  // Fall back to a general message
  return `Something went wrong (error ${status})`
}

// Send a request to the backend (every other function below uses this)
async function request(path, options = {}) {
  // Start with any headers we were given
  const headers = { ...(options.headers || {}) }
  // If we have a token, send it so the backend knows who we are
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  let response
  try {
    // Make the request
    response = await fetch(API_URL + path, { ...options, headers })
  } catch {
    // The request never reached the backend
    throw new Error('Cannot reach the server. Is the backend running?')
  }

  // "204" means success with nothing to send back
  if (response.status === 204) return null

  // Read the answer as JSON (or nothing if it is not JSON)
  let data = null
  try {
    data = await response.json()
  } catch {
    data = null
  }

  // If the backend said no, turn it into an error we can show
  if (!response.ok) throw new Error(errorMessage(data, response.status))
  // Otherwise hand back the data
  return data
}

// Log in with email and password, and get a token back
export function login(email, password) {
  // The login endpoint wants a form, with the email under the name "username"
  const body = new URLSearchParams({ username: email, password })
  return request('/auth/login', { method: 'POST', body })
}

// Create a new account
export function register(form) {
  return request('/auth/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form),
  })
}

// Get the details of whoever is logged in
export const getMe = () => request('/auth/me')