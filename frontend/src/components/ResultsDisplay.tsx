import React from 'react';

interface ProcessingResult {
  documentId: string;
  fileName: string;
  status: string;
  ocrResults?: any;
  classification?: any;
  summary?: any;
  uploadTime?: string;
}

interface ResultsDisplayProps {
  result: ProcessingResult;
  isProcessing: boolean;
}

const ResultsDisplay: React.FC<ResultsDisplayProps> = ({ result, isProcessing }) => {
  const getStatusMessage = () => {
    switch (result.status) {
      case 'uploaded':
        return 'Document uploaded successfully. Processing will begin shortly...';
      case 'processing_ocr':
        return 'Extracting text from document using OCR...';
      case 'processing_classification':
        return 'Classifying document type...';
      case 'processing_summarization':
        return 'Generating document summary...';
      case 'complete':
        return 'Processing complete!';
      case 'error':
        return 'An error occurred during processing.';
      default:
        return 'Processing...';
    }
  };

  const getProgressPercentage = () => {
    switch (result.status) {
      case 'uploaded':
        return 10;
      case 'processing_ocr':
        return 30;
      case 'processing_classification':
        return 60;
      case 'processing_summarization':
        return 80;
      case 'complete':
        return 100;
      default:
        return 0;
    }
  };

  return (
    <div className="results-container">
      <div className="document-info">
        <h2>Document: {result.fileName}</h2>
        <p><strong>Document ID:</strong> {result.documentId}</p>
        {result.uploadTime && (
          <p><strong>Uploaded:</strong> {new Date(result.uploadTime).toLocaleString()}</p>
        )}
      </div>

      <div className="processing-status">
        <h3>Processing Status</h3>
        <div className="status-message">
          {getStatusMessage()}
        </div>
        
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${getProgressPercentage()}%` }}
          ></div>
        </div>
        
        {isProcessing && (
          <div className="spinner">⏳ Processing...</div>
        )}
      </div>

      {result.ocrResults && (
        <div className="results-section">
          <h3>📄 OCR Results</h3>
          <div className="ocr-results">
            {result.ocrResults.rawText && (
              <div className="raw-text">
                <h4>Extracted Text:</h4>
                <pre className="text-content">{result.ocrResults.rawText}</pre>
              </div>
            )}
            
            {result.ocrResults.keyValuePairs && Object.keys(result.ocrResults.keyValuePairs).length > 0 && (
              <div className="key-value-pairs">
                <h4>Key-Value Pairs:</h4>
                <div className="kv-grid">
                  {Object.entries(result.ocrResults.keyValuePairs).map(([key, value]) => (
                    <div key={key} className="kv-pair">
                      <span className="key">{key}:</span>
                      <span className="value">{value as string}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.ocrResults.markdownJson && (
              <div className="markdown-json">
                <h4>Structured Data:</h4>
                <pre className="json-content">
                  {JSON.stringify(result.ocrResults.markdownJson, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}

      {result.classification && (
        <div className="results-section">
          <h3>🏷️ Document Classification</h3>
          <div className="classification-results">
            <div className="classification-item">
              <span className="label">Category:</span>
              <span className="category">{result.classification.category}</span>
            </div>
            <div className="classification-item">
              <span className="label">Confidence:</span>
              <span className="confidence">
                {(result.classification.confidence * 100).toFixed(1)}%
              </span>
            </div>
            {result.classification.reason && (
              <div className="classification-item">
                <span className="label">Reason:</span>
                <span className="reason">{result.classification.reason}</span>
              </div>
            )}
          </div>
        </div>
      )}

      {result.summary && (
        <div className="results-section">
          <h3>📝 Document Summary</h3>
          <div className="summary-results">
            {result.summary.text && (
              <div className="summary-text">
                <h4>Summary:</h4>
                <p>{result.summary.text}</p>
              </div>
            )}
            
            {result.summary.keyPoints && result.summary.keyPoints.length > 0 && (
              <div className="key-points">
                <h4>Key Points:</h4>
                <ul>
                  {result.summary.keyPoints.map((point: string, index: number) => (
                    <li key={index}>{point}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};

export default ResultsDisplay;
