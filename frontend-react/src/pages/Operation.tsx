import { useEffect, useState } from 'react'
import { Card } from '@/components/ui/Card'

export default function Operation() {
  const [height, setHeight] = useState('calc(100vh - 120px)')

  // Ajusta o height para remover barras de rolagem desnecessárias
  useEffect(() => {
    const handleResize = () => setHeight(`calc(100vh - 120px)`)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  return (
    <div className="w-full h-full p-0 m-0 overflow-hidden" style={{ height }}>
      <iframe 
        src="/legacy/crm" 
        className="w-full h-full border-0 rounded-lg shadow-sm"
        title="CRM Pipeline"
      />
    </div>
  )
}
