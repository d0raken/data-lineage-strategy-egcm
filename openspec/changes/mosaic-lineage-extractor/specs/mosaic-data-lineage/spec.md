## Purpose

Permite a extração automatizada de data lineage ponta a ponta (End-to-End) e catálogo semântico a partir de modelos Strategy Mosaic, abrangendo desde as fontes de dados de banco, tabelas físicas/lógicas, modelo de dados, atributos e métricas até os objetos dependentes downstream (Dashboards, Relatórios, Bots/Agentes de IA), com exportação multi-formato e publicação em SuperCube para diagramas Sankey no Strategy.

## ADDED Requirements

### Requirement: Extração de Metadados de Modelos Mosaic via REST
O sistema SHALL utilizar prioritariamente o `MSTR_PROJECT_ID` para autenticação e escopo da sessão na conexão, e consultar endpoints da Strategy REST API sob `/api/model/dataModels/{dataModelId}` para extrair métricas (`/metrics`), fact metrics (`/factMetrics`), atributos (`/attributes`) e relacionamentos de atributos e tabelas.

#### Scenario: Extração de elementos de modelo com sucesso
- **WHEN** usuário executa extração informando `dataModelId`, credenciais e `MSTR_PROJECT_ID` válido
- **THEN** sistema autentica no projeto via ID, consulta endpoints REST correspondentes e retorna listas estruturadas de atributos, métricas, fact metrics e relacionamentos

#### Scenario: Falha de autenticação ou modelo inexistente
- **WHEN** requisição REST falha com erro 401 ou 404
- **THEN** sistema encerra requisição informando código de erro descritivo sem corromper saídas anteriores

### Requirement: Extração Completa de Definições de Métricas
O sistema SHALL capturar para cada métrica sua fórmula textual legível, tokens de expressão com referências a objetos dependentes, tipo de agregação e dimensionalidade de nível.

#### Scenario: Mapeamento de fórmulas e dependências de métricas
- **WHEN** metadados de métricas são extraídos do modelo
- **THEN** sistema armazena para cada métrica sua expressão calculada, lista de fatos/colunas referenciadas e atributos de nível

### Requirement: Extração de Fontes de Dados Upstream (Data Sources / Conexões)
O sistema SHALL inspecionar a definição do modelo/cubo via `SuperCube.export_sql_view()` ou endpoint `/api/datasources` para identificar a conexão com o banco de dados (DB Instance / Data Source) e conectar as tabelas às suas respectivas fontes de origem.

#### Scenario: Detecção de DB Instance de banco
- **WHEN** metadados do modelo são extraídos
- **THEN** sistema identifica o DB Instance associado (ex: `postgres_emarinho`) e cria nós do tipo `datasource` vinculados às tabelas do modelo via arestas `stores` / `provides`

### Requirement: Extração de Objetos Dependentes Downstream (Consumidores)
O sistema SHALL consultar os dependentes do modelo analítico via `SuperCube.list_dependents()` e endpoints de busca de relacionamentos, identificando Dashboards/Dossiers, Relatórios, Bots/Agentes de IA e Cubos derivados que consomem o modelo.

#### Scenario: Descoberta de dependentes do modelo
- **WHEN** modelo analítico possui objetos que o utilizam no projeto
- **THEN** sistema extrai lista de dependentes com nome, ID, tipo e subtipo, criando nós correspondentes (`dossier`, `report`, `bot_agent`, `cube`) vinculados aos objetos do modelo via arestas `used_by`

### Requirement: Construção de Grafo de Lineage End-to-End (DAG 5 Estágios)
O sistema SHALL sintetizar todas as entidades em um Grafo Direcionado Acíclico (DAG) que possibilite rastreabilidade contínua em 5 estágios:
`Fonte de Dados (DB Connection)` ──▶ `Tabelas` ──▶ `Data Model` ──▶ `Atributos / Métricas` ──▶ `Dependentes (Dashboards / Relatórios / Agentes)`.

