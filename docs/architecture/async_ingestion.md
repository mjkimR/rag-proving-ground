# 비동기 문서 인제스션 아키텍처 (Asynchronous Ingestion Architecture)

본 문서는 **Taskiq**와 **Redis**를 기반으로 구축된 비동기 문서 인제스션 및 재처리 파이프라인의 아키텍처와 핵심 설계 패턴을 설명합니다.

---

## 1. 아키텍처 개요

문서 업로드 시 실행되는 **파싱 → 청킹 → 임베딩** 파이프라인은 고부하(CPU/GPU 집약적) 작업입니다. API 서버가 이를 동기적으로 처리할 경우 Connection Timeout 발생 및 API 워커 고갈로 전체 서비스가 마비될 위험이 있습니다. 

이를 해결하기 위해, 무거운 연산은 API 요청 흐름 외부로 격리하고 **비동기 Taskiq Worker 프로세스**로 위임하는 아키텍처를 채택하고 있습니다.

```
[ Client ] 
    │ (1) POST /upload (File)
    ▼
[ FastAPI App ] 
    │ (2) Upload Raw File to MinIO
    │ (3) Create DB Record (status = "QUEUED")
    │ (4) Dispatch Task to Taskiq Broker
    ▼
[ Client ] ◄── (5) HTTP 202 Accepted (Immediate Response with Doc ID)

──────────────────────────────────────────────────────────

[ Redis (Taskiq Broker & Result Backend) ]
    │
    │ (6) Fetch Task (Queues based on priority, e.g. kb_ingest:critical)
    ▼
[ Taskiq Worker Process ]
    │ (7) Download Raw File from MinIO
    │ (8) Docling Parsing (Local/Remote) ──────────► [ DB: status = "PARSING" ]
    │ (9) Semantic / Recursive Chunking ──────────► [ DB: status = "CHUNKING" ]
    │ (10) Embed & Upload Vectors (Qdrant) ──────► [ DB: status = "EMBEDDING" ]
    ▼
[ Complete Ingestion ] ──────────────────────────► [ DB: status = "COMPLETED" ]
                                                 └──► [ Redis Result Backend Update ]
```

---

## 2. 기술 스택 및 컴포넌트

| 컴포넌트 | 기술 스택 | 주요 역할 |
|---|---|---|
| **API Gateway** | **FastAPI** (Python 3.13) | 파일 검증, MinIO 원본 저장, DB 레코드 생성 및 `QUEUED` 상태 제어, Taskiq 브로커를 통한 비동기 태스크 발행 및 즉시 202 응답 반환 |
| **Message Broker** | **Redis (ListQueueBroker)** (`rag-redis`) | 태스크 메시지 중개. 우선순위별 큐(`kb_ingest:critical`, `high`, `medium`, `low`, `lowest`)를 구성하여 공평(Fair) 및 우선순위 스케줄링 처리 |
| **Async Worker** | **Taskiq** (`taskiq-redis`) | 태스크 구독 및 파이프라인 단계별 처리 프로세스 (API 프로세스와 물리적/논리적 격리) |
| **Result Backend** | **Redis (Result Backend)** | 처리 상태 및 작업 결과를 비동기적으로 저장 (2시간의 TTL을 적용하여 메모리 누수 방지) |
| **Storage & DB** | **MinIO** & **PostgreSQL** | 원본 파일 보존 및 파싱 이력/문서 메타데이터, 상태 추적 저장 |

---

## 3. 핵심 설계 패턴 및 구현 세부사항

### 3.1. 무중단 장애 복구 (Startup Recovery Routine)
네트워크 불안정이나 컨테이너 비정상 종료 등으로 인해 태스크 발행에 실패하거나, Worker가 비정상 종료되어 태스크가 유실되는 상황을 복구하기 위해 **Startup Recovery Routine**을 탑재하고 있습니다.

*   **동작 원리**: 
    1. Worker 프로세스가 구동될 때 DB를 스캔하여 생성된 지 **5분이 지난 `QUEUED` 또는 `PARSING` 상태**의 문서들을 탐색합니다.
    2. 중단된 문서들을 찾아 Taskiq 스케줄러 및 디스패처를 통해 태스크를 다시 큐에 발행하여 자가 복구(Self-healing)를 수행합니다.
