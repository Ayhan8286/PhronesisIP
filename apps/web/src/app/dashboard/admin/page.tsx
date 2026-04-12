"use client";

import React, { useEffect, useState } from 'react';
import { 
  ShieldAlert, 
  Activity, 
  TrendingUp, 
  RefreshCcw, 
  AlertTriangle, 
  CheckCircle2, 
  Users,
  Building2,
  DollarSign,
  Cpu,
  MousePointer2
} from 'lucide-react';
import { useAuth } from '@clerk/nextjs';
import { apiFetch } from '@/lib/api';
import { 
  AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts';

interface Incident {
  id: string;
  level: string;
  source: string;
  message: string;
  details: any;
  is_resolved: boolean;
  created_at: string;
}

interface FailedWorkflow {
  id: string;
  firm: string;
  type: string;
  created_at: string;
}

interface Economics {
  cumulative: {
    cost_usd: number;
    tokens_in: number;
    tokens_out: number;
  };
  top_consumers_30d: Array<{ firm: string; cost: number }>;
  trend: Array<{ name: string; cost: number }>;
}

interface UsageStat {
  action: string;
  count: number;
}

export default function AdminDashboard() {
  const { getToken } = useAuth();
  const [loading, setLoading] = useState(true);
  const [incidents, setIncidents] = useState<Incident[]>([]);
  const [workflows, setWorkflows] = useState<FailedWorkflow[]>([]);
  const [economics, setEconomics] = useState<Economics | null>(null);
  const [usageStats, setUsageStats] = useState<UsageStat[]>([]);
  const [growth, setGrowth] = useState<any>(null);
  const [retryingIds, setRetryingIds] = useState<Set<string>>(new Set());

  const fetchData = async () => {
    try {
      const token = await getToken();
      const headers = { Authorization: `Bearer ${token}` };
      
      const [incRes, workRes, econRes, usageRes, growthRes] = await Promise.all([
        apiFetch<Incident[]>('/api/v1/admin/incidents', { headers, token: token ?? undefined }),
        apiFetch<FailedWorkflow[]>('/api/v1/admin/monitoring/failed-workflows', { headers, token: token ?? undefined }),
        apiFetch<Economics>('/api/v1/admin/economics', { headers, token: token ?? undefined }),
        apiFetch<UsageStat[]>('/api/v1/admin/analytics/usage', { headers, token: token ?? undefined }),
        apiFetch<any>('/api/v1/admin/analytics/growth', { headers, token: token ?? undefined })
      ]);

      if (incRes) setIncidents(incRes);
      if (workRes) setWorkflows(workRes);
      if (econRes) setEconomics(econRes);
      if (usageRes) setUsageStats(usageRes);
      if (growthRes) setGrowth(growthRes);
    } catch (err) {
      console.error("Failed to load admin data", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000); 
    return () => clearInterval(interval);
  }, []);

  const handleRetry = async (id: string) => {
    setRetryingIds(prev => new Set(prev).add(id));
    try {
      const token = await getToken();
      await apiFetch(`/api/v1/admin/workflows/${id}/retry`, { 
        method: 'POST', 
        token: token ?? undefined 
      });
      await fetchData();
    } catch (err) {
      alert("Retry failed");
    } finally {
      setRetryingIds(prev => {
        const next = new Set(prev);
        next.delete(id);
        return next;
      });
    }
  };

  if (loading && !economics) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-indigo-500"></div>
      </div>
    );
  }

  return (
    <div className="p-8 space-y-8 max-w-[1600px] mx-auto animate-in fade-in duration-700 overflow-y-auto h-full">
      {/* HEADER */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-3">
            <ShieldAlert className="text-indigo-400 w-8 h-8" />
            Platform Control Center
          </h1>
          <p className="text-slate-400 mt-1">Real-time infrastructure health and economic telemetry</p>
        </div>
        <div className="flex items-center gap-2 px-3 py-1 bg-green-500/10 border border-green-500/20 rounded-full h-fit">
          <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
          <span className="text-xs font-medium text-green-400 uppercase tracking-wider">System Live</span>
        </div>
      </div>

      {/* TOP KPls */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Live Model Cost" 
          value={`$${economics?.cumulative.cost_usd.toFixed(2) || '0.00'}`} 
          subValue="Total Cloud Spend"
          icon={<DollarSign className="w-5 h-5 text-emerald-400" />}
        />
        <StatCard 
          title="Token Throughput" 
          value={`${((economics?.cumulative.tokens_in || 0) + (economics?.cumulative.tokens_out || 0)).toLocaleString()}`} 
          subValue="In/Out Combined"
          icon={<Cpu className="w-5 h-5 text-blue-400" />}
        />
        <StatCard 
          title="Active Firms" 
          value={growth?.total_firms || 0} 
          subValue="Onboarded Entities"
          icon={<Building2 className="w-5 h-5 text-purple-400" />}
        />
        <StatCard 
          title="System Load" 
          value={growth?.active_last_24h || 0} 
          subValue="Users Active (24h)"
          icon={<Users className="w-5 h-5 text-orange-400" />}
        />
      </div>

      {/* MAIN ANALYTICS GRID */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Cost Trend Chart */}
        <div className="lg:col-span-2 bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6 min-h-[400px] flex flex-col">
          <div className="flex items-center justify-between mb-8">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-indigo-400" />
              Operational Cost Trend
            </h3>
            <span className="text-xs text-slate-500">Past 7 Days</span>
          </div>
          <div className="flex-1 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={economics?.trend || []}>
                <defs>
                  <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" vertical={false} />
                <XAxis dataKey="name" stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} />
                <YAxis stroke="#64748b" fontSize={12} tickLine={false} axisLine={false} tickFormatter={(val) => `$${val}`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '8px', color: '#fff' }}
                />
                <Area type="monotone" dataKey="cost" stroke="#6366f1" fillOpacity={1} fill="url(#colorCost)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Feature Usage Analytics */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6 flex flex-col">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <MousePointer2 className="w-5 h-5 text-pink-400" />
            Top Features Used
          </h3>
          <div className="space-y-4 flex-1 overflow-y-auto">
            {usageStats.map((stat, idx) => (
              <div key={idx} className="group cursor-default">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm text-slate-300 group-hover:text-white transition-colors capitalize">
                    {stat.action.replace(/_/g, ' ')}
                  </span>
                  <span className="text-xs font-mono text-slate-500">{stat.count} calls</span>
                </div>
                <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                  <div 
                    className="bg-indigo-500 h-full rounded-full transition-all duration-1000"
                    style={{ width: `${Math.min(100, (stat.count / (usageStats[0]?.count || 1)) * 100)}%` }}
                  />
                </div>
              </div>
            ))}
            {usageStats.length === 0 && <p className="text-slate-500 text-sm text-center py-8">No usage data logged yet.</p>}
          </div>
        </div>
      </div>

      {/* OPERATIONAL RECOVERY & INCIDENTS */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 pb-12">
        
        {/* Failed Workflows - Actionable */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-lg font-semibold text-white flex items-center gap-2">
              <RefreshCcw className="w-5 h-5 text-orange-400" />
              Failed Analysis Workflows
            </h3>
            <span className={`px-2 py-0.5 text-xs font-bold rounded uppercase ${
              workflows.length > 0 ? 'bg-red-500/10 text-red-500' : 'bg-green-500/10 text-green-500'
            }`}>
              {workflows.length > 0 ? `${workflows.length} Action Needed` : 'Clean'}
            </span>
          </div>
          
          <div className="space-y-3 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            {workflows.map((wf) => (
              <div key={wf.id} className="flex items-center justify-between p-4 bg-white/5 rounded-xl border border-white/5 hover:border-white/10 transition-all">
                <div className="flex flex-col">
                  <span className="text-sm font-medium text-white">{wf.firm}</span>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-slate-500 uppercase">{wf.type}</span>
                    <span className="text-xs text-slate-600">•</span>
                    <span className="text-xs text-slate-500">{new Date(wf.created_at).toLocaleDateString()}</span>
                  </div>
                </div>
                <button 
                  onClick={() => handleRetry(wf.id)}
                  disabled={retryingIds.has(wf.id)}
                  className="p-2 bg-indigo-500/10 hover:bg-indigo-500/20 text-indigo-400 rounded-lg transition-colors disabled:opacity-50"
                  title="Retry Analysis"
                >
                  <RefreshCcw className={`w-4 h-4 ${retryingIds.has(wf.id) ? 'animate-spin' : ''}`} />
                </button>
              </div>
            ))}
            {workflows.length === 0 && (
              <div className="flex flex-col items-center justify-center py-12 text-slate-500">
                <CheckCircle2 className="w-12 h-12 text-green-500/20 mb-3" />
                <p>All background jobs running smoothly</p>
              </div>
            )}
          </div>
        </div>

        {/* Incident Feed */}
        <div className="bg-slate-900/50 backdrop-blur-xl border border-white/5 rounded-2xl p-6">
          <h3 className="text-lg font-semibold text-white mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-rose-400" />
            Live Incident Feed
          </h3>
          <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2 custom-scrollbar">
            {incidents.map((incident) => (
              <div key={incident.id} className="flex gap-4 p-4 bg-white/5 rounded-xl border-l-4 border-l-rose-500/50">
                <div className={`mt-1 p-1.5 rounded-full h-fit ${
                  incident.level === 'CRITICAL' ? 'bg-red-500/20 text-red-400' : 'bg-orange-500/20 text-orange-400'
                }`}>
                  <AlertTriangle className="w-4 h-4" />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex justify-between items-start mb-1">
                    <h4 className="text-sm font-semibold text-white truncate">{incident.source}</h4>
                    <span className="text-[10px] text-slate-500 whitespace-nowrap">{new Date(incident.created_at).toLocaleTimeString()}</span>
                  </div>
                  <p className="text-xs text-slate-400 line-clamp-2">{incident.message}</p>
                </div>
              </div>
            ))}
            {incidents.length === 0 && (
              <p className="text-slate-500 text-sm text-center py-12">No recent platform incidents.</p>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

function StatCard({ title, value, subValue, icon }: { title: string, value: string | number, subValue: string, icon: React.ReactNode }) {
  return (
    <div className="bg-slate-900/50 backdrop-blur-xl border border-white/5 p-6 rounded-2xl hover:border-white/10 transition-all pointer-events-none flex flex-col justify-between">
      <div className="flex justify-between items-start mb-4">
        <div className="p-2 bg-indigo-500/10 rounded-lg">
          {icon}
        </div>
      </div>
      <div>
        <h4 className="text-slate-500 text-sm font-medium">{title}</h4>
        <div className="text-2xl font-bold text-white mt-1 tabular-nums">
          {value}
        </div>
        <p className="text-[10px] text-slate-500 mt-1 uppercase tracking-wider">{subValue}</p>
      </div>
    </div>
  );
}
