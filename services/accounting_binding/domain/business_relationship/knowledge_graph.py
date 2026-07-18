"""
Knowledge Graph v2.0.5c — Domain Integrity & Explainability.

NodeProvenance, EdgeProvenance, PathExplanation, GraphValidationReport,
stable deterministic IDs, GraphBuilder as single entry point,
GraphExplainabilityService interface.

NOT a DB. NOT Neo4j. Pure domain abstraction.
"""
from __future__ import annotations

import uuid as _uuid
from collections import deque, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Protocol


# ── Enums ──

class GraphNodeType(str, Enum):
    ENTITY = "entity"
    PROPERTY = "property"
    DOCUMENT = "document"
    AGREEMENT = "agreement"
    DEAL = "deal"
    RELATIONSHIP = "relationship"
    FACT = "fact"


class EdgeType(str, Enum):
    MENTIONS = "mentions"
    REFERS_TO = "refers_to"
    PARTICIPATES_IN = "participates_in"
    SUPPORTS = "supports"
    RESULTED_IN = "resulted_in"
    OWNS = "owns"
    RELATES_TO = "relates_to"
    ATTACHED_TO = "attached_to"


EDGE_WEIGHTS: dict[EdgeType, float] = {
    EdgeType.SUPPORTS: 1.0,
    EdgeType.PARTICIPATES_IN: 0.95,
    EdgeType.OWNS: 0.90,
    EdgeType.RESULTED_IN: 0.85,
    EdgeType.ATTACHED_TO: 0.80,
    EdgeType.REFERS_TO: 0.75,
    EdgeType.MENTIONS: 0.70,
    EdgeType.RELATES_TO: 0.50,
}


def stable_id(prefix: str, key: str) -> str:
    """Deterministic node ID. No random UUID."""
    return f"{prefix}:{key}" if not key.startswith(f"{prefix}:") else key


# ── Provenance ──

@dataclass(frozen=True)
class NodeProvenance:
    """Why does this node exist?"""
    source_type: str = "entity"
    source_id: str = ""
    knowledge_version: int = 1
    document_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class EdgeProvenance:
    """Why does this edge exist?"""
    supporting_fact_ids: list[str] = field(default_factory=list)
    supporting_document_ids: list[str] = field(default_factory=list)
    supporting_agreement_ids: list[str] = field(default_factory=list)


# ── Node ──

@dataclass
class GraphNode:
    node_id: str
    node_type: GraphNodeType
    domain_object_id: str = ""
    label: str = ""
    provenance: NodeProvenance | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __hash__(self) -> int: return hash(self.node_id)
    def __eq__(self, other): return isinstance(other, GraphNode) and self.node_id == other.node_id


# ── Edge ──

@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    edge_type: EdgeType
    id: str = ""
    weight: float = 1.0
    confidence: float = 1.0
    document_id: str = ""
    provenance: EdgeProvenance | None = None
    source_node_type: str = ""
    target_node_type: str = ""

    def __post_init__(self):
        if not self.id:
            self.id = str(_uuid.uuid4())
        if self.weight == 1.0:
            self.weight = EDGE_WEIGHTS.get(self.edge_type, 0.5)

    def __hash__(self): return hash(self.id)


# ── Path Explanation ──

@dataclass
class PathExplanation:
    """Explainable path detail."""
    summary: str = ""
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.0
    total_weight: float = 0.0


@dataclass
class GraphPath:
    nodes: list[str] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    source_node: GraphNode | None = None
    target_node: GraphNode | None = None
    explanation: PathExplanation | None = None

    @property
    def length(self) -> int: return len(self.edges)
    @property
    def hop_count(self) -> int: return len(self.edges)

    @property
    def total_weight(self) -> float:
        return sum(e.weight for e in self.edges)

    @property
    def confidence(self) -> float:
        c = 1.0
        for e in self.edges: c *= e.confidence
        return c

    @property
    def summary(self) -> str:
        if not self.edges:
            return "empty path"
        steps = " → ".join(e.edge_type.value for e in self.edges)
        return (f"[{len(self.nodes)}n, {self.hop_count}h, "
                f"w={self.total_weight:.2f}, c={self.confidence:.2f}] {steps}")


# ── Validation Report ──

