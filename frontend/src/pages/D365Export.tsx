import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { DownloadCloud, Settings, Calendar, Hash, FileSpreadsheet } from 'lucide-react';
import './D365Export.css';

export default function D365Export() {
  const [terms, setTerms] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  
  const [term, setTerm] = useState('');
  const [year, setYear] = useState('');
  const [txTypeFilter, setTxTypeFilter] = useState('All (Tuition Invoices & Discounts)');
  
  // Routing settings
  const [revenueAccount, setRevenueAccount] = useState('4101004');
  const [discountAccount, setDiscountAccount] = useState('5201005');
  const [postingProfile, setPostingProfile] = useState('STD');
  const [currencyCode, setCurrencyCode] = useState('EGP');
  
  // Dates and references
  const [invoiceDate, setInvoiceDate] = useState(new Date().toISOString().split('T')[0]);
  const [dueDate, setDueDate] = useState(new Date().toISOString().split('T')[0]);
  const [lastFti, setLastFti] = useState('FTI-0012133');
  const [customerRef, setCustomerRef] = useState('');
  
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState('');

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
      if (response.data.terms?.length) setTerm(response.data.terms[1] || response.data.terms[0]);
      if (response.data.years?.length) setYear(response.data.years[0].toString());
    } catch (error) {
      console.error("Failed to fetch lookups", error);
    }
  };

  const handleExport = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!lastFti || !lastFti.includes('-')) {
      setErrorMsg("Please enter a valid Last FTI Number containing a hyphen (e.g. FTI-0012133).");
      return;
    }
    
    setLoading(true);
    setErrorMsg('');
    try {
      const token = localStorage.getItem('token');
      
      const params = new URLSearchParams();
      params.append('term', term);
      params.append('year', year);
      params.append('tx_type_filter', txTypeFilter);
      params.append('last_fti', lastFti);
      params.append('invoice_date', invoiceDate);
      params.append('due_date', dueDate);
      if (revenueAccount) params.append('revenue_account', revenueAccount);
      if (discountAccount) params.append('discount_account', discountAccount);
      params.append('posting_profile', postingProfile);
      params.append('currency_code', currencyCode);
      if (customerRef) params.append('customer_ref', customerRef);

      const response = await axios.get(`${import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'}/api/d365/export?${params.toString()}`, {
        headers: { Authorization: `Bearer ${token}` },
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('act');
      link.href = url;
      link.setAttribute('download', `Customer_free_text_invoice_${new Date().toISOString().split('T')[0]}.xlsx`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (error: any) {
      if (error.response && error.response.data instanceof Blob) {
        const text = await error.response.data.text();
        try {
          const json = JSON.parse(text);
          setErrorMsg(json.detail || "Export failed.");
        } catch {
          setErrorMsg("Export failed.");
        }
      } else {
        setErrorMsg("Failed to connect to the server.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="d365-container">
      <header className="page-header">
        <h1 className="page-title">Dynamics 365 Integration - FTI Export</h1>
        <p className="page-subtitle">Extract financial transactions in a format ready for direct upload as a Free Text Invoice.</p>
      </header>

      <div className="d365-grid">
        <form className="d365-form glass-panel animate-fade-in" onSubmit={handleExport}>
          {errorMsg && <div className="error-banner">{errorMsg}</div>}
          
          <div className="form-section">
            <h3 className="section-title"><Settings size={18} /> Basic Filters</h3>
            <div className="form-row three-cols">
              <div className="form-group">
                <label>Term</label>
                <select value={term} onChange={e => setTerm(e.target.value)} required>
                  {terms.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Year</label>
                <select value={year} onChange={e => setYear(e.target.value)} required>
                  {years.map(y => <option key={y} value={y}>{y}</option>)}
                </select>
              </div>
              <div className="form-group">
                <label>Transaction Type</label>
                <select value={txTypeFilter} onChange={e => setTxTypeFilter(e.target.value)}>
                  <option>All (Tuition Invoices & Discounts)</option>
                  <option>Tuition Invoices Only</option>
                  <option>Discounts Only (Scholarships)</option>
                  <option>Other Fees Only</option>
                  <option>Adjustments Only</option>
                </select>
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3 className="section-title"><FileSpreadsheet size={18} /> Accounting Routing Settings</h3>
            <div className="form-row two-cols">
              <div className="form-group">
                <label>Tuition Revenue Ledger Account</label>
                <input 
                  type="text" 
                  value={revenueAccount} 
                  onChange={e => setRevenueAccount(e.target.value)} 
                  disabled={txTypeFilter === 'Discounts Only (Scholarships)' || txTypeFilter === 'Other Fees Only' || txTypeFilter === 'Adjustments Only'}
                />
              </div>
              <div className="form-group">
                <label>Discount Ledger Account</label>
                <input 
                  type="text" 
                  value={discountAccount} 
                  onChange={e => setDiscountAccount(e.target.value)} 
                  disabled={txTypeFilter === 'Tuition Invoices Only' || txTypeFilter === 'Other Fees Only' || txTypeFilter === 'Adjustments Only'}
                />
              </div>
            </div>
            
            {(txTypeFilter === 'Other Fees Only' || txTypeFilter === 'Adjustments Only') && (
              <div className="info-banner">
                💡 <b>Important Note:</b> These vary in nature and require different ledger accounts. The Ledger Account column will be left blank in the generated file, allowing you to fill it manually based on the Description of each transaction.
              </div>
            )}
            
            <div className="form-row two-cols" style={{ marginTop: '16px' }}>
              <div className="form-group">
                <label>Posting Profile</label>
                <input type="text" value={postingProfile} onChange={e => setPostingProfile(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Currency</label>
                <input type="text" value={currencyCode} onChange={e => setCurrencyCode(e.target.value)} required />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3 className="section-title"><Calendar size={18} /> Invoice & Due Dates</h3>
            <div className="form-row two-cols">
              <div className="form-group">
                <label>Invoice Date</label>
                <input type="date" value={invoiceDate} onChange={e => setInvoiceDate(e.target.value)} required />
              </div>
              <div className="form-group">
                <label>Due Date</label>
                <input type="date" value={dueDate} onChange={e => setDueDate(e.target.value)} required />
              </div>
            </div>
          </div>

          <div className="form-section">
            <h3 className="section-title"><Hash size={18} /> Invoice Numbering & References</h3>
            <div className="form-row two-cols">
              <div className="form-group">
                <label>Last D365 FTI Number *</label>
                <input type="text" value={lastFti} onChange={e => setLastFti(e.target.value)} required placeholder="e.g. FTI-0012133" />
              </div>
              <div className="form-group">
                <label>Customer Reference (Optional)</label>
                <input type="text" value={customerRef} onChange={e => setCustomerRef(e.target.value)} />
              </div>
            </div>
          </div>
          
          <div className="form-actions">
            <button type="submit" disabled={loading} className="btn-primary full-width generate-btn">
              {loading ? <div className="spinner-small"></div> : <DownloadCloud size={20} />}
              Generate D365 Template
            </button>
          </div>
        </form>

        <div className="instructions-sidebar glass-panel">
          <h3>📘 How FTI Export Works</h3>
          <p>
            The <b>Free Text Invoice (FTI)</b> export creates an Excel document specifically formatted for the Microsoft Dynamics 365 Data Management workspace.
          </p>
          <div className="instruction-step">
            <div className="step-num">1</div>
            <div>
              <strong>Filter Transactions</strong>
              <p>Select the Academic Term and Year. Ensure you have run all bulk tuitions and discounts first.</p>
            </div>
          </div>
          <div className="instruction-step">
            <div className="step-num">2</div>
            <div>
              <strong>Verify Ledger Rules</strong>
              <p>Confirm the standard revenue and discount chart of account numbers. Dimensions are derived dynamically from student records.</p>
            </div>
          </div>
          <div className="instruction-step">
            <div className="step-num">3</div>
            <div>
              <strong>Set the Sequence</strong>
              <p>Check Dynamics 365 for your latest FTI ID. Enter it, and the system will automatically sequence upwards from there.</p>
            </div>
          </div>
          <div className="instruction-step">
            <div className="step-num">4</div>
            <div>
              <strong>Generate & Upload</strong>
              <p>Download the .xlsx file and upload it into D365 via the Data Management import project "Customer free text invoice".</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
