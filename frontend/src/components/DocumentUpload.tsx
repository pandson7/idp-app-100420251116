import React, { useState } from 'react';

interface DocumentUploadProps {
  onUploadSuccess: (documentId: string, fileName: string) => void;
}

const DocumentUpload: React.FC<DocumentUploadProps> = ({ onUploadSuccess }) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleFileSelect = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) {
      // Validate file type
      const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'];
      if (!allowedTypes.includes(file.type)) {
        setError('Please select a valid image file (JPEG, PNG, GIF) or PDF');
        return;
      }

      // Validate file size (10MB limit)
      if (file.size > 10 * 1024 * 1024) {
        setError('File size must be less than 10MB');
        return;
      }

      setSelectedFile(file);
      setError(null);
    }
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select a file first');
      return;
    }

    setIsUploading(true);
    setError(null);

    try {
      const apiEndpoint = 'https://ev980vxfa4.execute-api.us-east-1.amazonaws.com/prod';
      
      // Step 1: Get presigned URL
      const uploadResponse = await fetch(`${apiEndpoint}/upload`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          fileName: selectedFile.name,
        }),
      });

      if (!uploadResponse.ok) {
        throw new Error('Failed to get upload URL');
      }

      const uploadData = await uploadResponse.json();
      const { documentId, uploadUrl } = uploadData;

      // Step 2: Upload file to S3
      const s3Response = await fetch(uploadUrl, {
        method: 'PUT',
        body: selectedFile,
        headers: {
          'Content-Type': selectedFile.type,
        },
      });

      if (!s3Response.ok) {
        throw new Error('Failed to upload file');
      }

      // Success!
      onUploadSuccess(documentId, selectedFile.name);
      setSelectedFile(null);
      
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed');
    } finally {
      setIsUploading(false);
    }
  };

  return (
    <div className="upload-container">
      <div className="upload-box">
        <h2>Upload Document</h2>
        
        <div className="file-input-container">
          <input
            type="file"
            id="file-input"
            accept="image/*,.pdf"
            onChange={handleFileSelect}
            disabled={isUploading}
          />
          <label htmlFor="file-input" className="file-input-label">
            {selectedFile ? selectedFile.name : 'Choose File'}
          </label>
        </div>

        {selectedFile && (
          <div className="file-info">
            <p><strong>File:</strong> {selectedFile.name}</p>
            <p><strong>Size:</strong> {(selectedFile.size / 1024 / 1024).toFixed(2)} MB</p>
            <p><strong>Type:</strong> {selectedFile.type}</p>
          </div>
        )}

        {error && (
          <div className="error-message">
            {error}
          </div>
        )}

        <button
          onClick={handleUpload}
          disabled={!selectedFile || isUploading}
          className="upload-btn"
        >
          {isUploading ? 'Uploading...' : 'Upload & Process'}
        </button>

        <div className="upload-info">
          <p>Supported formats: JPEG, PNG, GIF, PDF</p>
          <p>Maximum file size: 10MB</p>
        </div>
      </div>
    </div>
  );
};

export default DocumentUpload;