@dataclass
class GraphValidationReport:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    orphan_nodes: list[str] = field(default_factory=list)
    duplicate_edges: list[str] = field(default_factory=list)
    cycles: list[str] = field(default_factory=list)
    node_count: int = 0
    edge_count: int = 0

    @property
    def summary(self) -> str:
        if self.valid:
            return f"Valid: {self.node_count}n {self.edge_count}e"
        return f"Invalid: {len(self.errors)} errors, {len(self.warnings)} warnings"


# ── Traversal Options ──

@dataclass
class TraversalOptions:
    max_depth: int = 10
    allowed_node_types: set[GraphNodeType] | None = None
    allowed_edge_types: set[EdgeType] | None = None
    minimum_weight: float = 0.0
    minimum_confidence: float = 0.0
    include_cycles: bool = False
    stop_on_types: set[GraphNodeType] | None = None

    def should_traverse_edge(self, e: GraphEdge) -> bool:
        if self.allowed_edge_types and e.edge_type not in self.allowed_edge_types: return False
        if e.weight < self.minimum_weight: return False
        if e.confidence < self.minimum_confidence: return False
        return True

    def should_visit_node(self, n: GraphNode) -> bool:
        if self.allowed_node_types and n.node_type not in self.allowed_node_types: return False
        return True

    def should_stop_on(self, n: GraphNode) -> bool:
        if self.stop_on_types and n.node_type in self.stop_on_types: return True
        return False


# ── KnowledgeGraph ──

