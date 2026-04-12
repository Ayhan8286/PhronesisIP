"use client";

import React, { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { 
  Activity, 
  ShieldCheck, 
  Database, 
  Zap, 
  AlertTriangle, 
  TrendingUp, 
  Users, 
  Building2,
  RefreshCw,
  Clock,
  CheckCircle2,
  AlertCircle,
  Play,
  ClipboardList
} from "lucide-react";
import { 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  ResponsiveContainer,
  AreaChart,
  Area
} from "recharts";

import { apiFetch } from "@/lib/api";

interface HealthData {
  status: string;
  timestamp: string;
  services: {
    database: string;
    inngest_connection: string;
    storage_r2: string;
  };
  incidents_24h: number;
}

interface EconomicData {
  cumulative: {
    cost_usd: number;
    tokens_in: number;
    tokens_out: number;
  };
  top_consumers_30d: { firm: string; cost: number }[];
}

interface Incident {
  id: string;
  level: string;
  source: string;
  message: string;
  details: string;
  is_resolved: boolean;
  created_at: string;
}

interface FailedWorkflow {
  id: string;
  firm: string;
  type: string;
  created_at: string;
}

export default function AdminDashboard() {
  const { getToken, isLoaded } = useAuth();
  const [health, setHealth] = useState<HealthData | null>(null);
  const [economics, setEconomics] = useState<EconomicData | null>(null);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [failedWorkflows, setFailedWorkflows] = useState<FailedWorkflow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [retryingId, setRetryingId] = useState<string | null>(null);

  const fetchData = async () => {
    try {
      setLoading(true);
      const token = await getToken();
      if (!token) throw new Error("No authentication token");

      const [healthRes, econRes, incRes, failRes] = await Promise.all([
        apiFetch<HealthData>("/api/v1/admin/health", { token: token ?? undefined }),
        apiFetch<EconomicData>("/api/v1/admin/economics", { token: token ?? undefined }),
        apiFetch<Incident[]>("/api/v1/admin/incidents", { token: token ?? undefined }),
        apiFetch<FailedWorkflow[]>("/api/v1/admin/monitoring/failed-workflows", { token: token ?? undefined })
      ]);

      setHealth(healthRes);
      setEconomics(econRes);
      setIncidents(incRes);
      setFailedWorkflows(failRes);
      setError(null);
    } catch (err: any) {
      setError(err.message || "Failed to load admin telemetry");
    } finally {
      setLoading(false);
    }
  };

  const handleRetry = async (id: string) => {
    try {
      setRetryingId(id);
      const token = await getToken();
      await apiFetch(`/api/v1/admin/workflows/${id}/retry`, { 
        method: "POST",
        token: token ?? undefined
      });
      // Refresh failed workflows list
      const failRes = await apiFetch<FailedWorkflow[]>("/api/v1/admin/monitoring/failed-workflows", { token: token ?? undefined });
      setFailedWorkflows(failRes);
    } catch (err: any) {
      alert(`Retry failed: ${err.message}`);
    } finally {
      setRetryingId(null);
    }
  };

  useEffect(() => {
    if (isLoaded) {
      fetchData();
    }
  }, [isLoaded]);

  if (loading && !health) {
    return (
      <div className="flex items-center justify-center min-h-[400px] text-white">
        <RefreshCw className="w-8 h-8 animate-spin text-indigo-500" />
      </div>
    );
  }

  return (
    <div className="page-content bg-[#0a0a0f] text-slate-200 p-8 font-sans">
      {/* Header */}
      <header className="flex justify-between items-center mb-10">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-white to-slate-500 bg-clip-text text-transparent">
            Platform Recovery Suite
          </h1>
          <p className="text-slate-500 mt-1 flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-500" />
            System Administrator Control Panel
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="px-4 py-2 bg-[#111118] rounded-full border border-slate-800 flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full animate-pulse ${health?.status === 'healthy' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
            <span className="text-xs font-semibold uppercase tracking-wider">
              {health?.status === 'healthy' ? 'Platform Normal' : 'Action Required'}
            </span>
          </div>
          <button 
            onClick={fetchData} 
            className="p-2 hover:bg-slate-800 rounded-lg transition-colors bg-[#111118] border border-slate-800"
          >
            <RefreshCw className="w-5 h-5 text-slate-400" />
          </button>
        </div>
      </header>

      {/* Main Grid */}
      <div className="grid grid-cols-1 xl:grid-cols-4 gap-8">
        
        {/* Left Column: Telemetry & Recovery */}
        <div className="xl:col-span-3 space-y-8">
          
          {/* Infrastructure Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <StatusCard 
              icon={<Database className="w-5 h-5 text-indigo-400" />}
              label="Persistence"
              value={health?.services.database === 'online' ? "Healthy" : "Failed"}
              status={health?.services.database === 'online' ? 'success' : 'error'}
            />
            <StatusCard 
              icon={<Zap className="w-5 h-5 text-amber-400" />}
              label="Job Engine"
              value="Idle"
              status="success"
            />
            <StatusCard 
              icon={<TrendingUp className="w-5 h-5 text-emerald-400" />}
              label="Economics"
              value={`$${economics?.cumulative.cost_usd.toFixed(2)}`}
              status="success"
            />
            <StatusCard 
              icon={<AlertTriangle className="w-5 h-5 text-rose-400" />}
              label="Alerts"
              value={`${incidents.filter(i => !i.is_resolved).length} Unresolved`}
              status={incidents.filter(i => !i.is_resolved).length === 0 ? 'success' : 'warning'}
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            {/* Economic Chart */}
            <div className="bg-[#111118] border border-slate-800 rounded-2xl p-6 shadow-2xl">
              <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
                <TrendingUp className="w-4 h-4" /> Usage Velocity (Global)
              </h3>
              <div className="h-[250px] w-full">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={mockChartData}>
                    <defs>
                      <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                        <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" vertical={false} />
                    <XAxis dataKey="name" stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                    <YAxis stroke="#64748b" fontSize={10} tickLine={false} axisLine={false} />
                    <Tooltip 
                      contentStyle={{ backgroundColor: '#0a0a0f', border: '1px solid #1e293b', borderRadius: '8px' }}
                      itemStyle={{ color: '#f1f5f9', fontSize: '12px' }}
                    />
                    <Area type="monotone" dataKey="cost" stroke="#6366f1" fillOpacity={1} fill="url(#colorCost)" strokeWidth={2} />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            {/* Recovery Module: Failed Workflows */}
            <div className="bg-[#111118] border border-slate-800 rounded-2xl p-6 shadow-2xl overflow-hidden">
              <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
                <Clock className="w-4 h-4" /> Analysis Recovery Suite
              </h3>
              
              <div className="space-y-4 max-h-[250px] overflow-y-auto pr-2 custom-scrollbar">
                {failedWorkflows.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-10 text-slate-600">
                    <CheckCircle2 className="w-8 h-8 mb-2 opacity-20" />
                    <span className="text-xs">No failed analysis jobs detected</span>
                  </div>
                ) : (
                  failedWorkflows.map((w) => (
                    <div key={w.id} className="flex items-center justify-between p-3 bg-[#0a0a0f] border border-slate-800 rounded-xl group hover:border-indigo-500/50 transition-all">
                      <div>
                        <p className="text-xs font-bold text-white mb-0.5">{w.firm}</p>
                        <p className="text-[10px] text-slate-500 uppercase">{w.type} • {new Date(w.created_at).toLocaleDateString()}</p>
                      </div>
                      <button 
                        onClick={() => handleRetry(w.id)}
                        disabled={retryingId === w.id}
                        className="p-2 bg-indigo-500/10 text-indigo-400 rounded-lg hover:bg-indigo-500 hover:text-white transition-all disabled:opacity-50"
                      >
                        {retryingId === w.id ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>

          {/* User & Firm Growth Table */}
          <div className="bg-[#111118] border border-slate-800 rounded-2xl p-6 shadow-2xl">
             <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
                <Building2 className="w-4 h-4" /> Firm Onboarding Metrics
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
                <div className="p-4 bg-[#0a0a0f] rounded-xl border border-slate-800">
                  <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Total Firms</p>
                  <p className="text-2xl font-black text-white italic tracking-tighter">42</p>
                </div>
                <div className="p-4 bg-[#0a0a0f] rounded-xl border border-slate-800">
                  <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Total Attorneys</p>
                  <p className="text-2xl font-black text-white italic tracking-tighter">184</p>
                </div>
                <div className="p-4 bg-[#0a0a0f] rounded-xl border border-slate-800">
                  <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Analyses Run</p>
                  <p className="text-2xl font-black text-white italic tracking-tighter">1.2k</p>
                </div>
                <div className="p-4 bg-[#0a0a0f] rounded-xl border border-slate-800">
                  <p className="text-[10px] uppercase text-slate-500 font-bold mb-1">Active Firms (24h)</p>
                  <p className="text-2xl font-black text-emerald-500 italic tracking-tighter">12</p>
                </div>
              </div>
          </div>

        </div>

        {/* Right Column: Incident Feed */}
        <div className="bg-[#111118] border border-slate-800 rounded-2xl p-6 shadow-2xl flex flex-col h-full max-h-[800px]">
          <h3 className="text-sm font-bold text-slate-500 uppercase tracking-widest mb-6 flex items-center gap-2">
            <ClipboardList className="w-4 h-4" /> System Incident Feed
          </h3>
          
          <div className="flex-1 overflow-y-auto space-y-4 custom-scrollbar pr-2">
            {incidents.length === 0 ? (
              <div className="text-center py-20 opacity-30 text-xs italic">
                No incidents reported
              </div>
            ) : (
              incidents.map((inc) => (
                <div key={inc.id} className={`p-4 rounded-xl border leading-relaxed ${
                  inc.level === 'critical' ? 'bg-rose-500/5 border-rose-500/20' : 
                  inc.level === 'warning' ? 'bg-amber-500/5 border-amber-500/20' : 
                  'bg-slate-500/5 border-slate-800'
                }`}>
                  <div className="flex items-center gap-2 mb-2">
                    {inc.level === 'critical' ? <AlertCircle className="w-4 h-4 text-rose-500" /> : <AlertTriangle className="w-4 h-4 text-amber-500" />}
                    <span className={`text-[10px] font-black uppercase tracking-widest ${
                       inc.level === 'critical' ? 'text-rose-400' : 'text-amber-400'
                    }`}>{inc.level}</span>
                    <span className="text-[10px] text-slate-600 ml-auto">{new Date(inc.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-xs font-bold text-white mb-1">{inc.message}</p>
                  <p className="text-[11px] text-slate-400 line-clamp-2">{inc.details}</p>
                </div>
              ))
            )}
          </div>

          <div className="mt-6 pt-6 border-t border-slate-800">
            <div className="p-4 bg-slate-900/50 rounded-xl border border-slate-800">
               <p className="text-[10px] uppercase text-slate-500 font-bold mb-3 flex items-center gap-2">
                 <RefreshCw className="w-3 h-3" /> Auto-Recovery Status
               </p>
               <div className="flex items-center gap-2">
                 <div className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                 <span className="text-xs font-medium">Watchdog Heartbeat OK</span>
               </div>
            </div>
          </div>
        </div>

      </div>
    </div>
  );
}

function StatusCard({ icon, label, value, status }: { icon: React.ReactNode, label: string, value: string, status: 'success' | 'warning' | 'error' }) {
  return (
    <div className="bg-[#111118] border border-slate-800 rounded-2xl p-4 shadow-lg hover:border-slate-700 transition-all">
      <div className="flex items-center gap-3 mb-3">
        <div className="p-1.5 bg-[#0a0a0f] rounded-lg border border-slate-800">{icon}</div>
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest">{label}</span>
      </div>
      <div className="flex items-center gap-2">
        <div className={`w-1 h-1 rounded-full ${status === 'success' ? 'bg-emerald-500' : status === 'warning' ? 'bg-amber-500' : 'bg-rose-500'}`} />
        <span className="text-lg font-black text-white italic tracking-tighter">{value}</span>
      </div>
    </div>
  );
}

const mockChartData = [
  { name: 'Mon', cost: 120 },
  { name: 'Tue', cost: 450 },
  { name: 'Wed', cost: 320 },
  { name: 'Thu', cost: 890 },
  { name: 'Fri', cost: 640 },
  { name: 'Sat', cost: 230 },
  { name: 'Sun', cost: 550 },
];
