"""Client for Strategy Mosaic REST API and mstrio connection."""

import logging
from typing import Any, Dict, List, Optional
from mstrio.connection import Connection
from mosaic_lineage.config import Config

logger = logging.getLogger("mosaic_lineage.client")


class MosaicClient:
    """Wrapper para autenticação e consultas aos endpoints REST de Data Models do Strategy Mosaic."""

    def __init__(self, config: Optional[Config] = None, connection: Optional[Connection] = None):
        self.config = config or Config()
        if connection:
            self.connection = connection
        else:
            self.config.validate()
            logger.info("Autenticando via mstrio Connection com base_url=%s", self.config.base_url)
            self.connection = Connection(
                base_url=self.config.base_url,
                username=self.config.username,
                password=self.config.password,
                project_id=self.config.project_id,
                project_name=self.config.project_name,
                ssl_verify=self.config.ssl_verify
            )

    def _get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """Executa requisição GET autenticada via Connection."""
        clean_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"

        # Garante que a requisição vá para /api/... caso base_url do mstrio tenha removido /api
        if not self.connection.base_url.endswith("/api") and not clean_endpoint.startswith("/api/"):
            clean_endpoint = f"/api{clean_endpoint}"
        elif self.connection.base_url.endswith("/api") and clean_endpoint.startswith("/api/"):
            clean_endpoint = clean_endpoint[4:]

        headers = {}
        proj_id = getattr(self.connection, "project_id", None)
        if proj_id and isinstance(proj_id, str):
            headers["X-MSTR-ProjectID"] = proj_id

        logger.debug("GET endpoint: %s, params: %s", clean_endpoint, params)
        if headers:
            response = self.connection.get(endpoint=clean_endpoint, headers=headers, params=params)
        else:
            response = self.connection.get(endpoint=clean_endpoint, params=params)

        if response.status_code >= 400:
            logger.warning(
                "Endpoint %s retornou status %s: %s",
                clean_endpoint, response.status_code, response.text
            )
            response.raise_for_status()

        return response.json()

    def list_data_models(self) -> List[Dict[str, Any]]:
        """Lista todos os data models disponíveis no projeto atual."""
        try:
            from mstrio.project_objects.mosaic_model import list_mosaic_models
            proj_id = getattr(self.connection, "project_id", None)
            models = list_mosaic_models(connection=self.connection, project_id=proj_id)
            return [{"id": m.id, "name": m.name, "description": getattr(m, "description", "")} for m in models]
        except Exception as e:
            logger.warning("Falha ao listar via list_mosaic_models: %s. Tentando endpoint REST...", e)
            try:
                data = self._get("/api/model/dataModels")
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    return data.get("dataModels") or data.get("models") or [data]
            except Exception as e2:
                logger.error("Consulta REST também falhou: %s", e2)
            return []

    def get_data_model(self, model_id: str) -> Dict[str, Any]:
        """Obtém metadados detalhados de um modelo específico."""
        endpoint = f"/model/dataModels/{model_id}"
        return self._get(endpoint)

    def get_metrics(self, model_id: str) -> List[Dict[str, Any]]:
        """Obtém todas as métricas contidas no data model."""
        endpoint = f"/model/dataModels/{model_id}/metrics"
        try:
            res = self._get(endpoint)
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                return res.get("metrics") or res.get("items") or []
            return []
        except Exception as e:
            logger.warning("Erro ao consultar métricas para modelo %s: %s", model_id, e)
            return []

    def get_fact_metrics(self, model_id: str) -> List[Dict[str, Any]]:
        """Obtém fact metrics vinculadas diretamente a colunas no data model."""
        endpoint = f"/model/dataModels/{model_id}/factMetrics"
        try:
            res = self._get(endpoint)
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                return res.get("factMetrics") or res.get("items") or []
            return []
        except Exception as e:
            logger.warning("Erro ao consultar factMetrics para modelo %s: %s", model_id, e)
            return []

    def get_attributes(self, model_id: str) -> List[Dict[str, Any]]:
        """Obtém todos os atributos configurados no data model."""
        endpoint = f"/model/dataModels/{model_id}/attributes"
        try:
            res = self._get(endpoint)
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                return res.get("attributes") or res.get("items") or []
            return []
        except Exception as e:
            logger.warning("Erro ao consultar attributes para modelo %s: %s", model_id, e)
            return []

    def get_relationships(
        self,
        model_id: str,
        attributes: Optional[List[Dict[str, Any]]] = None
    ) -> List[Dict[str, Any]]:
        """Obtém relacionamentos entre atributos dentro do data model."""
        rels: List[Dict[str, Any]] = []
        if attributes:
            for attr in attributes:
                for rel in attr.get("relationships", []):
                    rels.append(rel)
        if rels:
            return rels

        endpoint = f"/model/dataModels/{model_id}/relationships"
        try:
            res = self._get(endpoint)
            if isinstance(res, list):
                return res
            if isinstance(res, dict):
                return res.get("relationships") or res.get("items") or []
            return []
        except Exception as e:
            logger.debug("Endpoint dedicado de relationships não retornou dados para modelo %s: %s", model_id, e)
            return []

    def get_tables(self, model_id: str) -> List[Dict[str, Any]]:
        """Obtém todas as tabelas lógicas configuradas no data model."""
        endpoint = f"/model/dataModels/{model_id}/tables"
        try:
            res = self._get(endpoint)
            if isinstance(res, dict):
                return res.get("tables") or []
            if isinstance(res, list):
                return res
            return []
        except Exception as e:
            logger.debug("Erro ao consultar tabelas para modelo %s: %s", model_id, e)
            return []

    def get_table_details(self, model_id: str, table_id: str) -> Optional[Dict[str, Any]]:
        """Obtém detalhes de uma tabela específica, incluindo primaryDataSource e physicalTable."""
        endpoint = f"/model/dataModels/{model_id}/tables/{table_id}"
        try:
            return self._get(endpoint)
        except Exception as e:
            logger.debug("Erro ao consultar detalhes da tabela %s para modelo %s: %s", table_id, model_id, e)
            return None

    def get_datasource_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Extrai informação da fonte de dados (DB Instance / conexão) do modelo."""
        import json
        ds_map: Dict[str, Dict[str, Any]] = {}
        ds_cache: Dict[str, Any] = {}

        def _fetch_ds(ds_id: str) -> Optional[Dict[str, Any]]:
            if ds_id in ds_cache:
                return ds_cache[ds_id]
            try:
                data = self._get(f"/api/datasources/{ds_id}")
                ds_cache[ds_id] = data
                return data
            except Exception:
                return None

        def _scan_pipeline(node: Any) -> List[str]:
            found = []
            if isinstance(node, dict):
                if "importSource" in node and isinstance(node["importSource"], dict):
                    ds_id = node["importSource"].get("dataSourceId")
                    if ds_id:
                        found.append(ds_id)
                if "dataSourceId" in node and node["dataSourceId"]:
                    found.append(node["dataSourceId"])
                for v in node.values():
                    found.extend(_scan_pipeline(v))
            elif isinstance(node, list):
                for item in node:
                    found.extend(_scan_pipeline(item))
            return found

        # 1. Estratégia Nativa Mosaic REST API: inspecionar tabelas e physicalTables do modelo
        try:
            tables = self.get_tables(model_id)
            for t in tables:
                t_info = t.get("information", {})
                t_id = t_info.get("objectId")
                if not t_id:
                    continue
                t_detail = self.get_table_details(model_id, t_id)
                if not t_detail:
                    continue

                # A. primaryDataSource direto
                pds = t_detail.get("primaryDataSource")
                if pds and pds.get("name"):
                    pds_name = pds.get("name")
                    ds_id = pds.get("objectId") or pds.get("id") or f"ds_{pds_name.lower().replace(' ', '_')}"
                    ds_map[ds_id] = {
                        "id": ds_id,
                        "name": pds_name,
                        "type": "database_connection"
                    }
                    continue

                # B. physicalTable pipeline importSource
                pt = t_detail.get("physicalTable", {})
                pl = pt.get("pipeline")
                if pl:
                    if isinstance(pl, str):
                        try:
                            pl = json.loads(pl)
                        except Exception:
                            pl = None
                    if pl:
                        ds_ids = _scan_pipeline(pl)
                        for ds_id in set(ds_ids):
                            ds_obj = _fetch_ds(ds_id)
                            if ds_obj and ds_obj.get("name"):
                                ds_map[ds_id] = {
                                    "id": ds_id,
                                    "name": ds_obj.get("name"),
                                    "type": "database_connection"
                                }
        except Exception as e:
            logger.debug("Falha ao consultar tabelas para extrair datasources do modelo %s: %s", model_id, e)

        if ds_map:
            return list(ds_map.values())[0]

        # 2. Fallback: SuperCube export_sql_view (suportado para alguns cubos legados)
        try:
            from mstrio.project_objects.datasets.super_cube import SuperCube
            cube = SuperCube(connection=self.connection, id=model_id, progress_bar=False)
            sql_view = cube.export_sql_view()
            if sql_view:
                import re
                match = re.search(r"\[DB Instance:\s*([^\]]+)\]", sql_view)
                if match:
                    ds_name = match.group(1).strip()
                    ds_id = None
                    try:
                        datasources_data = self._get("/api/datasources")
                        ds_list = datasources_data.get("datasources", []) if isinstance(datasources_data, dict) else []
                        for ds in ds_list:
                            if ds.get("name") == ds_name:
                                ds_id = ds.get("id")
                                break
                    except Exception:
                        pass
                    return {
                        "id": ds_id or f"ds_{ds_name.lower().replace(' ', '_')}",
                        "name": ds_name,
                        "type": "database_connection"
                    }
        except Exception as e:
            logger.debug("Não foi possível extrair DB Instance via SQL view para modelo %s: %s", model_id, e)

        return None

    def get_dependents(self, model_id: str) -> List[Dict[str, Any]]:
        """Extrai lista de objetos dependentes do modelo (Dossiers, Reports, Bots/Agents)."""
        dependents: List[Dict[str, Any]] = []
        raw_deps: List[Dict[str, Any]] = []
        try:
            from mstrio.project_objects.datasets.super_cube import SuperCube
            cube = SuperCube(connection=self.connection, id=model_id, progress_bar=False)
            raw_deps = cube.list_dependents()
        except Exception as e:
            logger.debug("Tentativa via SuperCube falhou para modelo %s (%s). Tentando full_search...", model_id, e)
            try:
                from mstrio.object_management.search_operations import full_search
                proj_id = getattr(self.connection, "project_id", None)
                if proj_id:
                    for ot in (3, 256, 776, 8):
                        try:
                            found = full_search(
                                connection=self.connection,
                                project=proj_id,
                                uses_object_id=model_id,
                                uses_object_type=ot
                            )
                            if found:
                                raw_deps.extend(found)
                        except Exception:
                            pass
            except Exception as e2:
                logger.debug("full_search também falhou: %s", e2)

        for d in raw_deps:
            d_id = d.get("id") or d.get("objectId")
            if not d_id:
                continue
            d_name = d.get("name") or d_id
            d_type = d.get("type")
            d_subtype = d.get("subtype")

            if d_type == 22:
                # Objeto de Schema interno do Intelligence Server, não expor no grafo downstream
                continue

            if d_subtype == 779 or d_type == 55:
                mapped_type = "dossier"
            elif d_type == 3:
                mapped_type = "report"
            elif d_type == 68:
                mapped_type = "bot_agent"
            elif d_type in (256, 776):
                mapped_type = "cube"
            else:
                mapped_type = "object"

            dependents.append({
                "id": d_id,
                "name": d_name,
                "type": mapped_type,
                "subtype": d_subtype,
                "raw_type": d_type
            })
        return dependents
