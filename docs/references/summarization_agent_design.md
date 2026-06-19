# 문서 요약 에이전트 설계서 (Document Summarization Agent Design)

본 문서는 사용자가 첨부한 문서를 대상으로 요약 기능("이 파일 요약해줘")을 수행할 때 발생하는 의도 판별(Routing)과 RAG(Retrieval-Augmented Generation) 및 트리 요약(Tree Summarization)의 아키텍처 및 역할 경계를 정의합니다.

---

## 1. 핵심 당면 과제

사용자가 문서를 업로드하고 요약을 요청했을 때, 시스템은 사용자의 입력 쿼리에 따라 두 가지 요약 모델 중 하나를 동적으로 선택해 처리해야 합니다:

1. **전체 요약 (TREE Mode)**: 사용자가 문서 전체의 맥락이나 개요 요약을 원할 때, 문서 전체를 청크 단위로 나누고 병렬로 요약하여 점진적으로 결합하는 계층적 트리 요약 방식 (검색/임베딩 단계 생략).
2. **질의 맞춤 요약 (RAG Mode)**: 사용자가 문서의 특정 내용(예: "재무 파트만 요약해줘")에 대해 질문할 때, 질문과 관련된 일부 청크만 검색하여 종합 요약하는 방식 (임베딩 및 벡터 데이터베이스 검색 필수).

이 파이프라인이 안정적으로 작동하기 위해 라우팅의 주체와 RAG용 임시 지식 베이스(KB) 생성의 복잡성을 해결하는 최적의 디자인 레이아웃을 정의합니다.

---

## 2. RAG용 임시 KB 처리 아키텍처 대안

임시 파일을 처리하고 세션 만료 시 리소스를 회수하는 수명 주기 관리에 대한 세 가지 대안입니다.

### 방안 A: 세션 기반 임시 KB 생성 (Ephemeral Database KB) - 채택
백엔드에 임시 플래그(`is_temp: true` 또는 `expires_at`)를 가진 임시 KB를 동적으로 생성하고, 파일을 업로드하여 백엔드의 표준 인제스션 파이프라인(파싱 $\rightarrow$ 청킹 $\rightarrow$ 임베딩 $\rightarrow$ Qdrant 색인)을 그대로 실행합니다.

* **평가**: 백엔드 검색 API 규격을 그대로 재사용할 수 있어 코드의 일관성이 높고 대용량 파일 인제스션 시 안정적이지만, DB 리소스 누수 방지를 위한 정리(Cleanup) 로직 설계가 필요합니다. 수명 주기(TTL) 상세 설계는 [backend_task_and_session_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/backend_task_and_session_design.md)를 참조합니다.

### 방안 B: 무상태 파서 + 메모리 내 로컬 검색 (Stateless Parser & Local Retrieval) - 미채택
* 데이터베이스 오염이 없지만, Qdrant 하이브리드 검색을 활용할 수 없고 대용량 문서에서 메모리 압박이 발생합니다.

### 방안 C: 사용자별 고정 샌드박스 KB (Pre-allocated Sandbox KB) - 미채택
* 스키마 오버헤드가 없지만, 동시 다중 탭 사용 시 메타데이터 필터링 충돌 위험이 있습니다.

---

## 3. 하이브리드 작업 위임 모델 (Task-Delegated Agent) 설계

방안 A를 채택하되, 인제스션 시작 시점을 **파일 첨부 시점으로 앞당기는 Eager Ingest 패턴**을 적용하여 사용자 체감 지연 시간을 최소화하고, Graph 노드의 타임아웃 리스크를 해소합니다.

### 3.1. 전체 흐름 (Sequence)

