import React, { useState } from 'react';
import axios from 'axios';
import Papa from 'papaparse';
import { UploadCloud, CheckCircle, AlertTriangle, Download } from 'lucide-react';
import * as XLSX from 'xlsx';

export default function PowerCampusSync() {
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Dynamic filter options extracted from CSV
  const [dynamicOptions, setDynamicOptions] = useState({
    terms: [] as string[],
    years: [] as string[],
    summaryTypes: [] as string[],
    chargeTypes: [] as string[],
    chargeCodes: [] as string[]
  });

  // Selected filters
  const [filters, setFilters] = useState({
    startDate: '',
    endDate: '',
    term: '',
    year: '',
    chargeType: '',
    summaryType: '',
    chargeCode: ''
  });

  // Preview data
  const [previewData, setPreviewData] = useState<any>(null);
  
  // Commit status
  const [commitStatus, setCommitStatus] = useState<any>(null);

  const handleFileDrop = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;
    
    setFile(selectedFile);
    setPreviewData(null);
    setCommitStatus(null);
    setFilters({ startDate: '', endDate: '', term: '', year: '', chargeType: '', summaryType: '', chargeCode: '' });

    // Parse CSV to extract unique values
    Papa.parse(selectedFile, {
      header: true,
      skipEmptyLines: true,
      complete: (results) => {
        const terms = new Set<string>();
        const years = new Set<string>();
        const sumTypes = new Set<string>();
        const chargeTypes = new Set<string>();
        const chargeCodes = new Set<string>();

        results.data.forEach((row: any) => {
          if (row.ACADEMIC_TERM) terms.add(row.ACADEMIC_TERM);
          if (row.ACADEMIC_YEAR) years.add(row.ACADEMIC_YEAR);
          if (row.SUMMARY_TYPE) sumTypes.add(row.SUMMARY_TYPE);
          if (row.CHARGE_CREDIT_TYPE) chargeTypes.add(row.CHARGE_CREDIT_TYPE);
          if (row.CHARGE_CREDIT_CODE) chargeCodes.add(row.CHARGE_CREDIT_CODE);
        });

        setDynamicOptions({
          terms: Array.from(terms).sort(),
          years: Array.from(years).sort(),
          summaryTypes: Array.from(sumTypes).sort(),
          chargeTypes: Array.from(chargeTypes).sort(),
          chargeCodes: Array.from(chargeCodes).sort()
        });
      }
    });
  };

  const handleFilterChange = (field: string, value: string) => {
    setFilters(prev => ({ ...prev, [field]: value }));
  };

  const generatePreview = async () => {
    if (!file) return;
    setLoading(true);
    setErrorMsg('');
    setPreviewData(null);
    setCommitStatus(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('filters', JSON.stringify(filters));

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/bulk/power-campus/preview`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data' 
        }
      });
      setPreviewData(response.data);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to generate preview.');
    } finally {
      setLoading(false);
    }
  };

  const exportAuditExcel = () => {
    if (!previewData) return;
    
    // Combine valid and skipped rows for the audit report
    const auditRows = [
      ...previewData.valid_rows.map((r: any) => ({
        Status: 'Ready',
        Error_Reason: '',
        ...r
      })),
      ...previewData.skipped_rows.map((r: any) => ({
        Status: 'Skipped',
        Error_Reason: r['Error Reason'],
        ...r
      }))
    ];

    const ws = XLSX.utils.json_to_sheet(auditRows);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Audit Preview");
    XLSX.writeFile(wb, `PC_Audit_Preview_${new Date().getTime()}.xlsx`);
  };

  const commitBatch = async () => {
    if (!previewData?.valid_rows?.length) return;
    if (!window.confirm(`Are you sure you want to post ${previewData.valid_rows.length} transactions to the database?`)) return;

    setLoading(true);
    setErrorMsg('');

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/bulk/power-campus/commit`, {
        rows: previewData.valid_rows
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setCommitStatus(response.data);
      setPreviewData(null);
      setFile(null);
    } catch (err: any) {
      setErrorMsg(err.response?.data?.detail || 'Failed to commit batch.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="power-campus-sync">
      <div className="glass-panel" style={{ padding: '20px', marginBottom: '20px' }}>
        <h3>1. Select File & Filters</h3>
        
        <div className="file-input-wrapper" style={{ margin: '20px 0' }}>
          <input 
            type="file" 
            accept=".csv" 
            onChange={handleFileDrop} 
            className="file-input"
            id="pc-file"
          />
          <label htmlFor="pc-file" className="file-label">
            <UploadCloud size={24} />
            <span>{file ? file.name : "Click to select Power Campus .csv export"}</span>
          </label>
        </div>

        {file && (
          <div className="filters-grid" style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '15px', marginTop: '20px' }}>
            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Term</label>
              <select value={filters.term} onChange={e => handleFilterChange('term', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}>
                <option value="">All Terms</option>
                {dynamicOptions.terms.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            
            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Year</label>
              <select value={filters.year} onChange={e => handleFilterChange('year', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}>
                <option value="">All Years</option>
                {dynamicOptions.years.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Summary Type</label>
              <select value={filters.summaryType} onChange={e => handleFilterChange('summaryType', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}>
                <option value="">All Summary Types</option>
                {dynamicOptions.summaryTypes.map(s => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Charge/Credit Type</label>
              <select value={filters.chargeType} onChange={e => handleFilterChange('chargeType', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}>
                <option value="">All Types</option>
                {dynamicOptions.chargeTypes.map(c => <option key={c} value={c}>{c === 'C' ? 'Charge (C)' : 'Credit (R)'}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Charge Code</label>
              <select value={filters.chargeCode} onChange={e => handleFilterChange('chargeCode', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }}>
                <option value="">All Codes</option>
                {dynamicOptions.chargeCodes.map(c => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>Start Date</label>
              <input type="date" value={filters.startDate} onChange={e => handleFilterChange('startDate', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }} />
            </div>

            <div className="form-group">
              <label style={{ display: 'block', marginBottom: '5px' }}>End Date</label>
              <input type="date" value={filters.endDate} onChange={e => handleFilterChange('endDate', e.target.value)} style={{ width: '100%', padding: '8px', borderRadius: '4px', border: '1px solid var(--border-color)', background: 'var(--surface-color)', color: 'var(--text-primary)' }} />
            </div>
          </div>
        )}

        <button 
          onClick={generatePreview} 
          disabled={!file || loading} 
          className="btn-secondary" 
          style={{ marginTop: '20px', width: '100%', padding: '12px' }}
        >
          {loading && !previewData && !commitStatus ? <div className="spinner-small" style={{display: 'inline-block', marginRight: '10px'}}></div> : null}
          {loading && !previewData && !commitStatus ? 'Parsing & Validating...' : 'Generate Audit Preview'}
        </button>

        {errorMsg && (
          <div className="error-alert" style={{ marginTop: '15px' }}>
            <AlertTriangle size={20} style={{marginRight: '10px', verticalAlign: 'middle'}}/>
            <span>{errorMsg}</span>
          </div>
        )}
      </div>

      {previewData && (
        <div className="glass-panel animate-fade-in" style={{ padding: '20px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3>2. Preview & Audit</h3>
            <button onClick={exportAuditExcel} className="btn-secondary" style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
              <Download size={16} /> Export Audit Excel
            </button>
          </div>

          <div style={{ display: 'flex', gap: '20px', marginBottom: '20px', flexWrap: 'wrap' }}>
            <div style={{ flex: '1 1 200px', padding: '15px', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
              <h4 style={{ color: '#059669', margin: 0 }}>Valid Rows</h4>
              <p style={{ fontSize: '24px', fontWeight: 'bold', margin: '5px 0 0 0', color: '#059669' }}>{previewData.valid_rows.length}</p>
            </div>
            <div style={{ flex: '1 1 200px', padding: '15px', background: 'rgba(239, 68, 68, 0.1)', borderRadius: '8px', border: '1px solid rgba(239, 68, 68, 0.2)' }}>
              <h4 style={{ color: '#dc2626', margin: 0 }}>Skipped / Errors</h4>
              <p style={{ fontSize: '24px', fontWeight: 'bold', margin: '5px 0 0 0', color: '#dc2626' }}>{previewData.skipped_rows.length}</p>
            </div>
            <div style={{ flex: '1 1 200px', padding: '15px', background: 'var(--surface-color)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
              <h4 style={{ margin: 0 }}>Total Evaluated</h4>
              <p style={{ fontSize: '24px', fontWeight: 'bold', margin: '5px 0 0 0' }}>{previewData.valid_rows.length + previewData.skipped_rows.length}</p>
            </div>
          </div>

          <div style={{ marginBottom: '20px', padding: '15px', background: 'var(--surface-color)', borderRadius: '8px', border: '1px solid var(--border-color)' }}>
            <h4 style={{margin: '0 0 10px 0'}}>Summary Type Counts</h4>
            <div style={{ display: 'flex', gap: '15px', flexWrap: 'wrap' }}>
              {Object.entries(previewData.summary_counts).map(([type, count]) => (
                <span key={type} style={{ padding: '6px 12px', background: 'var(--primary-transparent)', color: 'var(--primary-color)', borderRadius: '15px', fontSize: '0.85rem', fontWeight: 600 }}>
                  {type}: {String(count)}
                </span>
              ))}
            </div>
          </div>

          {previewData.skipped_rows.length > 0 && (
            <div style={{ marginBottom: '20px' }}>
              <h4 style={{ color: '#dc2626', marginBottom: '10px' }}>⚠️ Skipped Rows Example</h4>
              <div className="table-responsive" style={{ maxHeight: '250px', overflowY: 'auto' }}>
                <table className="modern-table">
                  <thead>
                    <tr>
                      <th>Row</th>
                      <th>Student ID</th>
                      <th>Error Reason</th>
                      <th>Summary Type</th>
                      <th>Amount</th>
                    </tr>
                  </thead>
                  <tbody>
                    {previewData.skipped_rows.slice(0, 10).map((r: any, idx: number) => (
                      <tr key={idx}>
                        <td>{idx + 1}</td>
                        <td>{r.PEOPLE_ORG_ID}</td>
                        <td style={{ color: '#dc2626', fontWeight: 600 }}>{r['Error Reason']}</td>
                        <td>{r.SUMMARY_TYPE}</td>
                        <td>{r.AMOUNT}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {previewData.skipped_rows.length > 10 && <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginTop: '8px' }}>Showing 10 of {previewData.skipped_rows.length} errors. Export Audit Excel to view all.</p>}
            </div>
          )}

          <button 
            onClick={commitBatch} 
            disabled={loading || previewData.valid_rows.length === 0} 
            className="btn-primary" 
            style={{ width: '100%', padding: '16px', fontSize: '1.1rem', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '10px' }}
          >
            {loading ? <div className="spinner-small"></div> : <CheckCircle size={22} />} 
            Confirm & Post {previewData.valid_rows.length} Transactions
          </button>
        </div>
      )}

      {commitStatus && (
        <div className="glass-panel animate-fade-in" style={{ padding: '40px', textAlign: 'center', marginTop: '20px' }}>
          <CheckCircle size={56} color="#10B981" style={{ margin: '0 auto 20px' }} />
          <h2 style={{ color: '#10B981', marginBottom: '15px' }}>Batch Successfully Posted!</h2>
          <p style={{ fontSize: '1.2rem', marginBottom: '10px' }}>Imported {commitStatus.imported_count} transactions.</p>
          <p style={{ color: 'var(--text-secondary)', fontFamily: 'monospace', background: 'var(--surface-color)', display: 'inline-block', padding: '8px 12px', borderRadius: '6px' }}>Batch ID: {commitStatus.batch_id}</p>
        </div>
      )}
    </div>
  );
}
