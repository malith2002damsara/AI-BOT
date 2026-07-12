import { useState, useEffect } from 'react'
import { getPdfs, loadPdf, deletePdf } from '../api'

function PdfList({ onPdfLoaded, isConnected, language }) {
  const [pdfs, setPdfs] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [loadStatus, setLoadStatus] = useState({})

  useEffect(() => {
    // Define fetch function inside useEffect
    const fetchPdfs = async () => {
      if (!isConnected) return
      
      try {
        setError('')
        const data = await getPdfs()
        setPdfs(data.pdfs || [])
      } catch (error) {
        console.error('Error fetching PDFs:', error)
        setError(error.message || 'Failed to fetch PDFs')
      }
    }

    // Call the function
    fetchPdfs()
  }, [isConnected]) // Only re-run when isConnected changes

  // Define fetchPdfs as a separate function for reuse
  const refreshPdfs = async () => {
    if (!isConnected) return
    
    try {
      setError('')
      const data = await getPdfs()
      setPdfs(data.pdfs || [])
    } catch (error) {
      console.error('Error fetching PDFs:', error)
      setError(error.message || 'Failed to fetch PDFs')
    }
  }

  const handleLoadPdf = async (publicId) => {
    try {
      setLoading(true)
      setLoadStatus(prev => ({ ...prev, [publicId]: 'loading' }))
      
      const result = await loadPdf(publicId)
      console.log('Load result:', result)
      
      if (onPdfLoaded) {
        onPdfLoaded()
      }
      
      setLoadStatus(prev => ({ ...prev, [publicId]: 'success' }))
      
      // Show success message
      const message = language === 'sinhala' 
        ? 'PDF එක සාර්ථකව load කරන ලදී'
        : 'PDF loaded successfully'
      alert(message)
      
      // Clear status after 3 seconds
      setTimeout(() => {
        setLoadStatus(prev => ({ ...prev, [publicId]: undefined }))
      }, 3000)
      
    } catch (error) {
      console.error('Error loading PDF:', error)
      setLoadStatus(prev => ({ ...prev, [publicId]: 'error' }))
      
      const errorMsg = language === 'sinhala'
        ? 'PDF එක load කිරීමට අසමත් විය'
        : 'Failed to load PDF'
      alert(errorMsg + ': ' + error.message)
      
      setTimeout(() => {
        setLoadStatus(prev => ({ ...prev, [publicId]: undefined }))
      }, 3000)
    } finally {
      setLoading(false)
    }
  }

  const handleDeletePdf = async (publicId) => {
    const confirmMsg = language === 'sinhala'
      ? 'මෙම PDF එක මකා දැමීමට ඔබට අවශ්‍යද?'
      : 'Are you sure you want to delete this PDF?'
    
    if (!window.confirm(confirmMsg)) return

    try {
      setLoading(true)
      await deletePdf(publicId)
      // Refresh the list
      await refreshPdfs()
      
      const message = language === 'sinhala'
        ? 'PDF එක සාර්ථකව මකා දමන ලදී'
        : 'PDF deleted successfully'
      alert(message)
      
    } catch (error) {
      console.error('Error deleting PDF:', error)
      const errorMsg = language === 'sinhala'
        ? 'PDF එක මකා දැමීමට අසමත් විය'
        : 'Failed to delete PDF'
      alert(errorMsg + ': ' + error.message)
    } finally {
      setLoading(false)
    }
  }

  if (!isConnected) {
    return (
      <div className="pdf-list">
        <div className="pdf-list-header">
          <h3>{language === 'sinhala' ? '📄 PDF ලිස්ට් එක' : '📄 PDF List'}</h3>
        </div>
        <div className="pdf-list-empty">
          {language === 'sinhala' 
            ? 'Backend එකට සම්බන්ධ වී නැත'
            : 'Not connected to backend'}
        </div>
      </div>
    )
  }

  return (
    <div className="pdf-list">
      <div className="pdf-list-header">
        <h3>{language === 'sinhala' ? '📄 PDF ලිස්ට් එක' : '📄 PDF List'}</h3>
        <span className="pdf-count">{pdfs.length} {language === 'sinhala' ? 'PDF' : 'PDFs'}</span>
      </div>
      
      {loading && (
        <div className="pdf-list-loading">
          {language === 'sinhala' ? 'පූරණය වෙමින්...' : 'Loading...'}
        </div>
      )}

      {error && (
        <div className="pdf-list-error">{error}</div>
      )}

      {pdfs.length === 0 && !loading && (
        <div className="pdf-list-empty">
          {language === 'sinhala' 
            ? 'PDF කිසිවක් upload කර නැත'
            : 'No PDFs uploaded yet'}
        </div>
      )}

      <div className="pdf-list-items">
        {pdfs.map((pdf) => {
          const status = loadStatus[pdf.public_id]
          return (
            <div key={pdf.id || pdf.public_id} className="pdf-item">
              <div className="pdf-item-info">
                <span className="pdf-item-name">📄 {pdf.name}</span>
                <span className="pdf-item-date">
                  {pdf.uploaded_at ? new Date(pdf.uploaded_at).toLocaleDateString() : ''}
                </span>
                {status === 'success' && (
                  <span className="pdf-item-status success">✅ {language === 'sinhala' ? 'Load කරන ලදී' : 'Loaded'}</span>
                )}
                {status === 'error' && (
                  <span className="pdf-item-status error">❌ {language === 'sinhala' ? 'අසමත් විය' : 'Failed'}</span>
                )}
              </div>
              <div className="pdf-item-actions">
                <button 
                  className={`pdf-btn load-btn ${status === 'loading' ? 'loading' : ''}`}
                  onClick={() => handleLoadPdf(pdf.public_id)}
                  disabled={loading || status === 'loading'}
                  title={language === 'sinhala' ? 'Load PDF' : 'Load PDF'}
                >
                  {status === 'loading' ? '⏳' : '📂'}
                </button>
                <button 
                  className="pdf-btn delete-btn"
                  onClick={() => handleDeletePdf(pdf.public_id)}
                  disabled={loading}
                  title={language === 'sinhala' ? 'Delete PDF' : 'Delete PDF'}
                >
                  🗑️
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

export default PdfList