```
  파일 첨부 시점                        메시지 전송 시점
       │                                    │
       ▼                                    ▼
  ┌─────────┐    POST /sessions/            ┌─────────────────┐
  │  Web UI │───{thread_id}/files──────────>│ FastAPI Backend  │
  └────┬────┘                               └────────┬────────┘
       │                                             │
       │  ┌─ 업로드 프로그레스 바 표시                │ Taskiq 태스크 등록
       │  │  (UI가 task 상태 폴링)                   │
       │  │                                          ▼
       │  │                                   ┌──────────────┐
       │  │                                   │Taskiq Worker │
       │  │                                   │ Parse/Chunk  │
       │  │                                   │ Embed/Index  │
       │  │                                   └──────┬───────┘
       │  │                                          │
       │  └─ COMPLETED → 전송 버튼 활성화            │ MinIO/Qdrant/PG 저장
       │                                             ▼
       │     사용자가 질문 입력 후 전송
       │                                    ┌─────────────────┐
       └───────────────────────────────────>│ Aegra (Graph)   │
                                            │                 │
                                            │ 1. Safety Gate  │
                                            │    (KB 완료 확인)│
                                            │ 2. Routing      │
                                            │ 3. Search/요약  │
                                            │ 4. 스트리밍 응답 │
                                            └─────────────────┘
```

### 3.2. 역할 경계 상세 정의

#### UI (Web Frontend)
| 책임 | 설명 |
| :--- | :--- |
| **인제스션 선행 트리거** | 사용자가 파일을 첨부하는 즉시, 메시지 전송을 기다리지 않고 백엔드 파일 업로드 API를 호출하여 인제스션을 시작합니다. |
| **진행률 표시** | 태스크 상태 API를 폴링하여 "파싱 중 → 임베딩 중 → 완료"와 같은 프로그레스 바를 사용자에게 표시합니다. |
| **전송 버튼 제어** | 모든 첨부 파일의 인제스션이 `COMPLETED` 또는 `FAILED`로 종결될 때까지 메시지 전송 버튼을 비활성화합니다. |
| **추가 업로드 차단** | 인제스션 진행 중에는 추가 파일 첨부를 비활성화하여 상태 꼬임을 원천 방지합니다. 모든 태스크 종결 후 다시 활성화됩니다. |

### 3.3. 다중 파일 업로드 및 처리 중 인터랙션 정책
한 세션에서 여러 파일을 동시에 첨부할 경우의 처리 전략:
* **중복 업로드 방어 (Idempotency)**: 파일 첨부 시 백엔드는 즉시 파일 내용의 Hash(예: SHA-256)를 계산합니다. 해당 세션 임시 KB 내에 동일한 해시의 문서가 이미 존재한다면, 새로운 태스크를 생성하지 않고 기존 `doc_id`와 `COMPLETED` 상태를 즉시 반환(Fast-path)합니다.
* **전체 완료 보장 대기 (All-wait)**: 그래프는 첨부된 모든 파일에 대한 개별 태스크가 `COMPLETED` 또는 `FAILED` 상태로 완전 종결될 때까지 요약을 시작하지 않습니다.
* **부분 실패(Partial Failure) 예외 처리**: 다중 파일 중 일부가 `FAILED`(예: 암호화된 PDF 등) 상태로 종결되더라도 전체 프로세스를 중단하지 않습니다. 성공한 문서들만을 대상으로 요약을 진행하되, 시스템 응답 첫머리에 "일부 파일(파일명)은 읽을 수 없어 요약에서 제외되었습니다."라는 예외 문구를 명시하여 사용자에게 알립니다.
* **처리 중 추가 업로드 차단**: 인제스션 태스크가 진행 중인 동안에는 프론트엔드(UI)에서 추가 파일 업로드를 비활성화(Disable)하여, 중간에 새로운 파일이 끼어들어 상태가 꼬이는 것을 원천 방지합니다. 모든 태스크가 종결된 후에야 업로드 버튼이 다시 활성화됩니다.

#### Graph (Aegra LangGraph)
| 책임 | 설명 |
| :--- | :--- |
| **Safety Gate (완료 확인)** | 그래프 노드 진입 시, 세션에 연결된 임시 KB의 모든 태스크 상태가 `COMPLETED` 혹은 `FAILED`로 종결되었는지 확인합니다. 만약 `PENDING`이나 `PROCESSING` 상태가 남아있다면, 즉시 "문서 분석이 진행 중입니다. 잠시 후 다시 질문해주세요."라고 **에러를 반환(Fail-fast)**하여 실행을 종료합니다. |
| **의도 판별 (Routing)** | `IntentRouter`를 통해 사용자 질문을 분석하여 `TREE` 또는 `RAG` 분기를 결정합니다. |
| **요약 실행** | TREE 모드에서는 `TreeSummarizer`를, RAG 모드에서는 검색 후 LLM 요약을 그래프 내부에서 직접 실행합니다. |
| **스트리밍 응답** | 최종 요약 답변을 중간 프록시 없이 사용자에게 직접 토큰 스트리밍합니다. |

