"""Parser for Strategy metric expressions, tokens and dependencies."""

from typing import Any, Dict, List, Optional, Tuple
from mosaic_lineage.models import MetricDefinition, TokenReference


class MetricParser:
    """Extrai e reconstrói definições e fórmulas de métricas a partir dos tokens da API."""

    @staticmethod
    def parse_metric_dict(raw: Dict[str, Any]) -> MetricDefinition:
        """Converte dicionário retornado da API REST em objeto MetricDefinition."""
        info = raw.get("information") or {}
        metric_id = info.get("objectId") or raw.get("id") or raw.get("metricId") or raw.get("objectId") or ""
        name = info.get("name") or raw.get("name") or raw.get("metricName") or ""
        description = info.get("description") or raw.get("description", "")
        sub_type = info.get("subType") or raw.get("subType") or raw.get("type") or "METRIC"

        expression = raw.get("expression") or {}
        tokens = expression.get("tokens") or raw.get("tokens") or []

        formula_text, referenced_objects, is_compound = MetricParser.analyze_tokens(tokens)

        # Se expression tiver campo text
        if isinstance(expression, dict) and expression.get("text"):
            formula_text = expression.get("text")
        elif raw.get("expressionText"):
            formula_text = raw.get("expressionText")
        elif raw.get("formula"):
            formula_text = raw.get("formula")

        # Verifica embeddedObjects caso tokens não existam ou não tenham referências
        for emb in raw.get("embeddedObjects", []):
            emb_id = emb.get("id") or emb.get("objectId")
            emb_sub = str(emb.get("subType") or "METRIC").upper()
            emb_expr = emb.get("expression", {}).get("text", "")
            if emb_id and not any(r.object_id == emb_id for r in referenced_objects):
                referenced_objects.append(
                    TokenReference(
                        object_id=emb_id,
                        name=emb_expr or emb_id,
                        sub_type=emb_sub,
                        target_type=emb.get("type")
                    )
                )
                if emb_sub in ("METRIC", "AGG_METRIC"):
                    is_compound = True

        aggregation = raw.get("aggregation") or (expression.get("aggregation") if isinstance(expression, dict) else None)
        dimensionality = raw.get("dimensionality") or (expression.get("dimensionality") if isinstance(expression, dict) else []) or []

        return MetricDefinition(
            id=metric_id,
            name=name,
            description=description,
            sub_type=str(sub_type).upper(),
            formula_text=formula_text,
            expression_raw=expression if isinstance(expression, dict) else {},
            referenced_objects=referenced_objects,
            aggregation=aggregation,
            dimensionality=dimensionality if isinstance(dimensionality, list) else [],
            is_compound=is_compound
        )

    @staticmethod
    def analyze_tokens(tokens: List[Dict[str, Any]]) -> Tuple[str, List[TokenReference], bool]:
        """Varre tokens da expressão, monta a string da fórmula e identifica dependências."""
        formula_parts: List[str] = []
        references: List[TokenReference] = []
        seen_refs = set()
        is_compound = False

        for token in tokens:
            t_type = token.get("type", "")
            t_value = token.get("value", "")
            target = token.get("target") or {}

            # Tipos de token que referenciam outros objetos
            if t_type in ("object_reference", "object_at_form", "OBJECT_REFERENCE") or target:
                obj_id = target.get("objectId") or target.get("id") or ""
                obj_name = target.get("name") or t_value or obj_id
                sub_type = str(target.get("subType") or target.get("type") or "UNKNOWN").upper()

                if sub_type in ("METRIC", "AGG_METRIC"):
                    is_compound = True

                if obj_id and obj_id not in seen_refs:
                    seen_refs.add(obj_id)
                    references.append(
                        TokenReference(
                            object_id=obj_id,
                            name=obj_name,
                            sub_type=sub_type,
                            target_type=target.get("type")
                        )
                    )

                formula_parts.append(f"[{obj_name}]" if obj_name else t_value)
            else:
                # Constantes, operadores, funções matemáticas
                formula_parts.append(str(t_value))

        formula_text = " ".join(formula_parts).strip() if formula_parts else ""
        return formula_text, references, is_compound
