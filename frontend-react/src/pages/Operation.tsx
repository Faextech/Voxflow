import { useEffect, useState } from 'react'

/**
 * Call Hub — embeds the legacy CRM iframe.
 * Uses vanilla CSS classes from index.css (no Tailwind).
 */
export default function Operation() {
  const [height, setHeight] = useState('calc(100vh - 120px)')

  useEffect(() => {
    const handleResize = () => setHeight('calc(100vh - 120px)')
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div style={{ width: '100%', height, padding: 0, margin: 0, overflow: 'hidden' }}>
      <iframe
        src="/legacy/crm"
        style={{ width: '100%', height: '100%', border: 'none', borderRadius: '12px' }}
        title="CRM Pipeline"
      />
    </div>
  )
}
