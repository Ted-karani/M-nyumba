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

  // If our saved token was rejected, it has expired, so go back to the login screen
  if (response.status === 401 && token && path !== '/auth/login') {
    clearToken()
    window.location.reload()
    throw new Error('Your session has expired. Please sign in again.')
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

// Send data to the backend as JSON (used for creating and editing)
const sendJson = (method, path, body) =>
  request(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

// ---------- LOGIN ----------

// Log in with email and password, and get a token back
export function login(email, password) {
  // The login endpoint wants a form, with the email under the name "username"
  const body = new URLSearchParams({ username: email, password })
  return request('/auth/login', { method: 'POST', body })
}

// Create a new account
export const register = (form) => sendJson('POST', '/auth/register', form)

// Get the details of whoever is logged in
export const getMe = () => request('/auth/me')

// ---------- DASHBOARD ----------

// Get all the numbers for the dashboard
export const getDashboard = () => request('/dashboard')

// ---------- PROPERTIES ----------

// Get one property
export const getProperty = (id) => request(`/properties/${id}`)
// Add a property
export const createProperty = (data) => sendJson('POST', '/properties', data)
// Edit a property
export const updateProperty = (id, data) => sendJson('PUT', `/properties/${id}`, data)
// Delete a property
export const deleteProperty = (id) => request(`/properties/${id}`, { method: 'DELETE' })

// ---------- UNITS ----------

// Get all the units inside a property
export const getUnits = (propertyId) => request(`/properties/${propertyId}/units`)
// Add a unit inside a property
export const createUnit = (propertyId, data) => sendJson('POST', `/properties/${propertyId}/units`, data)
// Edit a unit
export const updateUnit = (id, data) => sendJson('PUT', `/units/${id}`, data)
// Delete a unit
export const deleteUnit = (id) => request(`/units/${id}`, { method: 'DELETE' })

// ---------- LEASES ----------

// Get leases, optionally filtered, like getLeases({ property_id: 1, status: 'active' })
export function getLeases(filters = {}) {
  // Turn the filters into the "?property_id=1&status=active" part of the address
  const query = new URLSearchParams(filters).toString()
  return request(`/leases${query ? `?${query}` : ''}`)
}