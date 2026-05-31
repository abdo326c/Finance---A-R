import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Upload, Settings, RefreshCw, AlertTriangle, CheckCircle, XCircle, FileSearch, ShieldAlert } from 'lucide-react';
import './Reconciliation.css';

interface ReconResult {
  matched: any[];
  mismatched: any[];
  missing_local: any[];
  missing_ext: any[];
}

export default function Reconciliation() {
  const [terms, setTerms] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  
  // Form State
  const [targetTerm, setTargetTerm] = useState('');
  const [targetYear, setTargetYear] = useState('');
  const [reconMode, setReconMode] = useState('PowerCampus ⇆ Local A/R Database');
  const [cohortScope, setCohortScope] = useState('Active Local Student Cohort Only');
  const [enableChargeDate, setEnableChargeDate] = useState(false);
  const [payCutoff, setPayCutoff] = useState('');
  const [chargeCutoff, setChargeCutoff] = useState('');
  const [file, setFile] = useState<File | null>(null);
  
  // Mapping
  const [idCol, setIdCol] = useState('PEOPLE_ORG_ID');
  const [fnameCol, setFnameCol] = useState('FIRST_NAME');
  const [lnameCol, setLnameCol] = useState('LAST_NAME');
  const [typeCol, setTypeCol] = useState('CHARGE_CREDIT_TYPE');
  const [amountCol, setAmountCol] = useState('AMOUNT');
  const [dateCol, setDateCol] = useState('ENTRY_DATE');
  const [descCol, setDescCol] = useState('CRG_CRD_DESC');
  const [codeCol, setCodeCol] = useState('CHARGE_CREDIT_CODE');
  const [termCol, setTermCol] = useState('ACADEMIC_TERM');
  const [yearCol, setYearCol] = useState('ACADEMIC_YEAR');

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ReconResult | null>(null);
  const [errorMsg, setErrorMsg] = useState('');

  // Resolution Inspector State
  const [selectedAuditId, setSelectedAuditId] = useState<string>('');
  const [simActive, setSimActive] = useState(false);
  
  useEffect(() => {
    fetchLookups();
  }, []);

  const fetchLookups = async () => {
    try {
      const token = localStorage.getItem('token');
      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/lookups`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      setTerms(response.data.terms || []);
      setYears(response.data.years || []);
      if (response.data.terms?.length) setTargetTerm(response.data.terms[1] || response.data.terms[0]);
      if (response.data.years?.length) setTargetYear(response.data.years[0].toString());
      
      const currentYear = new Date().getFullYear();
      setPayCutoff(`${currentYear}-03-18`);
      setChargeCutoff(`${currentYear}-03-18`);
    } catch (error) {
      console.error("Failed to fetch lookups", error);
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleAnalyze = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setErrorMsg("Please upload a file to begin.");
      return;
    }
    setLoading(true);
    setErrorMsg('');
    setResult(null);
    setSelectedAuditId('');
    
    const formData = new FormData();
    formData.append('file', file);
    formData.append('target_term', targetTerm);
    formData.append('target_year', targetYear.toString());
    formData.append('recon_mode', reconMode);
    formData.append('cohort_scope', cohortScope);
    if (payCutoff) formData.append('pay_cutoff', payCutoff);
    formData.append('enable_charge_date', enableChargeDate.toString());
    if (enableChargeDate && chargeCutoff) formData.append('charge_cutoff', chargeCutoff);
    
    formData.append('id_col', idCol);
    formData.append('fname_col', fnameCol);
    formData.append('lname_col', lnameCol);
    formData.append('type_col', typeCol);
    formData.append('amount_col', amountCol);
    formData.append('date_col', dateCol);
    formData.append('desc_col', descCol);
    formData.append('code_col', codeCol);
    formData.append('term_col', termCol);
    formData.append('year_col', yearCol);

    try {
      const token = localStorage.getItem('token');
      const response = await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/reconciliation/analyze`, formData, {
        headers: { 
          Authorization: `Bearer ${token}`,
          'Content-Type': 'multipart/form-data'
        }
      });
      setResult(response.data);
    } catch (error: any) {
      setErrorMsg(error.response?.data?.detail || "Reconciliation analysis failed");
    } finally {
      setLoading(false);
    }
  };

  const handleDisputeUpdate = async (studentId: number, isDisputed: boolean, notes: string) => {
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/reconciliation/dispute/${studentId}`, 
        { is_disputed: isDisputed, notes },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert("Dispute status saved successfully.");
      // Soft update local state
      if (result) {
        setResult({
          ...result,
          mismatched: result.mismatched.map(m => m.student_id === studentId.toString() ? { ...m, is_disputed: isDisputed, dispute_notes: notes } : m)
        });
      }
    } catch (error) {
      alert("Failed to update dispute status.");
    }
  };

  const handleResolve = async (studentId: number, action: string, amount: number) => {
    if (!window.confirm(`Are you sure you want to safe-import a ${action} of ${amount} EGP?`)) return;
    try {
      const token = localStorage.getItem('token');
      await axios.post(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/reconciliation/resolve/${action}`, 
        { student_id: studentId, term: targetTerm, year: parseInt(targetYear), amount },
        { headers: { Authorization: `Bearer ${token}` } }
      );
      alert("Resolution imported successfully!");
      // Re-run analysis
      handleAnalyze(new Event('submit') as any);
    } catch (error: any) {
      alert(error.response?.data?.detail || "Resolution failed.");
    }
  };

  const renderInspector = () => {
    if (!result || !selectedAuditId) return null;
    const item = result.mismatched.find(m => m.student_id === selectedAuditId);
    if (!item) return null;

    const chgDiff = item.pc_charges - item.loc_charges;
    const dscDiff = item.pc_discounts - item.loc_discounts;
    const pmtDiff = item.pc_payments - item.loc_payments;

    return (
      <div className="inspector-panel glass-panel animate-fade-in" style={{ marginTop: '24px' }}>
        <div className="inspector-header">
          <h3>🛠️ Diagnostics for {item.name} ({item.student_id})</h3>
          <span className="diff-badge">Total Diff: {item.discrepancy > 0 ? '+' : ''}{item.discrepancy.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</span>
        </div>

        {item.is_disputed && (
          <div className="alert-box danger">
            <ShieldAlert size={20} />
            <div>
              <strong>Account Flagged: Under Dispute</strong>
              <p>Notes: {item.dispute_notes}</p>
            </div>
          </div>
        )}

        <div className="dispute-form">
          <label className="checkbox-label">
            <input type="checkbox" checked={item.is_disputed} onChange={e => handleDisputeUpdate(parseInt(item.student_id), e.target.checked, item.dispute_notes)} />
            ⚠️ Flag student ledger under dispute
          </label>
          <div style={{ display: 'flex', gap: '12px', marginTop: '8px' }}>
            <input 
              type="text" 
              className="notes-input full-width" 
              placeholder="Dispute & Follow-up Notes..." 
              defaultValue={item.dispute_notes}
              onBlur={e => {
                if (e.target.value !== item.dispute_notes) {
                  handleDisputeUpdate(parseInt(item.student_id), item.is_disputed, e.target.value);
                }
              }}
            />
          </div>
        </div>

        <div className="three-step-diagnostics">
          <div className="diag-step">
            <h4>Step 1: Tuition Charges</h4>
            <p>PowerCampus: <b>{item.pc_charges.toLocaleString()} EGP</b></p>
            <p>Local A/R: <b>{item.loc_charges.toLocaleString()} EGP</b></p>
            {Math.abs(chgDiff) < 0.01 ? (
              <span className="status-text success"><CheckCircle size={14}/> Charges Match</span>
            ) : (
              <span className="status-text danger"><XCircle size={14}/> Mismatch: {chgDiff > 0 ? '+' : ''}{chgDiff.toLocaleString()} EGP</span>
            )}
          </div>
          <div className="diag-step">
            <h4>Step 2: Scholarships</h4>
            <p>PowerCampus: <b>{item.pc_discounts.toLocaleString()} EGP</b></p>
            <p>Local A/R: <b>{item.loc_discounts.toLocaleString()} EGP</b></p>
            {Math.abs(dscDiff) < 0.01 ? (
              <span className="status-text success"><CheckCircle size={14}/> Discounts Match</span>
            ) : (
              <span className="status-text danger"><XCircle size={14}/> Mismatch: {dscDiff > 0 ? '+' : ''}{dscDiff.toLocaleString()} EGP</span>
            )}
          </div>
          <div className="diag-step">
            <h4>Step 3: Payments & Receipts</h4>
            <p>PowerCampus: <b>{item.pc_payments.toLocaleString()} EGP</b></p>
            <p>Local A/R: <b>{item.loc_payments.toLocaleString()} EGP</b></p>
            {Math.abs(pmtDiff) < 0.01 ? (
              <span className="status-text success"><CheckCircle size={14}/> Payments Match</span>
            ) : (
              <span className="status-text danger"><XCircle size={14}/> Mismatch: {pmtDiff > 0 ? '+' : ''}{pmtDiff.toLocaleString()} EGP</span>
            )}
          </div>
        </div>

        {pmtDiff > 0 && (
          <div className="alert-box info" style={{ marginTop: '16px' }}>
            💡 <b>Live Transaction Detected</b>: A payment of {pmtDiff.toLocaleString()} EGP was processed externally but is missing locally.
          </div>
        )}

        <div className="sandbox-toggle" style={{ marginTop: '24px' }}>
          <label className="checkbox-label" style={{ fontSize: '1.1rem', color: '#60a5fa' }}>
            <input type="checkbox" checked={simActive} onChange={e => setSimActive(e.target.checked)} />
            🧪 Open 'Before vs. After' Ledger Simulation Sandbox & Remedies
          </label>
        </div>

        {simActive && (
          <div className="sandbox-panel">
            <p style={{ marginBottom: '16px', color: 'var(--text-secondary)' }}>
              Here is the simulated transition preview showing what your Local A/R database ledgers will look like after executing the imports.
            </p>
            
            <table className="recon-table">
              <thead>
                <tr>
                  <th>Financial Dimension</th>
                  <th className="text-right">Current Local</th>
                  <th className="text-right">Remedy Effect</th>
                  <th className="text-right">Projected Local</th>
                  <th className="text-right">PowerCampus Target</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td>📄 Tuition Charges (Debits)</td>
                  <td className="text-right">{item.loc_charges.toLocaleString()}</td>
                  <td className="text-right">{Math.abs(chgDiff) >= 0.01 ? chgDiff.toLocaleString() : '-'}</td>
                  <td className="text-right">{(item.loc_charges + (Math.abs(chgDiff) >= 0.01 ? chgDiff : 0)).toLocaleString()}</td>
                  <td className="text-right">{item.pc_charges.toLocaleString()}</td>
                  <td>
                    {Math.abs(chgDiff) >= 0.01 ? (
                      <button onClick={() => handleResolve(parseInt(item.student_id), 'charge', chgDiff)} className="btn-small btn-primary">Import Charge</button>
                    ) : <span className="status-text success">Matched</span>}
                  </td>
                </tr>
                <tr>
                  <td>🎓 Scholarships (Credits)</td>
                  <td className="text-right">{item.loc_discounts.toLocaleString()}</td>
                  <td className="text-right">{Math.abs(dscDiff) >= 0.01 ? dscDiff.toLocaleString() : '-'}</td>
                  <td className="text-right">{(item.loc_discounts + (Math.abs(dscDiff) >= 0.01 ? dscDiff : 0)).toLocaleString()}</td>
                  <td className="text-right">{item.pc_discounts.toLocaleString()}</td>
                  <td>
                    {Math.abs(dscDiff) >= 0.01 ? (
                      <button onClick={() => handleResolve(parseInt(item.student_id), 'discount', dscDiff)} className="btn-small btn-primary">Import Discount</button>
                    ) : <span className="status-text success">Matched</span>}
                  </td>
                </tr>
                <tr>
                  <td>💳 Payments & Receipts (Credits)</td>
                  <td className="text-right">{item.loc_payments.toLocaleString()}</td>
                  <td className="text-right">{Math.abs(pmtDiff) >= 0.01 ? pmtDiff.toLocaleString() : '-'}</td>
                  <td className="text-right">{(item.loc_payments + (Math.abs(pmtDiff) >= 0.01 ? pmtDiff : 0)).toLocaleString()}</td>
                  <td className="text-right">{item.pc_payments.toLocaleString()}</td>
                  <td>
                    {Math.abs(pmtDiff) >= 0.01 ? (
                      <button onClick={() => handleResolve(parseInt(item.student_id), 'payment', pmtDiff)} className="btn-small btn-success">Import Payment</button>
                    ) : <span className="status-text success">Matched</span>}
                  </td>
                </tr>
              </tbody>
            </table>
            
            {Math.abs(item.discrepancy) < 10 && Math.abs(item.discrepancy) > 0 && (
              <div style={{ marginTop: '16px' }}>
                <p>This looks like a rounding variance.</p>
                <button onClick={() => handleResolve(parseInt(item.student_id), 'adjustment', item.discrepancy)} className="btn-small btn-primary">
                  Post Penny Adjustment
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="page-container recon-container">
      <header className="page-header">
        <h1 className="page-title">Multi-System Account Reconciliation Hub</h1>
        <p className="page-subtitle">Bridge the legacy PowerCampus database, our Local A/R database, and Microsoft Dynamics ERP to spot mismatches instantly.</p>
      </header>

      <form className="recon-config glass-panel" onSubmit={handleAnalyze}>
        {errorMsg && <div className="alert-box danger"><AlertTriangle size={18} /> {errorMsg}</div>}
        
        <div className="config-grid">
          <div className="config-col">
            <h3>⚙️ Settings</h3>
            <div className="form-group">
              <label>Target Term</label>
              <select value={targetTerm} onChange={e => setTargetTerm(e.target.value)} required>
                {terms.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Target Year</label>
              <select value={targetYear} onChange={e => setTargetYear(e.target.value)} required>
                {years.map(y => <option key={y} value={y}>{y}</option>)}
              </select>
            </div>
            <div className="form-group">
              <label>Reconciliation Mode</label>
              <select value={reconMode} onChange={e => setReconMode(e.target.value)}>
                <option>PowerCampus ⇆ Local A/R Database</option>
                <option>Local A/R Database ⇆ Microsoft Dynamics 365</option>
              </select>
            </div>
          </div>
          
          <div className="config-col">
            <h3>📅 Date Filters</h3>
            <div className="form-group">
              <label>Include Payments ON or AFTER:</label>
              <input type="date" value={payCutoff} onChange={e => setPayCutoff(e.target.value)} />
            </div>
            <div className="form-group" style={{ flexDirection: 'row', alignItems: 'center', gap: '8px' }}>
              <input type="checkbox" checked={enableChargeDate} onChange={e => setEnableChargeDate(e.target.checked)} id="chargeDateCb" />
              <label htmlFor="chargeDateCb" style={{ margin: 0 }}>Filter Charges by Date?</label>
            </div>
            {enableChargeDate && (
              <div className="form-group">
                <label>Include Charges ON or AFTER:</label>
                <input type="date" value={chargeCutoff} onChange={e => setChargeCutoff(e.target.value)} />
              </div>
            )}
          </div>
          
          <div className="config-col">
            <h3>🎯 Cohort Scope</h3>
            <div className="radio-group">
              <label className="radio-label">
                <input type="radio" name="cohort" value="Active Local Student Cohort Only" checked={cohortScope === 'Active Local Student Cohort Only'} onChange={e => setCohortScope(e.target.value)} />
                <div>
                  <strong>Active Local Student Cohort Only</strong>
                  <p>Recommended - Filters out foreign PowerCampus categories.</p>
                </div>
              </label>
              <label className="radio-label">
                <input type="radio" name="cohort" value="All Uploaded PowerCampus Student Records" checked={cohortScope === 'All Uploaded PowerCampus Student Records'} onChange={e => setCohortScope(e.target.value)} />
                <div>
                  <strong>All Uploaded Records</strong>
                  <p>Full cross-system audit of all CSV rows.</p>
                </div>
              </label>
            </div>
          </div>
        </div>
        
        <div className="upload-section">
          <h3>📤 Upload External Ledger Export</h3>
          <div className="file-drop-zone">
            <Upload size={32} color="var(--text-secondary)" />
            <input type="file" accept=".csv, .xlsx" onChange={handleFileChange} required />
            <p>{file ? file.name : "Drag and drop or click to select Excel/CSV file"}</p>
          </div>
          
          <details className="mapping-details">
            <summary>⚙️ CSV Column Mapping (Verify or Adjust Columns)</summary>
            <div className="mapping-grid">
              <div className="form-group"><label>ID Col</label><input value={idCol} onChange={e => setIdCol(e.target.value)}/></div>
              <div className="form-group"><label>First Name</label><input value={fnameCol} onChange={e => setFnameCol(e.target.value)}/></div>
              <div className="form-group"><label>Last Name</label><input value={lnameCol} onChange={e => setLnameCol(e.target.value)}/></div>
              <div className="form-group"><label>Type (C/D/R)</label><input value={typeCol} onChange={e => setTypeCol(e.target.value)}/></div>
              <div className="form-group"><label>Amount</label><input value={amountCol} onChange={e => setAmountCol(e.target.value)}/></div>
              <div className="form-group"><label>Date</label><input value={dateCol} onChange={e => setDateCol(e.target.value)}/></div>
              <div className="form-group"><label>Term</label><input value={termCol} onChange={e => setTermCol(e.target.value)}/></div>
              <div className="form-group"><label>Year</label><input value={yearCol} onChange={e => setYearCol(e.target.value)}/></div>
            </div>
          </details>
        </div>

        <button type="submit" disabled={loading} className="btn-primary full-width generate-btn" style={{ marginTop: '24px' }}>
          {loading ? <div className="spinner-small"></div> : <RefreshCw size={20} />}
          Initialize Smart Reconciliation Engine
        </button>
      </form>

      {result && (
        <div className="recon-results animate-fade-in">
          <div className="metrics-grid">
            <div className="metric-card" style={{ borderLeftColor: '#10b981' }}>
              <span>🟢 Matched Accounts</span>
              <h2>{result.matched.length}</h2>
            </div>
            <div className="metric-card" style={{ borderLeftColor: '#f59e0b' }}>
              <span>🟡 Mismatched Balances</span>
              <h2>{result.mismatched.length}</h2>
            </div>
            <div className="metric-card" style={{ borderLeftColor: '#ef4444' }}>
              <span>🔴 Missing in Local</span>
              <h2>{result.missing_local.length}</h2>
            </div>
            <div className="metric-card" style={{ borderLeftColor: '#3b82f6' }}>
              <span>🔵 Missing in External</span>
              <h2>{result.missing_ext.length}</h2>
            </div>
          </div>

          {result.mismatched.length > 0 && (
            <div className="mismatches-panel glass-panel" style={{ marginTop: '24px' }}>
              <h3>🟡 Mismatched Balances ({result.mismatched.length})</h3>
              <div className="table-wrapper">
                <table className="recon-table">
                  <thead>
                    <tr>
                      <th>Student ID</th>
                      <th>Name</th>
                      <th className="text-right">PowerCampus Bal</th>
                      <th className="text-right">Local Bal</th>
                      <th className="text-right">Discrepancy (EGP)</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.mismatched.map((m: any, idx) => (
                      <tr key={idx} className={selectedAuditId === m.student_id ? 'selected-row' : ''}>
                        <td>{m.student_id}</td>
                        <td>{m.name} {m.is_disputed ? <ShieldAlert size={14} color="#ef4444" style={{verticalAlign:'middle'}}/> : ''}</td>
                        <td className="text-right">{m.pc_balance.toLocaleString()}</td>
                        <td className="text-right">{m.loc_balance.toLocaleString()}</td>
                        <td className="text-right" style={{ color: '#ef4444', fontWeight: 'bold' }}>
                          {m.discrepancy > 0 ? '+' : ''}{m.discrepancy.toLocaleString()}
                        </td>
                        <td>
                          <button 
                            className="btn-small btn-secondary" 
                            onClick={() => { setSelectedAuditId(m.student_id); setSimActive(false); }}
                          >
                            <FileSearch size={14}/> Audit
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              
              {renderInspector()}
            </div>
          )}

          {result.missing_local.length > 0 && (
            <div className="mismatches-panel glass-panel" style={{ marginTop: '24px' }}>
              <h3>🔴 Missing in Local A/R ({result.missing_local.length})</h3>
              <div className="table-wrapper">
                <table className="recon-table">
                  <thead>
                    <tr>
                      <th>Student ID</th>
                      <th>Name</th>
                      <th className="text-right">Ext Charges</th>
                      <th className="text-right">Ext Payments</th>
                      <th className="text-right">Ext Balance</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.missing_local.map((m: any, idx) => (
                      <tr key={idx}>
                        <td>{m.student_id}</td>
                        <td>{m.name}</td>
                        <td className="text-right">{m.pc_charges.toLocaleString()}</td>
                        <td className="text-right">{m.pc_payments.toLocaleString()}</td>
                        <td className="text-right">{m.pc_balance.toLocaleString()}</td>
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
