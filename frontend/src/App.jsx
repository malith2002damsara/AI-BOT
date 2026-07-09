import { useState } from 'react'
import PdfUpload from './components/PdfUpload'
import ChatWindow from './components/ChatWindow'

function App() {
  const [pdfReady, setPdfReady] = useState(false)
  const [language, setLanguage] = useState('sinhala')

  const handleLanguageChange = (newLanguage) => {
    setLanguage(newLanguage)
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
      </header>

      <PdfUpload onUploadSuccess={() => setPdfReady(true)} />
      <ChatWindow 
        pdfReady={pdfReady} 
        language={language}
        onLanguageChange={handleLanguageChange}
      />
    </div>
  )
}

export default App