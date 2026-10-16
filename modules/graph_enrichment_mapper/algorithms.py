"""
Graph Algorithms & Threat Intelligence Analytics Engine
Powers platform intelligence views, threat reputation scoring,
campaign clustering, and visual subgraph generation for UI visualizers.
"""

from typing import Any, Dict, List, Optional
from modules.graph_enrichment_mapper.infra.neo4j_driver import Neo4jDriver


# UI Visual styling metadata for frontend graph canvas (Cytoscape.js / React Flow)
NODE_STYLE_CONFIG = {
    "Observation": {"color": "#ef4444", "shape": "circle", "size": 32, "icon": "shield-alert"},
    "URL":         {"color": "#f97316", "shape": "round-rectangle", "size": 24, "icon": "link"},
    "Domain":      {"color": "#3b82f6", "shape": "hexagon", "size": 28, "icon": "globe"},
    "IPAddress":   {"color": "#10b981", "shape": "diamond", "size": 26, "icon": "server"},
    "AutonomousSystem": {"color": "#6366f1", "shape": "octagon", "size": 30, "icon": "cpu"},
    "Brand":       {"color": "#a855f7", "shape": "star", "size": 36, "icon": "tag"},
    "CampaignCandidate": {"color": "#dc2626", "shape": "triangle", "size": 34, "icon": "crosshair"},
    "Prediction":  {"color": "#eab308", "shape": "ellipse", "size": 22, "icon": "check-circle"},
    "ModelRun":    {"color": "#64748b", "shape": "box", "size": 20, "icon": "terminal"},
}


