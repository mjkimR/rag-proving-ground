# 백엔드 비동기 작업 큐 및 임시 KB 수명 주기(TTL) 설계서

본 문서는 RAG Proving Ground 백엔드에서 비동기 연산(인제스션, 대용량 분석 등)을 안정적으로 처리하기 위한 태스크 큐(`Taskiq`) 관리 체계와, 세션(Session)별 임시 지식 베이스(KB) 매핑 및 자원 누수 방지를 위한 수명 주기(TTL) 설계안을 기술합니다.

---

## 1. FastStream에서 Taskiq로의 완전 교체 근거

RAG 파이프라인에서 파일 파싱, 청킹, 임베딩, 색인은 몇 초에서 몇 분까지 걸리는 무거운 비동기 작업입니다.

현재 사용 중인 `FastStream`을 `Taskiq`로 **완전히 교체**하는 것을 채택하며, 그 근거를 정의합니다.

### 1.1. 교체 근거
* **FastStream의 한계**:
  * 마이크로서비스 간 메시지 퍼블리싱/서브스크라이브에 최적화되어 있으며, 고정된 단일 흐름(파싱→청킹→임베딩→색인)에서는 잘 동작합니다.
  * 그러나 작업 결과 반환(Result Backend) 기능이 기본 제공되지 않아, 특정 작업의 성공 여부나 진행 상태를 모니터링하기 위해서는 데이터베이스 상태 기록용 보일러플레이트 코드를 직접 설계해야 합니다.
  * 인제스션 흐름이 다각화되면서(예: `parse_only` vs. `full_ingest` 모드 분기, 임시 KB 생성 등) 고정된 Pub/Sub 구독 기반 흐름으로는 파이프라인 단계별 유연한 조합이 어려워지고 있습니다.
* **Taskiq 채택 이유**:
  * Celery의 모던 AsyncIO 대체재로 설계된 비동기 분산 태스크 큐입니다.
  * **Result Backend**가 프레임워크 수준에서 기본 제공되어, 특정 작업 ID에 대해 `task.wait_result()` 등의 API로 손쉽게 완료 여부와 상태를 폴링할 수 있습니다.
    * **주의 (메모리 누수 방지)**: 파싱/청킹된 실제 텍스트나 임베딩 데이터는 MinIO와 Qdrant에 저장되며, Taskiq의 Redis Result Backend에는 `{"status": "COMPLETED", "doc_id": "xxx"}` 형태의 **초경량 상태 메타데이터만** 저장됩니다. 그럼에도 불구하고 이 메타데이터가 Redis에 무한정 쌓이는 것을 막기 위해 브로커 설정 시 반드시 `result_expires=7200` (2시간) 등으로 TTL을 설정해야 합니다.
  * `taskiq-fastapi` 통합 라이브러리를 통해 FastAPI의 **의존성 주입(Dependency Injection)** 컨텍스트를 태스크와 100% 공유하므로, API 단에서 사용하던 데이터베이스 연결 및 설정 유틸을 워커 코드에서 그대로 재사용할 수 있습니다.
  * **Pipeline 추상화**를 제공하여 `call_next()`, `map()`, `filter()` 등을 통한 태스크 체이닝 및 조건부 분기가 가능합니다. 이를 통해 `parse_only` 모드에서는 임베딩 단계를 건너뛰고, `full_ingest` 모드에서는 전 단계를 순차 실행하는 유연한 파이프라인 구성이 코드 수준에서 자연스럽게 표현됩니다.

### 1.2. Taskiq Pipeline을 활용한 인제스션 모드 분리

```python
# pseudo-code: Taskiq Pipeline 활용 예시

@broker.task
async def parse_document(file_data: bytes, options: dict) -> ParseResult:
    """파서 엔진을 호출하여 텍스트 추출 및 청킹 수행."""
    ...

@broker.task
async def embed_and_index(parse_result: ParseResult, kb_id: UUID) -> IndexResult:
    """임베딩 생성 및 Qdrant 색인."""
    ...

# full_ingest: 파싱 -> 임베딩/색인 체이닝
pipeline = broker.pipeline(parse_document).call_next(embed_and_index)

# parse_only: 파싱만 수행하고 결과 반환
task = await parse_document.kiq(file_data, options)
result = await task.wait_result(timeout=120)
```

### 1.3. Taskiq 비동기 작업 처리 아키텍처

```
[FastAPI Router] ──(In-process call)──> [Taskiq Broker]
       │                                     │ (Push task to Broker)
       ▼                                     ▼
[Response to Client: task_id]           [Redis Queue]
                                             │
                                             ▼
                                     [Taskiq Worker]
                                             │ (Dependency Injection)
                                             ▼
                                     [Postgres / Qdrant Write]
```

