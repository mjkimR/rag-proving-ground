# Simple RAG 에이전트 아키텍처 (Simple RAG Agent Architecture)

본 문서는 `rag-proving-ground` 프로젝트의 지식 베이스 검색 증강 생성 에이전트인 `simple_rag` 그래프의 내부 파이프라인 및 설계 패턴을 다룹니다.

---

## 1. 개요 및 역할

*   **역할**: 지정된 다중 지식 베이스(Knowledge Base)로부터 질문에 유관한 텍스트 파편(Chunk)을 리트리브하고, 이를 컨텍스트로 보강하여 정확하고 신뢰성 있는 인용 기반 답변을 출력하는 핵심 RAG 에이전트입니다.
*   **특징**: 무상태(Stateless) AI 유틸리티들의 인프로세스 실행과 상태성(Stateful) 지식 검색 API의 백엔드 호출을 완벽하게 조합하여 고성능 레이턴시와 높은 품질을 동시에 달성합니다.

---

## 2. 그래프 토폴로지 및 내부 처리 파이프라인

`simple_rag` 그래프 자체는 단순한 직선 구조를 갖지만, 핵심 실행 노드인 `respond` 내부에 정교한 RAG 전처리 및 후처리 흐름을 포함하고 있습니다.

### 2.1. 전체 데이터 흐름도

```mermaid
flowchart TD
    START([START]) --> respond[respond 노드 실행]
    
    subgraph respond Node Internal Workflow
        A[마지막 Human 질의 추출] --> B{rewrite_mode?}
        B -- "rewrite / hybrid" --> C[Conversational Rewrite<br>이전 대화 맥락 반영]
        B -- "expand / hybrid" --> D[Query Expansion<br>3개 다중 쿼리 확장]
        B -- "None" --> E[Raw Query 유지]
        
        C & D & E --> F[Synonym Expander<br>사전 기반 동의어/약어 확장]
        F --> G[search_multi_knowledge_bases<br>백엔드 API 호출]
        
        subgraph Backend API Process
            G1[(Qdrant Dense)]
            G2[(ko-kiwi-bm25 Sparse)]
            G3[BGE Reranker]
            G1 & G2 -->|Hybrid Merge| G3
        end
        G --> Backend API Process
        Backend API Process -->|RetrievedChunk 반환| H[Context Formatting<br>max_context_chars 기준 Truncate]
        
        H --> I[System Prompt 합성<br>인용 cite 지시문 포함]
        I --> J[LiteLLM Invoke<br>답변 텍스트 스트리밍 생성]
        J --> K[References Metadata 결합<br>additional_kwargs 바인딩]
    end
    
    respond --> END([END])
```

---

## 3. 핵심 모듈 및 노드 설계

