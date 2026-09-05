import React, { useState, useEffect } from 'react';
import { 
  ShieldCheck, TrendingUp, AlertTriangle, CheckCircle2, 
  Clock, Send, CreditCard, Play, RefreshCw, XCircle, 
  Search, BarChart3, FileText, Layers
} from 'lucide-react';
import { 
  ResponsiveContainer, XAxis, YAxis, Tooltip, 
  BarChart, Bar, Cell, PieChart, Pie
} from 'recharts';

// API Base URL
const API_BASE = 'http://127.0.0.1:8000/api';

// Formatting helpers
const formatCurrency = (val: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: 0
  }).format(val);
};

export default function App() {
  const [activeTab, setActiveTab] = useState<'dashboard' | 'cases' | 'evaluation'>('dashboard');
  const [cases, setCases] = useState<any[]>([]);
  const [summary, setSummary] = useState<any>({
    revenue_at_risk: 0,
    revenue_recovered: 0,
    recovery_rate: 0,
    total_cases: 0,
    active_cases: 0,
    recovered_cases_count: 0,
    total_interventions: 0,
    failure_distribution: [],
    strategy_distribution: []
  });
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [selectedCase, setSelectedCase] = useState<any>(null);
  
  // Simulation input state
  const [simAmount, setSimAmount] = useState('2499');
  const [simReason, setSimReason] = useState('INSUFFICIENT_FUNDS');
  const [simType, setSimType] = useState('RECURRING');
  const [simMessage, setSimMessage] = useState('');
  
  // Customer chat reply input
  const [chatInput, setChatInput] = useState('');
  const [isSendingChat, setIsSendingChat] = useState(false);

  // Evaluation results state
  const [evalResults, setEvalResults] = useState<any>(null);
  const [evalLoading, setEvalLoading] = useState(false);

  // Simulation settings config
  const [simConfig, setSimConfig] = useState({
    outage_enabled: false,
    duplicate_webhook_enabled: false,
    notification_failure_enabled: false
  });

  // Filters state
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');

  // Fetch simulation config on start
  const fetchSimConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/simulation/config`);
      if (res.ok) {
        const data = await res.json();
        setSimConfig(data);
      }
    } catch (err) {
      console.error("Error fetching simulation config:", err);
    }
  };

  const handleToggleSimFlag = async (key: string) => {
    try {
      const updated = { ...simConfig, [key]: !((simConfig as any)[key]) };
      const res = await fetch(`${API_BASE}/simulation/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated)
      });
      if (res.ok) {
        const data = await res.json();
        setSimConfig(data);
      }
    } catch (err) {
      console.error("Error updating simulation config:", err);
    }
  };

  const handleTriggerShowcase = async (scenario: string) => {
    try {
      const res = await fetch(`${API_BASE}/simulation/showcase/${scenario}`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        if (data.case_id) {
          setSelectedCaseId(data.case_id);
          setActiveTab('cases');
          fetchData();
        }
      }
    } catch (err) {
      console.error("Error triggering showcase scenario:", err);
    }
  };

  // Fetch summary and cases
  const fetchData = async () => {
    try {
      const summaryRes = await fetch(`${API_BASE}/dashboard/summary`);
      const summaryData = await summaryRes.json();
      setSummary(summaryData);

      const casesRes = await fetch(`${API_BASE}/recovery-cases`);
      const casesData = await casesRes.json();
      setCases(casesData);

      // Refresh currently selected case details
      if (selectedCaseId) {
        fetchCaseDetails(selectedCaseId);
      }
    } catch (err) {
      console.error("Error fetching data:", err);
    }
  };

  const fetchCaseDetails = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/recovery-cases/${id}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedCase(data);
      }
    } catch (err) {
      console.error("Error fetching case details:", err);
    }
  };

  useEffect(() => {
    fetchSimConfig();
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 4000); // Polling every 4s
    return () => clearInterval(interval);
  }, [selectedCaseId]);

  useEffect(() => {
    // Load evaluation metrics on view change
    if (activeTab === 'evaluation') {
      fetchEvaluationResults();
    }
  }, [activeTab]);

  const handleSelectCase = (id: string) => {
    setSelectedCaseId(id);
    fetchCaseDetails(id);
  };

  // Run AI diagnosis & planning
  const handleRunRecovery = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/recovery-cases/${id}/run`, { method: 'POST' });
      if (res.ok) {
        setSimMessage("AI Diagnosis and Strategy execution triggered!");
        fetchData();
      }
    } catch (err) {
      setSimMessage("Failed to execute recovery run.");
    }
  };

  // Approve scheduled retry
  const handleApproveAction = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/recovery-cases/${id}/approve`, { method: 'POST' });
      if (res.ok) {
        setSimMessage("Action manually approved and executed!");
        fetchData();
      }
    } catch (err) {
      setSimMessage("Failed to execute action.");
    }
  };

  // Cancel/close case
  const handleCancelCase = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/recovery-cases/${id}/cancel`, { method: 'POST' });
      if (res.ok) {
        setSimMessage("Recovery case manually cancelled.");
        fetchData();
      }
    } catch (err) {
      setSimMessage("Failed to cancel case.");
    }
  };

  // Simulate webhook captured payment
  const handleSimulatePayment = async (id: string) => {
    try {
      const res = await fetch(`${API_BASE}/simulation/payment-success`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ case_id: id })
      });
      if (res.ok) {
        setSimMessage("Simulated customer checkout payment! Webhook processed.");
        fetchData();
      }
    } catch (err) {
      setSimMessage("Payment simulation failed.");
    }
  };

  // Simulate payment failure
  const handleSimulateFailure = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const failure_description = simReason === 'INSUFFICIENT_FUNDS' 
        ? 'Insufficient funds in the card account.' 
        : simReason === 'EXPIRED_CARD' 
        ? 'The card is expired.' 
        : simReason === 'GATEWAY_TIMEOUT' 
        ? 'Network request timed out.' 
        : 'Abandoned check out session.';

      const res = await fetch(`${API_BASE}/simulation/payment-failure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          amount: parseFloat(simAmount),
          payment_type: simType,
          failure_code: simReason,
          failure_description
        })
      });
      if (res.ok) {
        const data = await res.json();
        setSimMessage(`Mock failure registered! Case created: ${data.webhook_result.case_id}`);
        handleSelectCase(data.webhook_result.case_id);
        setActiveTab('cases');
        fetchData();
      }
    } catch (err) {
      setSimMessage("Failed to simulate failure.");
    }
  };

  // Send chat message
  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatInput.trim() || !selectedCaseId) return;

    setIsSendingChat(true);
    try {
      const res = await fetch(`${API_BASE}/recovery-cases/${selectedCaseId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ reply_text: chatInput })
      });
      if (res.ok) {
        setChatInput('');
        fetchCaseDetails(selectedCaseId);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setIsSendingChat(false);
    }
  };

  // Fetch evaluation metrics
  const fetchEvaluationResults = async () => {
    setEvalLoading(true);
    try {
      const res = await fetch(`${API_BASE}/evaluation/results`);
      if (res.ok) {
        const data = await res.json();
        setEvalResults(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setEvalLoading(false);
    }
  };

  // Trigger new evaluation run
  const handleRunEvaluation = async () => {
    setEvalLoading(true);
    try {
      const res = await fetch(`${API_BASE}/evaluation/run`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setEvalResults(data);
      }
    } catch (err) {
      console.error(err);
    } finally {
      setEvalLoading(false);
    }
  };

  // Filter cases list
  const filteredCases = cases.filter(c => {
    const matchesSearch = 
      c.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.customer.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.customer.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      (c.ai_diagnosis && c.ai_diagnosis.toLowerCase().includes(searchQuery.toLowerCase()));
      
    const matchesStatus = statusFilter === '' ? true : c.state === statusFilter;
    
    return matchesSearch && matchesStatus;
  });

  // Color schemas for state badges
  const getStateBadgeClass = (state: string) => {
    switch (state) {
      case 'RECOVERED':
        return 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30';
      case 'PAYMENT_FAILED':
        return 'bg-rose-500/10 text-rose-400 border border-rose-500/30';
      case 'DIAGNOSING':
      case 'ACTION_PENDING':
        return 'bg-blue-500/10 text-blue-400 border border-blue-500/30 animate-pulse';
      case 'RECOVERY_PLANNED':
        return 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/30';
      case 'WAITING':
        return 'bg-amber-500/10 text-amber-400 border border-amber-500/30';
      case 'MAX_ATTEMPTS':
      case 'EXPIRED':
        return 'bg-slate-500/10 text-slate-400 border border-slate-500/30';
      default:
        return 'bg-violet-500/10 text-violet-400 border border-violet-500/30';
    }
  };

  // Chart configuration colors
  const chartColors = ['#5275ff', '#10b981', '#f59e0b', '#ef4444', '#a855f7', '#64748b'];

  return (
    <div className="flex min-h-screen bg-[#070b13] text-gray-200">
      
      {/* SIDEBAR */}
      <aside className="w-64 border-r border-slate-800 bg-[#0b0f19] flex flex-col justify-between shrink-0">
        <div>
          <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-800">
            <Layers className="h-6 w-6 text-brand-500 shrink-0" />
            <div className="flex flex-col justify-center">
              <span className="font-bold text-base text-white tracking-wider leading-tight">PayRevive</span>
              <span className="text-[11px] text-gray-400 font-medium leading-tight">AI Revenue Recovery</span>
            </div>
          </div>
          
          <nav className="p-4 space-y-1">
            <button 
              onClick={() => setActiveTab('dashboard')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'dashboard' 
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20' 
                  : 'text-gray-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <BarChart3 className="h-4 w-4" />
              Merchant Dashboard
            </button>
            <button 
              onClick={() => setActiveTab('cases')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'cases' 
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20' 
                  : 'text-gray-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <FileText className="h-4 w-4" />
              Recovery Cases
              {cases.filter(c => !StateMachine.TERMINAL_STATES.has(c.state)).length > 0 && (
                <span className="ml-auto px-2 py-0.5 text-xs bg-rose-500 text-white rounded-full">
                  {cases.filter(c => !StateMachine.TERMINAL_STATES.has(c.state)).length}
                </span>
              )}
            </button>
            <button 
              onClick={() => setActiveTab('evaluation')}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all ${
                activeTab === 'evaluation' 
                  ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20' 
                  : 'text-gray-400 hover:text-white hover:bg-slate-800/50'
              }`}
            >
              <ShieldCheck className="h-4 w-4" />
              Evaluation Suite
            </button>
          </nav>
        </div>

        <div className="p-4 border-t border-slate-800 space-y-3">
          <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800 text-xs">
            <span className="font-semibold block text-white mb-1">Status Mode</span>
            <div className="flex items-center gap-2">
              <span className="h-2.5 w-2.5 bg-emerald-500 rounded-full animate-ping"></span>
              <span className="text-gray-400">Simulation Enabled</span>
            </div>
          </div>
        </div>
      </aside>

      {/* MAIN CONTAINER */}
      <main className="flex-1 flex flex-col min-w-0">
        
        {/* HEADER */}
        <header className="h-16 border-b border-slate-800 bg-[#0b0f19] flex items-center justify-between px-8">
          <h2 className="text-lg font-semibold text-white">
            {activeTab === 'dashboard' && 'Merchant Overview'}
            {activeTab === 'cases' && 'Recovery Pipelines'}
            {activeTab === 'evaluation' && 'AI Performance Evaluation'}
          </h2>
          <div className="flex items-center gap-4">
            {simMessage && (
              <div className="bg-slate-800 text-brand-300 px-4 py-1.5 rounded-full border border-slate-700 text-xs flex items-center gap-2 animate-fadeIn">
                <Clock className="h-3.5 w-3.5" />
                <span>{simMessage}</span>
              </div>
            )}
            <button 
              onClick={fetchData}
              className="p-2 text-gray-400 hover:text-white bg-slate-800 hover:bg-slate-700 border border-slate-750 rounded-lg transition"
              title="Manual Refresh"
            >
              <RefreshCw className="h-4 w-4" />
            </button>
          </div>
        </header>

        {/* WORKSPACE CONTENT */}
        <div className="flex-1 overflow-y-auto p-8">
          
          {/* 1. DASHBOARD VIEW */}
          {activeTab === 'dashboard' && (
            <div className="space-y-8">
              
              {/* STATS OVERVIEW CARDS */}
              <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
                
                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 shadow-md">
                  <div className="flex justify-between items-start text-gray-400">
                    <span className="text-sm font-medium">Revenue At Risk</span>
                    <AlertTriangle className="h-5 w-5 text-amber-500" />
                  </div>
                  <div className="mt-2">
                    <span className="text-3xl font-bold text-white tracking-tight">{formatCurrency(summary.revenue_at_risk)}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Total failed payments tracked
                  </div>
                </div>

                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 shadow-md">
                  <div className="flex justify-between items-start text-gray-400">
                    <span className="text-sm font-medium">Revenue Recovered</span>
                    <TrendingUp className="h-5 w-5 text-emerald-500" />
                  </div>
                  <div className="mt-2">
                    <span className="text-3xl font-bold text-emerald-400 tracking-tight">{formatCurrency(summary.revenue_recovered)}</span>
                  </div>
                  <div className="mt-1 text-xs text-emerald-500/80 font-medium">
                    Recovered successfully
                  </div>
                </div>

                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 shadow-md">
                  <div className="flex justify-between items-start text-gray-400">
                    <span className="text-sm font-medium">Recovery Rate</span>
                    <ShieldCheck className="h-5 w-5 text-brand-500" />
                  </div>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="text-3xl font-bold text-white tracking-tight">{summary.recovery_rate.toFixed(1)}%</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    AI recovery vs total risk
                  </div>
                </div>

                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 shadow-md">
                  <div className="flex justify-between items-start text-gray-400">
                    <span className="text-sm font-medium">Active Pipelines</span>
                    <Clock className="h-5 w-5 text-indigo-500" />
                  </div>
                  <div className="mt-2">
                    <span className="text-3xl font-bold text-white tracking-tight">{summary.active_cases}</span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    Cases undergoing recovery
                  </div>
                </div>

              </div>

              {/* SIMULATION SEED WIDGET */}
              <div className="bg-slate-900/40 p-6 rounded-xl border border-slate-800/80 grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
                <div className="md:col-span-1">
                  <h3 className="text-md font-semibold text-white flex items-center gap-2">
                    <Play className="h-4 w-4 text-brand-500 fill-brand-500" />
                    Interactive Failure Simulator
                  </h3>
                  <p className="text-xs text-gray-400 mt-1">
                    Simulate a payment failure event immediately. It triggers a Razorpay webhook that initializes the recovery cycle.
                  </p>
                </div>
                <form onSubmit={handleSimulateFailure} className="md:col-span-2 grid grid-cols-2 md:grid-cols-4 gap-4 items-end">
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1">Amount (₹)</label>
                    <input 
                      type="number" 
                      value={simAmount} 
                      onChange={e => setSimAmount(e.target.value)} 
                      className="w-full text-sm bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-white focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1">Failure Code</label>
                    <select 
                      value={simReason} 
                      onChange={e => setSimReason(e.target.value)}
                      className="w-full text-sm bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-white focus:outline-none focus:border-brand-500"
                    >
                      <option value="INSUFFICIENT_FUNDS">Insufficient Funds</option>
                      <option value="EXPIRED_CARD">Expired Card</option>
                      <option value="GATEWAY_TIMEOUT">Gateway Timeout</option>
                      <option value="CHECKOUT_ABANDONED">Abandonment</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-semibold text-gray-400 mb-1">Type</label>
                    <select 
                      value={simType} 
                      onChange={e => setSimType(e.target.value)}
                      className="w-full text-sm bg-slate-950 border border-slate-800 p-2.5 rounded-lg text-white focus:outline-none focus:border-brand-500"
                    >
                      <option value="RECURRING">Recurring</option>
                      <option value="ONE_TIME">One-Time</option>
                      <option value="INVOICE">Invoice</option>
                    </select>
                  </div>
                  <button 
                    type="submit" 
                    className="w-full bg-brand-500 hover:bg-brand-600 text-white font-medium text-sm py-2.5 px-4 rounded-lg shadow-lg shadow-brand-500/10 transition"
                  >
                    Simulate Failure
                  </button>
                </form>
              </div>

              {/* ADVANCED SIMULATION CONTROLS */}
              <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 grid grid-cols-1 lg:grid-cols-2 gap-8">
                <div>
                  <h3 className="text-sm font-semibold text-white mb-4">Simulation Flags & Sandbox Settings</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-850">
                      <div>
                        <span className="text-xs font-semibold text-white block">Simulate Provider Outage</span>
                        <span className="text-[10px] text-gray-500 block">Forces card charging and link creation calls to fail with 504 Gateway errors.</span>
                      </div>
                      <button
                        onClick={() => handleToggleSimFlag('outage_enabled')}
                        className={`w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${simConfig.outage_enabled ? 'bg-brand-500' : 'bg-slate-800'}`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 transform ${simConfig.outage_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-850">
                      <div>
                        <span className="text-xs font-semibold text-white block">Simulate Duplicate Webhook Delivery</span>
                        <span className="text-[10px] text-gray-500 block">Fires identical webhook payloads twice to verify that event idempotency works.</span>
                      </div>
                      <button
                        onClick={() => handleToggleSimFlag('duplicate_webhook_enabled')}
                        className={`w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${simConfig.duplicate_webhook_enabled ? 'bg-brand-500' : 'bg-slate-800'}`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 transform ${simConfig.duplicate_webhook_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                      </button>
                    </div>

                    <div className="flex items-center justify-between p-3 bg-slate-900/50 rounded-lg border border-slate-850">
                      <div>
                        <span className="text-xs font-semibold text-white block">Simulate Notification Delivery Failure</span>
                        <span className="text-[10px] text-gray-500 block">Fires 500 errors when sending emails or SMS link delivery alerts.</span>
                      </div>
                      <button
                        onClick={() => handleToggleSimFlag('notification_failure_enabled')}
                        className={`w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${simConfig.notification_failure_enabled ? 'bg-brand-500' : 'bg-slate-800'}`}
                      >
                        <div className={`w-4 h-4 rounded-full bg-white transition-transform duration-200 transform ${simConfig.notification_failure_enabled ? 'translate-x-6' : 'translate-x-1'}`} />
                      </button>
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-sm font-semibold text-white mb-4">Deterministic Showcase Scenarios</h3>
                  <div className="grid grid-cols-2 gap-3 text-xs">
                    <button
                      onClick={() => handleTriggerShowcase('insufficient_funds')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">1. Insufficient Funds</span>
                      <span className="text-[10px] text-gray-500">AI proposes link recovery flow, customer pays manually</span>
                    </button>

                    <button
                      onClick={() => handleTriggerShowcase('gateway_error')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">2. Gateway Error Retry</span>
                      <span className="text-[10px] text-gray-500">AI executes rapid bounded auto-retry with zero user friction</span>
                    </button>

                    <button
                      onClick={() => handleTriggerShowcase('card_expired')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">3. Card Expired</span>
                      <span className="text-[10px] text-gray-500">AI requests payment link directly to update method</span>
                    </button>

                    <button
                      onClick={() => handleTriggerShowcase('checkout_abandonment')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">4. Checkout Abandonment</span>
                      <span className="text-[10px] text-gray-500">AI sends recovery notification/link without transaction retry</span>
                    </button>

                    <button
                      onClick={() => handleTriggerShowcase('provider_outage')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">5. Provider Outage Fallback</span>
                      <span className="text-[10px] text-gray-500">Simulates gateway failure with immediate fallback transition</span>
                    </button>

                    <button
                      onClick={() => handleTriggerShowcase('race_condition')}
                      className="p-3 bg-slate-900 hover:bg-slate-850 text-left rounded-lg border border-slate-800 text-gray-300 font-medium transition flex flex-col justify-between"
                    >
                      <span className="text-white block font-semibold mb-1">6. Race Condition Check</span>
                      <span className="text-[10px] text-gray-500">Scheduled retry cancelled by manual webhook payment</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* CHARTS GRID */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                
                {/* FAILURE CAUSES PIE CHART */}
                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-6">Payment Failure Classification</h3>
                  <div className="h-64 flex items-center justify-between">
                    <div className="w-1/2 h-full">
                      <ResponsiveContainer width="100%" height="100%">
                        <PieChart>
                          <Pie
                            data={summary.failure_distribution}
                            cx="50%"
                            cy="50%"
                            innerRadius={50}
                            outerRadius={85}
                            paddingAngle={4}
                            dataKey="value"
                          >
                            {summary.failure_distribution.map((_: any, index: number) => (
                              <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} />
                            ))}
                          </Pie>
                        </PieChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="w-1/2 space-y-2">
                      {summary.failure_distribution.map((entry: any, index: number) => (
                        <div key={entry.name} className="flex items-center gap-2.5 text-xs text-gray-400">
                          <span 
                            className="h-3 w-3 rounded-full shrink-0" 
                            style={{ backgroundColor: chartColors[index % chartColors.length] }}
                          />
                          <span className="truncate">{entry.name}</span>
                          <span className="ml-auto font-semibold text-white">{entry.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>

                {/* STRATEGY DISTRIBUTION BAR CHART */}
                <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800">
                  <h3 className="text-sm font-semibold text-white mb-6">Intervention Strategies Applied</h3>
                  <div className="h-64">
                    <ResponsiveContainer width="100%" height="100%">
                      <BarChart data={summary.strategy_distribution}>
                        <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} />
                        <YAxis stroke="#64748b" fontSize={10} tickLine={false} />
                        <Tooltip 
                          contentStyle={{ backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: '8px' }}
                          labelStyle={{ color: '#fff' }}
                        />
                        <Bar dataKey="value" fill="#5275ff" radius={[4, 4, 0, 0]}>
                          {summary.strategy_distribution.map((_: any, index: number) => (
                            <Cell key={`cell-${index}`} fill={chartColors[index % chartColors.length]} />
                          ))}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

              </div>

            </div>
          )}

          {/* 2. RECOVERY CASES LIST + DETAILS PANEL */}
          {activeTab === 'cases' && (
            <div className="h-full flex gap-8">
              
              {/* CASES LIST SECTION */}
              <div className="flex-1 bg-[#0b0f19] border border-slate-800 rounded-xl flex flex-col min-w-0">
                
                {/* SEARCH AND FILTERS HEAD */}
                <div className="p-4 border-b border-slate-800 flex gap-4">
                  <div className="relative flex-1">
                    <Search className="absolute left-3 top-2.5 h-4.5 w-4.5 text-gray-500" />
                    <input 
                      type="text"
                      placeholder="Search cases by ID, customer name, email..."
                      value={searchQuery}
                      onChange={e => setSearchQuery(e.target.value)}
                      className="w-full pl-10 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-sm focus:outline-none focus:border-brand-500"
                    />
                  </div>
                  <div className="w-48">
                    <select
                      value={statusFilter}
                      onChange={e => setStatusFilter(e.target.value)}
                      className="w-full bg-slate-950 border border-slate-800 p-2 rounded-lg text-sm text-gray-300 focus:outline-none"
                    >
                      <option value="">All States</option>
                      <option value="PAYMENT_FAILED">Failed Payment</option>
                      <option value="DIAGNOSING">Diagnosing</option>
                      <option value="RECOVERY_PLANNED">Planned</option>
                      <option value="WAITING">Waiting</option>
                      <option value="RECOVERED">Recovered</option>
                      <option value="MAX_ATTEMPTS">Max Attempts</option>
                      <option value="CANCELLED">Cancelled</option>
                      <option value="DISPUTED">Disputed</option>
                    </select>
                  </div>
                </div>

                {/* CASES TABLE */}
                <div className="flex-1 overflow-y-auto">
                  <table className="w-full text-left border-collapse">
                    <thead>
                      <tr className="border-b border-slate-800 text-xs font-semibold text-gray-400 bg-slate-900/20">
                        <th className="p-4">Case ID</th>
                        <th className="p-4">Customer</th>
                        <th className="p-4">Amount</th>
                        <th className="p-4">Diagnosis</th>
                        <th className="p-4">State</th>
                        <th className="p-4 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-850">
                      {filteredCases.map(c => (
                        <tr 
                          key={c.id} 
                          onClick={() => handleSelectCase(c.id)}
                          className={`hover:bg-slate-900/35 cursor-pointer transition text-sm ${selectedCaseId === c.id ? 'bg-slate-900/50' : ''}`}
                        >
                          <td className="p-4 font-mono font-medium text-white">{c.id}</td>
                          <td className="p-4">
                            <span className="block text-white font-medium">{c.customer.name}</span>
                            <span className="block text-xs text-gray-500">{c.customer.email}</span>
                          </td>
                          <td className="p-4 font-semibold text-white">{formatCurrency(c.risk_amount)}</td>
                          <td className="p-4">
                            {c.ai_diagnosis ? (
                              <span className="text-indigo-400 font-medium text-xs">{c.ai_diagnosis}</span>
                            ) : (
                              <span className="text-gray-500 italic text-xs">Pending diagnosis</span>
                            )}
                          </td>
                          <td className="p-4">
                            <span className={`px-2 py-1 text-xs font-semibold rounded-full ${getStateBadgeClass(c.state)}`}>
                              {c.state}
                            </span>
                          </td>
                          <td className="p-4 text-right" onClick={e => e.stopPropagation()}>
                            <button
                              onClick={() => handleSelectCase(c.id)}
                              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-xs text-gray-300 font-medium rounded-md border border-slate-700 transition"
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

              </div>

              {/* INSPECT/CASE DETAIL PANEL */}
              <div className="w-120 bg-[#0b0f19] border border-slate-800 rounded-xl flex flex-col overflow-y-auto p-6 space-y-6">
                
                {selectedCase ? (
                  <>
                    {/* CASE HEADER */}
                    <div className="flex justify-between items-start border-b border-slate-800 pb-4">
                      <div>
                        <span className="text-xs text-gray-500 block">Case Reference</span>
                        <h3 className="text-lg font-mono font-bold text-white">{selectedCase.id}</h3>
                      </div>
                      <span className={`px-2.5 py-1 text-xs font-semibold rounded-full ${getStateBadgeClass(selectedCase.state)}`}>
                        {selectedCase.state}
                      </span>
                    </div>

                    {/* CUSTOMER & PAYMENT CARDS */}
                    <div className="grid grid-cols-2 gap-4">
                      <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                        <span className="text-xs text-gray-500 block mb-1">Customer Profile</span>
                        <span className="text-sm font-semibold text-white block">{selectedCase.customer.name}</span>
                        <span className="text-xs text-gray-400 block truncate">{selectedCase.customer.email}</span>
                        <span className="text-xs text-indigo-400 font-medium block mt-1">Channel: {selectedCase.customer.preferred_channel}</span>
                      </div>
                      <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800">
                        <span className="text-xs text-gray-500 block mb-1">Risk Amount</span>
                        <span className="text-sm font-semibold text-white block">{formatCurrency(selectedCase.risk_amount)}</span>
                        <span className="text-xs text-rose-400 block truncate">{selectedCase.failure_reason}</span>
                        <span className="text-xs text-gray-500 block mt-1">Attempts: {selectedCase.attempt_count} / {selectedCase.max_attempts}</span>
                      </div>
                    </div>

                    {/* AI DIAGNOSIS INTERFACE */}
                    <div className="bg-indigo-950/20 p-4 rounded-xl border border-indigo-900/40">
                      <h4 className="text-xs font-bold text-indigo-400 tracking-wider uppercase mb-3 flex justify-between items-center">
                        <span>AI Recommendation Engine</span>
                        {selectedCase.ai_confidence && (
                          <span className="px-2 py-0.5 bg-indigo-500/10 text-indigo-300 rounded text-[10px]">
                            Confidence: {(selectedCase.ai_confidence * 100).toFixed(0)}%
                          </span>
                        )}
                      </h4>
                      {selectedCase.ai_diagnosis ? (
                        <div className="space-y-2">
                          <div className="flex gap-2">
                            <span className="text-xs text-gray-400 font-medium">Diagnosis:</span>
                            <span className="text-xs text-indigo-300 font-semibold">{selectedCase.ai_diagnosis}</span>
                          </div>
                          <div className="flex gap-2">
                            <span className="text-xs text-gray-400 font-medium">Action Propose:</span>
                            <span className="text-xs text-emerald-400 font-semibold">{selectedCase.recommended_action}</span>
                          </div>
                          <p className="text-xs text-gray-300 bg-slate-950/40 p-2.5 rounded border border-indigo-950/80 leading-relaxed">
                            {selectedCase.ai_reasoning}
                          </p>
                        </div>
                      ) : (
                        <div className="py-2 text-center text-xs text-gray-500 italic">
                          No AI diagnosis created yet. Click "Run Recovery" below.
                        </div>
                      )}
                    </div>

                    {/* SAFETY / POLICY ENGINE CHECKLIST */}
                    <div className="bg-slate-900/50 p-4 rounded-xl border border-slate-800">
                      <h4 className="text-xs font-bold text-gray-400 tracking-wider uppercase mb-3">Safety / Policy Engine Checklist</h4>
                      <div className="space-y-2 text-xs">
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span className="text-gray-300">Opt-out Opt-in check (Opted-out: {selectedCase.customer.opted_out ? 'Yes' : 'No'})</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span className="text-gray-300">Attempts within limit ({selectedCase.attempt_count}/{selectedCase.max_attempts})</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span className="text-gray-300">Payment status is failed (Status: {selectedCase.payment.status})</span>
                        </div>
                        <div className="flex items-center gap-2">
                          <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />
                          <span className="text-gray-300">Dispute flag clear (Disputed: {selectedCase.disputed ? 'Yes' : 'No'})</span>
                        </div>
                      </div>
                    </div>

                    {/* OPERATOR CONTROL BOX */}
                    <div className="border-t border-slate-800 pt-4 space-y-3">
                      <span className="text-xs font-semibold text-gray-400 block mb-2">Intervention Actions</span>
                      
                      <div className="grid grid-cols-2 gap-3">
                        {/* Run Recovery */}
                        {(selectedCase.state === 'PAYMENT_FAILED' || selectedCase.state === 'DIAGNOSING') && (
                          <button
                            onClick={() => handleRunRecovery(selectedCase.id)}
                            className="bg-brand-500 hover:bg-brand-600 text-white font-medium text-xs py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition"
                          >
                            <Play className="h-3.5 w-3.5" />
                            Run Recovery
                          </button>
                        )}
                        
                        {/* Approve Scheduled action */}
                        {selectedCase.state === 'RECOVERY_PLANNED' && (
                          <button
                            onClick={() => handleApproveAction(selectedCase.id)}
                            className="bg-emerald-600 hover:bg-emerald-700 text-white font-medium text-xs py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition"
                          >
                            <CheckCircle2 className="h-3.5 w-3.5" />
                            Approve & Execute
                          </button>
                        )}

                        {/* Simulate user manual payment (checkout link click) */}
                        {!StateMachine.TERMINAL_STATES.has(selectedCase.state) && (
                          <button
                            onClick={() => handleSimulatePayment(selectedCase.id)}
                            className="bg-slate-800 hover:bg-slate-700 border border-slate-700 text-gray-200 font-medium text-xs py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition"
                          >
                            <CreditCard className="h-3.5 w-3.5" />
                            Simulate Payment
                          </button>
                        )}

                        {/* Cancel Case */}
                        {!StateMachine.TERMINAL_STATES.has(selectedCase.state) && (
                          <button
                            onClick={() => handleCancelCase(selectedCase.id)}
                            className="bg-rose-950/20 hover:bg-rose-950/40 border border-rose-900/40 text-rose-400 font-medium text-xs py-2 px-4 rounded-lg flex items-center justify-center gap-2 transition"
                          >
                            <XCircle className="h-3.5 w-3.5" />
                            Cancel Case
                          </button>
                        )}
                      </div>
                    </div>

                    {/* CONVERSATION Dunner widget */}
                    {!StateMachine.TERMINAL_STATES.has(selectedCase.state) && (
                      <div className="border-t border-slate-800 pt-4">
                        <span className="text-xs font-semibold text-gray-400 block mb-2">Simulate Customer Chat Reply</span>
                        <form onSubmit={handleSendChat} className="flex gap-2">
                          <input 
                            type="text" 
                            placeholder="Type: 'I'll pay on Friday' or 'stop messaging'" 
                            value={chatInput}
                            onChange={e => setChatInput(e.target.value)}
                            className="flex-1 bg-slate-950 border border-slate-800 px-3 py-1.5 rounded-lg text-xs focus:outline-none focus:border-brand-500 text-white"
                          />
                          <button 
                            type="submit" 
                            disabled={isSendingChat}
                            className="p-2 bg-brand-500 hover:bg-brand-600 rounded-lg text-white disabled:opacity-50"
                          >
                            <Send className="h-3.5 w-3.5" />
                          </button>
                        </form>
                      </div>
                    )}

                    {/* TIMELINE AUDIT EVENTS */}
                    <div className="border-t border-slate-800 pt-4">
                      <span className="text-xs font-semibold text-gray-400 block mb-3">Audit Log Timeline</span>
                      <div className="relative border-l border-slate-800 pl-4 space-y-4 text-xs ml-1.5">
                        {selectedCase.audit_events.map((evt: any) => (
                          <div key={evt.id} className="relative">
                            <span className="absolute -left-[21px] top-1.5 h-2 w-2 rounded-full bg-indigo-500 ring-4 ring-[#070b13]"></span>
                            <div className="flex justify-between items-center">
                              <span className="font-semibold text-white block">{evt.event_type}</span>
                              <span className="text-[10px] text-gray-500">
                                {new Date(evt.timestamp).toLocaleTimeString()}
                              </span>
                            </div>
                            {evt.original_error && (
                              <span className="text-rose-400 font-mono text-[10px] block mt-0.5">{evt.original_error}</span>
                            )}
                            {evt.metadata_json && (
                              <span className="text-gray-400 block mt-1 font-mono text-[10px] bg-slate-950/40 p-1.5 rounded border border-slate-850">
                                {JSON.stringify(evt.metadata_json)}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="my-auto text-center text-xs text-gray-500 py-12">
                    <Layers className="h-8 w-8 mx-auto text-slate-700 mb-2" />
                    Inspect a recovery case from the list to view timeline history, safety checks, and control operations.
                  </div>
                )}

              </div>

            </div>
          )}

          {/* 3. EVALUATION PANEL */}
          {activeTab === 'evaluation' && (
            <div className="space-y-8">
              
              {/* EVALUATION HEAD */}
              <div className="bg-[#0b0f19] p-6 rounded-xl border border-slate-800 flex justify-between items-center">
                <div>
                  <div className="flex items-center gap-3">
                    <h3 className="font-bold text-white text-md">AI Recovery Model vs. Standard Retry Baseline</h3>
                    {evalResults && (
                      <span className={`px-2.5 py-0.5 rounded text-[10px] font-bold ${
                        evalResults.execution_mode.includes('LIVE') 
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' 
                          : 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                      }`}>
                        {evalResults.execution_mode}
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-gray-400 mt-1">
                    Evaluates both engines over the 50 synthetic test cases. Baseline retries blindly after 24h (max 3 tries); AI recovers based on failure diagnosis.
                  </p>
                </div>
                <button
                  onClick={handleRunEvaluation}
                  disabled={evalLoading}
                  className="bg-brand-500 hover:bg-brand-600 text-white font-medium text-sm py-2.5 px-5 rounded-lg shadow-lg shadow-brand-500/10 flex items-center gap-2 disabled:opacity-50 transition"
                >
                  <RefreshCw className={`h-4 w-4 ${evalLoading ? 'animate-spin' : ''}`} />
                  Run Evaluator Loop
                </button>
              </div>

              {evalResults ? (
                <div className="space-y-8">
                  
                  {/* COMPARISON METRICS GRID */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
                    
                    {/* METRIC COMPARISON TABLE */}
                    <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6">
                      <h4 className="text-xs font-bold text-gray-400 tracking-wider uppercase mb-4">Core Metrics Comparison</h4>
                      <table className="w-full text-xs text-left border-collapse">
                        <thead>
                          <tr className="border-b border-slate-800 text-gray-500 pb-2">
                            <th className="pb-2">Metric</th>
                            <th className="pb-2">Baseline</th>
                            <th className="pb-2 text-brand-400 font-semibold">AI Recovery</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-850">
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Recovered Amount</td>
                            <td className="py-3 font-semibold text-white">{formatCurrency(evalResults.baseline.recovered_inr)}</td>
                            <td className="py-3 font-bold text-emerald-400">{formatCurrency(evalResults.ai_recovery.recovered_inr)}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Recovery Rate (INR)</td>
                            <td className="py-3 font-semibold text-white">{evalResults.baseline.recovery_rate_inr.toFixed(1)}%</td>
                            <td className="py-3 font-bold text-emerald-400">{evalResults.ai_recovery.recovery_rate_inr.toFixed(1)}%</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Recovered Cases</td>
                            <td className="py-3 font-semibold text-white">{evalResults.baseline.recovered_cases} / {evalResults.cases_run}</td>
                            <td className="py-3 font-bold text-emerald-400">{evalResults.ai_recovery.recovered_cases} / {evalResults.cases_run}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Recovery Attempt Overhead<br/><span className="text-[10px] text-gray-500">(Total Attempts / Recovered Cases)</span></td>
                            <td className="py-3 font-semibold text-white">{evalResults.baseline.recovery_attempt_overhead.toFixed(2)}</td>
                            <td className="py-3 font-semibold text-brand-400">{evalResults.ai_recovery.recovery_attempt_overhead.toFixed(2)}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Average Attempts per Case<br/><span className="text-[10px] text-gray-500">(Total Attempts / Total Cases)</span></td>
                            <td className="py-3 font-semibold text-white">{evalResults.baseline.avg_attempts_per_case.toFixed(2)}</td>
                            <td className="py-3 font-semibold text-brand-400">{evalResults.ai_recovery.avg_attempts_per_case.toFixed(2)}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Unnecessary Retry Rate</td>
                            <td className="py-3 font-semibold text-rose-400">{evalResults.baseline.unnecessary_retry_rate.toFixed(1)}%</td>
                            <td className="py-3 font-semibold text-emerald-400">{evalResults.ai_recovery.unnecessary_retry_rate.toFixed(1)}%</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Operational Recovery Cost</td>
                            <td className="py-3 font-semibold text-white">{formatCurrency(evalResults.baseline.operational_recovery_cost)}</td>
                            <td className="py-3 font-semibold text-brand-400">{formatCurrency(evalResults.ai_recovery.operational_recovery_cost)}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">False-Positive Cost<br/><span className="text-[10px] text-gray-500">(Cost of incorrect interventions)</span></td>
                            <td className="py-3 font-semibold text-rose-400">{formatCurrency(evalResults.baseline.false_positive_cost)}</td>
                            <td className="py-3 font-semibold text-emerald-400">{formatCurrency(evalResults.ai_recovery.false_positive_cost)}</td>
                          </tr>
                          <tr>
                            <td className="py-3 font-medium text-gray-300">Avg. Time to Recovery</td>
                            <td className="py-3 font-semibold text-white">{evalResults.baseline.avg_time_to_recovery_hours.toFixed(1)} hrs</td>
                            <td className="py-3 font-semibold text-brand-400">{evalResults.ai_recovery.avg_time_to_recovery_hours.toFixed(1)} hrs</td>
                          </tr>
                        </tbody>
                      </table>
                      <div className="mt-4 pt-4 border-t border-slate-850 space-y-3">
                        <div className="flex justify-between text-[10px] text-gray-500 font-mono">
                          <span>Dataset: {evalResults.dataset_size} synthetic cases</span>
                          <span>Seed: {evalResults.random_seed}</span>
                        </div>
                        <div className="text-[10px] text-gray-500 font-mono">
                          <span>Execution Mode: {evalResults.execution_mode}</span>
                        </div>
                        <p className="text-[10px] text-gray-400 leading-relaxed bg-slate-900/30 p-2.5 rounded border border-slate-850">
                          <strong>Benchmark note:</strong> The default offline evaluation uses a deterministic rule-based fallback for reproducible results. When an LLM API key is configured, the same evaluation pipeline can evaluate live LLM decisions. Ground-truth labels are used only after decisions are generated for scoring.
                        </p>
                      </div>
                    </div>

                    {/* ACCURACY BAR CHARTS */}
                    <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
                      <div>
                        <h4 className="text-xs font-bold text-gray-400 tracking-wider uppercase mb-1">AI Classification Accuracy</h4>
                        <p className="text-[10px] text-gray-500">Comparing AI output with independent ground truth labels</p>
                      </div>
                      
                      <div className="space-y-6 my-auto pt-6">
                        <div>
                          <div className="flex justify-between text-xs font-semibold mb-1">
                            <span>AI Diagnosis Accuracy</span>
                            <span className="text-indigo-400">{evalResults.ai_recovery.diagnosis_accuracy.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
                            <div className="bg-indigo-500 h-full rounded-full" style={{ width: `${evalResults.ai_recovery.diagnosis_accuracy}%` }}></div>
                          </div>
                        </div>

                        <div>
                          <div className="flex justify-between text-xs font-semibold mb-1">
                            <span>Action-Selection Accuracy</span>
                            <span className="text-emerald-400">{evalResults.ai_recovery.action_accuracy.toFixed(1)}%</span>
                          </div>
                          <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden border border-slate-800">
                            <div className="bg-emerald-500 h-full rounded-full" style={{ width: `${evalResults.ai_recovery.action_accuracy}%` }}></div>
                          </div>
                        </div>
                      </div>

                      <div className="bg-slate-900/50 p-3 rounded-lg border border-slate-800 text-xs text-gray-400 leading-relaxed mt-4">
                        <strong className="text-white block mb-0.5">Key Advantage:</strong>
                        AI Revenue Recovery reaches <span className="text-emerald-400 font-semibold">{evalResults.ai_recovery.recovery_rate_inr.toFixed(0)}% recovery</span> compared to baseline's <span className="text-gray-300 font-semibold">{evalResults.baseline.recovery_rate_inr.toFixed(0)}%</span>, while eliminating retries on dead endpoints like expired cards.
                      </div>
                    </div>

                  </div>

                </div>
              ) : (
                <div className="bg-[#0b0f19] border border-slate-800 rounded-xl p-12 text-center text-xs text-gray-500">
                  <BarChart3 className="h-8 w-8 mx-auto text-slate-700 mb-2" />
                  Click "Run Evaluator Loop" to compile recovery metrics and comparative analytics.
                </div>
              )}

            </div>
          )}

        </div>
      </main>

    </div>
  );
}

// Minimal state set representation helper
const StateMachine = {
  TERMINAL_STATES: new Set(['RECOVERED', 'MAX_ATTEMPTS', 'EXPIRED', 'CUSTOMER_DECLINED', 'DISPUTED', 'CANCELLED', 'ESCALATED'])
};
