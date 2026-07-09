import { useState } from 'react'
import PdfUpload from './components/PdfUpload'
import ChatWindow from './components/ChatWindow'

function App() {
  const [pdfReady, setPdfReady] = useState(false)

  return (
    <div className="app">
      <header className="app-header">
        <h1>🤖 RAG Agent Chat</h1>
        <p>PDF එකක් upload කරලා ඒ document එක ගැන අහන්න, එහෙමත් නැත්නම් Wikipedia වලින් general ප්‍රශ්න අහන්න</p>
      </header>

      <PdfUpload onUploadSuccess={() => setPdfReady(true)} />
      <ChatWindow pdfReady={pdfReady} />
    </div>
  )
}

export default App