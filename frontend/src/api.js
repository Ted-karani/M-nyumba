// The address of our backend (other files use it to build links)
export const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
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

  // If our saved token was rejected, it has expired (or the account was switched off), so go back to the login screen
  // (the sign-in steps are left out, because a wrong code there is not an expired session)
  if (response.status === 401 && token && !path.startsWith('/auth/login')) {
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

// Leave out any filter that is empty, and turn the rest into "?a=1&b=2"
function queryString(filters) {
  const used = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '' && value != null))
  const query = new URLSearchParams(used).toString()
  return query ? `?${query}` : ''
}

// Get a file from the backend (this sends the login token, which a plain link or picture tag cannot do)
export async function fetchBlob(path) {
  // Send the token so the backend knows who we are
  const token = getToken()
  let response
  try {
    response = await fetch(API_URL + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
  } catch {
    throw new Error('Cannot reach the server. Is the backend running?')
  }
  // If our saved token was rejected, go back to the login screen
  if (response.status === 401) {
    clearToken()
    window.location.reload()
    throw new Error('Your session has expired. Please sign in again.')
  }
  // If the backend said no, show why
  if (!response.ok) {
    let data = null
    try {
      data = await response.json()
    } catch {
      data = null
    }
    throw new Error(errorMessage(data, response.status))
  }
  return response.blob()
}

// Save a file that is in the browser's memory onto the person's computer
function triggerDownload(url, filename) {
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
}

// Download a file from the backend
export async function downloadFile(path, filename) {
  const blob = await fetchBlob(path)
  const url = URL.createObjectURL(blob)
  triggerDownload(url, filename)
  URL.revokeObjectURL(url)
}

// Open a file from the backend in a new tab
export async function openFile(path, filename) {
  // Open the tab right away (browsers only allow this straight after a click), and fill it in once the file arrives
  const tab = window.open('', '_blank')
  try {
    const blob = await fetchBlob(path)
    const url = URL.createObjectURL(blob)
    if (tab) tab.location.href = url
    else triggerDownload(url, filename)
    // Let go of the file in memory after a minute
    setTimeout(() => URL.revokeObjectURL(url), 60000)
  } catch (err) {
    if (tab) tab.close()
    throw err
  }
}

// ---------- LOGIN ----------

// Log in with email (or a tenant's phone number) and password (step one: this gives a token, or asks for a code)
export function login(email, password) {
  // The login endpoint wants a form, with the email under the name "username"
  const body = new URLSearchParams({ username: email, password })
  return request('/auth/login', { method: 'POST', body })
}

// Step two of signing in: send the short-lived pass together with the 6-digit code (or a recovery code)
export const verifyOtp = (challenge, code) => sendJson('POST', '/auth/login/verify', { challenge, code })

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

// Get every property together with all of its units (each unit also carries its property's name)
export async function getUnitDirectory() {
  // First get the list of properties
  const dashboard = await getDashboard()
  // Then get the units of every property at the same time
  const lists = await Promise.all(
    dashboard.properties.map((prop) =>
      getUnits(prop.property_id).then((units) => units.map((unit) => ({ ...unit, property_name: prop.name })))
    )
  )
  // Send back the properties and one flat list of all units
  return { properties: dashboard.properties, units: lists.flat() }
}

// ---------- TENANTS ----------

// Get all of this landlord's tenants
export const getTenants = () => request('/tenants')
// Get one tenant
export const getTenant = (id) => request(`/tenants/${id}`)
// Add a tenant
export const createTenant = (data) => sendJson('POST', '/tenants', data)
// Edit a tenant
export const updateTenant = (id, data) => sendJson('PUT', `/tenants/${id}`, data)
// Delete a tenant
export const deleteTenant = (id) => request(`/tenants/${id}`, { method: 'DELETE' })

// ---------- LEASES ----------

// Get leases, optionally filtered, like getLeases({ tenant_id: 1, status: 'active' })
export const getLeases = (filters = {}) => request(`/leases${queryString(filters)}`)
// Move a tenant into a unit
export const createLease = (data) => sendJson('POST', '/leases', data)
// End a lease: the tenant leaves and the unit becomes vacant (no date means today)
export const endLease = (id, data = {}) => sendJson('POST', `/leases/${id}/end`, data)

// ---------- CHARGES AND PAYMENTS ----------

// Get the charges on a lease
export const getCharges = (leaseId) => request(`/leases/${leaseId}/charges`)
// Add a charge to a lease
export const createCharge = (leaseId, data) => sendJson('POST', `/leases/${leaseId}/charges`, data)
// Delete a charge
export const deleteCharge = (id) => request(`/charges/${id}`, { method: 'DELETE' })
// Get the payments on a lease
export const getPayments = (leaseId) => request(`/leases/${leaseId}/payments`)
// Record a payment on a lease
export const createPayment = (leaseId, data) => sendJson('POST', `/leases/${leaseId}/payments`, data)
// Delete a payment
export const deletePayment = (id) => request(`/payments/${id}`, { method: 'DELETE' })

// Get all payments across every property, with filters like { month: '2026-10', method: 'cash' }
export const getPaymentsReport = (filters = {}) => request(`/payments${queryString(filters)}`)

// ---------- MONTHLY RENT ----------

// See which rent charges are missing, without adding anything
export const getRentPreview = () => request('/billing/rent-preview')
// Add all the missing rent charges
export const generateRent = () => request('/billing/generate-rent', { method: 'POST' })

// ---------- BILLS (WATER, ELECTRICITY, WI-FI) ----------

// Get the meter reading sheet for a property, a utility ("water" or "electricity"), and a month like "2026-10"
export function getMeterSheet(propertyId, utility, period) {
  const query = new URLSearchParams({ property_id: propertyId, utility, period }).toString()
  return request(`/utilities/sheet?${query}`)
}
// Save meter readings and charge the tenants for what they used
export const billMeters = (data) => sendJson('POST', '/utilities/bill', data)
// Undo a meter reading (this also removes the charge that came from it)
export const undoReading = (id) => request(`/utilities/readings/${id}`, { method: 'DELETE' })
// Get the Wi-Fi sheet for a property and a month
export function getWifiSheet(propertyId, period) {
  const query = new URLSearchParams({ property_id: propertyId, period }).toString()
  return request(`/utilities/wifi-sheet?${query}`)
}
// Charge a flat Wi-Fi fee to the chosen units
export const billWifi = (data) => sendJson('POST', '/utilities/bill-wifi', data)

// ---------- REPAIRS ----------

// Get repairs, optionally filtered, like getRepairs({ status: 'open', property_id: 1 })
export const getRepairs = (filters = {}) => request(`/maintenance${queryString(filters)}`)
// Report a new problem
export const createRepair = (data) => sendJson('POST', '/maintenance', data)
// Edit a repair
export const updateRepair = (id, data) => sendJson('PUT', `/maintenance/${id}`, data)
// Delete a repair
export const deleteRepair = (id) => request(`/maintenance/${id}`, { method: 'DELETE' })

// ---------- TEAM (CARETAKERS) ----------

// Get the properties a caretaker works with, with their units and tenants
export const getWorkProperties = () => request('/work/properties')
// The same list, in the shape the repair form expects
export async function getWorkDirectory() {
  // Get the properties a caretaker works with
  const list = await getWorkProperties()
  return {
    properties: list.map((prop) => ({ property_id: prop.property_id, name: prop.name })),
    units: list.flatMap((prop) =>
      prop.units.map((unit) => ({
        id: unit.unit_id,
        property_id: prop.property_id,
        unit_number: unit.unit_number,
        property_name: prop.name,
      }))
    ),
  }
}
// Mark an empty unit as "vacant" or "maintenance"
export const setUnitStatus = (id, status) => sendJson('PUT', `/work/units/${id}/status`, { status })
// Get the caretakers this owner created
export const getCaretakers = () => request('/caretakers')
// Add a caretaker
export const createCaretaker = (data) => sendJson('POST', '/caretakers', data)
// Edit a caretaker (change properties, reset the password, or switch the account off)
export const updateCaretaker = (id, data) => sendJson('PUT', `/caretakers/${id}`, data)

// ---------- SET UP EXISTING TENANTS ----------

// Check a list of existing tenants (dryRun true), or save it (dryRun false)
export const importExistingTenants = (rows, dryRun) =>
  sendJson('POST', '/onboarding/existing-tenants', { rows, dry_run: dryRun })

// ---------- REMINDERS ----------

// Get when each lease was last reminded
export const getReminderSummary = () => request('/reminders/summary')
// Record that a reminder was sent
export const logReminder = (data) => sendJson('POST', '/reminders', data)

// ---------- EXPENSES AND REPORTS ----------

// Get expenses, optionally filtered, like getExpenses({ month: '2026-10', property_id: 1 })
export const getExpenses = (filters = {}) => request(`/expenses${queryString(filters)}`)
// Record an expense
export const createExpense = (data) => sendJson('POST', '/expenses', data)
// Edit an expense
export const updateExpense = (id, data) => sendJson('PUT', `/expenses/${id}`, data)
// Delete an expense
export const deleteExpense = (id) => request(`/expenses/${id}`, { method: 'DELETE' })
// Get the monthly report (propertyId can be empty for all properties)
export const getMonthlyReport = (month, propertyId) =>
  request(`/reports/monthly${queryString({ month, property_id: propertyId })}`)

// ---------- DOCUMENTS AND TASKS ----------

// Get documents, optionally filtered, like getDocuments({ kind: 'permit', expiring: 'true' })
export const getDocuments = (filters = {}) => request(`/documents${queryString(filters)}`)
// Upload a document (the form holds the file and its details)
export const uploadDocument = (form) => request('/documents', { method: 'POST', body: form })
// Edit a document's details
export const updateDocument = (id, data) => sendJson('PUT', `/documents/${id}`, data)
// Delete a document and its file
export const deleteDocument = (id) => request(`/documents/${id}`, { method: 'DELETE' })

// Get tasks: "open", "done", or "all"
export const getTasks = (show = 'open') => request(`/tasks${queryString({ show })}`)
// Add a task
export const createTask = (data) => sendJson('POST', '/tasks', data)
// Edit a task
export const updateTask = (id, data) => sendJson('PUT', `/tasks/${id}`, data)
// Delete a task
export const deleteTask = (id) => request(`/tasks/${id}`, { method: 'DELETE' })
// Mark a task done (a repeating task moves to its next due date)
export const completeTask = (id) => request(`/tasks/${id}/done`, { method: 'POST' })
// Get what is coming up: tasks due soon and documents about to expire
export const getUpcoming = () => request('/tasks/upcoming')

// ---------- CHECKLISTS (MOVE-IN AND MOVE-OUT) ----------

// Get both checklists of a lease
export const getLeaseInspections = (leaseId) => request(`/inspections/lease/${leaseId}`)
// Start a checklist ("move_in" or "move_out")
export const startInspection = (leaseId, kind, data) => sendJson('POST', `/inspections/lease/${leaseId}/${kind}`, data)
// Edit a checklist's date, notes, or the tenant's details
export const updateInspection = (id, data) => sendJson('PUT', `/inspections/${id}`, data)
// Lock a checklist
export const finalizeInspection = (id) => request(`/inspections/${id}/finalize`, { method: 'POST' })
// Unlock a checklist (owners only)
export const unlockInspection = (id) => request(`/inspections/${id}/unlock`, { method: 'POST' })
// Delete a whole checklist (owners only)
export const deleteInspection = (id) => request(`/inspections/${id}`, { method: 'DELETE' })
// Add an area to a checklist
export const addInspectionItem = (id, area) => sendJson('POST', `/inspections/${id}/items`, { area })
// Rate an area or change its note
export const updateInspectionItem = (itemId, data) => sendJson('PUT', `/inspections/items/${itemId}`, data)
// Remove an area
export const deleteInspectionItem = (itemId) => request(`/inspections/items/${itemId}`, { method: 'DELETE' })
// Upload a photo (the form holds the picture and, optionally, the area it shows)
export const uploadInspectionPhoto = (id, form) => request(`/inspections/${id}/photos`, { method: 'POST', body: form })
// Delete a photo
export const deleteInspectionPhoto = (photoId) => request(`/inspections/photos/${photoId}`, { method: 'DELETE' })

// ---------- ACCOUNT, 2-STEP LOGIN, AND ACTIVITY ----------

// Change your own password
export const changePassword = (data) => sendJson('POST', '/account/change-password', data)
// Get the activity log (owners only), like getActivity({ days: 7, actor_id: 2 })
export const getActivity = (filters = {}) => request(`/account/activity${queryString(filters)}`)
// Find out whether 2-step login is on
export const getTwoStep = () => request('/account/2fa')
// Start the setup: get the secret and the QR code address
export const startTwoStep = () => request('/account/2fa/setup', { method: 'POST' })
// Finish the setup with a code from the app (this returns the recovery codes)
export const enableTwoStep = (code) => sendJson('POST', '/account/2fa/enable', { code })
// Turn it off (needs the password and a code)
export const disableTwoStep = (data) => sendJson('POST', '/account/2fa/disable', data)

// ---------- VACANCY LISTINGS ----------

// Get the owner's listings, and the empty units that have none yet
export const getListings = () => request('/listings')
// Make a listing for an empty unit
export const createListing = (data) => sendJson('POST', '/listings', data)
// Edit a listing
export const updateListing = (id, data) => sendJson('PUT', `/listings/${id}`, data)
// Delete a listing
export const deleteListing = (id) => request(`/listings/${id}`, { method: 'DELETE' })
// Make a new secret link (the old one stops working)
export const newListingLink = (id) => request(`/listings/${id}/regenerate-link`, { method: 'POST' })
// Add a photo to a listing (the form holds the picture)
export const uploadListingPhoto = (id, form) => request(`/listings/${id}/photos`, { method: 'POST', body: form })
// Delete a listing photo
export const deleteListingPhoto = (photoId) => request(`/listings/photos/${photoId}`, { method: 'DELETE' })
// Get a public listing (no login needed)
export const getPublicListing = (token) => request(`/public/listings/${token}`)

// ---------- TENANT PORTAL (WHAT TENANTS USE) ----------

// Find out whether the tenant still has to choose their own password
export const getPortalStatus = () => request('/portal/status')
// Choose a new password (this gives back a fresh token, so the tenant stays signed in)
export const changePortalPassword = (data) => sendJson('POST', '/portal/change-password', data)
// Get the home screen: balance, how to pay, and the latest notices
export const getPortalHome = () => request('/portal/home')
// Get the statement of one of the tenant's own leases
export const getPortalStatement = (leaseId) => request(`/portal/statement/${leaseId}`)
// Get all the notices the tenant may see
export const getPortalNotices = () => request('/portal/notices')
// Get the problems the tenant reported
export const getPortalRepairs = () => request('/portal/repairs')
// Report a problem
export const createPortalRepair = (data) => sendJson('POST', '/portal/repairs', data)

// ---------- TENANT PORTAL (WHAT OWNERS USE) ----------

// Get the list of tenants and whether they have access
export const getPortalAccess = () => request('/portal-access')
// Give a tenant access, or make a new temporary password for them
export const givePortalAccess = (tenantId) => request(`/portal-access/${tenantId}`, { method: 'POST' })
// Switch a tenant's access on or off
export const setPortalActive = (tenantId, isActive) => sendJson('PUT', `/portal-access/${tenantId}`, { is_active: isActive })
// Get the payment details tenants see
export const getPaymentDetails = () => request('/portal-access/payment-details')
// Save the payment details tenants see
export const savePaymentDetails = (data) => sendJson('PUT', '/portal-access/payment-details', data)
// Get the notice board
export const getNotices = () => request('/notices')
// Post a notice
export const createNotice = (data) => sendJson('POST', '/notices', data)
// Edit a notice
export const updateNotice = (id, data) => sendJson('PUT', `/notices/${id}`, data)
// Delete a notice
export const deleteNotice = (id) => request(`/notices/${id}`, { method: 'DELETE' })