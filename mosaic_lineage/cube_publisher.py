"""Module to publish lineage data as a Strategy SuperCube for Dossier Sankey visualization."""

import json
import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from mstrio.connection import Connection
from mstrio.object_management import Folder, full_search
from mstrio.project_objects.datasets import SuperCube
from mstrio.types import ObjectTypes
from mosaic_lineage.models import LineageGraph, Node

logger = logging.getLogger("mosaic_lineage.cube_publisher")


class CubePublisher:
    """Publica grafo de linhagem diretamente em um Cubo em memória no Strategy."""

    def __init__(self, connection: Connection):
        self.connection = connection

    def get_or_create_reports_folder(self, subfolder_name: str = "Data Lineage") -> Optional[Folder]:
        """Localiza a pasta de relatórios ('Public Objects > Reports' ou 'Objetos Públicos > Relatórios') e cria a subpasta de destino se não existir."""
        project_name = getattr(self.connection, "project_name", "")

        # 1. Tentar caminhos candidatos em inglês e português
        parent_folder: Optional[Folder] = None
        candidate_paths = [
            f"/{project_name}/Public Objects/Reports" if project_name else "",
            f"/{project_name}/Objetos Públicos/Relatórios" if project_name else "",
            f"/{project_name}/Objetos públicos/Relatórios" if project_name else "",
            f"/{project_name}/Public Objects/Relatórios" if project_name else "",
            f"/{project_name}/Objetos Públicos/Reports" if project_name else "",
            "/Public Objects/Reports",
            "/Objetos Públicos/Relatórios",
            "/Objetos públicos/Relatórios",
            "Public Objects/Reports",
            "Objetos Públicos/Relatórios",
            "Objetos públicos/Relatórios",
            "/Public Objects",
            "/Objetos Públicos",
            "/Objetos públicos"
        ]

        for p in candidate_paths:
            if not p:
                continue
            try:
                f = Folder(connection=self.connection, path=p)
                if f and getattr(f, "id", None):
                    parent_folder = f
                    logger.info("Pasta pai de relatórios encontrada via path: %s (id: %s)", p, f.id)
                    break
            except Exception:
                continue

        # 2. Fallback de busca se path direto falhar
        if not parent_folder:
            logger.info("Buscando pasta Reports/Relatórios via full_search...")
            proj_id = getattr(self.connection, "project_id", None)
            for search_term in ["Relatórios", "Reports", "Objetos públicos", "Objetos Públicos", "Public Objects"]:
                try:
                    results = full_search(
                        connection=self.connection,
                        name=search_term,
                        object_types=[ObjectTypes.FOLDER],
                        project=proj_id,
                        to_dictionary=False
                    )
                    for r in results:
                        path_str = str(getattr(r, "path", ""))
                        path_lower = path_str.lower()
                        r_name_lower = getattr(r, "name", "").lower()
                        if ("objetos" in path_lower or "public" in path_lower) and r_name_lower in ("relatórios", "reports"):
                            parent_folder = Folder(connection=self.connection, id=r.id)
                            logger.info("Pasta pai identificada via search '%s': %s (id: %s)", search_term, path_str, r.id)
                            break
                    if parent_folder:
                        break
                except Exception as e:
                    logger.warning("Falha no full_search para pasta '%s': %s", search_term, e)

        # 3. Localizar ou criar a subpasta destino
        if parent_folder:
            try:
                contents = parent_folder.get_contents()
                for item in contents:
                    if getattr(item, "name", "").lower() == subfolder_name.lower():
                        logger.info("Subpasta '%s' já existe com ID %s", item.name, item.id)
                        return Folder(connection=self.connection, id=item.id)
            except Exception as e:
                logger.warning("Não foi possível listar conteúdo de %s: %s", getattr(parent_folder, "name", "pasta pai"), e)

            # Criar a subpasta
            logger.info("Criando subpasta '%s' dentro de '%s'...", subfolder_name, getattr(parent_folder, "name", "pasta pai"))
            try:
                new_folder = Folder.create(
                    connection=self.connection,
                    name=subfolder_name,
                    parent=parent_folder,
                    description="Data Lineage cubes and semantic graphs"
                )
                return new_folder
            except Exception as e:
                logger.warning("Subpasta '%s' não pôde ser criada (já existe ou erro): %s. Buscando via search...", subfolder_name, e)
                try:
                    results = full_search(
                        connection=self.connection,
                        name=subfolder_name,
                        object_types=[ObjectTypes.FOLDER],
                        project=getattr(self.connection, "project_id", None),
                        to_dictionary=False
                    )
                    for r in results:
                        if getattr(r, "name", "").lower() == subfolder_name.lower():
                            logger.info("Subpasta '%s' localizada com sucesso via search (id: %s)", r.name, r.id)
                            return Folder(connection=self.connection, id=r.id)
                except Exception as e_search:
                    logger.debug("Busca por subpasta existente falhou: %s", e_search)
                return parent_folder

        # Fallback resiliente caso não encontre hierarquia pública
        logger.warning("Pasta de relatórios públicos não localizada explicitamente. Tentando criar na raiz.")
        try:
            return Folder.create(connection=self.connection, name=subfolder_name)
        except Exception:
            return None

    def build_sankey_dataframe(self, graph: LineageGraph) -> pd.DataFrame:
        """Gera DataFrame desnormalizado com atributos dedicados por estágio para Sankey e comparação no Dossier.

        Colunas geradas:
        - source_name: apenas o banco de dados / instância de conexão de origem (DB Instance)
        - table_name: tabela física ou lógica utilizada
        - model_name: modelo analítico Mosaic
        - object_name: atributo, métrica de fato ou métrica calculada
        - object_type: tipo do objeto (attribute, fact_metric, metric)
        - dependent_name: objeto consumidor downstream (dossier, report, bot_agent) ou '(Nenhum)'
        - dependent_type: tipo do dependente (dossier, report, bot_agent, none)
        - weight: métrica de contagem / peso (numérico = 1)
        """
        rows = []
        model_nodes = [n for n in graph.nodes.values() if n.type == "data_model"]

        if not model_nodes:
            for n in graph.nodes.values():
                rows.append({
                    "source_name": "N/A",
                    "table_name": "N/A",
                    "model_name": n.name,
                    "object_name": n.name,
                    "object_type": n.type,
                    "formula": "N/A",
                    "aggregation": "None",
                    "is_compound": "False",
                    "dependent_name": "(Nenhum)",
                    "dependent_type": "none",
                    "weight": 1
                })
            if not rows:
                rows.append({
                    "source_name": "N/A",
                    "table_name": "N/A",
                    "model_name": "N/A",
                    "object_name": "N/A",
                    "object_type": "none",
                    "formula": "N/A",
                    "aggregation": "None",
                    "is_compound": "False",
                    "dependent_name": "N/A",
                    "dependent_type": "none",
                    "weight": 0
                })
            return pd.DataFrame(rows)

        def get_object_table_ids(obj_id: str, visited: Optional[set] = None) -> set:
            """Busca tabelas associadas a um objeto, inclusive recursivamente para métricas calculadas."""
            if visited is None:
                visited = set()
            if obj_id in visited:
                return set()
            visited.add(obj_id)

            # 1. Tabelas diretas via maps_to ou sources_from
            tables = {
                e.target_id for e in graph.edges
                if e.source_id == obj_id and e.relationship_type in ("maps_to", "sources_from") and e.target_id in graph.nodes
            }
            if tables:
                return tables

            # 2. Se for métrica calculada, rastrear objetos referenciados via calculates_from
            ref_ids = [
                e.target_id for e in graph.edges
                if e.source_id == obj_id and e.relationship_type == "calculates_from" and e.target_id in graph.nodes
            ]
            for ref_id in ref_ids:
                tables.update(get_object_table_ids(ref_id, visited))

            return tables

        def get_first_fact_metric_for_metric(m_id: str, visited: Optional[set] = None) -> Optional[Node]:
            """Encontra a primeira fact_metric referenciada na fórmula de uma métrica calculada."""
            if visited is None:
                visited = set()
            if m_id in visited:
                return None
            visited.add(m_id)

            ref_ids = [
                e.target_id for e in graph.edges
                if e.source_id == m_id and e.relationship_type == "calculates_from" and e.target_id in graph.nodes
            ]
            for r_id in ref_ids:
                node = graph.nodes[r_id]
                if node.type == "fact_metric":
                    return node
            for r_id in ref_ids:
                node = graph.nodes[r_id]
                if node.type == "metric":
                    sub = get_first_fact_metric_for_metric(r_id, visited)
                    if sub:
                        return sub
            return None

        for model in model_nodes:
            # 1. Tabelas que alimentam este modelo
            model_table_ids = [
                e.source_id for e in graph.edges
                if e.target_id == model.id and e.relationship_type == "feeds" and e.source_id in graph.nodes
            ]
            model_tables = [graph.nodes[tid] for tid in dict.fromkeys(model_table_ids)]
            if not model_tables:
                model_tables = [n for n in graph.nodes.values() if n.type == "table"]
            if not model_tables:
                model_tables = [None]

            # 2. Objetos semânticos do modelo
            model_obj_ids = [
                e.target_id for e in graph.edges
                if e.source_id == model.id and e.relationship_type in ("defines", "contains") and e.target_id in graph.nodes
            ]
            for m_id in graph.metrics_catalog:
                if m_id in graph.nodes and m_id not in model_obj_ids:
                    model_obj_ids.append(m_id)

            model_objects = [graph.nodes[oid] for oid in dict.fromkeys(model_obj_ids) if oid in graph.nodes]
            if not model_objects:
                model_objects = [n for n in graph.nodes.values() if n.type in ("attribute", "fact_metric", "metric")]

            base_objects = [n for n in model_objects if n and n.type in ("attribute", "fact_metric")]
            calc_metrics = [n for n in model_objects if n and n.type == "metric"]
            # Garante que métricas do catálogo também estejam em calc_metrics se ausentes
            for m_id, m_def in graph.metrics_catalog.items():
                if m_id in graph.nodes and graph.nodes[m_id] not in calc_metrics:
                    calc_metrics.append(graph.nodes[m_id])

            # 3. Para cada tabela, identificar Data Source upstream
            for tbl in model_tables:
                datasources = []
                if tbl:
                    ds_ids = [
                        e.source_id for e in graph.edges
                        if e.target_id == tbl.id and e.relationship_type == "provides" and e.source_id in graph.nodes
                    ]
                    datasources = [graph.nodes[ds_id] for ds_id in dict.fromkeys(ds_ids)]

                if not datasources:
                    datasources = [n for n in graph.nodes.values() if n.type == "datasource"]
                if not datasources:
                    datasources = [None]

                for ds in datasources:
                    ds_name = ds.name if ds else "In-Memory / File Import"
                    tbl_name = tbl.name if tbl else "(Sem Tabela)"

                    # 4.A. Relacionamento Direto: Objetos Base (Attributes e Fact Metrics) -> Dependentes
                    for obj in base_objects:
                        obj_table_ids = get_object_table_ids(obj.id)
                        if tbl and obj_table_ids and tbl.id not in obj_table_ids:
                            continue

                        obj_name = obj.name
                        obj_type = obj.type

                        if obj_type == "fact_metric":
                            fn = obj.properties.get("function") or "Fact"
                            obj_formula = f"{fn}({obj.name})"
                            obj_aggregation = fn
                            obj_is_compound = "False"
                        else:
                            obj_formula = "N/A"
                            obj_aggregation = "None"
                            obj_is_compound = "False"

                        dep_ids = [
                            e.target_id for e in graph.edges
                            if e.source_id == obj.id and e.relationship_type == "used_by" and e.target_id in graph.nodes
                        ]
                        if not dep_ids:
                            dep_ids = [
                                e.target_id for e in graph.edges
                                if e.source_id == model.id and e.relationship_type == "used_by" and e.target_id in graph.nodes
                            ]
                        dependents = [graph.nodes[did] for did in dict.fromkeys(dep_ids)]
                        if not dependents:
                            dependents = [None]

                        for dep in dependents:
                            rows.append({
                                "source_name": ds_name,
                                "table_name": tbl_name,
                                "model_name": model.name,
                                "object_name": obj_name,
                                "object_type": obj_type,
                                "metric_name": "(Direto)",
                                "formula": obj_formula,
                                "aggregation": obj_aggregation,
                                "is_compound": obj_is_compound,
                                "dependent_name": dep.name if dep else "(Nenhum)",
                                "dependent_type": dep.type if dep else "none",
                                "weight": 1
                            })

                    # 4.B. Relacionamento com Métrica Calculada: Fact Metric -> Metric Name -> Dependentes
                    for m_obj in calc_metrics:
                        m_def = graph.metrics_catalog.get(m_obj.id)
                        fm_node = get_first_fact_metric_for_metric(m_obj.id)

                        if fm_node:
                            fm_table_ids = get_object_table_ids(fm_node.id)
                            if tbl and fm_table_ids and tbl.id not in fm_table_ids:
                                continue
                            parent_obj_name = fm_node.name
                            parent_obj_type = "fact_metric"
                        else:
                            m_table_ids = get_object_table_ids(m_obj.id)
                            if tbl and m_table_ids and tbl.id not in m_table_ids:
                                continue
                            parent_obj_name = "(Métrica Calculada)"
                            parent_obj_type = "metric"

                        if m_def and m_def.formula_text:
                            calc_formula = m_def.formula_text
                            calc_aggregation = m_def.aggregation or "Default"
                            calc_is_compound = "True" if m_def.is_compound else "False"
                        elif m_obj.properties.get("formula"):
                            calc_formula = str(m_obj.properties.get("formula"))
                            calc_aggregation = str(m_obj.properties.get("aggregation", "Default"))
                            calc_is_compound = str(m_obj.properties.get("is_compound", "False"))
                        elif m_def:
                            calc_formula = m_def.formula_text or "N/A"
                            calc_aggregation = m_def.aggregation or "Default"
                            calc_is_compound = "True" if m_def.is_compound else "False"
                        else:
                            calc_formula = "N/A"
                            calc_aggregation = "None"
                            calc_is_compound = "False"

                        dep_ids = [
                            e.target_id for e in graph.edges
                            if e.source_id == m_obj.id and e.relationship_type == "used_by" and e.target_id in graph.nodes
                        ]
                        if not dep_ids:
                            dep_ids = [
                                e.target_id for e in graph.edges
                                if e.source_id == model.id and e.relationship_type == "used_by" and e.target_id in graph.nodes
                            ]
                        dependents = [graph.nodes[did] for did in dict.fromkeys(dep_ids)]
                        if not dependents:
                            dependents = [None]

                        for dep in dependents:
                            rows.append({
                                "source_name": ds_name,
                                "table_name": tbl_name,
                                "model_name": model.name,
                                "object_name": parent_obj_name,
                                "object_type": parent_obj_type,
                                "metric_name": m_obj.name,
                                "formula": calc_formula,
                                "aggregation": calc_aggregation,
                                "is_compound": calc_is_compound,
                                "dependent_name": dep.name if dep else "(Nenhum)",
                                "dependent_type": dep.type if dep else "none",
                                "weight": 1
                            })

                    if not base_objects and not calc_metrics:
                        rows.append({
                            "source_name": ds_name,
                            "table_name": tbl_name,
                            "model_name": model.name,
                            "object_name": "(Sem Objetos)",
                            "object_type": "none",
                            "metric_name": "(N/A)",
                            "formula": "N/A",
                            "aggregation": "None",
                            "is_compound": "False",
                            "dependent_name": "(Nenhum)",
                            "dependent_type": "none",
                            "weight": 1
                        })

        if not rows:
            rows.append({
                "source_name": "N/A",
                "table_name": "N/A",
                "model_name": "N/A",
                "object_name": "N/A",
                "object_type": "none",
                "metric_name": "(N/A)",
                "formula": "N/A",
                "aggregation": "None",
                "is_compound": "False",
                "dependent_name": "N/A",
                "dependent_type": "none",
                "weight": 0
            })

        df = pd.DataFrame(rows).drop_duplicates()
        return df.reset_index(drop=True)

    def build_nodes_dataframe(self, graph: LineageGraph) -> pd.DataFrame:
        """Gera DataFrame de nós."""
        rows = [
            {
                "node_id": n.id,
                "node_name": n.name,
                "node_type": n.type,
                "properties": json.dumps(n.properties, ensure_ascii=False)
            }
            for n in graph.nodes.values()
        ]
        if not rows:
            rows.append({
                "node_id": "N/A",
                "node_name": "N/A",
                "node_type": "none",
                "properties": "{}"
            })
        return pd.DataFrame(rows)

    def build_edges_dataframe(self, graph: LineageGraph) -> pd.DataFrame:
        """Gera DataFrame de arestas."""
        rows = [
            {
                "source_id": e.source_id,
                "target_id": e.target_id,
                "relationship_type": e.relationship_type
            }
            for e in graph.edges
        ]
        if not rows:
            rows.append({
                "source_id": "N/A",
                "target_id": "N/A",
                "relationship_type": "none"
            })
        return pd.DataFrame(rows)

    def build_metrics_dataframe(self, graph: LineageGraph) -> pd.DataFrame:
        """Gera DataFrame de catálogo de métricas com chaves compatíveis com Lineage_Sankey."""
        model_nodes = [n for n in graph.nodes.values() if n.type == "data_model"]
        primary_model_name = model_nodes[0].name if model_nodes else "N/A"

        rows = [
            {
                "model_name": primary_model_name,
                "object_name": m.name,
                "metric_id": m.id,
                "metric_name": m.name,
                "formula": m.formula_text,
                "sub_type": m.sub_type,
                "aggregation": m.aggregation or "",
                "is_compound": "True" if m.is_compound else "False",
                "dependencies_count": len(m.referenced_objects),
                "dependencies_ids": ";".join([ref.object_id for ref in m.referenced_objects])
            }
            for m in graph.metrics_catalog.values()
        ]
        if not rows:
            rows.append({
                "model_name": primary_model_name,
                "object_name": "N/A",
                "metric_id": "N/A",
                "metric_name": "N/A",
                "formula": "N/A",
                "sub_type": "none",
                "aggregation": "none",
                "is_compound": "False",
                "dependencies_count": 0,
                "dependencies_ids": ""
            })
        return pd.DataFrame(rows)

    def publish(
        self,
        graph: LineageGraph,
        cube_name: str = "Mosaic Lineage Sankey Cube",
        subfolder_name: str = "Data Lineage"
    ) -> SuperCube:
        """Cria e publica o SuperCube contendo as 4 tabelas de lineage na pasta selecionada."""
        target_folder = self.get_or_create_reports_folder(subfolder_name=subfolder_name)
        folder_id = getattr(target_folder, "id", None)
        logger.info("Publicando cubo '%s' na pasta ID: %s", cube_name, folder_id)

        df_sankey = self.build_sankey_dataframe(graph)
        df_nodes = self.build_nodes_dataframe(graph)
        df_edges = self.build_edges_dataframe(graph)
        df_metrics = self.build_metrics_dataframe(graph)

        cube = SuperCube(connection=self.connection, name=cube_name, progress_bar=False)
        cube.add_table(name="Lineage_Sankey", data_frame=df_sankey, update_policy="replace")
        cube.add_table(name="Nodes", data_frame=df_nodes, update_policy="replace")
        cube.add_table(name="Edges", data_frame=df_edges, update_policy="replace")
        cube.add_table(name="Metrics_Catalog", data_frame=df_metrics, update_policy="replace")

        logger.info("Enviando dados e publicando cubo no Strategy Library...")
        cube.create(folder_id=folder_id, force=True)
        logger.info("Cubo publicado com sucesso! ID do Cubo: %s", cube.id)
        return cube