class KnowledgeGraph:
    """In-memory domain knowledge graph with full provenance and explainability."""

    def __init__(self):
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._adj_out: dict[str, list[GraphEdge]] = defaultdict(list)
        self._adj_in: dict[str, list[GraphEdge]] = defaultdict(list)
        self._adj_all: dict[str, list[GraphEdge]] = defaultdict(list)
        self.graph_version: int = 0
        self._built_from: str = ""

    def _add_node(self, node: GraphNode) -> GraphNode:
        self._nodes[node.node_id] = node
        return node

    def _add_edge(self, edge: GraphEdge) -> GraphEdge:
        self._edges.append(edge)
        self._adj_out[edge.source_id].append(edge)
        self._adj_in[edge.target_id].append(edge)
        self._adj_all[edge.source_id].append(edge)
        self._adj_all[edge.target_id].append(edge)
        return edge

    # ── Query ──

    def exists(self, node_id: str) -> bool: return node_id in self._nodes
    def node(self, node_id: str) -> GraphNode | None: return self._nodes.get(node_id)

    def nodes_by_type(self, node_type: GraphNodeType) -> list[GraphNode]:
        return [n for n in self._nodes.values() if n.node_type == node_type]

    def edges(self, node_id: str) -> list[GraphEdge]:
        return list(self._adj_all.get(node_id, []))

    def degree(self, node_id: str) -> int: return len(self.edges(node_id))

    def neighbors(self, node_id: str) -> list[GraphNode]:
        seen: set[str] = set()
        result = []
        for e in self._adj_all.get(node_id, []):
            other = e.target_id if e.source_id == node_id else e.source_id
            if other not in seen and other in self._nodes:
                seen.add(other)
                result.append(self._nodes[other])
        return result

    def contains_edge(self, source: str, target: str) -> bool:
        for e in self._adj_all.get(source, []):
            if e.target_id == target or e.source_id == target: return True
        return False

    def has_path(self, source: str, target: str, opts: TraversalOptions | None = None) -> bool:
        return self.find_path(source, target, opts) is not None

    def find_path(self, source: str, target: str, opts: TraversalOptions | None = None) -> GraphPath | None:
        opts = opts or TraversalOptions()
        if source not in self._nodes or target not in self._nodes: return None
        if source == target:
            return GraphPath(nodes=[source], source_node=self._nodes[source], target_node=self._nodes[target])

        queue = deque([(source, [], [source])])
        visited = {source}
        depth = {source: 0}

        while queue:
            current, pe, pn = queue.popleft()
            if depth[current] >= opts.max_depth: continue
            for e in self._adj_all.get(current, []):
                if not opts.should_traverse_edge(e): continue
                nb = e.target_id if e.source_id == current else e.source_id
                nn = self._nodes.get(nb)
                if nn and not opts.should_visit_node(nn): continue
                if nb == target:
                    ev = [e.source_node_type or self._nodes[e.source_id].node_type.value if e.source_id in self._nodes else "",
                          e.target_node_type or self._nodes[e.target_id].node_type.value if e.target_id in self._nodes else ""]
                    path = GraphPath(nodes=pn + [nb], edges=pe + [e],
                                     source_node=self._nodes[source], target_node=self._nodes[target])
                    path.explanation = PathExplanation(
                        summary=f"Found {len(pe)+1}h path via {e.edge_type.value}",
                        evidence=[f"edge: {e.edge_type.value} ({e.confidence:.2f})" for e in pe + [e]],
                        confidence=path.confidence,
                        total_weight=path.total_weight,
                    )
                    return path
                if nb not in visited:
                    visited.add(nb); depth[nb] = depth[current] + 1
                    queue.append((nb, pe + [e], pn + [nb]))
                    nn = self._nodes.get(nb)
                    if nn and opts.should_stop_on(nn): continue
        return None

    def distance(self, source: str, target: str, opts: TraversalOptions | None = None) -> int:
        p = self.find_path(source, target, opts)
        return p.hop_count if p else -1

    def reachable(self, source: str, opts: TraversalOptions | None = None) -> set[str]:
        opts = opts or TraversalOptions()
        if source not in self._nodes: return set()
        visited = {source}; queue = deque([(source, 0)])
        while queue:
            cur, d = queue.popleft()
            if d >= opts.max_depth: continue
            for e in self._adj_all.get(cur, []):
                if not opts.should_traverse_edge(e): continue
                nb = e.target_id if e.source_id == cur else e.source_id
                nn = self._nodes.get(nb)
                if nn and not opts.should_visit_node(nn): continue
                if nb not in visited:
                    visited.add(nb); queue.append((nb, d + 1))
        return visited

    def shortest_paths(self, source: str, opts: TraversalOptions | None = None) -> dict[str, GraphPath]:
        opts = opts or TraversalOptions()
        if source not in self._nodes: return {}
        paths: dict[str, GraphPath] = {}
        queue = deque([(source, [], [source])]); visited = {source}; depth = {source: 0}
        while queue:
            cur, pe, pn = queue.popleft()
            if depth[cur] >= opts.max_depth: continue
            for e in self._adj_all.get(cur, []):
                if not opts.should_traverse_edge(e): continue
                nb = e.target_id if e.source_id == cur else e.source_id
                nn = self._nodes.get(nb)
                if nn and not opts.should_visit_node(nn): continue
                if nb not in visited:
                    visited.add(nb); depth[nb] = depth[cur] + 1
                    gp = GraphPath(nodes=pn + [nb], edges=pe + [e],
                                   source_node=self._nodes[source], target_node=self._nodes.get(nb))
                    paths[nb] = gp
                    queue.append((nb, pe + [e], pn + [nb]))
                    if nn and opts.should_stop_on(nn): continue
        return paths

    def subgraph(self, node_ids: list[str]) -> KnowledgeGraph:
        g = KnowledgeGraph(); ids = set(node_ids)
        for nid in node_ids:
            if nid in self._nodes: g._add_node(self._nodes[nid])
        for e in self._edges:
            if e.source_id in ids and e.target_id in ids: g._add_edge(e)
        return g

    def connected_components(self) -> list[set[str]]:
        visited: set[str] = set(); components: list[set[str]] = []
        for nid in self._nodes:
            if nid in visited: continue
            comp: set[str] = set(); q = deque([nid])
            while q:
                cur = q.popleft()
                if cur in visited: continue
                visited.add(cur); comp.add(cur)
                for e in self._adj_all.get(cur, []):
                    nb = e.target_id if e.source_id == cur else e.source_id
                    if nb not in visited: q.append(nb)
            components.append(comp)
        return components

    # ── Validation ──

    def validate(self) -> GraphValidationReport:
        from domain.business_relationship.graph_schema import GraphSchema
        report = GraphValidationReport(node_count=self.node_count, edge_count=self.edge_count)

        for nid, n in self._nodes.items():
            # Check orphan
            if self.degree(nid) == 0:
                report.orphan_nodes.append(nid)

        seen_edges: set[tuple[str, str, str]] = set()
        for e in self._edges:
            key = (e.source_id, e.target_id, e.edge_type.value)
            if key in seen_edges:
                report.duplicate_edges.append(f"{e.source_id} → {e.target_id} ({e.edge_type.value})")
            seen_edges.add(key)

            # Schema check
            sn = self._nodes.get(e.source_id); tn = self._nodes.get(e.target_id)
            if sn and tn:
                try:
                    GraphSchema.validate(sn.node_type, tn.node_type, e.edge_type, e.source_id, e.target_id)
                except Exception as err:
                    report.errors.append(str(err)); report.valid = False

        if report.errors:
            report.valid = False
        return report

    # ── Metrics ──

    def metrics(self) -> dict:
        n = self.node_count; e = self.edge_count
        total_deg = sum(len(self._adj_all.get(nid, [])) for nid in self._nodes)
        avg_deg = total_deg / n if n else 0.0
        max_edges = n * (n - 1) / 2 if n > 1 else 0
        density = e / max_edges if max_edges else 0.0
        return {"nodes": n, "edges": e, "components": len(self.connected_components()),
                "avg_degree": round(avg_deg, 2), "density": round(density, 4)}

    @property
    def node_count(self) -> int: return len(self._nodes)
    @property
    def edge_count(self) -> int: return len(self._edges)
    @property
    def component_count(self) -> int: return len(self.connected_components())

    def summary(self) -> str:
        types: dict[str, int] = {}
        for n in self._nodes.values(): types[n.node_type.value] = types.get(n.node_type.value, 0) + 1
        et: dict[str, int] = {}
        for e in self._edges: et[e.edge_type.value] = et.get(e.edge_type.value, 0) + 1
        return f"Graph({self.node_count}n {self.edge_count}e {self.component_count}c types={types} edges={et})"