#### Scenario: Montagem de grafo completo encadeado
- **WHEN** extração de fontes, tabelas, modelo, atributos, métricas e dependentes é finalizada
- **THEN** sistema monta o grafo conectando cada estágio em sequência para que o fluxo de dados seja contínuo do início ao fim

### Requirement: Exportação Multi-formato de Lineage e Métricas
O sistema SHALL suportar exportação dos dados de lineage e dicionário de métricas nos formatos JSON, YAML e CSV de acordo com parâmetro de execução.

#### Scenario: Exportação para formato selecionado
- **WHEN** usuário especifica formato de exportação via CLI (`--format json`, `--format yaml`, `--format csv` ou `--format all`)
- **THEN** sistema gera arquivos correspondentes contendo grafo de lineage e definições detalhadas de métricas no diretório de destino

### Requirement: Publicação Direta em Cubo no Strategy para Diagrama Sankey, Matriz e Dicionário de Fórmulas
O sistema SHALL publicar o grafo de linhagem diretamente em um `SuperCube` no Strategy, gerando uma tabela desnormalizada `Lineage_Sankey` com colunas de estágio e definição de métricas dedicadas:
- `source_name`: apenas a fonte de dados / conexão com o banco (DB Instance)
- `table_name`: tabela lógica/física utilizada
- `model_name`: modelo de dados Mosaic
- `object_name`: nome do atributo ou métrica
- `object_type`: tipo do objeto (`attribute`, `fact_metric`, `metric`)
- `formula`: fórmula de cálculo resolvida da métrica (ou `'N/A'` para atributos)
- `aggregation`: agregação da métrica (ex: `Sum`, `Avg` ou `'N/A'`)
- `is_compound`: `'True'` / `'False'` (ou `'N/A'`)
- `dependent_name`: objeto dependente downstream (`dossier`, `report`, `bot_agent` ou `(Nenhum)`)
- `dependent_type`: tipo do dependente (`dossier`, `report`, `bot_agent`, `none`)
- `weight`: peso numérico (`1`)
Além disso, manter as tabelas `Nodes`, `Edges` e `Metrics_Catalog` (enriquecida com `object_name` e `model_name` para garantir relacionamento natural entre tabelas no Strategy), alocando o cubo sob a hierarquia de relatórios públicos de forma bilíngue (`Public Objects > Reports > Data Lineage` ou `Objetos Públicos > Relatórios > Data Lineage`).

#### Scenario: Visualização unificada no Dossier sem quebra de relacionamentos
- **WHEN** usuário adiciona atributos `source_name`, `table_name`, `model_name`, `object_name` e `formula` em uma planilha/grid ou gráfico no Dossier
- **THEN** todas as informações são apresentadas na mesma linha de visualização sem erros de relacionamentos ausentes entre tabelas do cubo

#### Scenario: Publicação em projetos com idioma inglês ou português
- **WHEN** usuário executa publicação de cubo em um projeto configurado em português (como `INCA`) ou em inglês (como `Strategy Labs`)
- **THEN** sistema resolve automaticamente a pasta pai (`Reports` ou `Relatórios` sob `Public Objects` ou `Objetos Públicos`), cria a subpasta `Data Lineage` e publica o cubo com êxito sem erros de caminho inexistente

#### Scenario: Presença e correspondência de métricas calculadas e fórmulas no Lineage_Sankey
- **WHEN** modelo de dados contiver métricas calculadas (endpoints `/metrics` ou catálogo semântico de métricas)
- **THEN** sistema gera linhas em `Lineage_Sankey` posicionando a métrica calculada em `metric_name`, associada à primeira `fact_metric` da fórmula em `object_name`, preenche `formula` com a expressão textual calculada, e preserva a cadeia até os dependentes downstream

#### Scenario: Preservação de relacionamento direto entre objetos base e dependentes
- **WHEN** atributo ou fact metric for consumido diretamente por relatório/dossier sem métrica calculada intermediária
- **THEN** sistema gera linha conectando diretamente `object_name` ao `dependent_name` com `metric_name="(Direto)"`, garantindo relacionamentos diretos e sem quebra no visual Sankey de 6 níveis


