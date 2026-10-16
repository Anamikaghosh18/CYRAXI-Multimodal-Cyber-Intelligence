# CYRAXI Platform Integration & Frontend Guide

This guide describes how to connect a frontend website, SOC dashboard, or external platform to the CYRAXI threat intelligence and knowledge graph services.

---

## 1. Quick Service Startup

Start the platform and graph services locally:

```powershell
# 1. Start Neo4j Database
docker compose up -d

# 2. Start Central Threat & Graph API (Port 8001)
uvicorn modules.graph_enrichment_mapper.api.server:app --port 8001 --reload
```

Interactive Swagger Documentation is available at: **http://localhost:8001/docs**

---

## 2. Platform REST Endpoints Reference

### A. Unified URL Scan & Triage (Primary Frontend Hook)
Used when a user pastes a suspicious URL into your website's search box.

* **Endpoint:** `POST /api/v1/platform/scan`
* **Request:**
  ```json
  {
    "url": "http://paypal-verification-account-update.xyz/login",
    "include_subgraph": true,
    "auto_ingest_graph": true
  }
  ```
* **Response (Sample):**
  ```json
  {
    "schema_version": "1.0.0",
    "observation_id": "obs_99c3df3324683516089cfafe9365e43c",
    "target_url": "http://paypal-verification-account-update.xyz/login",
    "scanned_at": "2026-10-16T10:55:00Z",
    "latency_ms": 38.4,
    "triage": {
      "is_phishing": true,
      "verdict": "phishing",
      "confidence_score": 0.965,
      "fused_risk_score": 0.985,
      "top_risk_factors": [
        "Targeted brand name used in URL path (spoofing)",
        "High-abuse top-level domain",
        "Abnormally long URL",
        "Historical Graph Alert: Host/domain flagged in prior campaigns (0.75 risk)"
      ],
      "identified_brand": null
    },
    "graph_reputation": {
      "graph_risk_score": 0.75,
      "verdict": "malicious",
      "signals": [
        "Host IP '104.21.55.2' has hosted 14 phishing observations across 3 distinct brand targets."
      ]
    },
    "visual_graph": {
      "node_count": 5,
      "edge_count": 4,
      "nodes": [
        {
          "id": "obs_99c3df3324683516089cfafe9365e43c",
          "type": "Observation",
          "label": "obs_99c3df...",
          "style": {"color": "#ef4444", "shape": "circle", "size": 32}
        },
        {
          "id": "paypal-verification-account-update.xyz",
          "type": "Domain",
          "label": "paypal-verification-account-update.xyz",
          "style": {"color": "#3b82f6", "shape": "hexagon", "size": 28}
        }
      ],
      "edges": [
        {"id": "e1", "source": "obs_99c3df...", "target": "url_hash...", "label": "CAPTURED_URL"},
        {"id": "e2", "source": "url_hash...", "target": "paypal-verification...", "label": "HOSTED_ON"}
      ]
    }
  }
  ```

---

### B. Interactive Graph Visualizer
Used to render the Cytoscape.js or React Flow network view.

* **Endpoint:** `GET /api/v1/graph/subgraph/{observation_id}?depth=2`
* **Direct format:** Returns nodes and edges formatted with visual styles (`color`, `shape`, `size`, `icon`).

---

### C. Infrastructure Threat Reputation Check
Used for automated IP/Domain/ASN enrichment lookups.

* **Endpoint:** `GET /api/v1/graph/reputation?domain=fake-paypal.com&ip=192.0.2.1`
* **Response:**
  ```json
  {
    "graph_risk_score": 0.85,
    "verdict": "malicious",
    "signals": [
      "Domain 'fake-paypal.com' has 3 previous phishing captures recorded.",
      "Host IP '192.0.2.1' has hosted 8 phishing observations across 2 distinct brand targets."
    ],
    "metrics": {
      "domain_previous_phish_count": 3,
      "ip_phish_count": 8,
      "ip_brands_targeted_count": 2,
      "asn_phish_count": 24
    }
  }
  ```

---

### D. Campaign Clustering & Multi-Brand Attacks
Used for threat intelligence and campaign tracking views.

* **Endpoint:** `GET /api/v1/graph/campaigns/clusters?min_size=2`
* **Response:**
  ```json
  {
    "total_clusters": 5,
    "clusters": [
      {
        "family_id": "kit_dhl_chase_v2",
        "campaign_id": "camp_e9a1b2...",
        "observation_count": 18,
        "targeted_brands": ["DHL", "Chase Bank"],
        "sample_domains": ["dhl-track-package.top", "chase-secure-login.xyz"],
        "sample_ips": ["45.142.122.9"],
        "hosting_asns": ["Hostinger International Ltd"]
      }
    ]
  }
  ```

---

### E. Dashboard Overview Statistics
Used to populate charts, metric cards, and leaderboards on the website home screen.

* **Endpoint:** `GET /api/v1/graph/analytics/overview`
* **Response:**
  ```json
  {
    "summary": {
      "obs_count": 1250,
      "dom_count": 840,
      "ip_count": 310,
      "brand_count": 65
    },
    "top_targeted_brands": [
      {"brand": "PayPal", "sector": "Finance", "count": 215},
      {"brand": "Microsoft", "sector": "Technology", "count": 180}
    ],
    "top_hosting_asns": [
      {"asn_name": "Cloudflare Inc.", "asn_code": "AS13335", "domain_count": 120}
    ],
    "top_hosting_countries": [
      {"code": "US", "name": "United States", "count": 540}
    ]
  }
  ```

---

## 3. Example Frontend Integration (React / Next.js)

```tsx
import React, { useState } from 'react';

export default function ThreatScanner() {
  const [url, setUrl] = useState('');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleScan = async () => {
    setLoading(true);
    try {
      const res = await fetch('http://localhost:8001/api/v1/platform/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url, include_subgraph: true, auto_ingest_graph: true })
      });
      const data = await res.json();
      setResult(data);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-8 max-w-4xl mx-auto font-sans">
      <h1 className="text-3xl font-bold mb-4">CYRAXI Threat Intelligence Scanner</h1>
      
      <div className="flex gap-2 mb-6">
        <input
          type="text"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="Enter suspicious URL (e.g. https://...)"
          className="border p-2 flex-grow rounded"
        />
        <button
          onClick={handleScan}
          disabled={loading}
          className="bg-red-600 text-white px-4 py-2 rounded font-semibold"
        >
          {loading ? 'Analyzing...' : 'Scan URL'}
        </button>
      </div>

      {result && (
        <div className="bg-slate-50 border p-6 rounded shadow-sm">
          <div className="flex justify-between items-center mb-4">
            <span className={`text-xl font-bold uppercase px-3 py-1 rounded ${
              result.triage.verdict === 'phishing' ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700'
            }`}>
              {result.triage.verdict} ({Math.round(result.triage.fused_risk_score * 100)}% Risk)
            </span>
            <span className="text-sm text-gray-500">Latency: {result.latency_ms} ms</span>
          </div>

          <h3 className="font-semibold mb-2">Key Risk Indicators:</h3>
          <ul className="list-disc pl-5 mb-4 space-y-1">
            {result.triage.top_risk_factors.map((factor, idx) => (
              <li key={idx} className="text-sm text-gray-700">{factor}</li>
            ))}
          </ul>

          {result.visual_graph && (
            <div className="text-sm text-gray-500">
              Graph Entities Discovered: {result.visual_graph.node_count} nodes, {result.visual_graph.edge_count} relationships.
            </div>
          )}
        </div>
      )}
    </div>
  );
}
```