#### Backend (FastAPI + Taskiq Worker)
| 책임 | 설명 |
| :--- | :--- |
| **파일 수신 및 태스크 등록** | UI로부터 파일을 수신하고, 인제스션 모드에 따라 Taskiq 태스크를 등록한 뒤 `task_id`를 즉시 반환합니다. |
| **인제스션 실행** | Taskiq Worker에서 파싱, 청킹, 임베딩, Qdrant 색인을 수행합니다. 결과 데이터는 기존대로 MinIO + PostgreSQL에 저장하고, Taskiq Result Backend(Redis)에는 상태와 참조 ID만 경량 기록합니다. |
| **검색 API 제공** | 인제스션이 완료된 임시 KB에 대해 기존 `/api/v1/knowledge_bases/search` 엔드포인트를 통해 검색을 제공합니다. |
| **청크 텍스트 제공** | TREE 모드를 위해 특정 문서의 전체 텍스트 청크 목록을 반환하는 엔드포인트를 제공합니다. |

### 3.3. 인제스션 모드 분리: `parse_only` vs. `full_ingest`
Taskiq Pipeline을 활용하여 인제스션 요청 시 `mode` 파라미터로 실행 범위를 제어합니다:
* **`parse_only`**: 파싱 $\rightarrow$ 청킹까지만 수행하고 결과를 MinIO/PostgreSQL에 저장합니다. 임베딩과 Qdrant 색인은 생략합니다. **TREE 모드**에서 사용하여 불필요한 임베딩 대기 시간(10~30초)을 완전히 제거합니다.
* **`full_ingest`**: 파싱 $\rightarrow$ 청킹 $\rightarrow$ 임베딩 $\rightarrow$ Qdrant 색인까지 전 과정을 수행합니다. **RAG 모드**에서 사용합니다.

## 3. 하이브리드 작업 위임 모델 (Task-Delegated Agent) 설계

방안 A를 채택하되, 인제스션 시작 시점을 **파일 첨부 시점으로 앞당기는 Eager Ingest 패턴**을 적용하여 사용자 체감 지연 시간을 최소화하고, Graph 노드의 타임아웃 리스크를 해소합니다. 구체적인 전역 파일 저장, 해시 기반 멱등성 및 파일 처리 아키텍처는 [file_attachment_layer_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/file_attachment_layer_design.md)을 따릅니다.

### 3.1. 전체 흐름 (Sequence)

```
  파일 첨부 시점                        메시지 전송 시점
       │                                    │
       ▼                                    ▼
  ┌─────────┐   Phase 1 Upload &            ┌─────────────────┐
  │  Web UI │───Phase 2 Attach/Process─────>│ FastAPI Backend  │
  └────┬────┘   (attachment_id, temp_kb)    └────────┬────────┘
       │                                             │
       │  ┌─ 업로드/분석 진행률 표시                  │ Taskiq 태스크 등록
       │  │  (UI가 task 상태 폴링)                   │
       │  │                                          ▼
       │  │                                   ┌──────────────┐
       │  │                                   │Taskiq Worker │
       │  │                                   │ Parse/Chunk  │
       │  │                                   │ Embed/Index  │
       │  │                                   └──────┬───────┘
       │  │                                          │
       │  └─ COMPLETED → 전송 버튼 활성화            │ MinIO/Qdrant/PG 저장
       │                                             ▼
       │     사용자가 질문 입력 후 전송
       │                                    ┌─────────────────┐
       │                                    │ Aegra (Graph)   │
       │                                    │                 │
       │ 1. GET /sessions/{id}/attachments──>│ 1. Safety Gate  │
       └───────────────────────────────────>│    (완료 상태 검증)│
                                            │ 2. Routing      │
                                            │ 3. Search/요약  │
                                            │ 4. 스트리밍 응답 │
                                            └─────────────────┘
```