### 1.4. 마이그레이션 전략
FastStream에서 Taskiq로의 완전 교체를 진행합니다:
1. Taskiq 브로커 및 Result Backend(Redis) 설정을 `apps/backend/app/worker/`에 새로 구성합니다.
2. 기존 FastStream 핸들러(`handlers/`)의 로직을 Taskiq `@broker.task` 데코레이터 기반으로 이관합니다.
3. 기존 `scheduling.py`의 주기적 작업(Recovery, Retry 등)을 Taskiq Scheduler로 전환합니다.
4. 이관 완료 후 FastStream 관련 코드(`broker.py`, `faststream` 의존성)를 제거합니다.

---

## 2. 세션-임시 KB 매핑 데이터베이스 설계

일반적인 파일 업로드 및 관리 아키텍처는 [file_attachment_layer_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/file_attachment_layer_design.md)의 `Attachment` 및 `SessionAttachment` 설계를 따릅니다. 텍스트 문서(PDF, TXT 등)가 세션에 첨부되면 세션 전용 임시 KB(Knowledge Base)로 변환 및 적재되며, 이를 관리하기 위한 관계형 스키마는 다음과 같습니다.

### 2.1. 관계 모델

Aegra(LangGraph Server)가 대화 세션(Thread)을 소유하고 있으므로, 백엔드에는 Aegra Thread ID를 논리적 외래키(`thread_id`)로 직접 참조하여 임시 KB 관계를 구성합니다.

```
┌──────────────────────────┐          ┌───────────────────┐
│ SessionKnowledgeBase     │          │   KnowledgeBase   │
├──────────────────────────┤          ├───────────────────┤
│ id (UUID)            PK  │          │ id (UUID)     PK  │
│ thread_id (str)          ├─────────o│ name              │
│ knowledge_base_id    FK  │          │ is_temp (Bool)    │
│ created_at               │          │ expires_at        │
└──────────────────────────┘          └───────────────────┘
```

* **세션당 하나의 임시 KB 매핑**:
  * 특정 `thread_id`에 속한 모든 텍스트 첨부파일(`SessionAttachment` 중 `purpose="temp_kb"`)은 동일한 `knowledge_base_id`에 속해 하나의 단위 KB로 인제스션됩니다.
  * `KnowledgeBase` 테이블의 `is_temp` 필드가 `True`로 설정되고, 만료 일시(`expires_at`)가 기록됩니다.

---

## 3. 임시 KB 및 세션 첨부파일 수명 주기(TTL) 청소 정책

임시 데이터가 Qdrant 벡터스토어, PostgreSQL, MinIO 파일 스토리지에 누적되어 서버 용량을 초과하는 것을 방지하기 위해 2중 청소 메커니즘을 적용합니다.

### 3.1. 수명 주기 시나리오

1. **액티브 제거 (Active Clean)**:
   * 사용자가 대화방을 나갈 때 또는 명시적으로 대화 이력을 지울 때 `DELETE /api/v1/sessions/{thread_id}/temp_kbs` (또는 통합 세션 정리 API)가 호출됩니다.
   * 백엔드는 `SessionKnowledgeBase` 및 `SessionAttachment` 매핑을 조회하여 연관된 모든 데이터(PostgreSQL 레코드, Qdrant 벡터 데이터, 오브젝트 스토리지 가공 파일)를 연쇄 물리 삭제(Cascade Delete)합니다.
2. **패시브 제거 (Garbage Collection Scheduler)**:
   * 사용자가 대화방을 명시적으로 삭제하지 않고 나가는 경우를 대비해 TTL 기반의 자동 청소를 도입합니다.
   * 파일 첨부/처리 시점에 `KnowledgeBase`의 `expires_at`을 현재 시각 기준 **2시간 후**로 설정하고, 임시 KB에 대한 검색 API 호출이 발생할 때마다 `expires_at`을 2시간 연장(Heartbeat)합니다.
   * `Taskiq Scheduler` 워커가 30분 단위 주기로 스케줄 작업을 실행하여 만료된 임시 KB와 해당 세션에 묶여 있던 `SessionAttachment`를 안전하게 정리합니다.

### 3.2. 정리 작업 멱등성 및 동기화
* 모든 리소스 삭제는 **멱등(Idempotent)** 하게 구현합니다. "이미 존재하지 않으면 성공" 원칙을 적용하여 GC 사이클 도중 네트워크/DB 에러로 실패하더라도 다음 사이클에서 안전하게 잔여 리소스를 재시도하여 정리합니다.
* 상세 정리 시퀀스 및 전역 원시 파일(`Attachment`)의 지연 정리(Lazy GC) 규칙은 [file_attachment_layer_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/file_attachment_layer_design.md)을 참조합니다.

