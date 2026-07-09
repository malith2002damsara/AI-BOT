import { useState, useRef } from 'react'
import { uploadPdf } from '../api'

function PdfUpload({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false)
  const [fileName, setFileName] = useState('')
  const [status, setStatus] = useState('')
  const fileInputRef = useRef(null)

  const handleFileChange = async (e) => {
    const file = e.target.files[0]
    if (!file) return

    if (file.type !== 'application/pdf') {
      setStatus('❌ PDF file එකක් විතරක් upload කරන්න')
      return
    }

    setFileName(file.name)
    setUploading(true)
    setStatus('⏳ Uploading & processing...')

    try {
      await uploadPdf(file)
      setStatus('✅ PDF එක සාර්ථකව process කරා. දැන් chat කරන්න පුළුවන්!')
      onUploadSuccess()
    } catch (err) {
      setStatus('❌ Upload එක fail උනා: ' + err.message)
    } finally {
      setUploading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  return (
    <div className="pdf-upload">
      <label className={`upload-btn ${uploading ? 'disabled' : ''}`}>
        {uploading ? 'Processing...' : '📄 PDF එකක් Upload කරන්න'}
        <input
          type="file"
          accept="application/pdf"
          onChange={handleFileChange}
          disabled={uploading}
          ref={fileInputRef}
          hidden
        />
      </label>
      {fileName && <p className="file-name">{fileName}</p>}
      {status && <p className="status-msg">{status}</p>}
    </div>
  )
}

export default PdfUpload