### 3.2. 역할 경계 상세 정의

#### UI (Web Frontend)
| 책임 | 설명 |
| :--- | :--- |
| **인제스션 선행 트리거** | 사용자가 파일을 첨부하는 즉시 1단계 업로드(`POST /attachments/upload`) 및 2단계 세션 처리(`POST /sessions/{thread_id}/files`)를 연쇄 트리거합니다. |
| **진행률 표시** | 태스크 상태 API를 폴링하여 "업로드 완료 -> 파싱 중 -> 완료"와 같은 상태를 상세히 노출합니다. |
| **전송 버튼 제어** | 모든 첨부 파일의 인제스션이 완료(`COMPLETED`)되거나 실패(`FAILED`)할 때까지 메시지 전송 버튼을 비활성화합니다. |
| **추가 업로드 차단** | 인제스션 진행 중에는 추가 파일 첨부를 비활성화하여 상태 꼬임을 방지합니다. |

#### Graph (Aegra LangGraph)
| 책임 | 설명 |
| :--- | :--- |
| **Safety Gate (완료 확인)** | 그래프 진입 시 세션에 연결된 모든 `SessionAttachment` 상태가 `COMPLETED` 혹은 `FAILED`로 종결되었는지 확인합니다. 작업 중(`PENDING`, `PROCESSING`)인 파일이 있다면 "문서 분석이 진행 중입니다. 잠시 후 다시 질문해주세요."라며 **에러를 반환(Fail-fast)**합니다. |
| **의도 판별 (Routing)** | `IntentRouter`를 통해 사용자 질문을 분석하여 `TREE` (전체 요약) 또는 `RAG` (질의 맞춤 요약) 분기를 결정합니다. |
| **요약 실행** | TREE 모드에서는 `TreeSummarizer`를, RAG 모드에서는 검색 후 LLM 요약을 그래프 내부에서 직접 실행합니다. |
| **스트리밍 응답** | 최종 요약 답변을 사용자에게 직접 토큰 스트리밍합니다. |

#### Backend (FastAPI + Taskiq Worker)
* **파일 수신 및 작업 실행**: Phase 1/Phase 2 API를 제공하며, `Taskiq Worker`를 통해 실제 파싱 및 RAG 인제스션을 수행합니다. (상세 내역은 [file_attachment_layer_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/file_attachment_layer_design.md) 참조)
* **검색 및 텍스트 제공 API**: 인제스션이 완료된 임시 KB에 대해 검색을 제공하고, TREE 모드를 위한 문서 청크 텍스트 전체 조회 엔드포인트를 제공합니다.

---

## 4. 요약 에이전트 전용 백엔드 API 엔드포인트 명세

일반적인 파일 업로드/처리 API 외에 요약 에이전트 작동 및 트리 요약(TREE Mode) 구동을 위한 전용 엔드포인트 명세입니다.

### 4.1. 문서 청크 텍스트 전체 조회
```
GET /api/v1/documents/{doc_id}/chunks
```
TREE 모드에서 Graph가 전체 문서의 청크 텍스트를 가져와 `TreeSummarizer`에 전달할 때 사용합니다.

* **Path Parameter**:
  * `doc_id` (UUID): 문서 ID
* **Query Parameter**:
  * `text_only` (bool, 선택, 기본값: true): true이면 메타데이터 없이 텍스트 배열만 반환
* **Response** (`200 OK`):
  ```json
  {
    "doc_id": "uuid",
    "total_chunks": 42,
    "chunks": [
      "첫 번째 청크 텍스트...",
      "두 번째 청크 텍스트...",
      "..."
    ]
  }
  ```

### 4.2. 세션별 임시 KB 및 첨부파일 목록 조회
```
GET /api/v1/sessions/{thread_id}/attachments
```
Graph가 Safety Gate에서 세션에 연결된 모든 파일의 인제스션 처리 상태(`status`)를 일괄 확인하거나, RAG 모드 시 검색 대상 KB ID를 획득하기 위해 사용합니다. (상세 스키마는 [file_attachment_layer_design.md](file:///Users/mj/workspace/playground/rag-proving-ground/docs/references/file_attachment_layer_design.md)를 참조합니다.)