class ThreatGraphAnalyticsEngine:
    """Core analytical engine operating on the Neo4j Knowledge Graph."""

    def __init__(self, driver: Neo4jDriver):
        self._driver = driver

    # ─────────────────────────────────────────────────────────────────────────
    # 1. VISUAL SUBGRAPH EXPORTER (UI Cytoscape / React Flow format)
    # ─────────────────────────────────────────────────────────────────────────
    def get_observation_subgraph(self, observation_id: str, depth: int = 2) -> Dict[str, Any]:
        """
        Extract the local ego-network around an observation up to N hops.
        Formats data directly for Cytoscape.js:
        {
          "nodes": [{"id": ..., "label": ..., "type": ..., "style": ...}],
          "edges": [{"id": ..., "source": ..., "target": ..., "label": ...}]
        }
        """
        query = """
        MATCH path = (o:Observation {observation_id: $obs_id})-[r*1..2]-(n)
        UNWIND nodes(path) AS node
        UNWIND relationships(path) AS rel
        RETURN collect(DISTINCT node) AS raw_nodes, collect(DISTINCT rel) AS raw_rels
        """
        records = self._driver.run_query(query, {"obs_id": observation_id})
        if not records or not records[0].get("raw_nodes"):
            return {"nodes": [], "edges": [], "observation_id": observation_id}

        raw_nodes = records[0]["raw_nodes"]
        raw_rels = records[0]["raw_rels"]

        nodes = []
        edges = []
        seen_nodes = set()
        seen_edges = set()

        for n in raw_nodes:
            # Determine node primary label and ID
            labels = getattr(n, "labels", None) or (n.get("_labels") if isinstance(n, dict) else ["Unknown"])
            label = list(labels)[0] if labels else "Entity"
            props = dict(n) if hasattr(n, "items") else {}

            node_id = (
                props.get("observation_id") or
                props.get("url_hash") or
                props.get("name") or
                props.get("ip") or
                props.get("asn") or
                props.get("brand_id") or
                props.get("campaign_id") or
                props.get("prediction_id") or
                str(getattr(n, "id", hash(str(props))))
            )

            if node_id in seen_nodes:
                continue
            seen_nodes.add(node_id)

            display_name = (
                props.get("raw_url", "")[:45] or
                props.get("name") or
                props.get("ip") or
                props.get("asn") or
                props.get("brand_id") or
                props.get("family_id") or
                node_id
            )

            style = NODE_STYLE_CONFIG.get(label, {"color": "#94a3b8", "shape": "ellipse", "size": 24})

            nodes.append({
                "id": str(node_id),
                "type": label,
                "label": str(display_name),
                "properties": props,
                "style": style,
            })

        for r in raw_rels:
            if isinstance(r, dict):
                rel_type = r.get("type", "RELATED_TO")
                start_id = r.get("start_node") or r.get("start") or r.get("source")
                end_id = r.get("end_node") or r.get("end") or r.get("target")
            else:
                rel_type = getattr(r, "type", "RELATED_TO")
                start_id = getattr(r, "start_node", None) or getattr(r, "start", None)
                end_id = getattr(r, "end_node", None) or getattr(r, "end", None)

            edge_id = f"{start_id}_{rel_type}_{end_id}"

            if edge_id in seen_edges:
                continue
            seen_edges.add(edge_id)

            edges.append({
                "id": edge_id,
                "source": str(start_id) if start_id else "",
                "target": str(end_id) if end_id else "",
                "label": rel_type,
            })


        return {
            "observation_id": observation_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes": nodes,
            "edges": edges,
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 2. GRAPH-ASSISTED THREAT REPUTATION SCORING
    # ─────────────────────────────────────────────────────────────────────────
    def compute_infrastructure_reputation(
        self,
        domain: Optional[str] = None,
        ip: Optional[str] = None,
        asn: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate risk reputation based on historical phishing graph connectivity.
        Calculates an empirical graph risk score between 0.0 and 1.0.
        """
        signals: List[str] = []
        risk_components: List[float] = []

        # 1. Historical domain check
        domain_phish_count = 0
        if domain:
            dom_query = """
            MATCH (d:Domain {name: $domain})<-[:HOSTED_ON]-(u:URL)<-[:CAPTURED_URL]-(o:Observation)
            RETURN count(o) AS phish_count
            """
            rows = self._driver.run_query(dom_query, {"domain": domain.lower()})
            if rows and rows[0]["phish_count"] > 0:
                domain_phish_count = rows[0]["phish_count"]
                signals.append(f"Domain '{domain}' has {domain_phish_count} previous phishing captures recorded.")
                risk_components.append(min(1.0, 0.60 + (0.10 * domain_phish_count)))

        # 2. IP Host Phishing Density
        ip_phish_count = 0
        brands_targeted_from_ip = 0
        if ip:
            ip_query = """
            MATCH (i:IPAddress {ip: $ip})<-[:RESOLVED_TO]-(d:Domain)<-[:HOSTED_ON]-(u:URL)<-[:CAPTURED_URL]-(o:Observation)
            OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
            RETURN count(DISTINCT o) AS phish_count, count(DISTINCT b) AS brands_count
            """
            rows = self._driver.run_query(ip_query, {"ip": ip})
            if rows and rows[0]["phish_count"] > 0:
                ip_phish_count = rows[0]["phish_count"]
                brands_targeted_from_ip = rows[0]["brands_count"]
                signals.append(
                    f"Host IP '{ip}' has hosted {ip_phish_count} phishing observations "
                    f"across {brands_targeted_from_ip} distinct brand targets."
                )
                risk_components.append(min(0.95, 0.40 + (0.05 * ip_phish_count)))

        # 3. Autonomous System (ASN) Bad Neighborhood Density
        asn_phish_count = 0
        if asn:
            asn_norm = asn if asn.upper().startswith("AS") else f"AS{asn}"
            asn_query = """
            MATCH (a:AutonomousSystem {asn: $asn})<-[:ANNOUNCED_BY]-(i:IPAddress)
                  <-[:RESOLVED_TO]-(d:Domain)<-[:HOSTED_ON]-(u:URL)<-[:CAPTURED_URL]-(o:Observation)
            RETURN count(DISTINCT o) AS phish_count
            """
            rows = self._driver.run_query(asn_query, {"asn": asn_norm})
            if rows and rows[0]["phish_count"] > 0:
                asn_phish_count = rows[0]["phish_count"]
                if asn_phish_count > 5:
                    signals.append(f"Routing ASN '{asn_norm}' has hosted {asn_phish_count} active phishing sites in graph.")
                    risk_components.append(min(0.85, 0.30 + (0.02 * asn_phish_count)))

        # Aggregate risk score
        final_score = max(risk_components) if risk_components else 0.05
        verdict = "malicious" if final_score >= 0.70 else ("suspicious" if final_score >= 0.35 else "clean")

        return {
            "graph_risk_score": round(final_score, 4),
            "verdict": verdict,
            "signals": signals,
            "metrics": {
                "domain_previous_phish_count": domain_phish_count,
                "ip_phish_count": ip_phish_count,
                "ip_brands_targeted_count": brands_targeted_from_ip,
                "asn_phish_count": asn_phish_count,
            }
        }

    # ─────────────────────────────────────────────────────────────────────────
    # 3. CAMPAIGN CLUSTER DISCOVERY (Multi-Brand Infrastructure Rings)
    # ─────────────────────────────────────────────────────────────────────────
    def discover_campaign_clusters(self, min_size: int = 2, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Identifies campaigns that share infrastructure (IP, ASN, or phishing kits)
        targeting multiple organizations simultaneously.
        """
        query = """
        MATCH (c:CampaignCandidate)<-[:SUSPECTED_CAMPAIGN_MEMBER]-(o:Observation)
        MATCH (o)-[:CAPTURED_URL]->(u:URL)-[:HOSTED_ON]->(d:Domain)-[:RESOLVED_TO]->(i:IPAddress)
        OPTIONAL MATCH (o)-[:TARGETS_BRAND]->(b:Brand)
        OPTIONAL MATCH (i)-[:ANNOUNCED_BY]->(a:AutonomousSystem)
        WITH c,
             count(DISTINCT o) AS total_observations,
             collect(DISTINCT b.name) AS targeted_brands,
             collect(DISTINCT d.name) AS active_domains,
             collect(DISTINCT i.ip) AS hosting_ips,
             collect(DISTINCT a.name) AS asns
        WHERE total_observations >= $min_size
        RETURN c.family_id AS family_id,
               c.campaign_id AS campaign_id,
               total_observations,
               targeted_brands,
               active_domains[..5] AS sample_domains,
               hosting_ips[..5] AS sample_ips,
               asns[..3] AS hosting_asns
        ORDER BY total_observations DESC
        LIMIT $limit
        """
        rows = self._driver.run_query(query, {"min_size": min_size, "limit": limit})
        clusters = []
        for r in rows:
            clusters.append({
                "family_id": r.get("family_id") or "unclassified_cluster",
                "campaign_id": r.get("campaign_id"),
                "observation_count": r.get("total_observations", 0),
                "targeted_brands": [b for b in r.get("targeted_brands", []) if b],
                "sample_domains": r.get("sample_domains", []),
                "sample_ips": r.get("sample_ips", []),
                "hosting_asns": [a for a in r.get("hosting_asns", []) if a],
            })
        return clusters

    # ─────────────────────────────────────────────────────────────────────────
    # 4. PLATFORM THREAT INTELLIGENCE DASHBOARD OVERVIEW
    # ─────────────────────────────────────────────────────────────────────────
    def get_dashboard_analytics_overview(self) -> Dict[str, Any]:
        """
        Aggregates summary intelligence metrics for the platform's landing view:
        - Total observations, unique domains, IPs, brands
        - Top 5 targeted brands
        - Top 5 phishing-hosting ASNs
        - Top 5 hosting countries
        """
        # Node count summary
        counts_query = """
        MATCH (o:Observation) WITH count(o) AS obs_count
        MATCH (d:Domain) WITH obs_count, count(d) AS dom_count
        MATCH (i:IPAddress) WITH obs_count, dom_count, count(i) AS ip_count
        MATCH (b:Brand) WITH obs_count, dom_count, ip_count, count(b) AS brand_count
        RETURN obs_count, dom_count, ip_count, brand_count
        """
        counts = self._driver.run_query(counts_query)
        summary_counts = counts[0] if counts else {"obs_count": 0, "dom_count": 0, "ip_count": 0, "brand_count": 0}

        # Top targeted brands
        brands_query = """
        MATCH (o:Observation)-[:TARGETS_BRAND]->(b:Brand)
        RETURN b.name AS brand, b.sector AS sector, count(o) AS count
        ORDER BY count DESC LIMIT 5
        """
        top_brands = self._driver.run_query(brands_query)

        # Top hosting ASNs
        asns_query = """
        MATCH (o:Observation)-[:CAPTURED_URL]->(u:URL)-[:HOSTED_ON]->(d:Domain)-[:RESOLVED_TO]->(i:IPAddress)-[:ANNOUNCED_BY]->(a:AutonomousSystem)
        RETURN a.name AS asn_name, a.asn AS asn_code, count(DISTINCT d) AS domain_count
        ORDER BY domain_count DESC LIMIT 5
        """
        top_asns = self._driver.run_query(asns_query)

        # Top countries
        countries_query = """
        MATCH (i:IPAddress)
        WHERE i.country_code IS NOT NULL AND i.country_code <> ''
        RETURN i.country_code AS code, i.country_name AS name, count(i) AS count
        ORDER BY count DESC LIMIT 5
        """
        top_countries = self._driver.run_query(countries_query)

        return {
            "summary": summary_counts,
            "top_targeted_brands": top_brands,
            "top_hosting_asns": top_asns,
            "top_hosting_countries": top_countries,
        }
