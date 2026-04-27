import { useState, useEffect } from 'react'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

const STATUS_CONFIG = {
  draft:                { label: 'Draft',             color: 'bg-gray-100 text-gray-600' },
  submitted:            { label: 'Submitted',         color: 'bg-blue-100 text-blue-700' },
  under_review:         { label: 'Under Review',      color: 'bg-yellow-100 text-yellow-700' },
  approved:             { label: 'Approved',          color: 'bg-green-100 text-green-700' },
  rejected:             { label: 'Rejected',          color: 'bg-red-100 text-red-700' },
  more_info_requested:  { label: 'More Info Needed',  color: 'bg-orange-100 text-orange-700' },
}

const TRANSITIONS = {
  submitted:            [{ state: 'under_review', label: 'Start Review', cls: 'bg-blue-600 hover:bg-blue-700' }],
  under_review:         [
    { state: 'approved',            label: '✓ Approve',       cls: 'bg-green-600 hover:bg-green-700' },
    { state: 'rejected',            label: '✗ Reject',        cls: 'bg-red-600 hover:bg-red-700' },
    { state: 'more_info_requested', label: '? Request Info',  cls: 'bg-orange-500 hover:bg-orange-600' },
  ],
  more_info_requested:  [{ state: 'under_review', label: 'Mark Under Review', cls: 'bg-yellow-600 hover:bg-yellow-700' }],
}

function MetricCard({ label, value, sub, highlight }) {
  return (
    <div className={`bg-white rounded-xl border p-5 ${highlight ? 'border-red-200' : 'border-gray-100'}`}>
      <p className="text-sm text-gray-500">{label}</p>
      <p className={`text-3xl font-bold mt-1 ${highlight ? 'text-red-600' : 'text-gray-900'}`}>{value}</p>
      {sub && <p className="text-xs text-gray-400 mt-1">{sub}</p>}
    </div>
  )
}

