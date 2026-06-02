import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { UserPlus, Upload, FileSpreadsheet, AlertTriangle, CheckCircle2 } from 'lucide-react';
import './Registration.css';

export default function Registration() {
  const [activeTab, setActiveTab] = useState<'manual'|'bulk'>('manual');
  const [flash, setFlash] = useState<{msg: string, type: 'success'|'error'} | null>(null);
  const [colleges, setColleges] = useState<string[]>([]);
  
  useEffect(() => {
    const fetchColleges = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setColleges(res.data.colleges || []);
      } catch (e) {
        console.error(e);
      }
    };
    fetchColleges();
  }, []);

  const showFlash = (msg: string, type: 'success'|'error') => {
    setFlash({ msg, type });
    setTimeout(() => setFlash(null), 5000);
  };

  return (
    <div className="registration-container">
      <header className="page-header">
        <h1 className="page-title"><UserPlus size={28} /> Student Registration</h1>
        <p className="page-subtitle">Register new students individually or via bulk Excel upload.</p>
      </header>

      {flash && (
        <div className={`flash-message ${flash.type} animate-fade-in`}>
          {flash.type === 'error' ? <AlertTriangle size={20} /> : <CheckCircle2 size={20} />}
          <span>{flash.msg}</span>
        </div>
      )}

      <div className="tabs-container">
        <button className={`tab-btn ${activeTab === 'manual' ? 'active' : ''}`} onClick={() => setActiveTab('manual')}>Manual Entry</button>
        <button className={`tab-btn ${activeTab === 'bulk' ? 'active' : ''}`} onClick={() => setActiveTab('bulk')}>Bulk Upload (Excel)</button>
      </div>

      <div className="tab-content glass-panel">
        {activeTab === 'manual' && <ManualEntryTab colleges={colleges} showFlash={showFlash} />}
        {activeTab === 'bulk' && <BulkUploadTab showFlash={showFlash} />}
      </div>
    </div>
  );
}

