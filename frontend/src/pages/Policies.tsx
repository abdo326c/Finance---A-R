import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FileText, Download, Trash2, Eye, Upload, AlertTriangle, CheckCircle2 } from 'lucide-react';
import './Policies.css';

interface PolicyDoc {
  id: number;
  title: string;
  academic_year: string;
  file_name: string;
  uploaded_by: string;
  uploaded_at: string;
}

export default function Policies() {
  const [docs, setDocs] = useState<PolicyDoc[]>([]);
  const [years, setYears] = useState<string[]>([]);
  const [selectedYear, setSelectedYear] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [isAdmin, setIsAdmin] = useState(false);
  
  const [viewingDoc, setViewingDoc] = useState<PolicyDoc | null>(null);

  // Upload state
  const [uploadTitle, setUploadTitle] = useState('');
  const [uploadYear, setUploadYear] = useState('');
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [flash, setFlash] = useState<{msg: string, type: 'success'|'error'} | null>(null);

  useEffect(() => {
    // Decode JWT to check role (naive check for UI purposes, backend still enforces security)
    try {
      const token = localStorage.getItem('token');
      if (token) {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.role === 'Admin') setIsAdmin(true);
      }
    } catch (e) {}
    
    fetchYears();
  }, []);

  const fetchYears = async () => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/policies/years', {
        headers: { Authorization: `Bearer ${token}` }
      });
      const fetchedYears = res.data.length ? res.data : ["2024/2025"];
      setYears(fetchedYears);
      setSelectedYear(fetchedYears[0]);
    } catch (err) {
      console.error(err);
      setYears(["2024/2025"]);
      setSelectedYear("2024/2025");
    }
  };

  useEffect(() => {
    if (selectedYear) fetchDocs();
  }, [selectedYear]);

  const fetchDocs = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get('http://127.0.0.1:8000/api/policies', {
        params: { academic_year: selectedYear },
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocs(res.data);
    } catch (err) {
      console.error(err);
      setDocs([]);
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!uploadTitle || !uploadYear || !uploadFile) return;

    setUploading(true);
    const formData = new FormData();
    formData.append('title', uploadTitle);
    formData.append('academic_year', uploadYear);
    formData.append('file', uploadFile);

    try {
      const token = localStorage.getItem('token');
      await axios.post('http://127.0.0.1:8000/api/policies/upload', formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      setFlash({ msg: 'Document uploaded successfully!', type: 'success' });
      setUploadTitle('');
      setUploadFile(null);
      // If we uploaded to a new year, add it to the dropdown
      if (!years.includes(uploadYear)) {
        setYears(prev => [...prev, uploadYear].sort().reverse());
      }
      if (selectedYear === uploadYear) {
        fetchDocs();
      } else {
        setSelectedYear(uploadYear);
      }
    } catch (err: any) {
      setFlash({ msg: err.response?.data?.detail || 'Upload failed.', type: 'error' });
    } finally {
      setUploading(false);
      setTimeout(() => setFlash(null), 3000);
    }
  };

  const handleDelete = async (doc: PolicyDoc) => {
    if (!window.confirm(`Are you sure you want to delete '${doc.title}'?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.delete(`http://127.0.0.1:8000/api/policies/${doc.id}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setDocs(prev => prev.filter(d => d.id !== doc.id));
      if (viewingDoc?.id === doc.id) setViewingDoc(null);
    } catch (err) {
      alert("Failed to delete document.");
    }
  };

  const getDownloadUrl = (id: number) => {
    const token = localStorage.getItem('token');
    // Using a direct URL might not send Auth header easily in an iframe, 
    // but we can fetch it as blob or just pass token in URL if backend supported it.
    // For now, since it's an authenticated API, we should fetch blob.
  };

  const handleDownload = async (doc: PolicyDoc) => {
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`http://127.0.0.1:8000/api/policies/${doc.id}/download`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', doc.file_name);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (err) {
      console.error(err);
      alert("Failed to download file.");
    }
  };

  const handleView = async (doc: PolicyDoc) => {
    setViewingDoc(doc);
  };

  return (
    <div className="policies-container">
      <header className="page-header">
        <h1 className="page-title"><FileText size={28} /> University Financial Policies</h1>
        <p className="page-subtitle">View and manage official scholarship policies, tuition guidelines, and procedural documents.</p>
      </header>

      {flash && (
        <div className={`flash-message ${flash.type} animate-fade-in`}>
          {flash.type === 'error' ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          <span>{flash.msg}</span>
        </div>
      )}

      <div className="policies-layout">
        {/* Left Column: List & Upload */}
        <div className="policies-sidebar">
          
          <div className="glass-panel policies-card">
            <div className="card-header">
              <h3>Browse Documents</h3>
            </div>
            <div className="card-body">
              <div className="form-group mb-4">
                <label>Academic Year</label>
                <select value={selectedYear} onChange={e => setSelectedYear(e.target.value)}>
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>

              {loading ? (
                <div className="spinner-small" style={{ margin: '20px auto' }}></div>
              ) : docs.length === 0 ? (
                <div className="empty-state-small">
                  <FileText size={24} style={{ opacity: 0.5, marginBottom: '8px' }} />
                  <p>No documents found for this year.</p>
                </div>
              ) : (
                <div className="doc-list">
                  {docs.map(doc => (
                    <div key={doc.id} className={`doc-item ${viewingDoc?.id === doc.id ? 'active' : ''}`}>
                      <div className="doc-info" onClick={() => handleView(doc)}>
                        <h4>{doc.title}</h4>
                        <span>Uploaded {new Date(doc.uploaded_at).toLocaleDateString()}</span>
                      </div>
                      <div className="doc-actions">
                        <button className="btn-icon" onClick={() => handleDownload(doc)} title="Download">
                          <Download size={16} />
                        </button>
                        {isAdmin && (
                          <button className="btn-icon text-danger" onClick={() => handleDelete(doc)} title="Delete">
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {isAdmin && (
            <div className="glass-panel policies-card mt-4">
              <div className="card-header">
                <h3>Upload New Document</h3>
              </div>
              <div className="card-body">
                <form onSubmit={handleUpload} className="upload-form">
                  <div className="form-group">
                    <label>Document Title</label>
                    <input 
                      type="text" 
                      required 
                      placeholder="e.g. 2025 Scholarship Policy" 
                      value={uploadTitle}
                      onChange={e => setUploadTitle(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Academic Year</label>
                    <input 
                      type="text" 
                      required 
                      placeholder="e.g. 2024/2025" 
                      value={uploadYear}
                      onChange={e => setUploadYear(e.target.value)}
                    />
                  </div>
                  <div className="form-group">
                    <label>Select PDF File</label>
                    <input 
                      type="file" 
                      accept=".pdf" 
                      required 
                      onChange={e => setUploadFile(e.target.files?.[0] || null)}
                      style={{ padding: '8px 0' }}
                    />
                  </div>
                  <button type="submit" className="btn-primary w-100 mt-2" disabled={uploading}>
                    {uploading ? <div className="spinner-small"></div> : <Upload size={18} />}
                    Upload Document
                  </button>
                </form>
              </div>
            </div>
          )}

        </div>

        {/* Right Column: PDF Viewer */}
        <div className="policies-main glass-panel">
          {viewingDoc ? (
            <div className="pdf-viewer-wrapper">
              <div className="pdf-header">
                <h3>{viewingDoc.title}</h3>
                <button className="btn-secondary" onClick={() => setViewingDoc(null)}>Close Viewer</button>
              </div>
              <div className="pdf-content">
                {/* Since we need auth, we can't just use an iframe src=url. 
                    We can fetch it as blob, then create object URL for iframe */}
                <PdfIframe doc={viewingDoc} />
              </div>
            </div>
          ) : (
            <div className="empty-viewer">
              <Eye size={48} style={{ opacity: 0.2, marginBottom: '16px' }} />
              <h3>Select a document to view</h3>
              <p>Click on any document from the list to preview it here.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Subcomponent to handle fetching blob and rendering iframe securely
function PdfIframe({ doc }: { doc: PolicyDoc }) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let url = '';
    const fetchBlob = async () => {
      setLoading(true);
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get(`http://127.0.0.1:8000/api/policies/${doc.id}/download`, {
          headers: { Authorization: `Bearer ${token}` },
          responseType: 'blob'
        });
        url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
        setBlobUrl(url);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchBlob();
    return () => {
      if (url) window.URL.revokeObjectURL(url);
    };
  }, [doc.id]);

  if (loading) return <div className="spinner-large" style={{ margin: 'auto' }}></div>;
  if (!blobUrl) return <div className="error-state">Failed to load PDF preview.</div>;

  return (
    <iframe src={blobUrl} className="pdf-iframe" title={doc.title} />
  );
}
