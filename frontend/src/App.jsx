import React, { useState, useEffect } from 'react'
import axios from 'axios'
import DashboardEmbed from './components/DashboardEmbed'
import './App.css'

/**
 * Main application component for AI/BI External Embedding (mTLS)
 *
 * Handles:
 * - Fetching dashboard configuration and OAuth tokens from backend
 * - Rendering the DashboardEmbed component with device-bound tokens
 */
const App = () => {
  const [loading, setLoading] = useState(true)
  const [errorInfo, setErrorInfo] = useState(null)
  const [errorDetails, setErrorDetails] = useState(null)
  const [dashboardConfig, setDashboardConfig] = useState(null)

  useEffect(() => {
    fetchDashboardConfig()
  }, [])

  /**
   * Fetch dashboard embedding configuration from backend
   * This includes the OAuth token minted for the mTLS-authenticated device
   * 
   * Makes direct HTTPS call to nginx (https://localhost:443) so browser
   * can present the client certificate during TLS handshake
   */
  const fetchDashboardConfig = async () => {
    setLoading(true)
    setErrorInfo(null)
    setErrorDetails(null)

    try {
      // Call backend API (same origin when served through nginx)
      const response = await axios.get('/api/dashboard/embed-config')
      setDashboardConfig(response.data)
    } catch (err) {
      console.error('Dashboard config error:', err)

      const errorString = [
        err?.name,
        err?.message,
        err?.code,
        err?.cause?.message,
        err?.cause,
        err?.toString?.(),
        String(err || '')
      ].join(' ')
      const isCertAuthorityError = /ERR_CERT_AUTHORITY_INVALID|CERT_AUTHORITY_INVALID/i.test(errorString)
      const isNetworkError = /Network Error/i.test(err?.message || '') || err?.code === 'ERR_NETWORK'
      const requestUrl = err?.config?.url || ''
      const responseUrl = err?.request?.responseURL || ''
      const isHttpsLocalhost = /^https:\/\/localhost(?::443)?\b/i.test(requestUrl)
        || /^https:\/\/localhost(?::443)?\b/i.test(responseUrl)
      const isLocalhostPage = typeof window !== 'undefined' && window.location?.hostname === 'localhost'
      const isNoResponse = !err?.response
      const isLikelyTlsHandshakeFailure = isNetworkError && (isHttpsLocalhost || isLocalhostPage)
      const isRequestStatusZero = err?.request?.status === 0

      setErrorDetails({
        message: err?.message,
        code: err?.code,
        name: err?.name,
        requestUrl,
        responseUrl
      })

      // Handle different error scenarios with helpful messages
      if (
        isCertAuthorityError
        || isLikelyTlsHandshakeFailure
        || (isNetworkError && isNoResponse && (isHttpsLocalhost || isLocalhostPage))
        || (isNetworkError && isRequestStatusZero && (isHttpsLocalhost || isLocalhostPage))
      ) {
        setErrorInfo({
          kind: 'cert-authority',
          message:
            'Certificate Authority not trusted. Import certs/ca.crt into your system keychain and set it to Always Trust, then restart your browser.'
        })
      } else if (err?.response?.status === 400 || err?.message?.includes('400')) {
        setErrorInfo({
          kind: 'missing-cert',
          message:
            'Bad Request: No required SSL certificate was sent. Please ensure you have installed and selected the client certificate (factory-tv-01.p12) in your browser.'
        })
      } else if (err?.response?.status === 401) {
        const errorData = err.response?.data
        const errorMessage = errorData?.error || 'mTLS client certificate is required to view this dashboard.'
        setErrorInfo({
          kind: 'mtls-auth',
          message: `Authentication Error: ${errorMessage}`
        })
      } else if (err?.response?.data?.error) {
        // Display backend error message if available
        setErrorInfo({
          kind: 'backend',
          message: `Error: ${err.response.data.error}`
        })
      } else if (err?.message) {
        setErrorInfo({
          kind: 'network',
          message: `Error: ${err.message}`
        })
      } else {
        setErrorInfo({
          kind: 'generic',
          message: 'Failed to load dashboard configuration. Please check your backend connection and credentials.'
        })
      }
    } finally {
      setLoading(false)
    }
  }

  if (loading && !dashboardConfig) {
    return (
      <div className="app">
        <div className="loading">Loading...</div>
      </div>
    )
  }

  return (
    <div className="app">
      <header className="header">
        <div className="header-content">
          <h1>AI/BI External Embedding (mTLS)</h1>
        </div>
      </header>

      <main className="dashboard-container">
        {errorInfo && (
          <div className="error">
            <h3>⚠️ Error</h3>
            <p>{errorInfo.message}</p>
            {(errorInfo.kind === 'cert-authority' || errorInfo.kind === 'missing-cert') && (
              <div className="error-help">
                <h4>How to fix:</h4>
                <ol>
                  <li>Generate the PKCS#12 certificate bundle:
                    <pre>openssl pkcs12 -export -in certs/factory-tv-01.crt -inkey certs/factory-tv-01.key -out certs/factory-tv-01.p12 -name "factory-tv-01"</pre>
                  </li>
                  <li>Install the certificate in your system keychain (macOS: double-click the .p12 file)</li>
                  <li>Trust the CA certificate (macOS): open <code>certs/ca.crt</code> and set Always Trust</li>
                  <li>Restart your browser</li>
                  <li>When accessing the site, select the "factory-tv-01" certificate when prompted</li>
                </ol>
              </div>
            )}
            {errorDetails && (
              <div className="error-help">
                <h4>Debug details:</h4>
                <pre>{JSON.stringify(errorDetails, null, 2)}</pre>
              </div>
            )}
            <button onClick={fetchDashboardConfig} className="retry-button">
              Retry
            </button>
          </div>
        )}

        {!errorInfo && dashboardConfig && (
          <div className="dashboard-info">
            <small>
              Viewing dashboard: {dashboardConfig.dashboard_id} | 
              Device context: {dashboardConfig.user_context.email} ({dashboardConfig.user_context.department})
            </small>
          </div>
        )}

        {!errorInfo && (
          <div className="dashboard-embed">
            <DashboardEmbed
              config={dashboardConfig}
              onError={(message) => setErrorInfo({ kind: 'generic', message })}
            />
          </div>
        )}
      </main>
    </div>
  )
}

export default App