function ManualEntryTab({ colleges, showFlash }: { colleges: string[], showFlash: (m: string, t: 'success'|'error') => void }) {
  const [formData, setFormData] = useState({
    id: '',
    name: '',
    college: '',
    program: '',
    price_per_hr: '',
    email: '',
    mobile: '',
    national_id: '',
    nationality: 'Egyptian',
    birth_date: '',
    admit_year: new Date().getFullYear().toString()
  });
  const [submitting, setSubmitting] = useState(false);

  // Set default college once loaded
  useEffect(() => {
    if (colleges.length > 0 && !formData.college) {
      setFormData(prev => ({ ...prev, college: colleges[0] }));
    }
  }, [colleges, formData.college]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/registration`, {
        id: Number(formData.id),
        name: formData.name,
        college: formData.college,
        program: formData.program || null,
        price_per_hr: Number(formData.price_per_hr),
        email: formData.email || null,
        mobile: formData.mobile || null,
        national_id: formData.national_id || null,
        nationality: formData.nationality,
        birth_date: formData.birth_date || null,
        admit_year: Number(formData.admit_year)
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      showFlash(`Student ${formData.name} registered successfully!`, 'success');
      setFormData({
        id: '', name: '', college: colleges[0] || '', program: '', price_per_hr: '',
        email: '', mobile: '', national_id: '', nationality: 'Egyptian', birth_date: '', admit_year: new Date().getFullYear().toString()
      });
    } catch (err: any) {
      showFlash(err.response?.data?.detail || 'Registration failed', 'error');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="manual-entry-tab">
      <form className="registration-form" onSubmit={handleSubmit}>
        <div className="form-row">
          <div className="form-group flex-1">
            <label>Student ID *</label>
            <input type="number" name="id" required placeholder="e.g. 26100123" value={formData.id} onChange={handleChange} />
          </div>
          <div className="form-group flex-2">
            <label>Full Name *</label>
            <input type="text" name="name" required value={formData.name} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>College *</label>
            <select name="college" required value={formData.college} onChange={handleChange}>
              <option value="">Select College</option>
              {colleges.map(c => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group flex-1">
            <label>Program</label>
            <input type="text" name="program" value={formData.program} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>Price / Credit Hour (EGP) *</label>
            <input type="number" name="price_per_hr" required min="0" step="100" value={formData.price_per_hr} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>University Email</label>
            <input type="email" name="email" value={formData.email} onChange={handleChange} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group flex-1">
            <label>Mobile</label>
            <input type="text" name="mobile" value={formData.mobile} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>National ID</label>
            <input type="text" name="national_id" value={formData.national_id} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>Nationality</label>
            <input type="text" name="nationality" value={formData.nationality} onChange={handleChange} />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group flex-1">
            <label>Birth Date</label>
            <input type="date" name="birth_date" value={formData.birth_date} onChange={handleChange} />
          </div>
          <div className="form-group flex-1">
            <label>Admit Year *</label>
            <input type="number" name="admit_year" required value={formData.admit_year} onChange={handleChange} />
          </div>
        </div>

        <div className="form-actions mt-4">
          <button type="submit" className="btn-primary" disabled={submitting}>
            {submitting ? <div className="spinner-small"></div> : <UserPlus size={18} />} Register Student
          </button>
        </div>
      </form>
    </div>
  );
}

const BULK_REG_TYPES = [
  "New Students Registration",
  "Bulk Academic Status",
  "Bulk Financial Status",
  "Bulk Siblings",
  "Bulk Sponsors"
];

function BulkUploadTab({ showFlash }: { showFlash: (m: string, t: 'success'|'error') => void }) {
  const [bType, setBType] = useState(BULK_REG_TYPES[0]);
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [failedRows, setFailedRows] = useState<any[]>([]);
  const [successCount, setSuccessCount] = useState<number | null>(null);

  const handleDownloadTemplate = async () => {
    if (bType === "New Students Registration") {
      // Generate dummy CSV template for student registration
      const headers = ["ID", "Name", "College", "Program", "Price Per Hr", "Email", "Mobile", "National ID", "Nationality", "Admit Year", "Birth Date"];
      const example = ["26100123", "Ahmed Ali", "ENG", "Computer Eng", "4600.0", "ahmed@nu.edu.eg", "01000000000", "29901010000000", "Egyptian", new Date().getFullYear().toString(), "2005-01-01"];
      
      const csv = [headers.join(','), example.map(x => `"${x}"`).join(',')].join('\n');
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "Template_Students.csv");
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } else {
      // Download from bulk templates endpoint
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
        showFlash('Failed to download template.', 'error');
      }
    }
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) return;

    setUploading(true);
    setFailedRows([]);
    setSuccessCount(null);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('token');
      
      if (bType === "New Students Registration") {
        const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/registration/bulk`, formData, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
        });
        showFlash(res.data.message, res.data.failed_count === 0 ? 'success' : 'error');
        if (res.data.failed_rows?.length > 0) setFailedRows(res.data.failed_rows);
        setSuccessCount(res.data.success_count || 0);
      } else {
        formData.append('b_type', bType);
        const res = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/bulk/upload`, formData, {
          headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'multipart/form-data' }
        });
        const success = res.data.success_count;
        const failed = res.data.failed_count;
        showFlash(`Batch complete: ${success} successful, ${failed} failed.`, failed === 0 ? 'success' : 'error');
        if (res.data.failed_rows?.length > 0) setFailedRows(res.data.failed_rows);
        setSuccessCount(success);
      }
      
      setFile(null);
    } catch (err: any) {
      showFlash(err.response?.data?.detail || 'Upload failed', 'error');
    } finally {
      setUploading(false);
    }
  };
  return (
    <div className="bulk-upload-tab">
      <div className="upload-container">
        
        <div className="type-selector mb-4" style={{ display: 'flex', flexWrap: 'wrap', gap: '12px', background: 'var(--surface-hover)', padding: '16px', borderRadius: '8px' }}>
          {BULK_REG_TYPES.map(type => (
            <label key={type} className={`type-radio ${bType === type ? 'active' : ''}`} style={{
              display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px', background: bType === type ? 'var(--primary-color)' : 'transparent', color: bType === type ? '#fff' : 'var(--text-primary)', borderRadius: '20px', cursor: 'pointer', border: '1px solid var(--border-color)'
            }}>
              <input 
                type="radio" 
                name="bulkRegType" 
                value={type} 
                checked={bType === type}
                onChange={(e) => setBType(e.target.value)} 
                style={{ display: 'none' }}
              />
              {type}
            </label>
          ))}
        </div>

        <div className="template-section mb-4">
          <p className="text-secondary mb-2">Download the template and fill it with data. Ensure codes match the system lookups exactly.</p>
          <button className="btn-secondary" onClick={handleDownloadTemplate}><FileSpreadsheet size={18} /> Download Template</button>
        </div>
        
        <form className="upload-form-box" onSubmit={handleUpload}>
          <div className="file-drop-area">
            <Upload size={48} className="upload-icon" />
            <h3>Select Excel File</h3>
            <p className="text-secondary">Supported format: .xlsx</p>
            <input 
              type="file" 
              accept=".xlsx, .xls" 
              className="file-input-overlay"
              onChange={e => setFile(e.target.files?.[0] || null)}
            />
            {file && <div className="selected-file mt-2 text-success">Selected: {file.name}</div>}
          </div>
          <button type="submit" className="btn-primary mt-4 w-100" disabled={!file || uploading}>
            {uploading ? <div className="spinner-small"></div> : 'Process Bulk Upload'}
          </button>
        </form>

        {failedRows.length > 0 && (
          <div className="failed-rows mt-4">
            <h4 className="text-danger mb-2">⚠️ {failedRows.length} rows failed to import:</h4>
            <div className="table-responsive">
              <table className="failed-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Name</th>
                    <th>Error Reason</th>
                  </tr>
                </thead>
                <tbody>
                  {failedRows.map((r, i) => (
                    <tr key={i}>
                      <td>{r.ID}</td>
                      <td>{r.Name}</td>
                      <td className="text-danger">{r["Error Reason"]}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
