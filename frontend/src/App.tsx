import React, { useState } from 'react';
import './App.css';
import DocumentUpload from './components/DocumentUpload';
import ResultsDisplay from './components/ResultsDisplay';

interface ProcessingResult {
  documentId: string;
  fileName: string;
  status: string;
  ocrResults?: any;
  classification?: any;
  summary?: any;
  uploadTime?: string;
}

function App() {
  const [currentResult, setCurrentResult] = useState<ProcessingResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleUploadSuccess = (documentId: string, fileName: string) => {
    setCurrentResult({
      documentId,
      fileName,
      status: 'uploaded'
    });
    setIsProcessing(true);
    
    // Start polling for results
    pollForResults(documentId);
  };

  const pollForResults = async (documentId: string) => {
    const apiEndpoint = 'https://ev980vxfa4.execute-api.us-east-1.amazonaws.com/prod';
    const maxAttempts = 30; // 5 minutes with 10-second intervals
    let attempts = 0;

    const poll = async () => {
      try {
        const response = await fetch(`${apiEndpoint}/results/${documentId}`);
        const data = await response.json();

        if (response.ok) {
          setCurrentResult(data);
          
          if (data.status === 'complete' || data.status === 'error') {
            setIsProcessing(false);
            return;
          }
        }

        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 10000); // Poll every 10 seconds
        } else {
          setIsProcessing(false);
          console.error('Polling timeout');
        }
      } catch (error) {
        console.error('Error polling for results:', error);
        attempts++;
        if (attempts < maxAttempts) {
          setTimeout(poll, 10000);
        } else {
          setIsProcessing(false);
        }
      }
    };

    poll();
  };

  const handleNewUpload = () => {
    setCurrentResult(null);
    setIsProcessing(false);
  };

  return (
    <div className="App">
      <header className="App-header">
        <h1>Intelligent Document Processing</h1>
        <p>Upload documents for OCR, classification, and summarization</p>
      </header>

      <main className="App-main">
        {!currentResult ? (
          <DocumentUpload onUploadSuccess={handleUploadSuccess} />
        ) : (
          <div>
            <ResultsDisplay 
              result={currentResult} 
              isProcessing={isProcessing}
            />
            <button 
              onClick={handleNewUpload}
              className="new-upload-btn"
            >
              Upload Another Document
            </button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
