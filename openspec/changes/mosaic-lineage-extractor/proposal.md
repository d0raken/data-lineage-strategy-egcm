## Why

Data lineage atual em Strategy/MicroStrategy necessita de rastreabilidade completa de ponta a ponta (End-to-End). O usuário precisa visualizar no Sankey Diagram todo o ciclo de vida do dado: desde a fonte física de dados (conexão com o banco / DB Instance), passando pelas tabelas de origem, modelo Mosaic, objetos semânticos (atributos e métricas) até os artefatos downstream que consomem o modelo (Dashboards/Dossiers, Relatórios, Agentes de IA/Bots).

## What Changes

- Expandir extração de lineage para 5 estágios encadeados:
  1. **Data Source (Fonte de Dados)**: Identificação da conexão/DB Instance de origem (ex: PostgreSQL, Snowflake) via `export_sql_view` / `/api/datasources`.
  2. **Tabelas do Modelo**: Tabelas lógicas e físicas que compõem o modelo.
  3. **Mosaic Data Model**: Entidade central do modelo analítico.
  4. **Objetos Criados**: Atributos, fatos e métricas calculadas/compostas com suas fórmulas e hierarquias.
  5. **Objetos Dependentes (Consumidores)**: Dashboards/Dossiers, Relatórios e Bots/Agentes de IA que utilizam o modelo, descobertos via `list_dependents()` e `/api/searches/dependents`.
- Sintetizar o grafo DAG com fluxo contínuo direcionado e desnormalizado em estágios explícitos:
  1. `source_name`: Apenas a fonte de dados / banco de dados (ex: `postgres_emarinho`).
  2. `table_name`: Tabela física/lógica utilizada pelo modelo.
  3. `model_name`: Modelo de dados Mosaic.
  4. `object_name` e `object_type`: Atributo, métrica de fato ou métrica calculada (`attribute`, `fact_metric`, `metric`).
  5. `formula`, `aggregation`, `is_compound`: Definição e fórmula da métrica diretamente associada à linha do objeto (reconstituída via tokens/expressões para métricas calculadas e agregações para fatos).
  6. `dependent_name` e `dependent_type`: Artefatos downstream consumidores (Dossiers, Relatórios, Bots/Agentes) ou `(Nenhum)`.
- Rastrear tabelas upstream de métricas calculadas (`object_type: metric`) através das dependências dos fatos referenciados pela fórmula, garantindo integridade no caminho `source_name --> table_name --> model_name --> object_name --> formula`.
- Reestruturar tabela `Lineage_Sankey` no SuperCube para conter tanto os nós do fluxo quanto `formula`, eliminando quebra de relacionamentos ao montar planilhas/grids com `source_name --> table_name --> model_name --> object_name --> formula`.
- Harmonizar nomes de chaves entre `Lineage_Sankey` e `Metrics_Catalog` (`object_name`, `model_name`) para que o Strategy estabeleça relacionamento natural entre as tabelas do cubo.
- Suportar internacionalização de pastas no Strategy: salvar e localizar automaticamente sob `Public Objects > Reports > Data Lineage` OU `Objetos Públicos > Relatórios > Data Lineage`.
- Manter exportação multi-formato (JSON, YAML, CSV) enriquecida com metadados de fontes e dependentes.

## Capabilities

### New Capabilities
- `mosaic-data-lineage`: Extração de linhagem ponta a ponta (Fontes de Dados -> Tabelas -> Modelos Mosaic -> Atributos/Métricas -> Objetos Dependentes como Dossiers, Reports e Bots), resolução de fórmulas, exportação multi-formato e publicação de SuperCube para diagrama Sankey no Strategy.

### Modified Capabilities

## Impact

- **Código**: Extensão de `MosaicClient`, `GraphBuilder`, `CubePublisher` e modelos de dados para suportar nós de `datasource` e `dependents`.
- **APIs**: Uso adicional de `SuperCube.export_sql_view()`, `SuperCube.list_dependents()` e `/api/datasources`.
- **Configuração**: Mantém `.env` com autenticação determinística por `MSTR_PROJECT_ID`.
- **Saída**: Grafo e tabela `Lineage_Sankey` com rastreabilidade upstream e downstream completa.
