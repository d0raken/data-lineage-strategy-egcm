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

    def get_datasource_info(self, model_id: str) -> Optional[Dict[str, Any]]:
        """Extrai informação da fonte de dados (DB Instance / conexão) do modelo."""
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
        try:
            from mstrio.project_objects.datasets.super_cube import SuperCube
            cube = SuperCube(connection=self.connection, id=model_id, progress_bar=False)
            raw_deps = cube.list_dependents()
            for d in raw_deps:
                d_id = d.get("id") or d.get("objectId")
                if not d_id:
                    continue
                d_name = d.get("name") or d_id
                d_type = d.get("type")
                d_subtype = d.get("subtype")

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
        except Exception as e:
            logger.debug("Não foi possível obter dependentes do modelo %s: %s", model_id, e)
        return dependents