*   **파일 복원**: 원본 파일은 DB 트랜잭션 커밋 완료 직후 이미 MinIO 저장소에 업로드되어 안전하므로, 데이터 손실 우려 없이 언제든 재시도가 가능합니다.

### 3.2. 애플리케이션 및 자원 격리 (Resource Isolation)
API 서버 프로세스와 Worker 프로세스는 완전히 독립된 프로세스로 실행됩니다.
*   Docling 파싱 및 대규모 임베딩 연산 시 발생하는 CPU/GPU 부하가 **실시간 LLM 서빙 및 대화형 API 응답 이벤트 루프를 간섭하거나 블로킹하지 않도록 보장**합니다.
*   추후 CPU/GPU 부하량에 따라 API 서버 인스턴스와 Worker 인스턴스를 각각 다르게 오토스케일링(Scale-out)할 수 있는 아키텍처적 유연성을 가집니다.

### 3.3. 견고한 재시도 전략 (Retry Strategy)
*   **네트워크 및 외부 연동 예외 대응**: Worker의 태스크 핸들러는 `tenacity` 패키지의 `@retry(stop=stop_after_attempt(3))` 장치를 도입하여 일시적인 외부 연동(예: OOM, 외부 API 타임아웃, DB 커넥션 병목 등) 실패 시 최대 3회 자동 재시도합니다.
*   **비즈니스 예외 추적**: 영구적인 에러 발생 시에는 비즈니스 로직 수준에서 실패 단계를 추적하여 DB의 문서 상태를 `FAILED`로 변경하고 상세 실패 이력을 생성합니다.

### 3.4. 수동 의존성 조립 (Manual Wiring Factory Pattern)
Worker 애플리케이션은 FastAPI 라이프사이클 외부에서 독립적으로 가동되므로 FastAPI의 `@app.Depends` 의존성 주입 도구를 직접 사용하기 어렵습니다.
*   이를 해결하기 위해 `app.worker.services`에 **`build_pipeline_service()` 수동 DI 팩토리**를 선언하여 DB Repository, History Service, Pipeline Service를 결합도 낮고 일관성 있게 생성하여 사용합니다.

---

## 4. 파이프라인 상태 머신 (State Machine)

문서의 전 생애주기 동안 데이터베이스 레코드의 `status` 필드는 다음과 같이 정밀하게 전이됩니다.

```
[QUEUED] (API 요청 접수)
   │
   ▼
[PARSING] (Docling / Marker 파서 가동)
   │
   ├──────────────────────────────┐ (에러 발생 시)
   ▼                              ▼
[CHUNKING] (문서 조각 분할)    [FAILED] (파이프라인 실패 상세 기록)
   │                              ▲
   ├──────────────────────────────┤ (에러 발생 시)
   ▼                              ▼
[EMBEDDING] (벡터 임베딩 연산)  [FAILED]
   │                              ▲
   ├──────────────────────────────┘ (에러 발생 시)
   ▼
[COMPLETED] (Qdrant 색인 완료 및 서빙 준비)
```

---

## 5. 실행 및 관리 가이드

### 5.1. 설정 변수
*   **`.env` 환경변수**: `REDIS_URL` 변수를 통해 Broker에 접근합니다.
    ```bash
    REDIS_URL=redis://localhost:16379/0
    ```

### 5.2. 개발 실행 명령
*   **통합 실행**: `just dev` 명령 실행 시 API 서버와 함께 백그라운드에서 Taskiq Worker가 자동으로 시작되며, 정상 종료(SIGINT/SIGTERM) 발생 시 두 프로세스가 안전하게 리소스를 반환하고 함께 내려갑니다.
*   **Worker 개별 실행**: 무거운 연산 로그 모니터링이나 Worker 디버깅 시에는 다음 명령을 통해 Worker 프로세스만 단독으로 띄워 모니터링할 수 있습니다.
    ```bash
    just worker
    ```