### 3.1. 질의 재작성 및 확장 (Query Rewrite / Expansion)
*   **사용 클래스**: [QueryRewriter](file:///Users/mj/workspace/playground/rag-proving-ground/packages/rag-core/src/rag_core/query_rewrite/rewriter.py) (`rag-core` 직접 임포트)
*   **동작 모드 (`rewrite_mode`)**:
    *   `rewrite`: 유저의 이전 대화 기록을 프롬프트 맥락으로 참고하여, 대명사("그것", "이때")나 생략된 조사 등을 복원한 독립적(De-contextualized) 검색 쿼리를 재생성합니다.
    *   `expand`: 원래 질문의 주요 키워드를 다양한 유의어로 확장하여 3개의 탐색 쿼리 리스트로 분할 생성합니다.
    *   `hybrid`: 맥락 재작성과 쿼리 확장을 순차적으로 동시 수행하여 하이브리드 매칭 성능을 보강합니다.

### 3.2. 어휘 동의어 사전 확장 (Synonym Expansion)
*   **사용 클래스**: [SynonymExpander](file:///Users/mj/workspace/playground/rag-proving-ground/packages/rag-core/src/rag_core/query_rewrite/synonym_expander.py) (`rag-core` 직접 임포트)
*   **역할**: 도메인 사전 데이터베이스에서 한국어 조사 및 영문 약어를 파악하여 `(AI | 인공지능)`, `(K8s | 쿠버네티스)` 등의 동의어 토큰을 검색어 뒤에 덧붙여 BM25 검색의 단어 누락을 방지합니다.

### 3.3. 백엔드 경유 다중 지식 검색 (Multi-KB Search)
*   **호출 함수**: [search_multi_knowledge_bases](file:///Users/mj/workspace/playground/rag-proving-ground/packages/graphs/src/rag_graphs/util/backend.py) (백엔드 클라이언트 통신 래퍼)
*   **백엔드 수행 역할**:
    *   전달받은 다중 쿼리 목록과 다중 지식 베이스 ID 리스트를 기반으로 Qdrant 벡터스토어에 병렬 Dense + Sparse(`ko-kiwi-bm25`) 하이브리드 매칭을 실행합니다.
    *   리턴된 다수의 청크 목록을 `RerankerConfig` 사양에 맞춰 교차 점수 표준화(Reranking)를 돌린 뒤 최상위 `limit` 개의 고정밀 청크 배열을 반환합니다.

### 3.4. 컨텍스트 구성 및 인용 매핑
*   **컨텍스트 포맷팅**: 반환된 청크들은 `[1] kb=... doc=... source=... page=... \n {본문 내용}` 형태로 순차 문자열 직렬화됩니다. 이 문자열이 `max_context_chars`를 넘어가면 문장/단락 경계선에서 안전하게 절단(Truncate)됩니다.
*   **메타데이터 주입**: 생성된 AI 답변은 UI 단에서 출처 하이라이트 처리를 수행할 수 있도록, 참조한 각 청크의 식별 정보(`kb_id`, `doc_id`, `chunk_id`, `score`, `source`, `page`) 목록을 `additional_kwargs["references"]` 내에 고스란히 담아 배출합니다.

---

## 4. 런타임 설정 및 상태 스키마

### 4.1. `GraphConfig` (런타임 옵션)
`RunnableConfig`의 `configurable`을 통해 에이전트의 RAG 강도를 조율할 수 있는 스키마입니다.

| 필드명 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `model_name` | `str \| None` | `None` | 생성에 사용할 LLM 모델 식별자. |
| `knowledge_base_ids` | `list[str]` | `[]` | RAG 탐색 대상 지식 베이스 UUID 목록. |
| `limit` | `int` | `5` | 최종 답변 생성에 사용할 청크 개수 (1~100). |
| `candidate_limit` | `int \| None` | `None` | 1차 검색(리랭크 전) 후보 청크 개수. |
| `reranker_config` | `dict \| None` | `None` | 리랭커 설정 (`model`, `top_n`). 2개 이상의 KB 검색 시 필수입니다. |
| `max_context_chars` | `int` | `16,000` | 컨텍스트로 전달할 최대 글자 수. |
| `retrieval_mode` | `str \| None` | `None` | 검색 방식 (`dense`, `sparse`, `hybrid`). |
| `sparse_model` | `str \| None` | `None` | BM25용 Sparse 모델 (예: `"ko-kiwi-bm25"`). |
| `rewrite_mode` | `str \| None` | `None` | 쿼리 재작성 모드 (`rewrite`, `expand`, `hybrid`, `None`). |

---

## 5. 소스 코드 참조
*   에이전트 정의 및 respond 로직: [simple_rag.py](file:///Users/mj/workspace/playground/rag-proving-ground/packages/graphs/src/rag_graphs/simple_rag.py)
*   백엔드 데이터 검색 헬퍼: [util/backend.py](file:///Users/mj/workspace/playground/rag-proving-ground/packages/graphs/src/rag_graphs/util/backend.py)
