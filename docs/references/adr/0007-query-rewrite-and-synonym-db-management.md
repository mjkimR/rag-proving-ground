# ADR-0007: 질의 재작성/확장 모듈 독립 및 데이터베이스 기반 동의어 사전 아키텍처 도입

* **작성일 (Date)**: 2026-06-18
* **상태 (Status)**: 승인됨 (Accepted)

---

## 맥락 (Context)
- 본 프로젝트는 모듈형 RAG 실험 및 서빙 스캐폴드로서 검색 재현율(Recall) 향상을 위해 질의 재작성(Query Rewrite) 및 쿼리 확장(Query Expansion) 단계를 도입하고자 함.
- 쿼리 확장 시 단일 사용자 질문이 N개의 하위/대안 검색 질문으로 분할되는데, 이를 검색(Search) API 내부에서 직접 LLM을 호출해 확장할 경우 다음과 같은 문제가 발생함:
  1. **단일 책임 원칙(SRP) 위배**: 단순 Retrieval을 수행하는 검색 컴포넌트가 무겁고 복잡한 LLM 생성 연산과 결합됨.
  2. **에이전틱 유연성 부족**: LangGraph 오케스트레이터나 클라이언트가 중간에 생성된 확장 쿼리 목록을 가로채거나, 이를 기반으로 분기 로직(Routing)을 수행하기 어려워짐.
- 또한, 전문 용어와 사내 약어에 매핑되는 동의어 사전(Synonym Dictionary)은 소스 코드 내의 JSON 파일과 같이 정적으로 관리하는 대신, 어드민 사용자가 웹 UI를 통해 실시간으로 추가, 수정, 삭제(CRUD)할 수 있는 동적 영속 레이어(PostgreSQL) 및 캐싱 메커니즘이 필요함.

---

## 결정 (Decision)
> **요약**: 검색 API의 책임 범위를 순수 검색/Rerank로 격리하고 입력 구조를 간소화하기 위해, 검색 API 스키마를 **`queries: list[str]` (최소 1개 요소 필수) 필드로 일원화**함. 동시에, LLM 기반의 쿼리 재작성 모듈과 데이터베이스 연동형 동의어 사전 관리 체계를 독자적인 컴포넌트로 구축하여 외부에서 조합(Compose)하도록 결정함. 또한 동의어 도메인 패키지를 지식 베이스 계층 하위로 재배치하고, UI 컴포넌트를 분리하여 아키텍처 정밀성을 확보함.

