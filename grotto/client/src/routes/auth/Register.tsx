import { useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { useAuth } from '@/context/AuthContext'
import './auth.css'

const STRENGTH_LABELS = ['Weak', 'Fair', 'Good', 'Strong']

function getPasswordStrength(pw: string): number {
  if (pw.length === 0) return 0
  let score = 0
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[A-Z]/.test(pw) && /[0-9]/.test(pw)) score++
  if (/[^A-Za-z0-9]/.test(pw)) score++
  return Math.min(score, 4)
}

export default function Register() {
  const { register } = useAuth()
  const navigate = useNavigate()

  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [usernameError, setUsernameError] = useState(false)
  const [emailError, setEmailError] = useState(false)
  const [passwordError, setPasswordError] = useState(false)
  const [usernameShake, setUsernameShake] = useState(false)
  const [emailShake, setEmailShake] = useState(false)
  const [passwordShake, setPasswordShake] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const strength = getPasswordStrength(password)

  function shake(setter: (v: boolean) => void) {
    setter(true)
    setTimeout(() => setter(false), 300)
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
    let valid = true

    if (!username.trim()) {
      setUsernameError(true)
      shake(setUsernameShake)
      valid = false
    } else {
      setUsernameError(false)
    }

    if (!emailRe.test(email.trim())) {
      setEmailError(true)
      shake(setEmailShake)
      valid = false
    } else {
      setEmailError(false)
    }

    if (password.length < 8) {
      setPasswordError(true)
      shake(setPasswordShake)
      valid = false
    } else {
      setPasswordError(false)
    }

    if (!valid) return

    setError(null)
    setLoading(true)
    try {
      await register(email, username, password)
      navigate('/', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Registration failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="auth-page">
    <div className="auth-root">
      {/* Left panel */}
      <div className="auth-left">
        <div className="auth-left-top">
          <div className="auth-wordmark">
            <div className="auth-wordmark-icon">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect x="1" y="10" width="3" height="5" rx="1" fill="rgba(255,255,255,0.55)" />
                <rect x="6" y="6" width="3" height="9" rx="1" fill="rgba(255,255,255,0.7)" />
                <rect x="11" y="2" width="3" height="13" rx="1" fill="rgba(255,255,255,0.9)" />
              </svg>
            </div>
            <span className="auth-wordmark-name">Grotto</span>
          </div>
          <div className="auth-hero">
            <h1 className="auth-hero-heading">
              Everything you<br />need to manage<br /><em>your library.</em>
            </h1>
            <p className="auth-hero-sub">
              Connect your sources, queue up requests, and keep your library
              organized — all in one private workspace.
            </p>
          </div>
        </div>

        <div className="auth-feature-list">
          {[
            { title: 'Unified search', desc: 'Search movies, shows, and anime across every connected source.' },
            { title: 'Automated downloads', desc: 'Requests route straight to your Sonarr and Radarr instances.' },
            { title: 'One dashboard', desc: 'Track everything in your library from a single place.' },
          ].map(({ title, desc }) => (
            <div className="auth-feature-item" key={title}>
              <div className="auth-feature-dot" />
              <div>
                <p className="auth-feature-title">{title}</p>
                <p className="auth-feature-desc">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Right panel */}
      <div className="auth-right">
        <p className="auth-form-eyebrow">Create your account</p>
        <h2 className="auth-form-title">Start building your<br />library</h2>

        {error && <p className="auth-api-error">{error}</p>}

        <form onSubmit={handleSubmit} noValidate>
          <div className="auth-form-group">
            <label className="auth-form-label">Username</label>
            <input
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoComplete="username"
              placeholder="johndoe"
              className={`auth-form-input${usernameError ? ' error' : ''}${usernameShake ? ' auth-shake' : ''}`}
            />
            {usernameError && <p className="auth-field-error">Required.</p>}
          </div>

          <div className="auth-form-group">
            <label className="auth-form-label">Email address</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              autoComplete="email"
              placeholder="you@example.com"
              className={`auth-form-input${emailError ? ' error' : ''}${emailShake ? ' auth-shake' : ''}`}
            />
            {emailError && (
              <p className="auth-field-error">Please enter a valid email address.</p>
            )}
          </div>

          <div className="auth-form-group">
            <label className="auth-form-label">Password</label>
            <div className="auth-input-wrap">
              <input
                type={showPassword ? 'text' : 'password'}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="new-password"
                placeholder="••••••••••"
                className={`auth-form-input${passwordError ? ' error' : ''}${passwordShake ? ' auth-shake' : ''}`}
              />
              <span
                className="auth-input-suffix"
                onClick={() => setShowPassword((v) => !v)}
              >
                {showPassword ? 'hide' : 'show'}
              </span>
            </div>
            <div
              className="auth-strength-bar"
              data-strength={password.length > 0 ? strength : 0}
            >
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="auth-strength-segment" />
              ))}
            </div>
            {password.length > 0 && (
              <div className="auth-strength-label" data-strength={strength}>
                {STRENGTH_LABELS[strength - 1]}
              </div>
            )}
            {passwordError && (
              <p className="auth-field-error">Password must be at least 8 characters.</p>
            )}
          </div>

          <button type="submit" disabled={loading} className="auth-submit-btn">
            {loading ? 'Creating account…' : 'Create account'}
            {!loading && (
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M2 7h10M8 3l4 4-4 4"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            )}
          </button>
        </form>

        <div className="auth-bottom-row">
          <span className="auth-bottom-text">Already have an account? </span>
          <Link to="/login" className="auth-bottom-link">Sign in</Link>
        </div>
      </div>
    </div>
    </div>
  )
}
