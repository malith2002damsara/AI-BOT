import { useState, useRef } from "react";
import { uploadPdf } from "../api";

function PdfUpload({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [status, setStatus] = useState("");
  const [statusType, setStatusType] = useState("");

  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      setStatusType("error");
      setStatus("❌ Please select a PDF file.");
      return;
    }

    setFileName(file.name);
    setUploading(true);
    setStatusType("info");
    setStatus("⏳ Uploading PDF...");

    try {
      const res = await uploadPdf(file);
      console.log("Upload Response:", res);

      setStatusType("success");
      setStatus("✅ PDF uploaded successfully.");

      if (onUploadSuccess) {
        onUploadSuccess(res);
      }
    } catch (error) {
      console.error("Upload error:", error);

      setStatusType("error");
      
      if (error.message.includes("Failed to fetch") || error.message.includes("connect")) {
        setStatus("❌ Cannot connect to backend server. Make sure the backend is running on port 8000.");
      } else if (error.response) {
        setStatus(`❌ Server Error (${error.response.status})`);
      } else {
        setStatus(`❌ ${error.message}`);
      }
    } finally {
      setUploading(false);

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  return (
    <div className="pdf-upload">
      <label className={`upload-btn ${uploading ? "disabled" : ""}`}>
        {uploading ? "Processing..." : "📄 Upload PDF"}

        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf"
          hidden
          disabled={uploading}
          onChange={handleFileChange}
        />
      </label>

      {fileName && <p className="file-name">{fileName}</p>}
      {status && (
        <p className={`status-msg ${statusType}`}>
          {status}
        </p>
      )}
    </div>
  );
}

export default PdfUpload;