### 2.1. 다중 쿼리 배치 검색 API 설계 (Decoupled & Unified Search Input)
- **질의 재작성 모듈 독립**: [QueryRewriter](file:///home/mj/projects/rag-proving-ground/packages/rag-core/src/rag_core/query_rewrite/rewriter.py) 모듈을 [packages/rag-core](file:///home/mj/projects/rag-proving-ground/packages/rag-core/) 아래에 순수 LLM 호출 객체로 격리하여 구현함.
  - 대화 맥락이 있을 경우 LLM을 통해 지시 사항 및 대명사를 정리하여 단일화된 검색 쿼리로 복원하는 `rewrite()` 메소드 구현.
  - LLM의 Structured Output 기능을 통해 단일 쿼리로부터 다각도의 확장 쿼리 목록을 반환하는 `expand()` 메소드 구현.
- **검색 API 입력 일원화**: `SearchMultiKnowledgeBaseUseCase`와 core의 `retrieve_multi_knowledge_chunks`는 `queries: list[str]` 필드 하나만 필수적으로 입력받도록 스펙을 일원화함. 단일 쿼리 검색 역시 프론트엔드/백엔드 인터페이스 상에서 `queries: ["검색어"]` 형태로 감싸 전송하도록 일관성을 확보함.
- **비동기 검색 병렬 처리**: 백엔드(FastAPI)와 Qdrant 간의 검색은 `asyncio.gather`를 통한 비동기 병렬 요청을 수행하여, LangChain의 고수준 추상화(`QdrantVectorStore`)와 호환성을 유지하면서도 지연 시간(Latency)을 최소화함.
- **Reranking & Deduplication**: 수집된 N개의 검색 결과는 청크 ID 기준으로 병합(Merge) 및 중복 제거(Deduplication)를 수행한 후, LiteLLM Reranker 모듈을 통해 최종 Top-K를 정제하여 비용과 속도를 최적화함.

### 2.2. 데이터베이스 연동형 동의어 사전 관리 아키텍처 및 2-Depth 패키지 이동
- **도메인 계층 정리**: 동의어 사전은 지식 베이스 검색과 종속 관계에 있는 정보이므로, 백엔드 디렉토리 계층을 [app/features/knowledge/synonyms/](file:///home/mj/projects/rag-proving-ground/apps/backend/app/features/knowledge/synonyms/)로 재배치하여 결합도를 낮추고 도메인 계층 구조를 명확히 함.
- **데이터 저장 및 CRUD**: PostgreSQL 데이터베이스에 `synonym_maps` 테이블을 구축하고, FastAPI 라우터에 표준 CRUD REST API(`/api/v1/synonyms`)를 노출함.
- **메모리 내 고속 매핑 캐시**: 실시간 검색 쿼리 파이프라인에서 매번 PostgreSQL을 조회하여 발생하는 지연을 차단하기 위해, [synonym_expander.py](file:///home/mj/projects/rag-proving-ground/packages/rag-core/src/rag_core/query_rewrite/synonym_expander.py)에 동적 DB 로더 바인딩 및 메모리 캐싱(`_CACHED_SYNONYMS`)을 구축함. 동의어가 생성/수정/삭제될 때 캐시가 명시적으로 무효화(Invalidate)되도록 서비스 레이어와 연계함.
- **한국어 조사/어미 매핑 개선**: 명사 뒤에 `은, 는, 이, 가, 을, 를` 등의 조사가 자연스럽게 결합할 수 있도록 정규식 lookahead boundary 조건을 보강함:
  ```python
  pattern = re.compile(rf"(?<![a-zA-Z0-9가-힣]){re.escape(keyword)}(?![a-zA-Z0-9])", re.IGNORECASE)
  ```
  이를 통해 단어 시작 부분의 불완전 매칭은 방지하고 단어 끝부분의 조사 결합을 허용하여 한국어 매칭 정밀도를 대폭 향상함.

### 2.3. Frontend UI 리팩토링 및 API 동기화
- **UI 컴포넌트 세분화**: 단일 거대 뷰 파일 구조를 개선하기 위해 [apps/web/src/views/Synonyms/](file:///home/mj/projects/rag-proving-ground/apps/web/src/views/Synonyms/) 하위에 목록 테이블 역할을 하는 [SynonymTable.tsx](file:///home/mj/projects/rag-proving-ground/apps/web/src/views/Synonyms/components/SynonymTable.tsx)와 추가/수정용 Form 모달인 [SynonymModal.tsx](file:///home/mj/projects/rag-proving-ground/apps/web/src/views/Synonyms/components/SynonymModal.tsx)를 분리하여 컴포넌트 복잡도를 낮추고 유지보수성을 극대화함.
- **타입 클라이언트 자동 동기화**: `just gen-ui-api`를 활용하여 수정된 `queries` API 스펙 및 동의어 CRUD 스키마를 React OpenAPI 클라이언트와 완전히 동기화하고 TypeScript 타입 안전성을 확보함.

---

## 근거 및 대안 비교 (Rationale & Alternatives)

### 1. Qdrant Native `search_batch` 직접 호출 배제
- Qdrant의 `search_batch` API는 1회의 네트워크 호출로 배치 쿼리를 처리할 수 있으나, LangChain의 `QdrantVectorStore` 래퍼 추상화 레이어를 완전히 우회해야 함.
- 이 경우, 다중 벡터 인덱스 쿼리 시 텍스트 임베딩 모델 호출, Qdrant 메타데이터 오버레이 및 복잡한 필터 파싱 코드를 백엔드 단에서 직접 구현해야 하므로 코드 복잡도가 폭증함.
- 인트라넷 환경에서 `asyncio.gather`를 활용한 동시 비동기 연결 호출은 RTT가 수 ms 미만이므로 실질적인 Latency 차이가 없으며, 코드가 훨씬 간결하고 다른 Vector DB로의 이식성이 높음.

### 2. 검색 입력 필드를 query/queries 복수 구조로 유지하는 대안 배제
- 백엔드와 프론트엔드가 강결합되어 빌드 주기를 같이 통제하는 monorepo 환경이므로, 굳이 유효성 검사 로직과 API 규격을 복잡하게 만드는 다중 인터페이스 구조(`query` & `queries` 공존)를 유지할 필요가 없음.
- `queries: list[str]` 하나의 필드로 일원화하는 규격이 백엔드 유스케이스, 프론트엔드 Playground, LangGraph 파이프라인 전반의 코드를 단일 흐름으로 단순화하여 복잡도를 낮추는 Best Practice에 부합함.

---

## 파급 효과 (Consequences)

* **긍정적 효과**:
  - 검색 API가 다중 쿼리 검색, 중복 제거, Rerank 파이프라인라는 독립적 책임만 수행하므로 테스트 작성이 용이하고 결합도가 낮아짐.
  - 단일화된 `queries` 규격 덕분에 API 전송 포맷과 유효성 검증 로직이 한층 단순화됨.
  - LangGraph 에이전트 개발 시, LLM이 생성한 확장 쿼리 목록을 관찰(Observation)하여 답변 생성 전 의도 분류 및 동적 분기 로직에 유연하게 활용 가능.
  - 어드민 사용자가 별도의 개발/배포 과정 없이 웹 화면에서 단어를 제어하여 검색 품질을 즉시 통제 가능.
* **부정적 효과 및 완화 조치**:
  - LLM 호출과 다중 검색 쿼리로 인해 RAG 응답의 TTFT(Time-to-First-Token)가 소폭 증가할 수 있음.
  - **완화 조치**: 쿼리 확장이 불필요한 단순 키워드 질의나 대화 이력이 없는 첫 턴에서는 Heuristic 판별기를 거쳐 LLM 확장을 스킵하고 캐시된 동의어 필터링만 가볍게 적용하도록 우회 통로를 지원함.
