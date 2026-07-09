import { useState, useRef, useEffect } from 'react'
import { sendMessage } from '../api'

function ChatWindow({ pdfReady, language, onLanguageChange }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleSend = async () => {
    if (!input.trim() || loading) return

    const userMsg = { role: 'user', content: input.trim() }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    try {
      const data = await sendMessage(userMsg.content, language)
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }])
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: '❌ Error: ' + err.message },
      ])
    } finally {
      setLoading(false)
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const toggleLanguage = () => {
    const newLanguage = language === 'sinhala' ? 'english' : 'sinhala'
    onLanguageChange(newLanguage)
  }

  return (
    <div className="chat-window">
      <div className="chat-header">
        <div className="language-toggle">
          <button 
            className={`toggle-btn ${language === 'sinhala' ? 'active' : ''}`}
            onClick={toggleLanguage}
          >
            <span className="toggle-label">
              {language === 'sinhala' ? '🇱🇰 සිංහල' : '🇬🇧 English'}
            </span>
            <span className="toggle-switch">
              <span className={`toggle-slider ${language === 'english' ? 'active' : ''}`}></span>
            </span>
          </button>
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 && (
          <p className="empty-msg">
            {pdfReady
              ? language === 'sinhala' 
                ? 'ප්‍රශ්නයක් අහන්න...'
                : 'Ask a question...'
              : language === 'sinhala'
                ? 'PDF එකක් upload කරලා ඒක ගැන අහන්න, එහෙමත් නැත්නම් සාමාන්‍ය ප්‍රශ්නයක් අහන්න (Wikipedia)'
                : 'Upload a PDF and ask about it, or ask a general question (Wikipedia)'}
          </p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <span className="bubble">{msg.content}</span>
          </div>
        ))}
        {loading && (
          <div className="message assistant">
            <span className="bubble typing">
              {language === 'sinhala' ? 'ටයිප් කරමින්...' : 'Typing...'}
            </span>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="input-area">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={language === 'sinhala' ? 'Message එකක් type කරන්න...' : 'Type a message...'}
          rows={1}
        />
        <button onClick={handleSend} disabled={loading || !input.trim()}>
          {language === 'sinhala' ? 'Send' : 'Send'}
        </button>
      </div>
    </div>
  )
}

export default ChatWindow