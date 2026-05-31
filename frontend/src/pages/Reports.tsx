import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { FileBarChart, Download, Settings, ChevronDown, ChevronUp } from 'lucide-react';
import './Reports.css';

const FORMATS = [
  "Accounting Summary",
  "Full Detailed Log",
  "Period Closing (Activity Summary)",
  "Student Academic Status Report",
];

export default function Reports() {
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState<{ columns: string[], data: any[] }>({ columns: [], data: [] });
  const [hasGenerated, setHasGenerated] = useState(false);
  const [configOpen, setConfigOpen] = useState(true);

  // Dynamic Lookups
  const [availableColleges, setAvailableColleges] = useState<string[]>([]);
  const [availableTerms, setAvailableTerms] = useState<string[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  const [availableStatuses, setAvailableStatuses] = useState<string[]>([]);

  // Filters
  const [format, setFormat] = useState(FORMATS[0]);
  const [colleges, setColleges] = useState<string[]>([]);
  const [terms, setTerms] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [statuses, setStatuses] = useState<string[]>([]);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

  useEffect(() => {
    const fetchLookups = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups`, {
          headers: { Authorization: `Bearer ${token}` }
        });
        setAvailableColleges(response.data.colleges || []);
        setAvailableTerms(response.data.terms || []);
        setAvailableYears(response.data.years || []);
        setAvailableStatuses(response.data.statuses || []);
      } catch (error) {
        console.error("Failed to fetch lookups", error);
      }
    };
    fetchLookups();
  }, []);

  const handleMultiSelect = (setter: React.Dispatch<React.SetStateAction<any[]>>, value: any) => {
    setter(prev => prev.includes(value) ? prev.filter(item => item !== value) : [...prev, value]);
  };

  const buildParams = () => {
    const params: any = { format: format };
    if (colleges.length) params.colleges = colleges;
    if (terms.length) params.terms = terms;
    if (years.length) params.years = years;
    if (statuses.length) params.statuses = statuses;
    if (startDate) params.start_date = startDate;
    if (endDate) params.end_date = endDate;
    return params;
  };

  const serializeParams = (params: any) => {
    const searchParams = new URLSearchParams();
    for (const key in params) {
      if (Array.isArray(params[key])) {
        params[key].forEach((val: any) => searchParams.append(key, val));
      } else if (params[key] !== undefined && params[key] !== null && params[key] !== '') {
        searchParams.append(key, params[key]);
      }
    }
    return searchParams.toString();
  };

  const handleGenerate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (format === "Period Closing (Activity Summary)" && (!startDate || !endDate)) {
      alert("Please select both start and end dates for Period Closing report.");
      return;
    }
    
    setLoading(true);
    setHasGenerated(true);
    
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/reports/generate`, {
        params: buildParams(),
        paramsSerializer: serializeParams,
        headers: { Authorization: `Bearer ${token}` }
      });
      setReportData(response.data);
      // Auto-collapse config panel if data is found to maximize table space
      if (response.data.data.length > 0) {
        setConfigOpen(false);
      }
    } catch (error) {
      console.error("Error generating report", error);
      setReportData({ columns: [], data: [] });
    } finally {
      setLoading(false);
    }
  };

  const downloadExcel = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/reports/excel`, {
        params: buildParams(),
        paramsSerializer: serializeParams,
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Report_${format.replace(/ /g, '_')}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (error) {
      console.error("Error downloading report", error);
    }
  };

  const formatValue = (col: string, val: any) => {
    if (typeof val === 'number') {
      if (col.toLowerCase().includes('id') || col.toLowerCase().includes('year')) {
        return val.toString();
      }
      return new Intl.NumberFormat('en-EG', { maximumFractionDigits: 2 }).format(val);
    }
    return val;
  };

  return (
    <div className="reports-container">
      <header className="page-header">
        <h1 className="page-title">Financial Management Reports</h1>
        <p className="page-subtitle">Generate dynamic reports with advanced filtering capabilities.</p>
      </header>

      <div className="reports-layout-top">
        <section className="reports-config-panel glass-panel animate-fade-in">
          <div className="config-header" onClick={() => setConfigOpen(!configOpen)} style={{ cursor: 'pointer' }}>
            <div className="sidebar-title" style={{ marginBottom: 0, borderBottom: 'none', paddingBottom: 0 }}>
              <Settings size={18} /> Configuration
            </div>
            <button className="btn-toggle-config">
              {configOpen ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
            </button>
          </div>
          
          {configOpen && (
            <form onSubmit={handleGenerate} className="reports-form-grid">
              <div className="form-row-top">
                <div className="form-group">
                  <label>Report Format</label>
                  <select value={format} onChange={e => setFormat(e.target.value)} required>
                    {FORMATS.map(f => <option key={f} value={f}>{f}</option>)}
                  </select>
                </div>

                <div className="form-group">
                  <label>Date Range (Optional)</label>
                  <div className="date-inputs-row">
                    <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)} />
                    <span className="date-separator">to</span>
                    <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)} />
                  </div>
                </div>

                <div className="form-group">
                  <label>Year</label>
                  <select 
                    value={years.length > 0 ? years[0].toString() : ""} 
                    onChange={e => {
                      const val = e.target.value;
                      setYears(val ? [parseInt(val)] : []);
                    }}
                  >
                    <option value="">All Years</option>
                    {availableYears.map(y => (
                      <option key={y} value={y}>{y}</option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="form-row-bottom">
                <div className="filter-group">
                  <label>Colleges</label>
                  <div className="checkbox-row">
                    {availableColleges.map(c => (
                      <label key={c} className="custom-checkbox">
                        <input type="checkbox" checked={colleges.includes(c)} onChange={() => handleMultiSelect(setColleges, c)} />
                        <span>{c}</span>
                      </label>
                    ))}
                  </div>
                </div>

                <div className="filter-group">
                  <label>Terms</label>
                  <div className="checkbox-row">
                    {availableTerms.map(t => (
                      <label key={t} className="custom-checkbox">
                        <input type="checkbox" checked={terms.includes(t)} onChange={() => handleMultiSelect(setTerms, t)} />
                        <span>{t}</span>
                      </label>
                    ))}
                  </div>
                </div>
                
                <div className="action-group">
                  <button type="submit" className="btn-generate" disabled={loading}>
                    {loading ? <div className="spinner-small"></div> : <FileBarChart size={18} />}
                    Generate Report
                  </button>
                </div>
              </div>
            </form>
          )}
        </section>

        <section className="reports-content glass-panel animate-fade-in">
          {!hasGenerated ? (
            <div className="empty-state">
              <FileBarChart size={48} style={{ opacity: 0.5, marginBottom: '16px' }} />
              <h3>No Report Generated</h3>
              <p>Select your filters and click generate to view data.</p>
            </div>
          ) : loading ? (
            <div className="empty-state">
              <div className="spinner-large"></div>
              <p>Aggregating financial data...</p>
            </div>
          ) : reportData.data.length === 0 ? (
            <div className="empty-state">
              <h3>No Data Found</h3>
              <p>Your filter criteria did not match any records.</p>
            </div>
          ) : (
            <div className="results-container">
              <div className="results-header">
                <h3>{format}</h3>
                <button onClick={downloadExcel} className="btn-download-excel">
                  <Download size={16} /> Export to Excel
                </button>
              </div>
              <div className="table-responsive">
                <table className="data-table reports-table">
                  <thead style={{ position: 'sticky', top: 0, zIndex: 1 }}>
                    <tr>
                      {reportData.columns.map((col, i) => <th key={i}>{col}</th>)}
                    </tr>
                  </thead>
                  <tbody>
                    {reportData.data.map((row, i) => (
                      <tr key={i} className={row["Student Name"] === "TOTAL" ? "total-row" : ""}>
                        {reportData.columns.map((col, j) => (
                          <td key={j} className={typeof row[col] === 'number' ? 'text-right' : ''}>
                            {formatValue(col, row[col])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
