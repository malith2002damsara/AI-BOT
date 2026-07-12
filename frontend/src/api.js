const API_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'

// Custom error class
class ApiError extends Error {
  constructor(message, options = {}) {
    super(message, options)
    this.name = 'ApiError'
    this.status = options.status || null
    this.response = options.response || null
  }
}

export async function uploadPdf(file) {
  const formData = new FormData()
  formData.append('file', file)

  try {
    console.log('Uploading to:', `${API_URL}/upload`)
    
    const res = await fetch(`${API_URL}/upload`, {
      method: 'POST',
      body: formData,
    })

    if (!res.ok) {
      let responseData = {}
      try {
        responseData = await res.json()
      } catch {
        responseData = { detail: res.statusText }
      }
      
      throw new ApiError(
        responseData.detail || 'Upload failed',
        { 
          cause: new Error(`HTTP ${res.status}`),
          status: res.status,
          response: responseData
        }
      )
    }

    return await res.json()
  } catch (error) {
    console.error('Upload error:', error)
    
    if (error instanceof ApiError) {
      throw error
    }
    
    throw new ApiError(
      error.message || 'Failed to connect to server. Make sure the backend is running on port 8000.',
      { cause: error }
    )
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
      let responseData = {}
      try {
        responseData = await res.json()
      } catch {
        responseData = { detail: res.statusText }
      }
      
      throw new ApiError(
        responseData.detail || 'Chat request failed',
        { 
          cause: new Error(`HTTP ${res.status}`),
          status: res.status,
          response: responseData
        }
      )
    }

    return await res.json()
  } catch (error) {
    console.error('Chat error:', error)
    
    if (error instanceof ApiError) {
      throw error
    }
    
    throw new ApiError(
      error.message || 'Failed to connect to server. Make sure the backend is running on port 8000.',
      { cause: error }
    )
  }
}

export async function getPdfs() {
  try {
    const res = await fetch(`${API_URL}/pdfs`)
    if (!res.ok) {
      throw new ApiError('Failed to fetch PDFs', { status: res.status })
    }
    const data = await res.json()
    return data
  } catch (error) {
    console.error('Get PDFs error:', error)
    throw error
  }
}

export async function loadPdf(publicId) {
  try {
    console.log('Loading PDF:', publicId)
    const res = await fetch(`${API_URL}/load-pdf/${publicId}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    if (!res.ok) {
      let errorData = {}
      try {
        errorData = await res.json()
      } catch {
        errorData = { detail: `HTTP ${res.status}: ${res.statusText}` }
      }
      throw new ApiError(
        errorData.detail || 'Failed to load PDF',
        { status: res.status, response: errorData }
      )
    }
    return await res.json()
  } catch (error) {
    console.error('Load PDF error:', error)
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(
      error.message || 'Failed to load PDF from server',
      { cause: error }
    )
  }
}

export async function deletePdf(publicId) {
  try {
    console.log('Deleting PDF:', publicId)
    const res = await fetch(`${API_URL}/pdf/${publicId}`, {
      method: 'DELETE',
    })
    if (!res.ok) {
      let errorData = {}
      try {
        errorData = await res.json()
      } catch {
        errorData = { detail: res.statusText }
      }
      throw new ApiError(
        errorData.detail || 'Failed to delete PDF',
        { status: res.status, response: errorData }
      )
    }
    return await res.json()
  } catch (error) {
    console.error('Delete PDF error:', error)
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(
      error.message || 'Failed to delete PDF from server',
      { cause: error }
    )
  }
}

export async function testConnection() {
  try {
    const res = await fetch(`${API_URL}/`)
    if (!res.ok) {
      throw new ApiError(`Connection failed with status: ${res.status}`, { status: res.status })
    }
    return await res.json()
  } catch (error) {
    console.error('Connection test failed:', error)
    
    if (error instanceof ApiError) {
      throw error
    }
    
    throw new ApiError(
      error.message || 'Cannot connect to backend. Please make sure the server is running on port 8000.',
      { cause: error }
    )
  }
}