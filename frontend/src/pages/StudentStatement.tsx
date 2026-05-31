import React, { useState } from 'react';
import axios from 'axios';
import { Search, Download, FileText, User } from 'lucide-react';
import './StudentStatement.css';

interface Transaction {
  "Student ID": number;
  "Name": string;
  "College": string;
  "Ref No": string;
  "Date": string;
  "Term": string;
  "Year": number;
  "Type": string;
  "Description": string;
  "Debit": number;
  "Credit": number;
}

export default function StudentStatement() {
  const [loading, setLoading] = useState(false);
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [metrics, setMetrics] = useState({ total_debit: 0, total_credit: 0, net_balance: 0 });
  const [hasSearched, setHasSearched] = useState(false);

  // Form State
  const [sid, setSid] = useState('');
  const [sysRef, setSysRef] = useState('');
  const [bankRef, setBankRef] = useState('');
  const [term, setTerm] = useState('');
  const [year, setYear] = useState('');

  const buildParams = () => {
    const params: any = {};
    if (sid) params.sid = sid;
    if (sysRef) params.sys = sysRef;
    if (bankRef) params.bank = bankRef;
    if (term) params.terms = [term];
    if (year) params.years = [parseInt(year)];
    return params;
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sid && !sysRef && !bankRef) return;
    
    setLoading(true);
    setHasSearched(true);
    
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('http://127.0.0.1:8000/api/statement/search', {
        params: buildParams(),
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setTransactions(response.data.transactions);
      setMetrics(response.data.metrics);
    } catch (error: any) {
      console.error("Error fetching statement", error);
      setTransactions([]);
      if (error.response?.status === 401) {
        alert("Your secure session has expired. Please click Logout in the sidebar and log back in.");
      }
    } finally {
      setLoading(false);
    }
  };

  const downloadFile = async (type: 'pdf' | 'excel') => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`http://127.0.0.1:8000/api/statement/${type}`, {
        params: buildParams(),
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Statement_${sid || 'Search'}.${type === 'excel' ? 'xlsx' : 'pdf'}`);
      document.body.appendChild(link);
      link.click();
      link.parentNode?.removeChild(link);
    } catch (error) {
      console.error(`Error downloading ${type}`, error);
    }
  };

  const formatCurrency = (value: number) => {
    return new Intl.NumberFormat('en-EG', { style: 'currency', currency: 'EGP', maximumFractionDigits: 2 }).format(value);
  };

  return (
    <div className="statement-container">
      <header className="page-header">
        <h1 className="page-title">Statement of Account</h1>
        <p className="page-subtitle">Search and generate financial statements for students or global transactions.</p>
      </header>

      <form onSubmit={handleSearch} className="search-form glass-panel animate-fade-in">
        <div className="search-grid">
          <div className="input-group">
            <label>Student ID</label>
            <div className="input-with-icon">
              <User size={18} />
              <input type="text" value={sid} onChange={e => setSid(e.target.value)} placeholder="e.g. 26100123" />
            </div>
          </div>
          <div className="input-group">
            <label>System Ref No</label>
            <input type="text" value={sysRef} onChange={e => setSysRef(e.target.value)} placeholder="e.g. INV-004751" />
          </div>
          <div className="input-group">
            <label>Bank Ref / Desc</label>
            <input type="text" value={bankRef} onChange={e => setBankRef(e.target.value)} placeholder="e.g. CIB or 12345" />
          </div>
          <div className="input-group">
            <label>Term</label>
            <select value={term} onChange={e => setTerm(e.target.value)}>
              <option value="">All Terms</option>
              <option value="Fall">Fall</option>
              <option value="Spring">Spring</option>
              <option value="Summer">Summer</option>
            </select>
          </div>
          <div className="input-group">
            <label>Year</label>
            <select value={year} onChange={e => setYear(e.target.value)}>
              <option value="">All Years</option>
              <option value="2023">2023</option>
              <option value="2024">2024</option>
              <option value="2025">2025</option>
              <option value="2026">2026</option>
            </select>
          </div>
        </div>
        
        <div className="form-actions">
          <button type="submit" className="btn-search" disabled={loading || (!sid && !sysRef && !bankRef)}>
            {loading ? <div className="spinner-small"></div> : <Search size={18} />}
            Search Transactions
          </button>
        </div>
      </form>

      {hasSearched && !loading && transactions.length === 0 && (
        <div className="empty-state glass-panel animate-fade-in">
          <p>No transactions found matching your criteria.</p>
        </div>
      )}

      {transactions.length > 0 && (
        <div className="results-section animate-fade-in">
          {sid && (
            <div className="metrics-row">
              <div className="metric-box glass-panel">
                <p>Total Debit</p>
                <h3 style={{color: '#ef4444'}}>{formatCurrency(metrics.total_debit)}</h3>
              </div>
              <div className="metric-box glass-panel">
                <p>Total Credit</p>
                <h3 style={{color: '#10b981'}}>{formatCurrency(metrics.total_credit)}</h3>
              </div>
              <div className="metric-box glass-panel highlight">
                <p>Net Balance Due</p>
                <h3>{formatCurrency(metrics.net_balance)}</h3>
              </div>
              
              <div className="action-buttons">
                <button onClick={() => downloadFile('pdf')} className="btn-download pdf">
                  <FileText size={18} /> Download PDF
                </button>
                <button onClick={() => downloadFile('excel')} className="btn-download excel">
                  <Download size={18} /> Download Excel
                </button>
              </div>
            </div>
          )}

          <div className="table-container glass-panel">
            <div className="table-wrapper">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Date</th>
                    <th>Ref No</th>
                    <th>Term/Yr</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th className="text-right">Debit</th>
                    <th className="text-right">Credit</th>
                  </tr>
                </thead>
                <tbody>
                  {transactions.map((t, idx) => (
                    <tr key={idx}>
                      <td>{t.Date}</td>
                      <td><strong>{t['Ref No']}</strong></td>
                      <td>{t.Term} {t.Year}</td>
                      <td><span className={`badge ${t.Type.toLowerCase().replace(' ', '-')}`}>{t.Type}</span></td>
                      <td>{t.Description}</td>
                      <td className="text-right" style={{color: t.Debit > 0 ? '#ef4444' : ''}}>
                        {t.Debit > 0 ? formatCurrency(t.Debit) : '—'}
                      </td>
                      <td className="text-right" style={{color: t.Credit > 0 ? '#10b981' : ''}}>
                        {t.Credit > 0 ? formatCurrency(t.Credit) : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
