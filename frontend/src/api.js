const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

export async function uploadPdf(file) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    console.log('Uploading to:', `${API_URL}/upload`)
    
    const res = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      body: formData,
      // Don't set Content-Type header - let browser set it with boundary
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const error = new Error(err.detail || 'Upload failed')
      error.cause = { status: res.status, response: err }
      throw error
    }

    return await res.json()
  } catch (error) {
    console.error('Upload error:', error)
    
    // If it's already an error with cause, rethrow it
    if (error.cause) {
      throw error
    }
    
    // Otherwise create a new error with cause
    const newError = new Error(
      error.message || 'Failed to connect to server. Make sure the backend is running on port 8000.'
    )
    newError.cause = error
    throw newError
  }
}

export async function sendMessage(message, language = 'sinhala') {
  try {
    console.log('Sending message to:', `${API_URL}/chat`)
    
    const res = await fetch(`${API_URL}/chat`, {
      method: 'POST',
      headers: { 
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({ message, language }),
    })

    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      const error = new Error(err.detail || 'Chat request failed')
      error.cause = { status: res.status, response: err }
      throw error
    }

    return await res.json()
  } catch (error) {
    console.error('Chat error:', error)
    
    // If it's already an error with cause, rethrow it
    if (error.cause) {
      throw error
    }
    
    // Otherwise create a new error with cause
    const newError = new Error(
      error.message || 'Failed to connect to server. Make sure the backend is running on port 8000.'
    )
    newError.cause = error
    throw newError
  }
}

// Test function to check if backend is accessible
export async function testConnection() {
  try {
    const res = await fetch(`${API_URL}/`)
    if (!res.ok) {
      const error = new Error(`Connection failed with status: ${res.status}`)
      error.cause = { status: res.status }
      throw error
    }
    return await res.json()
  } catch (error) {
    console.error('Connection test failed:', error)
    
    const newError = new Error(
      error.message || 'Cannot connect to backend. Please make sure the server is running on port 8000.'
    )
    newError.cause = error
    throw newError
  }
}