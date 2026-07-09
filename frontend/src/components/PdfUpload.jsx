import { useState, useRef } from "react";
import { uploadPdf } from "../api";

function PdfUpload({ onUploadSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [fileName, setFileName] = useState("");
  const [status, setStatus] = useState("");

  const fileInputRef = useRef(null);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];

    if (!file) return;

    if (file.type !== "application/pdf") {
      setStatus("❌ Please select a PDF file.");
      return;
    }

    setFileName(file.name);
    setUploading(true);
    setStatus("⏳ Uploading PDF...");

    try {
      const res = await uploadPdf(file);

      console.log("Upload Response:", res);

      setStatus("✅ PDF uploaded successfully.");

      if (onUploadSuccess) {
        onUploadSuccess(res);
      }
    } catch (error) {
      console.error(error);

      if (error.response) {
        setStatus(`❌ Server Error (${error.response.status})`);
      } else if (error.request) {
        setStatus("❌ Cannot connect to backend server.");
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

      {fileName && <p>{fileName}</p>}
      {status && <p>{status}</p>}
    </div>
  );
}

export default PdfUpload;