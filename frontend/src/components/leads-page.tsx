"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Listing, LeadsResponse, STATUS_COLORS, STATUS_LABELS } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";

export function LeadsPage() {
  const [leads, setLeads] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("all");
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sortBy, setSortBy] = useState("match_score");

  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true);
      let path = `/api/v1/leads?sort_by=${sortBy}&sort_dir=desc&per_page=50`;
      if (statusFilter !== "all") path += `&status=${statusFilter}`;
      if (sourceFilter !== "all") path += `&source=${sourceFilter}`;
      const data = await api.get<LeadsResponse>(path);
      setLeads(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to fetch leads", e);
    } finally {
      setLoading(false);
    }
  }, [statusFilter, sourceFilter, sortBy]);

  useEffect(() => { fetchLeads(); }, [fetchLeads]);

  const updateStatus = async (id: number, status: string) => {
    await api.patch(`/api/v1/leads/${id}/status`, { status });
    fetchLeads();
  };

  const triggerTour = async (id: number) => {
    await api.post(`/api/v1/leads/${id}/tour`);
    fetchLeads();
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Hot Leads ({total})</h1>
        <Button variant="outline" onClick={fetchLeads} disabled={loading}>
          {loading ? "Loading..." : "Refresh"}
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <Select value={statusFilter} onValueChange={(v) => v && setStatusFilter(v)}>
          <SelectTrigger className="w-[160px]"><SelectValue placeholder="Status" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.entries(STATUS_LABELS).map(([val, label]) => (
              <SelectItem key={val} value={val}>{label}</SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={sourceFilter} onValueChange={(v) => v && setSourceFilter(v)}>
          <SelectTrigger className="w-[160px]"><SelectValue placeholder="Source" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Sources</SelectItem>
            <SelectItem value="streeteasy">StreetEasy</SelectItem>
            <SelectItem value="zillow">Zillow</SelectItem>
          </SelectContent>
        </Select>

        <Select value={sortBy} onValueChange={(v) => v && setSortBy(v)}>
          <SelectTrigger className="w-[160px]"><SelectValue placeholder="Sort by" /></SelectTrigger>
          <SelectContent>
            <SelectItem value="match_score">Score</SelectItem>
            <SelectItem value="price">Price</SelectItem>
            <SelectItem value="commute_minutes">Commute</SelectItem>
            <SelectItem value="first_seen">Date Found</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Leads list */}
      <div className="space-y-3">
        {leads.map((lead) => (
          <LeadCard
            key={lead.id}
            lead={lead}
            onTour={() => triggerTour(lead.id)}
            onPass={() => updateStatus(lead.id, "passed")}
          />
        ))}
        {!loading && leads.length === 0 && (
          <Card className="p-8 text-center text-gray-500">
            No leads found. The scraper runs every 6 hours — check back soon!
          </Card>
        )}
      </div>
    </div>
  );
}

function LeadCard({ lead, onTour, onPass }: { lead: Listing; onTour: () => void; onPass: () => void }) {
  const statusClass = STATUS_COLORS[lead.status] || "bg-gray-100 text-gray-600";

  return (
    <Card className="p-4">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        {/* Score */}
        <div className="flex-shrink-0 w-14 h-14 rounded-full bg-gray-900 text-white flex items-center justify-center font-bold text-lg">
          {lead.match_score ?? "?"}
        </div>

        {/* Details */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold truncate">{lead.address || lead.title || "Unknown address"}</h3>
            <Badge className={statusClass}>{STATUS_LABELS[lead.status] || lead.status}</Badge>
            <Badge variant="outline" className="text-xs">{lead.source}</Badge>
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-600 mt-1 flex-wrap">
            {lead.price && <span className="font-semibold text-gray-900">${lead.price.toLocaleString()}/mo</span>}
            {lead.beds && <span>{lead.beds}BR</span>}
            {lead.baths && <span>{lead.baths}BA</span>}
            {lead.sqft && <span>{lead.sqft.toLocaleString()} sqft</span>}
            {lead.commute_minutes && <span>🚇 {lead.commute_minutes} min</span>}
            {lead.neighborhood && <span>📍 {lead.neighborhood}</span>}
          </div>
          {lead.amenities.length > 0 && (
            <div className="flex gap-1 mt-1 flex-wrap">
              {lead.amenities.slice(0, 5).map((a) => (
                <span key={a} className="text-xs bg-gray-100 px-2 py-0.5 rounded">{a}</span>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex gap-2 flex-shrink-0">
          <a href={lead.url} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">View</Button>
          </a>
          {lead.status !== "tour_scheduled" && lead.status !== "passed" && (
            <Button size="sm" onClick={onTour} className="bg-green-600 hover:bg-green-700">
              Tour
            </Button>
          )}
          {lead.status !== "passed" && (
            <Button variant="ghost" size="sm" onClick={onPass} className="text-gray-500">
              Pass
            </Button>
          )}
        </div>
      </div>
      {lead.broker_email_sent && (
        <div className="mt-2 text-xs text-green-600">✅ Broker email sent</div>
      )}
    </Card>
  );
}
