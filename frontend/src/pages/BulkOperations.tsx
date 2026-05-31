import React, { useState } from 'react';
import axios from 'axios';
import { UploadCloud, Download, AlertTriangle, CheckCircle, FileSpreadsheet } from 'lucide-react';
import './BulkOperations.css';

const BULK_TYPES = [
  "Bulk Payments",
  "Bulk Invoices (Tuition)",
  "Bulk Other Fees",
  "Credit Hours Adjustments",
  "Update Student Rates",
  "General Adjustments",
];

export default function BulkOperations() {
  const [bType, setBType] = useState(BULK_TYPES[0]);
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [errorMsg, setErrorMsg] = useState('');

  const handleDownloadTemplate = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/bulk/template/${encodeURIComponent(bType)}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Tpl_${bType.replace(/ /g, '_')}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (err) {
      console.error(err);
      alert('Failed to download template.');
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setLoading(true);
    setErrorMsg('');
    setResult(null);

    const formData = new FormData();
    formData.append('b_type', bType);
    formData.append('file', file);

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/bulk/upload`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data' 
        }
      });
      setResult(response.data);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'An error occurred during upload.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="bulk-page">
      <div className="page-header">
        <h1><FileSpreadsheet size={28} style={{ marginRight: '10px' }} /> Bulk Financial Operations</h1>
        <p>Process hundreds of transactions simultaneously using Excel templates.</p>
      </div>

      <div className="bulk-container glass-panel">
        <div className="bulk-form-section">
          <h3>1. Select Operation Type</h3>
          <div className="type-selector">
            {BULK_TYPES.map(type => (
              <label key={type} className={`type-radio ${bType === type ? 'active' : ''}`}>
                <input 
                  type="radio" 
                  name="bulkType" 
                  value={type} 
                  checked={bType === type}
                  onChange={(e) => setBType(e.target.value)} 
                />
                {type}
              </label>
            ))}
          </div>

          <div className="template-download">
            <p><strong>Note:</strong> Delete the example row (ID: 0) before uploading.</p>
            <button onClick={handleDownloadTemplate} className="btn-secondary">
              <Download size={16} /> Download Template
            </button>
          </div>

          <h3>2. Upload Excel File</h3>
          <form onSubmit={handleUpload} className="upload-form">
            <div className="file-input-wrapper">
              <input 
                type="file" 
                accept=".xlsx" 
                onChange={(e) => setFile(e.target.files ? e.target.files[0] : null)} 
                className="file-input"
                id="bulk-file"
              />
              <label htmlFor="bulk-file" className="file-label">
                <UploadCloud size={24} />
                <span>{file ? file.name : "Click to select or drag and drop .xlsx file"}</span>
              </label>
            </div>

            <button type="submit" className="btn-primary bulk-submit" disabled={!file || loading}>
              {loading ? <div className="spinner-small"></div> : <CheckCircle size={18} />} 
              Confirm & Run Batch
            </button>
          </form>

          {errorMsg && (
            <div className="error-banner">
              <AlertTriangle size={20} />
              <span>{errorMsg}</span>
            </div>
          )}
        </div>
      </div>

      {result && (
        <div className="bulk-results glass-panel animate-fade-in">
          <h3>Batch Results (ID: {result.batch_id})</h3>
          
          <div className="result-stats">
            <div className="stat-card success">
              <div className="stat-label">Successfully Processed</div>
              <div className="stat-value">{result.success_count}</div>
            </div>
            <div className={`stat-card ${result.failed_count > 0 ? 'error' : 'neutral'}`}>
              <div className="stat-label">Failed / Skipped</div>
              <div className="stat-value">{result.failed_count}</div>
            </div>
          </div>

          {result.failed_count > 0 && (
            <div className="failed-rows">
              <h4>⚠️ Failed Rows</h4>
              <div className="table-responsive">
                <table className="modern-table">
                  <thead>
                    <tr>
                      <th>ID</th>
                      <th>Error Reason</th>
                      {/* Dynamically show keys from the first failed row excluding ID/Error */}
                      {Object.keys(result.failed_rows[0] || {})
                        .filter(k => k !== 'ID' && k !== 'Error Reason')
                        .slice(0, 5)
                        .map(k => <th key={k}>{k}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {result.failed_rows.map((row: any, idx: number) => (
                      <tr key={idx}>
                        <td>{row.ID}</td>
                        <td style={{color: '#e74c3c', fontWeight: 'bold'}}>{row['Error Reason']}</td>
                        {Object.keys(result.failed_rows[0] || {})
                        .filter(k => k !== 'ID' && k !== 'Error Reason')
                        .slice(0, 5)
                        .map(k => <td key={k}>{String(row[k])}</td>)}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
