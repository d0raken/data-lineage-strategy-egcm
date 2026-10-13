"""Data models and schemas for Mosaic lineage and catalog representation."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TokenReference:
    """Referência a objeto dentro de token de expressão."""
    object_id: str
    name: str
    sub_type: str
    target_type: Optional[str] = None


@dataclass
class MetricDefinition:
    """Definição detalhada de métrica e sua fórmula."""
    id: str
    name: str
    description: str = ""
    sub_type: str = "METRIC"
    formula_text: str = ""
    expression_raw: Dict[str, Any] = field(default_factory=dict)
    referenced_objects: List[TokenReference] = field(default_factory=list)
    aggregation: Optional[str] = None
    dimensionality: List[Dict[str, Any]] = field(default_factory=list)
    is_compound: bool = False


@dataclass
class FactMetricDefinition:
    """Métrica de fato atômica vinculada a coluna de tabela."""
    id: str
    name: str
    description: str = ""
    data_type: Optional[str] = None
    table_id: Optional[str] = None
    table_name: Optional[str] = None
    column_name: Optional[str] = None
    expression_raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AttributeFormDefinition:
    """Forma de atributo (ID, DESC, etc.)."""
    id: str
    name: str
    category: str
    data_type: Optional[str] = None
    expressions: List[Dict[str, Any]] = field(default_factory=list)
    source_tables: List[str] = field(default_factory=list)


@dataclass
class AttributeDefinition:
    """Definição de atributo dentro do modelo."""
    id: str
    name: str
    description: str = ""
    forms: List[AttributeFormDefinition] = field(default_factory=list)
    source_tables: List[str] = field(default_factory=list)


@dataclass
class RelationshipDefinition:
    """Relacionamento entre atributos (pai-filho)."""
    parent_id: str
    parent_name: str
    child_id: str
    child_name: str
    relation_type: str = "1_TO_N"


@dataclass
class DataModelMetadata:
    """Metadados raiz de um modelo de dados Mosaic."""
    id: str
    name: str
    description: str = ""
    project_id: Optional[str] = None
    date_created: Optional[str] = None
    date_modified: Optional[str] = None
    tables: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class Node:
    """Vértice do grafo de lineage."""
    id: str
    name: str
    type: str  # data_model, attribute, metric, fact_metric, table, column
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Aresta direcionada do grafo de lineage."""
    source_id: str
    target_id: str
    relationship_type: str  # contains, calculates_from, maps_to, relates_to, sources_from
    properties: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LineageGraph:
    """Grafo de Data Lineage completo."""
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: List[Edge] = field(default_factory=list)
    metrics_catalog: Dict[str, MetricDefinition] = field(default_factory=dict)

    def add_node(self, node: Node) -> None:
        """Adiciona ou atualiza um nó no grafo."""
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge) -> None:
        """Adiciona aresta ao grafo evitando duplicatas exatas."""
        for e in self.edges:
            if (e.source_id == edge.source_id and
                e.target_id == edge.target_id and
                e.relationship_type == edge.relationship_type):
                return
        self.edges.append(edge)

    def to_dict(self) -> Dict[str, Any]:
        """Converte grafo para dicionário serializável em JSON."""
        return {
            "summary": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "total_metrics": len(self.metrics_catalog)
            },
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "type": n.type,
                    "properties": n.properties
                }
                for n in self.nodes.values()
            ],
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "relationship_type": e.relationship_type,
                    "properties": e.properties
                }
                for e in self.edges
            ],
            "metrics_catalog": {
                m_id: {
                    "id": m.id,
                    "name": m.name,
                    "description": m.description,
                    "formula_text": m.formula_text,
                    "sub_type": m.sub_type,
                    "aggregation": m.aggregation,
                    "is_compound": m.is_compound,
                    "referenced_objects": [
                        {
                            "id": r.object_id,
                            "name": r.name,
                            "sub_type": r.sub_type,
                            "target_type": r.target_type
                        }
                        for r in m.referenced_objects
                    ]
                }
                for m_id, m in self.metrics_catalog.items()
            }
        }
