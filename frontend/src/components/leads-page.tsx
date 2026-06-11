"use client";

import { useEffect, useState, useCallback } from "react";
import { api } from "@/lib/api";
import { Listing, LeadsResponse, STATUS_COLORS, STATUS_LABELS } from "@/lib/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";

export function LeadsPage() {
  const [leads, setLeads] = useState<Listing[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("all");
  const [scraping, setScraping] = useState(false);
  const [submitUrl, setSubmitUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitResult, setSubmitResult] = useState<{ ok?: boolean; error?: string } | null>(null);
  const [emailPreview, setEmailPreview] = useState<{ listingId: number; subject: string; body: string; brokerEmail: string } | null>(null);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [noOhDialog, setNoOhDialog] = useState(false);
  const [sourceFilter, setSourceFilter] = useState("all");
  const [sortBy, setSortBy] = useState("match_score");

  const fetchLeads = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      let path = `/api/v1/leads?sort_by=${sortBy}&sort_dir=desc&per_page=50`;
      if (statusFilter !== "all") path += `&status=${statusFilter}`;
      if (sourceFilter !== "all") path += `&source=${sourceFilter}`;
      const data = await api.get<LeadsResponse>(path);
      setLeads(data.items);
      setTotal(data.total);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "Failed to connect";
      setError(msg);
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

  const openEmailPreview = async (listingId: number) => {
    try {
      const res = await api.post<{ subject: string; body: string; broker_email: string }>(`/api/v1/leads/${listingId}/preview-email`);
      setEmailPreview({ listingId, subject: res.subject, body: res.body, brokerEmail: res.broker_email });
    } catch (e) {
      console.error("Failed to load preview", e);
    }
  };

  const sendPreviewEmail = async () => {
    if (!emailPreview) return;
    setSendingEmail(true);
    try {
      // Save broker email to listing first
      if (emailPreview.brokerEmail) {
        await api.patch(`/api/v1/leads/${emailPreview.listingId}/status`, {
          broker_email: emailPreview.brokerEmail,
        });
      }
      await api.post(`/api/v1/leads/${emailPreview.listingId}/send-email`, {
        subject: emailPreview.subject,
        body: emailPreview.body,
      });
      setEmailPreview(null);
      fetchLeads();
    } catch (e) {
      console.error("Failed to send", e);
    }
    setSendingEmail(false);
  };

  const triggerScrape = async () => {
    setScraping(true);
    try {
      await api.post("/api/v1/leads/trigger-scrape");
      setTimeout(() => { fetchLeads(); setScraping(false); }, 5000);
    } catch (e) {
      setScraping(false);
    }
  };

  const handleSubmitUrl = async () => {
    if (!submitUrl.trim()) return;
    setSubmitting(true);
    setSubmitResult(null);
    try {
      const res = await api.post<{ ok?: boolean; error?: string; listing?: Listing }>("/api/v1/leads/submit-url", { url: submitUrl.trim() });
      if (res.error) {
        setSubmitResult({ error: res.error });
      } else {
        setSubmitResult({ ok: true });
        setSubmitUrl("");
        fetchLeads();
      }
    } catch (e) {
      setSubmitResult({ error: e instanceof Error ? e.message : "Failed to submit" });
    }
    setSubmitting(false);
  };

  return (
    <div>
      {/* URL Submission */}
      <Card className="p-4 mb-6">
        <h2 className="text-sm font-semibold mb-2">Add a listing manually</h2>
        <div className="flex gap-2">
          <Input
            placeholder="Paste a StreetEasy or Zillow listing URL..."
            value={submitUrl}
            onChange={(e) => setSubmitUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !submitting && handleSubmitUrl()}
            disabled={submitting}
            className="flex-1"
          />
          <Button onClick={handleSubmitUrl} disabled={submitting || !submitUrl.trim()}>
            {submitting ? "Scraping..." : "Add Listing"}
          </Button>
        </div>
        {submitting && (
          <p className="text-xs text-gray-500 mt-2">Scraping listing details — this may take 10-30 seconds...</p>
        )}
        {submitResult?.error && (
          <p className="text-xs text-red-600 mt-2">{submitResult.error}</p>
        )}
        {submitResult?.ok && (
          <p className="text-xs text-green-600 mt-2">Listing added and scored! Check below and your Telegram for the alert.</p>
        )}
      </Card>

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Hot Leads ({total})</h1>
        <div className="flex gap-2">
          <Button variant="outline" onClick={triggerScrape} disabled={scraping}>
            {scraping ? "Scraping..." : "Run Scrape"}
          </Button>
          <Button variant="outline" onClick={fetchLeads} disabled={loading}>
            {loading ? "Loading..." : "Refresh"}
          </Button>
        </div>
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

      {error && (
        <Card className="p-6 mb-4 border-yellow-200 bg-yellow-50">
          <p className="font-medium text-yellow-800">Backend not connected</p>
          <p className="text-sm text-yellow-600 mt-1">{error}</p>
          <Button variant="outline" size="sm" className="mt-3" onClick={fetchLeads}>Retry</Button>
        </Card>
      )}

      {/* Leads list */}
      <div className="space-y-3">
        {leads.map((lead) => (
          <LeadCard
            key={lead.id}
            lead={lead}
            onEmailPreview={() => openEmailPreview(lead.id)}
            onTour={() => triggerTour(lead.id)}
            onPass={() => updateStatus(lead.id, "passed")}
            onNoOpenHouse={() => setNoOhDialog(true)}
          />
        ))}
        {!loading && leads.length === 0 && (
          <Card className="p-8 text-center text-gray-500">
            No leads found. The scraper runs every 6 hours — check back soon!
          </Card>
        )}
      </div>

      {/* Email Preview Dialog */}
      <Dialog open={!!emailPreview} onOpenChange={(open) => !open && setEmailPreview(null)}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Preview Broker Email</DialogTitle>
          </DialogHeader>
          {emailPreview && (
            <div className="space-y-4">
              <div>
                <Label className="text-sm">To (broker email)</Label>
                <Input
                  value={emailPreview.brokerEmail}
                  onChange={(e) => setEmailPreview({ ...emailPreview, brokerEmail: e.target.value })}
                  placeholder="broker@email.com"
                />
              </div>
              <div>
                <Label className="text-sm">Subject</Label>
                <Input
                  value={emailPreview.subject}
                  onChange={(e) => setEmailPreview({ ...emailPreview, subject: e.target.value })}
                />
              </div>
              <div>
                <Label className="text-sm">Body</Label>
                <Textarea
                  value={emailPreview.body}
                  onChange={(e) => setEmailPreview({ ...emailPreview, body: e.target.value })}
                  rows={12}
                  className="font-mono text-sm"
                />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setEmailPreview(null)}>Cancel</Button>
            <Button onClick={sendPreviewEmail} disabled={sendingEmail || !emailPreview?.brokerEmail}>
              {sendingEmail ? "Sending..." : "Send Email"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* No Open House Dialog */}
      <Dialog open={noOhDialog} onOpenChange={setNoOhDialog}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>No Open House Listed</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-gray-600">
            There isn&apos;t an open house scheduled for this apartment. You can email the broker to coordinate a viewing time.
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setNoOhDialog(false)}>Close</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function LeadCard({ lead, onEmailPreview, onTour, onPass, onNoOpenHouse }: {
  lead: Listing;
  onEmailPreview: () => void;
  onTour: () => void;
  onPass: () => void;
  onNoOpenHouse: () => void;
}) {
  const statusClass = STATUS_COLORS[lead.status] || "bg-gray-100 text-gray-600";
  const hasOpenHouse = lead.open_house_dates && lead.open_house_dates.length > 0;

  return (
    <Card className="p-4">
      <div className="flex flex-col sm:flex-row sm:items-center gap-3">
        <div className="flex-shrink-0 w-14 h-14 rounded-full bg-gray-900 text-white flex items-center justify-center font-bold text-lg">
          {lead.match_score ?? "?"}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="font-semibold truncate">{lead.address || lead.title || "Unknown address"}</h3>
            <Badge className={statusClass}>{STATUS_LABELS[lead.status] || lead.status}</Badge>
            <Badge variant="outline" className="text-xs">{lead.source}</Badge>
            {lead.search_name && <Badge variant="secondary" className="text-xs">{lead.search_name}</Badge>}
          </div>
          <div className="flex items-center gap-4 text-sm text-gray-600 mt-1 flex-wrap">
            {lead.price && <span className="font-semibold text-gray-900">${lead.price.toLocaleString()}/mo</span>}
            {lead.beds && <span>{lead.beds}BR</span>}
            {lead.baths && <span>{lead.baths}BA</span>}
            {lead.sqft && <span>{lead.sqft.toLocaleString()} sqft</span>}
            {lead.commute_minutes && <span>🚇 {lead.commute_minutes} min</span>}
            {lead.available_date && <span>📅 {lead.available_date.toLowerCase() === "immediately" ? "Now" : lead.available_date}</span>}
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

        <div className="flex gap-2 flex-shrink-0 flex-wrap">
          <a href={lead.url} target="_blank" rel="noopener noreferrer">
            <Button variant="outline" size="sm">View</Button>
          </a>
          {lead.status !== "passed" && (
            <Button size="sm" variant="outline" onClick={onEmailPreview}>
              Email Broker
            </Button>
          )}
          {lead.status !== "passed" && (
            hasOpenHouse ? (
              <Button size="sm" onClick={onTour} className="bg-green-600 hover:bg-green-700">
                Schedule Tour
              </Button>
            ) : (
              <Button size="sm" variant="outline" disabled className="opacity-50" onClick={onNoOpenHouse}>
                Schedule Tour
              </Button>
            )
          )}
          {lead.status !== "passed" && (
            <Button variant="ghost" size="sm" onClick={onPass} className="text-gray-500">
              Pass
            </Button>
          )}
        </div>
      </div>
      <div className="mt-2 flex items-center gap-2 flex-wrap">
        {lead.broker_email ? (
          <span className="text-xs text-gray-500">Broker: {lead.broker_name || ""} &lt;{lead.broker_email}&gt;</span>
        ) : (
          <span className="text-xs text-gray-400">No broker email — add one via &quot;Email Broker&quot;</span>
        )}
        {lead.broker_email_sent && <span className="text-xs text-green-600">✅ Sent</span>}
      </div>
    </Card>
  );
}
