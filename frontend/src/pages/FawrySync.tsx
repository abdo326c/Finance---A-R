import React, { useState, useEffect } from 'react';
import axios from 'axios';
import DataTable from 'react-data-table-component';
import { RefreshCw, CheckCircle, XCircle, AlertTriangle, CloudRain, Save } from 'lucide-react';
import './FawrySync.css';

interface FawryTx {
  reference_number: string;
  student_id: string;
  student_id_int: number | null;
  student_found: boolean;
  student_name: string;
  payment_date: string;
  item_name: string;
  item_price: number;
  bank: string;
  fawry_fees: number;
  net_amount: number;
  include: boolean; // For UI selection
}

export default function FawrySync() {
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [transactions, setTransactions] = useState<FawryTx[]>([]);
  const [errorMsg, setErrorMsg] = useState('');
  
  // Lookups
  const [terms, setTerms] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [selectedTerm, setSelectedTerm] = useState('');
  const [selectedYear, setSelectedYear] = useState('');

  // Sync result
  const [syncResult, setSyncResult] = useState<any>(null);

  useEffect(() => {
    fetchLookups();
  }, []);

  const fetchLookups = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('http://127.0.0.1:8000/api/lookups', {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTerms(response.data.terms || []);
      setYears(response.data.years || []);
      if (response.data.terms?.length) setSelectedTerm(response.data.terms[1] || response.data.terms[0]);
      if (response.data.years?.length) setSelectedYear(response.data.years[0].toString());
    } catch (error) {
      console.error("Failed to fetch lookups", error);
    }
  };

  const fetchSupabase = async () => {
    setLoading(true);
    setErrorMsg('');
    setSyncResult(null);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get('http://127.0.0.1:8000/api/fawry/fetch', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (response.data.unsynced) {
        setTransactions(response.data.unsynced.map((t: any) => ({ ...t, include: t.student_found })));
      }
    } catch (error: any) {
      setErrorMsg(error.response?.data?.detail || "Failed to fetch from Supabase");
    } finally {
      setLoading(false);
    }
  };

  const handleSync = async () => {
    const refsToSync = transactions.filter(t => t.include && t.student_found).map(t => t.reference_number);
    if (refsToSync.length === 0) {
      alert("No valid transactions selected for sync.");
      return;
    }
    if (!selectedTerm || !selectedYear) {
      alert("Please select a target term and year.");
      return;
    }

    setSyncing(true);
    try {
      const token = localStorage.getItem('token');
      const response = await axios.post('http://127.0.0.1:8000/api/fawry/sync', {
        refs_to_sync: refsToSync,
        term: selectedTerm,
        year: parseInt(selectedYear)
      }, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setSyncResult(response.data);
      // Remove synced items from the list
      setTransactions(prev => prev.filter(t => !refsToSync.includes(t.reference_number)));
    } catch (error: any) {
      alert(error.response?.data?.detail || "Sync failed");
    } finally {
      setSyncing(false);
    }
  };

  const handleCheckboxChange = (ref: string, checked: boolean) => {
    setTransactions(prev => prev.map(t => t.reference_number === ref ? { ...t, include: checked } : t));
  };

  const columns = [
    {
      name: 'Include',
      cell: (row: FawryTx) => (
        <input 
          type="checkbox" 
          checked={row.include} 
          disabled={!row.student_found}
          onChange={(e) => handleCheckboxChange(row.reference_number, e.target.checked)} 
        />
      ),
      width: '80px',
      center: true
    },
    {
      name: 'Fawry Ref',
      selector: (row: FawryTx) => row.reference_number,
      sortable: true,
      width: '120px'
    },
    {
      name: 'Date',
      selector: (row: FawryTx) => row.payment_date,
      sortable: true,
      width: '110px'
    },
    {
      name: 'Student ID',
      selector: (row: FawryTx) => row.student_id,
      sortable: true,
      width: '100px'
    },
    {
      name: 'Student Name / Status',
      cell: (row: FawryTx) => (
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {row.student_found ? <CheckCircle size={14} color="#10b981" /> : <XCircle size={14} color="#ef4444" />}
          <span style={{ color: row.student_found ? 'inherit' : '#ef4444' }}>{row.student_name}</span>
        </div>
      ),
      sortable: true,
      grow: 2
    },
    {
      name: 'Item',
      selector: (row: FawryTx) => row.item_name,
      sortable: true
    },
    {
      name: 'Amount',
      selector: (row: FawryTx) => row.item_price,
      sortable: true,
      right: true,
      format: (row: FawryTx) => `${row.item_price.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP`
    }
  ];

  return (
    <div className="fawry-container">
      <header className="page-header">
        <h1 className="page-title">Fawry Sync Bridge</h1>
        <p className="page-subtitle">Pull live payment transactions from Supabase into the local A/R system.</p>
      </header>

      {syncResult && (
        <div className="sync-summary-banner glass-panel animate-fade-in">
          <h3>📊 Sync Complete</h3>
          <div className="summary-grid">
            <div className="summary-box success">
              <p>Successfully Synced</p>
              <h2>{syncResult.sync_count}</h2>
              <span>{syncResult.sync_amount.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</span>
            </div>
            {syncResult.failed_count > 0 && (
              <div className="summary-box danger">
                <p>Failed to Sync</p>
                <h2>{syncResult.failed_count}</h2>
              </div>
            )}
            <div className="summary-box info">
              <p>Batch ID</p>
              <h4>{syncResult.batch_id}</h4>
            </div>
          </div>
          {syncResult.failed_details?.length > 0 && (
            <div className="failed-details">
              <strong>Errors:</strong>
              <ul>
                {syncResult.failed_details.map((err: string, i: number) => <li key={i}>{err}</li>)}
              </ul>
            </div>
          )}
        </div>
      )}

      <div className="fawry-card glass-panel">
        <div className="card-header">
          <div className="header-text">
            <h3>🌐 Supabase Integration</h3>
            <p>Connects securely to the external payment gateway to fetch validated payment logs.</p>
          </div>
          <button onClick={fetchSupabase} disabled={loading} className="btn-primary">
            {loading ? <div className="spinner-small"></div> : <RefreshCw size={16} />} 
            Fetch Unsynced Records
          </button>
        </div>

        {errorMsg && (
          <div className="error-banner">
            <AlertTriangle size={20} />
            {errorMsg}
          </div>
        )}
      </div>

      {transactions.length > 0 && (
        <div className="sync-workspace animate-fade-in">
          <div className="settings-panel glass-panel">
            <h3>⚙️ Sync Posting Defaults</h3>
            <p>Select the Academic Term and Year to assign to these bulk payments.</p>
            <div className="form-row">
              <div className="form-group">
                <label>Target Term</label>
                <select value={selectedTerm} onChange={e => setSelectedTerm(e.target.value)}>
                  {terms.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Target Year</label>
                <select value={selectedYear} onChange={e => setSelectedYear(e.target.value)}>
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>
            
            <div className="metrics-row" style={{ marginTop: '20px' }}>
              <div className="metric">
                <label>Pending Valid Payments</label>
                <span>{transactions.filter(t => t.student_found).length}</span>
              </div>
              <div className="metric">
                <label>Total Outstanding Volume</label>
                <span className="highlight-green">
                  {transactions.filter(t => t.student_found && t.include).reduce((acc, t) => acc + t.item_price, 0).toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP
                </span>
              </div>
            </div>

            <button 
              onClick={handleSync} 
              disabled={syncing || transactions.filter(t => t.include && t.student_found).length === 0} 
              className="btn-success full-width"
              style={{ marginTop: '20px' }}
            >
              {syncing ? <div className="spinner-small"></div> : <Save size={18} />}
              Synchronize Selected Valid Payments
            </button>
          </div>

          <div className="table-panel glass-panel">
            <DataTable
              columns={columns}
              data={transactions}
              pagination
              highlightOnHover
              theme="dark"
              customStyles={{
                table: { style: { backgroundColor: 'transparent' } },
                headRow: { style: { backgroundColor: 'rgba(0,0,0,0.2)', borderBottom: '1px solid rgba(255,255,255,0.1)' } },
                rows: { style: { backgroundColor: 'transparent', borderBottom: '1px solid rgba(255,255,255,0.05)' } },
                pagination: { style: { backgroundColor: 'transparent', borderTop: '1px solid rgba(255,255,255,0.1)' } }
              }}
            />
          </div>
        </div>
      )}

      {!loading && transactions.length === 0 && !errorMsg && !syncResult && (
        <div className="empty-state glass-panel">
          <CloudRain size={48} style={{ opacity: 0.5, marginBottom: '16px' }} />
          <h3>No Pending Transactions</h3>
          <p>Click "Fetch Unsynced Records" to check Supabase for new Fawry payments.</p>
        </div>
      )}
    </div>
  );
}