# ── GraphBuilder (SINGLE entry point) ──

class GraphBuilder:
    """Sole entry point for graph construction. NO manual node/edge creation.

    build(context) — full graph from domain objects
    extend(graph, context) — add to existing graph (future)
    """

    @staticmethod
    def build(
        document_id: str,
        entities: list | None = None,
        properties: list | None = None,
        agreement_id: str = "",
        agreement_type: str = "",
        agreement_participants: list | None = None,
        deal_id: str = "",
        document_references: list | None = None,
        knowledge_version: int = 1,
    ) -> KnowledgeGraph:
        from domain.business_relationship.graph_schema import GraphSchema

        g = KnowledgeGraph()
        g.graph_version = 1
        g._built_from = "builder"

        def _make_node_id(typ: str, key: str) -> str:
            return stable_id(typ, key.strip())

        def _safe_add_edge(src: str, tgt: str, etype: EdgeType, **kw) -> GraphEdge | None:
            sn = g.node(src); tn = g.node(tgt)
            if not sn or not tn: return None
            try:
                GraphSchema.validate(sn.node_type, tn.node_type, etype, src, tgt)
                edge = GraphEdge(src, tgt, etype,
                                 source_node_type=sn.node_type.value,
                                 target_node_type=tn.node_type.value,
                                 **kw)
                g._add_edge(edge)
                return edge
            except Exception:
                return None

        # 1. Document node
        did = _make_node_id("DOCUMENT", document_id)
        g._add_node(GraphNode(did, GraphNodeType.DOCUMENT, document_id,
                              f"Doc#{document_id[:12]}",
                              provenance=NodeProvenance("document", document_id, knowledge_version)))

        # 2. Entity nodes
        for e in (entities or []):
            eid = getattr(e, "id", "") or (e.get("id") if isinstance(e, dict) else "")
            label = getattr(e, "display_name", "") or (e.get("display_name", "") if isinstance(e, dict) else "")
            nid = _make_node_id("ENTITY", eid)
            g._add_node(GraphNode(nid, GraphNodeType.ENTITY, eid, label,
                                  provenance=NodeProvenance("entity", eid, knowledge_version, [document_id])))
            _safe_add_edge(did, nid, EdgeType.MENTIONS, document_id=document_id)

        # 3. Property nodes
        for p in (properties or []):
            pid = getattr(p, "id", "") if not isinstance(p, dict) else p.get("id", "")
            cad = getattr(p, "cadastral_number", "") if not isinstance(p, dict) else p.get("cadastral_number", "")
            nid = _make_node_id("PROPERTY", pid or cad)
            g._add_node(GraphNode(nid, GraphNodeType.PROPERTY, pid or cad, cad,
                                  provenance=NodeProvenance("property", pid or cad, knowledge_version, [document_id])))
            _safe_add_edge(did, nid, EdgeType.MENTIONS, document_id=document_id)

        # 4. Entity ↔ Property (OWNS)
        ent_nodes = [n for n in g._nodes.values() if n.node_type == GraphNodeType.ENTITY]
        prop_nodes = [n for n in g._nodes.values() if n.node_type == GraphNodeType.PROPERTY]
        for en in ent_nodes:
            for pn in prop_nodes:
                if not g.contains_edge(en.node_id, pn.node_id):
                    _safe_add_edge(en.node_id, pn.node_id, EdgeType.OWNS, document_id=document_id)

        # 5. Agreement node
        if agreement_id:
            aid = _make_node_id("AGREEMENT", agreement_id)
            g._add_node(GraphNode(aid, GraphNodeType.AGREEMENT, agreement_id, agreement_type or f"Ag#{agreement_id[:8]}",
                                  provenance=NodeProvenance("agreement", agreement_id, knowledge_version, [document_id])))
            _safe_add_edge(aid, did, EdgeType.SUPPORTS, document_id=document_id)

            # Entity → PARTICIPATES_IN → Agreement
            for part in (agreement_participants or []):
                peid = part.entity_id if hasattr(part, "entity_id") else (part.get("entity_id") if isinstance(part, dict) else "")
                if peid:
                    penid = _make_node_id("ENTITY", peid)
                    if g.exists(penid):
                        _safe_add_edge(penid, aid, EdgeType.PARTICIPATES_IN, document_id=document_id)

        # 6. Deal node
        if deal_id:
            deid = _make_node_id("DEAL", deal_id)
            g._add_node(GraphNode(deid, GraphNodeType.DEAL, deal_id, f"Deal#{deal_id[:8]}",
                                  provenance=NodeProvenance("deal", deal_id, knowledge_version, [document_id])))
            target = aid if agreement_id else did
            _safe_add_edge(target, deid, EdgeType.RESULTED_IN, document_id=document_id)
            _safe_add_edge(did, deid, EdgeType.ATTACHED_TO, document_id=document_id)

        # 7. Document references
        for ref in (document_references or []):
            rt = getattr(ref, "reference_type", "refers_to")
            if hasattr(rt, "value"): rt = rt.value
            target = getattr(ref, "target_document_identifier", "")
            if target:
                tid = _make_node_id("DOCUMENT", f"ref-{target}")
                if not g.exists(tid):
                    g._add_node(GraphNode(tid, GraphNodeType.DOCUMENT, target, target,
                                          provenance=NodeProvenance("document_reference", target, knowledge_version)))
                _safe_add_edge(did, tid, EdgeType.REFERS_TO, document_id=document_id)

        return g


