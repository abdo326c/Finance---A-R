import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Send, UserCheck, AlertTriangle, ShieldCheck } from 'lucide-react';
import './Operations.css';

const TX_TYPES = ["Payment Receipt", "Invoice", "Credit Hours Adjustment", "Other Fees", "General Adjustment"];

export default function Operations() {
  const [action, setAction] = useState(TX_TYPES[0]);
  const [bypassDup, setBypassDup] = useState(false);
  const [studentId, setStudentId] = useState('');
  
  // Lookups
  const [availableTerms, setAvailableTerms] = useState<string[]>([]);
  const [availableYears, setAvailableYears] = useState<number[]>([]);
  
  // Date/Term
  const [date, setDate] = useState(new Date().toISOString().split('T')[0]);
  const [term, setTerm] = useState('');
  const [year, setYear] = useState<number>(new Date().getFullYear());
  
  // Action specific
  const [bankName, setBankName] = useState('');
  const [bankRef, setBankRef] = useState('');
  const [amountPaid, setAmountPaid] = useState<number | ''>('');
  
  const [regHours, setRegHours] = useState<number | ''>('');
  const [description, setDescription] = useState('');
  
  const [hoursDelta, setHoursDelta] = useState<number | ''>('');
  const [feeAmount, setFeeAmount] = useState<number | ''>('');
  
  const [debit, setDebit] = useState<number | ''>('');
  const [credit, setCredit] = useState<number | ''>('');
  
  const [internalNote, setInternalNote] = useState('');
  
  // Preview
  const [preview, setPreview] = useState<any>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Submitting
  const [submitting, setSubmitting] = useState(false);
  const [flashMsg, setFlashMsg] = useState<{type: 'success' | 'error', text: string} | null>(null);

  // Fetch Lookups
  useEffect(() => {
    const fetchLookups = async () => {
      try {
        const token = localStorage.getItem('token');
        const response = await axios.get('http://127.0.0.1:8000/api/lookups', {
          headers: { Authorization: `Bearer ${token}` }
        });
        setAvailableTerms(response.data.terms || []);
        setAvailableYears(response.data.years || []);
        if (response.data.terms?.length) setTerm(response.data.terms[0]);
        if (response.data.years?.length) setYear(response.data.years[0]);
      } catch (error) {
        console.error("Failed to fetch lookups", error);
      }
    };
    fetchLookups();
  }, []);

  // Fetch Preview
  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (studentId && !isNaN(Number(studentId)) && term && year) {
        fetchPreview();
      } else {
        setPreview(null);
      }
    }, 500);

    return () => clearTimeout(delayDebounceFn);
  }, [studentId, term, year]);

  const fetchPreview = async () => {
    setPreviewLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await axios.get(`http://127.0.0.1:8000/api/operations/preview/${studentId}`, {
        params: { term, year },
        headers: { Authorization: `Bearer ${token}` }
      });
      setPreview(res.data);
    } catch (err) {
      setPreview(null);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!studentId || isNaN(Number(studentId))) {
      setFlashMsg({ type: 'error', text: "Please enter a valid Student ID." });
      return;
    }
    
    setSubmitting(true);
    setFlashMsg(null);
    
    try {
      const token = localStorage.getItem('token');
      const payload = {
        action_type: action,
        student_id: Number(studentId),
        date,
        term,
        year,
        bypass_dup: bypassDup,
        bank_name: bankName,
        bank_ref: bankRef,
        amount_paid: Number(amountPaid) || 0,
        reg_hours: Number(regHours) || 0,
        description,
        hours_delta: Number(hoursDelta) || 0,
        fee_amount: Number(feeAmount) || 0,
        debit: Number(debit) || 0,
        credit: Number(credit) || 0,
        internal_note: internalNote
      };
      
      const res = await axios.post('http://127.0.0.1:8000/api/operations/transaction', payload, {
        headers: { Authorization: `Bearer ${token}` }
      });
      
      setFlashMsg({ type: 'success', text: res.data.message });
      setAmountPaid('');
      setRegHours('');
      setHoursDelta('');
      setDebit('');
      setCredit('');
      setFeeAmount('');
      
    } catch (err: any) {
      const msg = err.response?.data?.detail || "An error occurred while posting the transaction.";
      setFlashMsg({ type: 'error', text: msg });
    } finally {
      setSubmitting(false);
    }
  };

  const renderSandbox = () => {
    if (previewLoading) return <div className="preview-loading">Loading student data...</div>;
    if (!preview && studentId) return <div className="preview-error">Student not found or invalid ID.</div>;
    if (!preview) return <div className="preview-empty">💡 Enter a registered Student ID to trigger the interactive cost preview.</div>;

    const rate = preview.price_per_hr || 0;
    let actionPreview = null;
    
    if (action === "Invoice" && Number(regHours) > 0) {
      const total_pct = preview.scholarships.reduce((acc: number, s: any) => acc + s.percentage, 0);
      const effective_pct = Math.min(100.0, total_pct);
      
      const gross_tuition = Number(regHours) * rate;
      const discount_amt = gross_tuition * (effective_pct / 100.0);
      const net_tuition = gross_tuition - discount_amt;
      
      actionPreview = (
        <div className="sandbox-card invoice-sandbox">
          <h4>🧾 Tuition Billing Summary</h4>
          <div className="sandbox-row">
            <span>Gross Tuition Cost:</span>
            <strong>{gross_tuition.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</strong>
          </div>
          <div className="sandbox-row text-danger">
            <span>Scholarship Deductions ({effective_pct.toFixed(1)}%):</span>
            <strong>-{discount_amt.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</strong>
          </div>
          <hr />
          <div className="sandbox-row text-primary text-large">
            <span>Projected Net Billing:</span>
            <strong>+{net_tuition.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</strong>
          </div>
          {preview.scholarships.length > 0 && (
            <div className="active-policies">
              <p>Active Policies Applied:</p>
              <ul>
                {preview.scholarships.map((s: any, idx: number) => (
                  <li key={idx}><strong>{s.name}</strong>: {s.percentage.toFixed(1)}% {s.internal_note ? `(${s.internal_note})` : ''}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      );
    } else if (action === "Payment Receipt" && Number(amountPaid) > 0) {
      actionPreview = (
        <div className="sandbox-card payment-sandbox">
          <h4>💳 Payment Receipt Summary</h4>
          <div className="sandbox-row text-success text-large">
            <span>Account Credit Receipt:</span>
            <strong>-{Number(amountPaid).toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</strong>
          </div>
          <small>Ledger balance will decrease by this amount.</small>
        </div>
      );
    } else if (action === "Credit Hours Adjustment" && Number(hoursDelta) !== 0) {
      const adj_val = Number(hoursDelta) * rate;
      const isPositive = adj_val > 0;
      
      actionPreview = (
        <div className="sandbox-card adj-sandbox">
          <h4>🔄 Adjustment Summary</h4>
          <div className="sandbox-row">
            <span>Adjustment Hours:</span>
            <strong>{Number(hoursDelta) > 0 ? '+' : ''}{hoursDelta} CH</strong>
          </div>
          <div className={`sandbox-row text-large ${isPositive ? 'text-danger' : 'text-success'}`}>
            <span>Projected Impact:</span>
            <strong>{isPositive ? '+' : ''}{adj_val.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP</strong>
          </div>
        </div>
      );
    }

    return (
      <div className="sandbox-content animate-fade-in">
        <div className="student-badge">
          <UserCheck size={24} className="text-success" />
          <div className="student-info">
            <h3>{preview.name}</h3>
            <p>{preview.college || "—"} | {preview.program || "—"}</p>
            <p className="tuition-rate">Tuition Rate: {rate.toLocaleString('en-EG', {minimumFractionDigits: 2})} EGP / hour</p>
          </div>
        </div>
        {actionPreview}
      </div>
    );
  };

  return (
    <div className="operations-container">
      <header className="page-header">
        <h1 className="page-title">Post Manual Transaction</h1>
        <p className="page-subtitle">Execute secure accounting operations with live sandbox validation.</p>
      </header>

      {flashMsg && (
        <div className={`flash-message ${flashMsg.type} animate-fade-in`}>
          {flashMsg.type === 'error' ? <AlertTriangle size={20} /> : <ShieldCheck size={20} />}
          <span>{flashMsg.text}</span>
          <button className="close-flash" onClick={() => setFlashMsg(null)}>×</button>
        </div>
      )}

      <div className="operations-layout">
        <section className="operations-form-section glass-panel animate-fade-in">
          <form onSubmit={handleSubmit} className="operations-form">
            <div className="form-group mb-4">
              <label>Action Type</label>
              <select value={action} onChange={e => {
                setAction(e.target.value);
                if (e.target.value === "Invoice") setDescription("Tuition Invoice");
                else setDescription("");
              }} className="action-select">
                {TX_TYPES.map(t => <option key={t} value={t}>{t}</option>)}
              </select>
            </div>
            
            <div className="form-group mb-4">
              <label className="checkbox-label text-warning">
                <input 
                  type="checkbox" 
                  checked={bypassDup} 
                  onChange={e => setBypassDup(e.target.checked)} 
                />
                ⚠️ Bypass Duplicate Check (force posting)
              </label>
            </div>

            <div className="form-row">
              <div className="form-group flex-2">
                <label>Student ID</label>
                <input 
                  type="text" 
                  value={studentId} 
                  onChange={e => setStudentId(e.target.value)} 
                  placeholder="e.g. 26100123"
                  required
                />
              </div>
              <div className="form-group flex-1">
                <label>Date</label>
                <input type="date" value={date} onChange={e => setDate(e.target.value)} required />
              </div>
            </div>

            <div className="form-row mb-4">
              <div className="form-group flex-1">
                <label>Term</label>
                <select value={term} onChange={e => setTerm(e.target.value)} required>
                  <option value="" disabled>Select</option>
                  {availableTerms.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group flex-1">
                <label>Year</label>
                <select value={year} onChange={e => setYear(parseInt(e.target.value))} required>
                  <option value="" disabled>Select</option>
                  {availableYears.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
            </div>

            <div className="dynamic-fields">
              {action === "Payment Receipt" && (
                <>
                  <div className="form-row">
                    <div className="form-group flex-1">
                      <label>Bank Name</label>
                      <input type="text" value={bankName} onChange={e => setBankName(e.target.value)} />
                    </div>
                    <div className="form-group flex-1">
                      <label>Bank Ref No</label>
                      <input type="text" value={bankRef} onChange={e => setBankRef(e.target.value)} />
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Amount Paid (EGP)</label>
                    <input type="number" min="0" step="0.01" value={amountPaid} onChange={e => setAmountPaid(e.target.value)} required />
                  </div>
                </>
              )}

              {action === "Invoice" && (
                <>
                  <div className="form-group">
                    <label>Registered Credit Hours</label>
                    <input type="number" min="0" step="1" value={regHours} onChange={e => setRegHours(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label>Description</label>
                    <input type="text" value={description} onChange={e => setDescription(e.target.value)} required />
                  </div>
                </>
              )}

              {action === "Credit Hours Adjustment" && (
                <div className="form-group">
                  <label>Hours Delta (+/−)</label>
                  <input type="number" step="0.5" value={hoursDelta} onChange={e => setHoursDelta(e.target.value)} required />
                </div>
              )}

              {action === "Other Fees" && (
                <>
                  <div className="form-group">
                    <label>Fee Amount (EGP)</label>
                    <input type="number" min="0" step="0.01" value={feeAmount} onChange={e => setFeeAmount(e.target.value)} required />
                  </div>
                  <div className="form-group">
                    <label>Description</label>
                    <input type="text" value={description} onChange={e => setDescription(e.target.value)} required />
                  </div>
                </>
              )}

              {action === "General Adjustment" && (
                <>
                  <div className="form-row">
                    <div className="form-group flex-1">
                      <label>Debit (EGP)</label>
                      <input type="number" min="0" step="0.01" value={debit} onChange={e => setDebit(e.target.value)} required />
                    </div>
                    <div className="form-group flex-1">
                      <label>Credit (EGP)</label>
                      <input type="number" min="0" step="0.01" value={credit} onChange={e => setCredit(e.target.value)} required />
                    </div>
                  </div>
                  <div className="form-group">
                    <label>Description</label>
                    <input type="text" value={description} onChange={e => setDescription(e.target.value)} required />
                  </div>
                </>
              )}
              
              <div className="form-group mt-3">
                <label>Internal Note (Optional)</label>
                <input type="text" value={internalNote} onChange={e => setInternalNote(e.target.value)} placeholder="Will not be printed on student statements" />
              </div>
            </div>

            <div className="form-actions mt-4">
              <button type="submit" className="btn-primary w-100" disabled={submitting}>
                {submitting ? <div className="spinner-small"></div> : <Send size={18} />}
                Process Transaction
              </button>
            </div>
          </form>
        </section>

        <section className="operations-sandbox-section glass-panel animate-fade-in" style={{ animationDelay: '0.1s' }}>
          <div className="sandbox-header">
            <h3>💡 Live Cost & Policy Sandbox</h3>
          </div>
          <div className="sandbox-body">
            {renderSandbox()}
          </div>
        </section>
      </div>
    </div>
  );
}
