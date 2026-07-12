import { useState, useEffect } from 'react'
import PdfUpload from './components/PdfUpload'
import PdfList from './components/PdfList'
import ChatWindow from './components/ChatWindow'
import { testConnection } from './api'

function App() {
  const [pdfReady, setPdfReady] = useState(false)
  const [language, setLanguage] = useState('sinhala')
  const [isConnected, setIsConnected] = useState(false)
  const [connectionError, setConnectionError] = useState('')

  useEffect(() => {
    const checkConnection = async () => {
      try {
        const result = await testConnection()
        console.log('Backend connection successful:', result)
        setIsConnected(true)
        setConnectionError('')
        if (result.pdf_loaded) {
          setPdfReady(true)
        }
      } catch (error) {
        console.error('Backend connection failed:', error)
        setIsConnected(false)
        setConnectionError('Cannot connect to backend. Please make sure the server is running on port 8000.')
      }
    }

    checkConnection()
  }, [])

  const handleLanguageChange = (newLanguage) => {
    setLanguage(newLanguage)
  }

  const handlePdfLoaded = () => {
    setPdfReady(true)
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🤖 RAG Agent Chat</h1>
        <p>
          {language === 'sinhala' 
            ? 'PDF එකක් upload කරලා ඒ document එක ගැන අහන්න, එහෙමත් නැත්නම් Wikipedia වලින් general ප්‍රශ්න අහන්න'
            : 'Upload a PDF and ask questions about it, or ask general questions from Wikipedia'}
        </p>
        {!isConnected && (
          <div className="connection-error">
            ⚠️ {connectionError || 'Connecting to backend...'}
          </div>
        )}
        {isConnected && (
          <div className="connection-success">
            ✅ Connected to backend {pdfReady ? '📄 PDF loaded' : ''}
          </div>
        )}
      </header>

      <div className="main-container">
        <div className="left-panel">
          <PdfUpload 
            onUploadSuccess={handlePdfLoaded} 
            isConnected={isConnected}
            language={language}
          />
          <PdfList 
            onPdfLoaded={handlePdfLoaded}
            isConnected={isConnected}
            language={language}
          />
        </div>
        <div className="right-panel">
          <ChatWindow 
            pdfReady={pdfReady} 
            language={language}
            onLanguageChange={handleLanguageChange}
            isConnected={isConnected}
          />
        </div>
      </div>
    </div>
  )
}

export default App