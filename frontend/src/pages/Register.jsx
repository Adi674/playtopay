import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import api from '../api/client'
import { useAuth } from '../context/AuthContext'

export default function Register() {
  const [form, setForm] = useState({
    username: '', email: '', password: '', first_name: '', last_name: '', phone: '', role: 'merchant'
  })
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const { login } = useAuth()
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      const res = await api.post('/auth/register/', form)
      login(res.data.token, res.data.user)
      navigate('/kyc')
    } catch (err) {
      const details = err.response?.data?.details
      if (details) {
        const msgs = Object.entries(details).map(([k,v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : v}`)
        setError(msgs.join(' | '))
      } else {
        setError(err.response?.data?.error || 'Registration failed.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="bg-white rounded-2xl shadow-lg w-full max-w-md p-8">
        <div className="mb-6 text-center">
          <div className="inline-flex items-center justify-center w-12 h-12 bg-indigo-600 rounded-xl mb-4">
            <span className="text-white text-xl font-bold">P</span>
          </div>
          <h1 className="text-2xl font-bold text-gray-900">Create Account</h1>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">{error}</div>
        )}

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">First Name</label>
              <input className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={form.first_name} onChange={e => setForm({...form, first_name: e.target.value})} />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-700 mb-1">Last Name</label>
              <input className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={form.last_name} onChange={e => setForm({...form, last_name: e.target.value})} />
            </div>
          </div>
          {[
            { label: 'Username', key: 'username', type: 'text', required: true },
            { label: 'Email', key: 'email', type: 'email', required: true },
            { label: 'Phone', key: 'phone', type: 'tel' },
            { label: 'Password', key: 'password', type: 'password', required: true },
          ].map(({ label, key, type, required }) => (
            <div key={key}>
              <label className="block text-xs font-medium text-gray-700 mb-1">{label}</label>
              <input type={type} required={required}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                value={form[key]} onChange={e => setForm({...form, [key]: e.target.value})} />
            </div>
          ))}
          <button type="submit" disabled={loading}
            className="w-full bg-indigo-600 text-white py-2.5 rounded-lg font-medium hover:bg-indigo-700 disabled:opacity-50 transition-colors mt-2">
            {loading ? 'Creating account…' : 'Create Account'}
          </button>
        </form>
        <p className="mt-4 text-center text-sm text-gray-500">
          Already have an account? <Link to="/login" className="text-indigo-600 hover:underline font-medium">Sign in</Link>
        </p>
      </div>
    </div>
  )
}
