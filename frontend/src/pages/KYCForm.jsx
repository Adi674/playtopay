import { useState, useEffect, useRef } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'
import { useNavigate } from 'react-router-dom'

const STEPS = ['Personal Details', 'Business Details', 'Documents']
const STATUS_CONFIG = {
  draft:                { label: 'Draft', color: 'bg-gray-100 text-gray-700' },
  submitted:            { label: 'Submitted', color: 'bg-blue-100 text-blue-700' },
  under_review:         { label: 'Under Review', color: 'bg-yellow-100 text-yellow-700' },
  approved:             { label: 'Approved ✓', color: 'bg-green-100 text-green-700' },
  rejected:             { label: 'Rejected', color: 'bg-red-100 text-red-700' },
  more_info_requested:  { label: 'More Info Needed', color: 'bg-orange-100 text-orange-700' },
}

function FileDropZone({ label, fieldName, currentUrl, onFile, disabled }) {
  const [dragging, setDragging] = useState(false)
  const [fileName, setFileName] = useState('')
  const inputRef = useRef()

  const handleFile = (file) => {
    if (!file) return
    setFileName(file.name)
    onFile(fieldName, file)
  }

  return (
    <div>
      <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFile(e.dataTransfer.files[0]) }}
        onClick={() => !disabled && inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-4 text-center cursor-pointer transition-colors
          ${dragging ? 'border-indigo-400 bg-indigo-50' : 'border-gray-300 hover:border-indigo-400'}
          ${disabled ? 'opacity-50 cursor-not-allowed' : ''}`}
      >
        <input ref={inputRef} type="file" accept=".pdf,.jpg,.jpeg,.png" className="hidden"
          onChange={e => handleFile(e.target.files[0])} disabled={disabled} />
        {fileName ? (
          <p className="text-sm text-indigo-600 font-medium">📎 {fileName}</p>
        ) : currentUrl ? (
          <p className="text-sm text-green-600">✓ Uploaded — <a href={currentUrl} target="_blank" rel="noreferrer" className="underline" onClick={e => e.stopPropagation()}>view</a></p>
        ) : (
          <p className="text-sm text-gray-400">Drop file or click to upload<br /><span className="text-xs">PDF, JPG, PNG · max 5 MB</span></p>
        )}
      </div>
    </div>
  )
}

export default function KYCForm() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [step, setStep] = useState(0)
  const [submission, setSubmission] = useState(null)
  const [form, setForm] = useState({
    full_name: '', email: '', phone: '',
    business_name: '', business_type: '', monthly_volume_usd: '',
  })
  const [files, setFiles] = useState({})
  const [saving, setSaving] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  useEffect(() => {
    loadSubmission()
  }, [])

  const loadSubmission = async () => {
    try {
      const res = await api.get('/kyc/my-submission/')
      setSubmission(res.data)
      setForm({
        full_name: res.data.full_name || '',
        email: res.data.email || '',
        phone: res.data.phone || '',
        business_name: res.data.business_name || '',
        business_type: res.data.business_type || '',
        monthly_volume_usd: res.data.monthly_volume_usd || '',
      })
    } catch (err) {
      if (err.response?.status === 404) {
        // Create a draft automatically on first visit
        const res = await api.post('/kyc/my-submission/')
        setSubmission(res.data)
      }
    }
  }

  const isEditable = !submission || ['draft', 'more_info_requested'].includes(submission.status)

  const handleSave = async () => {
    if (!isEditable) return
    setSaving(true)
    setError('')
    try {
      const data = new FormData()
      Object.entries(form).forEach(([k, v]) => { if (v !== '') data.append(k, v) })
      Object.entries(files).forEach(([k, v]) => data.append(k, v))
      const res = await api.put('/kyc/my-submission/', data, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      setSubmission(res.data)
      setFiles({})
      setSuccess('Progress saved!')
      setTimeout(() => setSuccess(''), 3000)
    } catch (err) {
      const details = err.response?.data?.details
      if (details) {
        const msgs = Object.values(details).flat()
        setError(msgs.join(' '))
      } else {
        setError(err.response?.data?.error || 'Save failed.')
      }
    } finally {
      setSaving(false)
    }
  }

  const handleSubmit = async () => {
    setSubmitting(true)
    setError('')
    try {
      await handleSave()
      const res = await api.post('/kyc/my-submission/submit/')
      setSubmission(res.data)
      setSuccess('KYC submitted successfully! We will review your application soon.')
    } catch (err) {
      const e = err.response?.data
      if (e?.missing_fields) {
        setError(`Please complete all fields: ${e.missing_fields.join(', ')}`)
      } else {
        setError(e?.error || 'Submission failed.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  const status = submission?.status || 'draft'
  const cfg = STATUS_CONFIG[status] || STATUS_CONFIG.draft

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">P</span>
          </div>
          <span className="font-semibold text-gray-900">Playto Pay KYC</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600">Hi, {user?.first_name || user?.username}</span>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto py-8 px-4">
        {/* Status banner */}
        {submission && (
          <div className={`mb-6 px-4 py-3 rounded-xl flex items-center justify-between ${cfg.color}`}>
            <span className="font-medium">{cfg.label}</span>
            {submission.reviewer_note && (
              <span className="text-sm italic">"{submission.reviewer_note}"</span>
            )}
          </div>
        )}

        {/* Alerts */}
        {error && <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>}
        {success && <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-lg text-green-700 text-sm">{success}</div>}

        {/* Step tabs */}
        <div className="flex gap-1 mb-6 bg-gray-100 rounded-xl p-1">
          {STEPS.map((s, i) => (
            <button key={i} onClick={() => setStep(i)}
              className={`flex-1 py-2 text-sm font-medium rounded-lg transition-colors
                ${step === i ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500 hover:text-gray-700'}`}>
              {i + 1}. {s}
            </button>
          ))}
        </div>

        {/* Form card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-100 p-6">
          {step === 0 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Personal Details</h2>
              {[
                { label: 'Full Name', key: 'full_name', type: 'text' },
                { label: 'Email', key: 'email', type: 'email' },
                { label: 'Phone', key: 'phone', type: 'tel' },
              ].map(({ label, key, type }) => (
                <div key={key}>
                  <label className="block text-sm font-medium text-gray-700 mb-1">{label}</label>
                  <input type={type} disabled={!isEditable}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50 disabled:text-gray-500"
                    value={form[key]} onChange={e => setForm({ ...form, [key]: e.target.value })} />
                </div>
              ))}
            </div>
          )}

          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Business Details</h2>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Name</label>
                <input disabled={!isEditable}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
                  value={form.business_name} onChange={e => setForm({ ...form, business_name: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Business Type</label>
                <select disabled={!isEditable}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
                  value={form.business_type} onChange={e => setForm({ ...form, business_type: e.target.value })}>
                  <option value="">Select type…</option>
                  {[['agency','Agency'],['freelancer','Freelancer'],['ecommerce','E-Commerce'],['saas','SaaS'],['other','Other']].map(([v,l]) =>
                    <option key={v} value={v}>{l}</option>
                  )}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Expected Monthly Volume (USD)</label>
                <input type="number" min="0" disabled={!isEditable}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-50"
                  value={form.monthly_volume_usd} onChange={e => setForm({ ...form, monthly_volume_usd: e.target.value })} />
              </div>
            </div>
          )}

          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">Document Upload</h2>
              <p className="text-sm text-gray-500 mb-4">Upload PDF, JPG, or PNG. Max 5 MB each.</p>
              <FileDropZone label="PAN Card" fieldName="pan_document"
                currentUrl={submission?.pan_document_url} disabled={!isEditable}
                onFile={(k, v) => setFiles(f => ({ ...f, [k]: v }))} />
              <FileDropZone label="Aadhaar Card" fieldName="aadhaar_document"
                currentUrl={submission?.aadhaar_document_url} disabled={!isEditable}
                onFile={(k, v) => setFiles(f => ({ ...f, [k]: v }))} />
              <FileDropZone label="Bank Statement" fieldName="bank_statement"
                currentUrl={submission?.bank_statement_url} disabled={!isEditable}
                onFile={(k, v) => setFiles(f => ({ ...f, [k]: v }))} />
            </div>
          )}
        </div>

        {/* Actions */}
        {isEditable && (
          <div className="mt-4 flex gap-3 justify-between">
            <div className="flex gap-2">
              {step > 0 && (
                <button onClick={() => setStep(s => s - 1)}
                  className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors">
                  ← Back
                </button>
              )}
              {step < STEPS.length - 1 && (
                <button onClick={() => setStep(s => s + 1)}
                  className="px-4 py-2 text-sm bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
                  Next →
                </button>
              )}
            </div>
            <div className="flex gap-2">
              <button onClick={handleSave} disabled={saving}
                className="px-4 py-2 text-sm border border-indigo-200 text-indigo-600 rounded-lg hover:bg-indigo-50 disabled:opacity-50 transition-colors">
                {saving ? 'Saving…' : 'Save Progress'}
              </button>
              {step === STEPS.length - 1 && (
                <button onClick={handleSubmit} disabled={submitting}
                  className="px-5 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 transition-colors font-medium">
                  {submitting ? 'Submitting…' : 'Submit KYC →'}
                </button>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