function SubmissionPanel({ submission, onTransition }) {
  const [note, setNote] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const actions = TRANSITIONS[submission.status] || []

  const doTransition = async (newState) => {
    if (['rejected', 'more_info_requested'].includes(newState) && !note.trim()) {
      setError('Please add a note explaining the reason.')
      return
    }
    setLoading(true)
    setError('')
    try {
      const res = await api.post(`/kyc/submissions/${submission.id}/transition/`, { new_state: newState, note })
      onTransition(res.data)
      setNote('')
    } catch (err) {
      setError(err.response?.data?.error || 'Transition failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="bg-white rounded-2xl border border-gray-100 p-6 space-y-5">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">{submission.full_name || submission.merchant_username}</h2>
          <p className="text-sm text-gray-500">{submission.business_name} · {submission.business_type}</p>
        </div>
        <div className="flex items-center gap-2">
          {submission.is_at_risk && (
            <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-medium rounded-full animate-pulse">⚠ AT RISK</span>
          )}
          <span className={`px-2.5 py-1 rounded-full text-xs font-medium ${STATUS_CONFIG[submission.status]?.color}`}>
            {STATUS_CONFIG[submission.status]?.label}
          </span>
        </div>
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-3 text-sm">
        {[
          ['Email', submission.email], ['Phone', submission.phone],
          ['Monthly Volume', submission.monthly_volume_usd ? `$${Number(submission.monthly_volume_usd).toLocaleString()}` : '—'],
          ['In Queue', submission.time_in_queue_hours != null ? `${submission.time_in_queue_hours}h` : '—'],
          ['Submitted', submission.submitted_at ? new Date(submission.submitted_at).toLocaleString() : 'Not yet'],
          ['Reviewer', submission.reviewer || '—'],
        ].map(([k, v]) => (
          <div key={k} className="bg-gray-50 rounded-lg p-3">
            <p className="text-gray-400 text-xs mb-0.5">{k}</p>
            <p className="font-medium text-gray-800">{v}</p>
          </div>
        ))}
      </div>

      {/* Documents */}
      <div>
        <p className="text-sm font-medium text-gray-700 mb-2">Documents</p>
        <div className="flex flex-wrap gap-2">
          {[
            ['PAN Card', submission.pan_document_url],
            ['Aadhaar', submission.aadhaar_document_url],
            ['Bank Statement', submission.bank_statement_url],
          ].map(([label, url]) => (
            url
              ? <a key={label} href={url} target="_blank" rel="noreferrer"
                  className="px-3 py-1.5 bg-indigo-50 text-indigo-700 text-xs font-medium rounded-lg hover:bg-indigo-100 transition-colors">
                  📄 {label}
                </a>
              : <span key={label} className="px-3 py-1.5 bg-gray-100 text-gray-400 text-xs rounded-lg">
                  {label} (missing)
                </span>
          ))}
        </div>
      </div>

      {/* Previous reviewer note */}
      {submission.reviewer_note && (
        <div className="p-3 bg-yellow-50 rounded-lg text-sm text-yellow-800">
          <span className="font-medium">Previous note: </span>{submission.reviewer_note}
        </div>
      )}

      {/* Actions */}
      {actions.length > 0 && (
        <div className="space-y-3 pt-2 border-t border-gray-100">
          <textarea
            rows={2} placeholder="Add a note (required for rejection/more info)…"
            className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
            value={note} onChange={e => setNote(e.target.value)} />
          {error && <p className="text-red-600 text-xs">{error}</p>}
          <div className="flex flex-wrap gap-2">
            {actions.map(({ state, label, cls }) => (
              <button key={state} onClick={() => doTransition(state)} disabled={loading}
                className={`px-4 py-2 text-white text-sm font-medium rounded-lg disabled:opacity-50 transition-colors ${cls}`}>
                {loading ? '…' : label}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

export default function ReviewerDashboard() {
  const { user, logout } = useAuth()
  const [metrics, setMetrics] = useState(null)
  const [queue, setQueue] = useState([])
  const [allSubmissions, setAllSubmissions] = useState([])
  const [selected, setSelected] = useState(null)
  const [tab, setTab] = useState('queue')
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('')

  useEffect(() => { loadData() }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [mRes, qRes, aRes] = await Promise.all([
        api.get('/kyc/metrics/'),
        api.get('/kyc/queue/'),
        api.get('/kyc/submissions/'),
      ])
      setMetrics(mRes.data)
      setQueue(qRes.data.results)
      setAllSubmissions(aRes.data.results)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  const handleTransition = (updated) => {
    setSelected(updated)
    loadData()
  }

  const filtered = statusFilter
    ? allSubmissions.filter(s => s.status === statusFilter)
    : allSubmissions

  const displayList = tab === 'queue' ? queue : filtered

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 bg-indigo-600 rounded-lg flex items-center justify-center">
            <span className="text-white font-bold text-sm">P</span>
          </div>
          <span className="font-semibold text-gray-900">Reviewer Dashboard</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-gray-600">{user?.username}</span>
          <button onClick={logout} className="text-sm text-gray-400 hover:text-gray-600">Sign out</button>
        </div>
      </header>

      <div className="max-w-7xl mx-auto py-6 px-4">
        {/* Metrics */}
        {metrics && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <MetricCard label="In Queue" value={metrics.queue_count} sub="submitted + under review" />
            <MetricCard label="At Risk" value={metrics.at_risk_count} sub=">24h in queue" highlight={metrics.at_risk_count > 0} />
            <MetricCard label="Avg Queue Time" value={`${metrics.avg_time_in_queue_hours}h`} sub="current queue" />
            <MetricCard label="7-Day Approval Rate" value={`${metrics.approval_rate_7d}%`} sub="last 7 days" />
          </div>
        )}

        <div className="flex gap-6">
          {/* Left: list */}
          <div className="w-96 flex-shrink-0 space-y-3">
            {/* Tabs */}
            <div className="flex bg-gray-100 rounded-xl p-1 gap-1">
              {[['queue','Queue'],['all','All']].map(([t, l]) => (
                <button key={t} onClick={() => setTab(t)}
                  className={`flex-1 py-1.5 text-sm font-medium rounded-lg transition-colors
                    ${tab === t ? 'bg-white text-indigo-600 shadow-sm' : 'text-gray-500'}`}>
                  {l} {t === 'queue' ? `(${queue.length})` : `(${allSubmissions.length})`}
                </button>
              ))}
            </div>

            {tab === 'all' && (
              <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
                <option value="">All statuses</option>
                {Object.entries(STATUS_CONFIG).map(([v, { label }]) => (
                  <option key={v} value={v}>{label}</option>
                ))}
              </select>
            )}

            {loading ? (
              <div className="text-center py-8 text-gray-400 text-sm">Loading…</div>
            ) : displayList.length === 0 ? (
              <div className="text-center py-8 text-gray-400 text-sm">No submissions here.</div>
            ) : (
              displayList.map(sub => (
                <button key={sub.id} onClick={() => setSelected(sub)}
                  className={`w-full text-left p-4 rounded-xl border transition-all
                    ${selected?.id === sub.id ? 'border-indigo-300 bg-indigo-50' : 'bg-white border-gray-100 hover:border-gray-300'}`}>
                  <div className="flex items-start justify-between mb-1">
                    <span className="font-medium text-sm text-gray-900 truncate">
                      {sub.full_name || sub.merchant_username}
                    </span>
                    <div className="flex items-center gap-1 ml-2 flex-shrink-0">
                      {sub.is_at_risk && <span className="text-red-500 text-xs">⚠</span>}
                      <span className={`px-2 py-0.5 rounded-full text-xs ${STATUS_CONFIG[sub.status]?.color}`}>
                        {STATUS_CONFIG[sub.status]?.label}
                      </span>
                    </div>
                  </div>
                  <p className="text-xs text-gray-400 truncate">{sub.business_name}</p>
                  {sub.submitted_at && (
                    <p className="text-xs text-gray-400 mt-1">
                      {new Date(sub.submitted_at).toLocaleDateString()}
                      {sub.time_in_queue_hours != null && ` · ${sub.time_in_queue_hours}h in queue`}
                    </p>
                  )}
                </button>
              ))
            )}
          </div>

          {/* Right: detail */}
          <div className="flex-1">
            {selected ? (
              <SubmissionPanel submission={selected} onTransition={handleTransition} />
            ) : (
              <div className="bg-white rounded-2xl border border-gray-100 p-12 text-center text-gray-400">
                <p className="text-4xl mb-3">📋</p>
                <p className="text-sm">Select a submission from the left to review it.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
