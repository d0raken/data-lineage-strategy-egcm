"""Builds DAG lineage graph from extracted Mosaic model artifacts."""

from typing import Any, Dict, List, Optional
from mosaic_lineage.metric_parser import MetricParser
from mosaic_lineage.models import Edge, LineageGraph, Node


class GraphBuilder:
    """Constrói grafo direcionado de linhagem conectando modelos, atributos, métricas e tabelas."""

    def __init__(self):
        self.graph = LineageGraph()

    def _ensure_table_node(self, tbl_id: str, tbl_name: str, properties: Optional[Dict[str, Any]] = None) -> None:
        """Adiciona nó de tabela ao grafo se ainda não existir."""
        if tbl_id not in self.graph.nodes:
            self.graph.add_node(
                Node(
                    id=tbl_id,
                    name=tbl_name or tbl_id,
                    type="table",
                    properties=properties or {}
                )
            )

    def build_from_model_data(
        self,
        model_metadata: Dict[str, Any],
        attributes_data: List[Dict[str, Any]],
        metrics_data: List[Dict[str, Any]],
        fact_metrics_data: List[Dict[str, Any]],
        relationships_data: List[Dict[str, Any]],
        datasource_data: Optional[Dict[str, Any]] = None,
        dependents_data: Optional[List[Dict[str, Any]]] = None
    ) -> LineageGraph:
        """Processa todos os artefatos de um Data Model e sintetiza o grafo de linhagem."""
        m_info = model_metadata.get("information") or {}
        model_id = m_info.get("objectId") or model_metadata.get("id") or model_metadata.get("modelId") or "unknown_model"
        model_name = m_info.get("name") or model_metadata.get("name") or model_metadata.get("modelName") or model_id

        # Rastreia tabelas e objetos semânticos para o encadeamento Sankey
        discovered_tables: set[str] = set()
        semantic_objects: set[str] = set()

        # 1. Nó do Modelo
        self.graph.add_node(
            Node(
                id=model_id,
                name=model_name,
                type="data_model",
                properties={
                    "description": m_info.get("description") or model_metadata.get("description", ""),
                    "project_id": model_metadata.get("projectId"),
                    "date_modified": m_info.get("dateModified") or model_metadata.get("dateModified")
                }
            )
        )

        # 2. Tabelas declaradas no modelo
        tables = model_metadata.get("tables", [])
        for tbl in tables:
            tbl_id = tbl.get("id") or tbl.get("objectId") or tbl.get("tableId") or tbl.get("name")
            if tbl_id:
                discovered_tables.add(tbl_id)
                self._ensure_table_node(
                    tbl_id=tbl_id,
                    tbl_name=tbl.get("name", tbl_id),
                    properties={
                        "physical_name": tbl.get("physicalName"),
                        "datasource": tbl.get("datasource")
                    }
                )
                self.graph.add_edge(
                    Edge(source_id=tbl_id, target_id=model_id, relationship_type="feeds")
                )

        # 3. Atributos
        for attr in attributes_data:
            info = attr.get("information") or {}
            attr_id = info.get("objectId") or attr.get("id") or attr.get("attributeId")
            if not attr_id:
                continue
            attr_name = info.get("name") or attr.get("name") or attr_id
            attr_desc = info.get("description") or attr.get("description", "")

            self.graph.add_node(
                Node(
                    id=attr_id,
                    name=attr_name,
                    type="attribute",
                    properties={
                        "description": attr_desc,
                        "forms_count": len(attr.get("forms", []))
                    }
                )
            )
            self.graph.add_edge(
                Edge(source_id=model_id, target_id=attr_id, relationship_type="contains")
            )

            # Mapeamento atributo -> tabelas fonte através de forms e expressions
            for form in attr.get("forms", []):
                lookup_tbl = form.get("lookupTable")
                if isinstance(lookup_tbl, dict):
                    t_id = lookup_tbl.get("objectId") or lookup_tbl.get("id")
                    t_name = lookup_tbl.get("name") or t_id
                    if t_id:
                        discovered_tables.add(t_id)
                        self._ensure_table_node(t_id, t_name)
                        self.graph.add_edge(Edge(source_id=attr_id, target_id=t_id, relationship_type="maps_to"))
                        self.graph.add_edge(Edge(source_id=t_id, target_id=model_id, relationship_type="feeds"))

                form_tables = form.get("tables") or form.get("sourceTables") or []
                for tbl in form_tables:
                    t_id = tbl.get("objectId") or tbl.get("id") or (tbl if isinstance(tbl, str) else "")
                    t_name = tbl.get("name", t_id) if isinstance(tbl, dict) else t_id
                    if t_id:
                        discovered_tables.add(t_id)
                        self._ensure_table_node(t_id, t_name)
                        self.graph.add_edge(Edge(source_id=attr_id, target_id=t_id, relationship_type="maps_to"))
                        self.graph.add_edge(Edge(source_id=t_id, target_id=model_id, relationship_type="feeds"))

                for expr in form.get("expressions", []):
                    for tbl in expr.get("tables", []):
                        t_id = tbl.get("objectId") or tbl.get("id") or (tbl if isinstance(tbl, str) else "")
                        t_name = tbl.get("name", t_id) if isinstance(tbl, dict) else t_id
                        if t_id:
                            discovered_tables.add(t_id)
                            self._ensure_table_node(t_id, t_name)
                            self.graph.add_edge(Edge(source_id=attr_id, target_id=t_id, relationship_type="maps_to"))
                            self.graph.add_edge(Edge(source_id=t_id, target_id=model_id, relationship_type="feeds"))

            # Lookup de atributo
            attr_lookup = attr.get("attributeLookupTable")
            if isinstance(attr_lookup, dict):
                t_id = attr_lookup.get("objectId") or attr_lookup.get("id")
                t_name = attr_lookup.get("name") or t_id
                if t_id:
                    discovered_tables.add(t_id)
                    self._ensure_table_node(t_id, t_name)
                    self.graph.add_edge(Edge(source_id=attr_id, target_id=t_id, relationship_type="maps_to"))
                    self.graph.add_edge(Edge(source_id=t_id, target_id=model_id, relationship_type="feeds"))

            # Registra como objeto semântico exposto
            semantic_objects.add(attr_id)
            self.graph.add_edge(Edge(source_id=model_id, target_id=attr_id, relationship_type="defines"))

            # Relacionamentos embutidos no atributo
            for rel in attr.get("relationships", []):
                p_obj = rel.get("parent") or {}
                c_obj = rel.get("child") or {}
                p_id = p_obj.get("objectId") or p_obj.get("id")
                c_id = c_obj.get("objectId") or c_obj.get("id")
                r_type = rel.get("relationshipType") or rel.get("type") or "relates_to"
                if p_id and c_id:
                    if p_id not in self.graph.nodes:
                        self.graph.add_node(Node(id=p_id, name=p_obj.get("name", p_id), type="attribute"))
                    if c_id not in self.graph.nodes:
                        self.graph.add_node(Node(id=c_id, name=c_obj.get("name", c_id), type="attribute"))
                    self.graph.add_edge(
                        Edge(source_id=p_id, target_id=c_id, relationship_type="relates_to", properties={"relation_type": r_type})
                    )

        # 4. Relacionamentos entre Atributos (Hierarquias de lista avulsa)
        for rel in relationships_data:
            p_obj = rel.get("parent") or {}
            c_obj = rel.get("child") or {}
            parent_id = rel.get("parentId") or rel.get("parentAttributeId") or p_obj.get("objectId") or p_obj.get("id")
            child_id = rel.get("childId") or rel.get("childAttributeId") or c_obj.get("objectId") or c_obj.get("id")
            rel_type = rel.get("type") or rel.get("relationType") or rel.get("relationshipType") or "1_TO_N"

            if parent_id and child_id:
                if parent_id not in self.graph.nodes:
                    self.graph.add_node(Node(id=parent_id, name=p_obj.get("name", parent_id), type="attribute"))
                if child_id not in self.graph.nodes:
                    self.graph.add_node(Node(id=child_id, name=c_obj.get("name", child_id), type="attribute"))
                self.graph.add_edge(
                    Edge(
                        source_id=parent_id,
                        target_id=child_id,
                        relationship_type="relates_to",
                        properties={"relation_type": rel_type}
                    )
                )

        # 5. Fact Metrics
        for fm in fact_metrics_data:
            info = fm.get("information") or {}
            fm_id = info.get("objectId") or fm.get("id") or fm.get("factMetricId")
            if not fm_id:
                continue
            fm_name = info.get("name") or fm.get("name") or fm_id
            fm_desc = info.get("description") or fm.get("description", "")

            self.graph.add_node(
                Node(
                    id=fm_id,
                    name=fm_name,
                    type="fact_metric",
                    properties={
                        "data_type": str(fm.get("fact", {}).get("dataType") or fm.get("dataType", "")),
                        "description": fm_desc,
                        "function": fm.get("function", "")
                    }
                )
            )
            self.graph.add_edge(
                Edge(source_id=model_id, target_id=fm_id, relationship_type="contains")
            )
            self.graph.add_edge(
                Edge(source_id=model_id, target_id=fm_id, relationship_type="defines")
            )
            semantic_objects.add(fm_id)

            # Vínculo com tabela de origem via expressões
            fact_obj = fm.get("fact") or {}
            for expr in fact_obj.get("expressions", []):
                for tbl in expr.get("tables", []):
                    t_id = tbl.get("objectId") or tbl.get("id") or (tbl if isinstance(tbl, str) else "")
                    t_name = tbl.get("name", t_id) if isinstance(tbl, dict) else t_id
                    if t_id:
                        discovered_tables.add(t_id)
                        self._ensure_table_node(t_id, t_name)
                        self.graph.add_edge(
                            Edge(source_id=fm_id, target_id=t_id, relationship_type="sources_from")
                        )
                        self.graph.add_edge(
                            Edge(source_id=t_id, target_id=model_id, relationship_type="feeds")
                        )

            # Vínculo com tabela direta se presente
            tbl_info = fm.get("table") or {}
            tbl_id = tbl_info.get("objectId") or tbl_info.get("id") or fm.get("tableId")
            if tbl_id:
                discovered_tables.add(tbl_id)
                self._ensure_table_node(tbl_id, tbl_info.get("name", tbl_id))
                self.graph.add_edge(
                    Edge(source_id=fm_id, target_id=tbl_id, relationship_type="sources_from")
                )
                self.graph.add_edge(
                    Edge(source_id=tbl_id, target_id=model_id, relationship_type="feeds")
                )

        # 6. Métricas e Fórmulas Calculadas
        for m_raw in metrics_data:
            m_def = MetricParser.parse_metric_dict(m_raw)
            if not m_def.id:
                continue

            self.graph.add_node(
                Node(
                    id=m_def.id,
                    name=m_def.name,
                    type="metric",
                    properties={
                        "formula": m_def.formula_text,
                        "aggregation": m_def.aggregation,
                        "sub_type": m_def.sub_type,
                        "is_compound": m_def.is_compound,
                        "dimensionality": m_def.dimensionality
                    }
                )
            )
            self.graph.add_edge(
                Edge(source_id=model_id, target_id=m_def.id, relationship_type="contains")
            )
            self.graph.add_edge(
                Edge(source_id=model_id, target_id=m_def.id, relationship_type="defines")
            )
            semantic_objects.add(m_def.id)

            # Dependências da métrica (calculates_from)
            for ref in m_def.referenced_objects:
                target_node_type = (
                    "metric" if ref.sub_type in ("METRIC", "AGG_METRIC")
                    else "fact_metric" if "FACT" in ref.sub_type
                    else "attribute" if "ATTRIBUTE" in ref.sub_type
                    else "object"
                )

                if ref.object_id not in self.graph.nodes:
                    self.graph.add_node(
                        Node(id=ref.object_id, name=ref.name, type=target_node_type)
                    )

                self.graph.add_edge(
                    Edge(
                        source_id=m_def.id,
                        target_id=ref.object_id,
                        relationship_type="calculates_from"
                    )
                )

            self.graph.metrics_catalog[m_def.id] = m_def

        # 7. Fonte de Dados (Upstream: DataSource -> Tabelas)
        if datasource_data:
            ds_id = datasource_data.get("id") or "ds_default"
            ds_name = datasource_data.get("name") or "Data Source"
            self.graph.add_node(
                Node(
                    id=ds_id,
                    name=ds_name,
                    type="datasource",
                    properties=datasource_data
                )
            )
            for t_id in discovered_tables:
                self.graph.add_edge(
                    Edge(source_id=ds_id, target_id=t_id, relationship_type="provides")
                )

        # 8. Dependentes Downstream (Objetos -> Dashboards, Reports, Bots/Agents)
        if dependents_data:
            for dep in dependents_data:
                dep_id = dep.get("id")
                if not dep_id:
                    continue
                dep_name = dep.get("name") or dep_id
                dep_type = dep.get("type") or "dossier"

                self.graph.add_node(
                    Node(
                        id=dep_id,
                        name=dep_name,
                        type=dep_type,
                        properties=dep
                    )
                )

                # Conecta objetos semânticos expostos do modelo aos dependentes
                if semantic_objects:
                    for s_id in semantic_objects:
                        self.graph.add_edge(
                            Edge(source_id=s_id, target_id=dep_id, relationship_type="used_by")
                        )
                else:
                    self.graph.add_edge(
                        Edge(source_id=model_id, target_id=dep_id, relationship_type="used_by")
                    )

        return self.graph
