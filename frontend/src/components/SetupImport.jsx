// Import the React tools we need
import { useMemo, useState } from 'react'
// Import the link tool and the icons we use
import { Link } from 'react-router-dom'
import { AlertCircle, CheckCircle2, Download, Loader2, Upload } from 'lucide-react'
// Import our own files
import { importExistingTenants } from '../api'
import { COLUMN_LABELS, downloadText, rowsFromTable, templateCsv } from '../csv'
import { inputClass } from './Field'

// The page section for importing a whole list of existing tenants
export default function SetupImport({ properties }) {
  // The pasted or uploaded text
  const [text, setText] = useState('')
  // What the backend found when we checked the list (nothing until we check)
  const [result, setResult] = useState(null)
  // How many tenants were imported (shown after a successful import)
  const [imported, setImported] = useState(null)
  // The error message to show (empty means none)
  const [error, setError] = useState('')
  // True while we wait for the backend
  const [busy, setBusy] = useState(false)

  // Read the text into rows every time it changes
  const parsed = useMemo(() => rowsFromTable(text), [text])
  // Can we check the list?
  const canCheck = parsed.rows.length > 0 && parsed.missing.length === 0 && !busy

  // Change the text, and forget any old check (so we never import something different from what was checked)
  function changeText(value) {
    setText(value)
    setResult(null)
    setImported(null)
    setError('')
  }

  // Read a chosen file into the box
  async function handleFile(event) {
    const file = event.target.files[0]
    if (file) changeText(await file.text())
    // Allow choosing the same file again later
    event.target.value = ''
  }

  // Check the list without saving anything
  async function check() {
    setError('')
    setBusy(true)
    try {
      setResult(await importExistingTenants(parsed.rows, true))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // Save the list (only possible after a check where every row was fine)
  async function save() {
    setError('')
    setBusy(true)
    try {
      const done = await importExistingTenants(parsed.rows, false)
      if (done.ok) {
        // Success: show how many, and clear the box
        setImported(done.imported)
        setText('')
        setResult(null)
      } else {
        // Something changed since the check, so show the new result
        setResult(done)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  // The success message after importing
  if (imported !== null) {
    return (
      <div className="mt-6 rounded-3xl bg-forest-100 p-8 text-center">
        <CheckCircle2 size={36} className="mx-auto text-forest-500" />
        <p className="mt-3 font-display text-2xl font-bold text-forest-900">
          {imported} tenant{imported === 1 ? '' : 's'} imported
        </p>
        <p className="mt-1 text-sm text-forest-700">
          Open the Dashboard to add this month's rent for them, or check the Tenants page.
        </p>
        <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
          <Link to="/tenants" className="rounded-xl bg-forest-900 px-5 py-3 text-sm font-semibold text-white hover:bg-forest-700">
            See tenants
          </Link>
          <button onClick={() => setImported(null)} className="rounded-xl bg-paper px-5 py-3 text-sm font-semibold text-forest-700 hover:bg-forest-200">
            Import another list
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="mt-6">
      {/* How it works */}
      <div className="rounded-3xl bg-paper p-5 shadow-sm">
        <h2 className="font-display text-lg font-bold text-forest-900">Bring your notebook in at once</h2>
        <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-muted">
          <li>Download the example, and type your tenants into it (Excel or Google Sheets, one tenant per row).</li>
          <li>Copy the cells and paste them below, or save as CSV and upload the file.</li>
          <li>Press <span className="font-semibold text-forest-900">Check my list</span>. Nothing is saved until every row is fine.</li>
        </ol>
        <div className="mt-4 flex flex-wrap gap-2">
          <button
            onClick={() => downloadText('mnyumba-tenants-example.csv', templateCsv(properties.length > 0 ? properties[0].name : 'Kinoru Apartments'))}
            className="flex items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200"
          >
            <Download size={16} /> Download example
          </button>
          <label className="flex cursor-pointer items-center gap-2 rounded-xl bg-forest-100 px-4 py-2.5 text-sm font-semibold text-forest-700 hover:bg-forest-200">
            <Upload size={16} /> Upload a CSV file
            <input type="file" accept=".csv,.tsv,.txt" onChange={handleFile} className="hidden" />
          </label>
        </div>
        <p className="mt-3 text-xs text-muted">
          Your property names must match exactly: {properties.map((prop) => prop.name).join(', ') || 'add a property first'}.
        </p>
      </div>

      {/* The box for the list */}
      <textarea
        value={text}
        onChange={(e) => changeText(e.target.value)}
        placeholder="Paste your list here, including the heading row"
        spellCheck={false}
        className={`${inputClass} mt-4 min-h-48 font-mono text-xs`}
      />

      {/* What we understood from the text */}
      {text.trim() !== '' && (
        <div className="mt-3 text-sm">
          {parsed.missing.length > 0 ? (
            <p className="flex items-start gap-2 font-medium text-terracotta">
              <AlertCircle size={18} className="mt-0.5 shrink-0" />
              Missing columns: {parsed.missing.map((key) => COLUMN_LABELS[key]).join(', ')}. Check the heading row.
            </p>
          ) : (
            <p className="text-muted">
              {parsed.rows.length} tenant{parsed.rows.length === 1 ? '' : 's'} found.
              {parsed.unknown.length > 0 ? ` Ignoring columns: ${parsed.unknown.join(', ')}.` : ''}
            </p>
          )}
        </div>
      )}

      {/* The result of checking the list */}
      {result && (
        <div className="mt-4">
          <p className={`rounded-2xl px-4 py-3 text-sm font-semibold ${result.ok ? 'bg-forest-100 text-forest-700' : 'bg-terracotta/10 text-terracotta'}`}>
            {result.ok
              ? `All ${result.results.length} rows are fine and ready to import.`
              : `${result.error_count} of ${result.results.length} rows need fixing. Nothing was saved. Fix them above and check again.`}
          </p>
          <ul className="mt-3 divide-y divide-forest-100 overflow-hidden rounded-2xl bg-paper shadow-sm">
            {result.results.map((item) => (
              <li key={item.row_number} className="flex items-start gap-3 p-4">
                {item.ok ? (
                  <CheckCircle2 size={20} className="mt-0.5 shrink-0 text-forest-500" />
                ) : (
                  <AlertCircle size={20} className="mt-0.5 shrink-0 text-terracotta" />
                )}
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-forest-900">
                    Row {item.row_number}
                    {item.tenant_name ? ` · ${item.tenant_name}` : ''}
                    {item.unit_number ? ` · unit ${item.unit_number}` : ''}
                  </p>
                  {item.ok ? (
                    <p className="text-xs text-muted">
                      {item.new_tenant ? 'New tenant' : 'Existing tenant'} · {item.new_unit ? 'new unit will be created' : 'existing unit'}
                    </p>
                  ) : (
                    <p className="text-sm text-terracotta">{item.message}</p>
                  )}
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div role="alert" className="mt-4 rounded-xl bg-terracotta/10 px-4 py-3 text-sm font-medium text-terracotta">
          {error}
        </div>
      )}

      {/* The buttons: check first, then import */}
      <div className="mt-5 flex flex-col gap-3 sm:flex-row">
        <button
          onClick={check}
          disabled={!canCheck}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-100 py-3.5 font-semibold text-forest-700 hover:bg-forest-200 disabled:opacity-50"
        >
          {busy && !result && <Loader2 size={18} className="animate-spin" />}
          Check my list
        </button>
        <button
          onClick={save}
          disabled={!result || !result.ok || busy}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-forest-900 py-3.5 font-semibold text-white shadow-lg shadow-forest-900/20 hover:bg-forest-700 disabled:opacity-50"
        >
          {busy && result && <Loader2 size={18} className="animate-spin" />}
          {result && result.ok ? `Import ${result.results.length} tenant${result.results.length === 1 ? '' : 's'}` : 'Import'}
        </button>
      </div>
    </div>
  )
}