# ── GraphExplainabilityService (interface) ──

class GraphExplainabilityService(Protocol):
    """Explainability interface for Knowledge Graph. NO implementation storage."""

    def explain_node(self, node_id: str) -> NodeProvenance | None: ...
    def explain_edge(self, edge_id: str) -> EdgeProvenance | None: ...
    def explain_path(self, path: GraphPath) -> PathExplanation: ...
    def explain_subgraph(self, graph: KnowledgeGraph) -> str: ...


# ── Workspace Graph ──

@dataclass
class WorkspaceGraph:
    root_graph: KnowledgeGraph | None = None
    selected_node_ids: set[str] = field(default_factory=set)

    def resolve(self) -> KnowledgeGraph | None:
        if self.root_graph and self.selected_node_ids:
            return self.root_graph.subgraph(list(self.selected_node_ids))
        return None


# ── Graph Cache Interface ──

class GraphCache(Protocol):
    def get_graph(self, doc_id: str) -> KnowledgeGraph | None: ...
    def get_context(self, entity_id: str) -> KnowledgeGraph | None: ...
    def put(self, key: str, graph: KnowledgeGraph): ...
    def invalidate(self, key: str): ...


# ── ContextQuery ──

@dataclass
class ContextQuery:
    start_node: str = ""
    target_node: str = ""
    depth: int = 3
    node_filter: set[GraphNodeType] | None = None
    edge_filter: set[EdgeType] | None = None
    minimum_weight: float = 0.0
