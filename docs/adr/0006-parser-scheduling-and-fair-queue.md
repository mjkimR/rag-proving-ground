# ADR-0006: 파서별 워커 격리 및 지식 베이스(KB)별 공정 스케줄러(Round-Robin) 도입

* **작성일 (Date)**: 2026-06-15
* **상태 (Status)**: 제안됨 (Proposed)

---

## 맥락 (Context)
- 현재 본 리포지토리의 문서 파싱(`document.parse`) 단계는 단일 Redis Queue 채널과 FastStream `@router.subscriber("document.parse", max_workers=2)` 구독자를 통해 처리되고 있음.
- 해당 아키텍처는 다음 두 가지 주요 성능 병목 및 작업 배분 공정성(Fairness) 문제를 내포함:
  1. **파서 종류와 무관한 단일 워커 제한 (Scenario 1)**:
     - GPU/CPU 연산이 무거운 딥러닝 기반 파서인 `Docling`과 가벼운 CPU 텍스트 파서인 `native_text`가 단일 워커 풀(`max_workers=2`)을 완전히 공유하고 있음.
     - 이로 인해 특정 파서(`Docling`)의 대량 요청이 유입되어 워커 풀을 점유할 경우, 가벼운 파서(`native_text`) 요청은 즉각적인 연산이 가능함에도 이전 대형 작업이 완료될 때까지 기약 없이 대기해야 하는 한계가 존재함.
  2. **지식 베이스(KB) 수준의 대기 독점 (Scenario 2)**:
     - 단일 지식 베이스(`KB1`)에 수백 개의 문서가 일괄 업로드된 상태에서 다른 지식 베이스(`KB2`)에 단 1개의 문서가 업로드되는 경우, FIFO(First-In, First-Out) 큐 구조의 특성상 `KB2`는 `KB1`의 모든 문서 처리가 끝날 때까지 수십 분 이상 대기해야 함.
     - 사용자 관점에서 지식 베이스 단위로 작업이 공평하게 교차 분배되는 **라운드 로빈(Round-Robin) 방식**의 공정 스케줄링(Fair Scheduling) 설계가 부재함.

---

## 결정 (Decision)
> **요약**: 파서별 부하량 차이에 따른 워커 풀 고갈을 방지하기 위해 기동(Startup) 시점에 파서별 전용 큐 및 워커를 동적 등록(Dynamic Handler Registration)하여 격리하고, Redis의 기본 자료구조(`List`, `Set`)를 결합해 지식 베이스(KB) 단위로 균등하게 작업을 교차 배분하는 라운드 로빈 스케줄링 메커니즘을 도입함.

### 2.1. 파서별 독립 큐 설계 (워커 격리 및 동적 등록)
파서 엔진의 종류에 따라 전용 큐 및 워커를 할당하여 자원 간섭을 격리하되, 코드 내에 정적으로 하드코딩하지 않고 워커 기동(Startup) 시점에 **동적으로 구독자(Subscriber)를 바인딩**하도록 설계함.
- **동적 바인딩 메커니즘**: `ParserRegistry`에 등록된 활성 파서 엔진 목록(예: `docling`, `native_text` 등)을 기동 단계에서 로드하여 FastStream의 `router.subscriber` 데코레이터를 프로그래밍 방식으로 호출하고 개별 큐를 동적으로 선언함.
- **파서별 동시성 설정**:
  - `docling`: `max_workers=2` (연산 집약적인 로컬 ML 파서용)
  - `native_text` 및 고속/외부 파서: `max_workers=10` (가벼운 CPU 연산 및 API 기반 파서용)
- **폴백(Fallback) 대응**: 하위 호환성 유지 및 미지정 파서 처리를 위한 정적 `document.parse` 큐(`max_workers=2`)를 병행 가동함.

### 2.2. Redis 기반 지식 베이스별 공정 큐 스케줄러(Fair Queue Scheduler) 구현
Redis의 원자적(Atomic) 기본 명령만으로 스케줄링 오버헤드를 제어하고 영속성을 확보할 수 있는 라운드 로빈 디스패처를 구축함.

#### 데이터 구조 디자인:
1. **`kb_queue:{kb_id}:{provider}` (Redis List)**: 특정 지식 베이스(KB)에서 특정 파서로 처리가 대기 중인 문서 메시지들을 순차적으로 보관하는 리스트.
2. **`active_queues:{provider}` (Redis List)**: 대기 메시지가 남아 있는 `kb_id`들을 스케줄링 순서대로 보관하는 원형 순환용 리스트.
3. **`active_kbs:{provider}` (Redis Set)**: 특정 `kb_id`가 `active_queues`에 중복으로 재등록되는 것을 방지하기 위한 유일성 검증용 집합.

#### 동작 알고리즘:

##### A. 메시지 발행 (Enqueue):
API 서버 혹은 Stuck Recovery 루틴에서 직접 FastStream 채널로 전송하지 않고, 아래의 Redis 오퍼레이션을 통해 Staging 큐에 격리 보관함:
1. 해당 `kb_id`가 `active_kbs:{provider}` 집합에 속해 있는지 확인 (`SADD active_kbs:{provider} {kb_id}`의 반환값 확인).
2. 최초 등록되어 성공적으로 Set에 추가된 경우에만, 원형 순환용 리스트 맨 뒤에 추가 (`RPUSH active_queues:{provider} {kb_id}`).
3. 해당 KB 전용 작업 리스트에 메시지 적재 (`RPUSH kb_queue:{kb_id}:{provider} {msg_json}`).

##### B. 스케줄링 디스패치 (Dispatch Loop):
Worker 프로세스의 Startup Lifespan 진입 시, 각 파서별로 독립적인 `asyncio.create_task` 루프(디스패처)를 실행하여 큐를 스캔함.
1. `active_queues:{provider}`의 가장 앞에서 다음 대상 `kb_id`를 디큐(Dequeue)함 (`LPOP active_queues:{provider}`).
2. 스케줄 큐가 완전히 비어있을 경우, 일정 주기(`asyncio.sleep(0.5)`) 동안 대기 후 루프를 재수행함.
3. 확보한 `kb_id`에 해당하는 작업 큐 `kb_queue:{kb_id}:{provider}`에서 단일 메시지를 인출함 (`LPOP kb_queue:{kb_id}:{provider}`).
4. 추출된 메시지를 실제 FastStream 큐인 `document.parse.{provider}` (또는 fallback) 채널로 발행하여 워커가 즉시 실행할 수 있게 함.
5. 해당 `kb_queue:{kb_id}:{provider}`의 잔여 작업량을 파악함 (`LLEN kb_queue:{kb_id}:{provider}`).
   - 잔여 메시지가 **1개 이상**인 경우, 해당 `kb_id`를 순환 스케줄 큐의 맨 뒤에 재등록함 (`RPUSH active_queues:{provider} {kb_id}`).
   - 잔여 메시지가 **0개**인 경우, 중복 방지용 Set에서 삭제하여 스케줄링 사이클에서 제외시킴 (`SREM active_kbs:{provider} {kb_id}`).

```
[ API Ingest ]
      │ (RPUSH)
      ▼
┌──────────────────────────────────────────────┐
│  Redis Staging Area                          │
│                                              │
│  - kb_queue:KB1:docling [msg1, msg2, msg3]   │
│  - kb_queue:KB2:docling [msgA]               │
│                                              │
│  - active_queues:docling [KB1, KB2] (List)   │
│  - active_kbs:docling {KB1, KB2} (Set)        │
└──────────────────────────────────────────────┘
      │
      ▼ (LPOP / RPUSH Round-Robin)
[ Scheduling Dispatcher Task ]
      │
      ▼ (Interleaved Publish)
┌──────────────────────────────────────────────┐
│  FastStream Redis Worker Queues              │
│                                              │
│  - document.parse.docling: [msg1, msgA, msg2]│
└──────────────────────────────────────────────┘
      │
      ├──────────────────────┐
      ▼ (max_workers=2)      ▼
┌──────────────┐       ┌──────────────┐
│ Worker Node1 │       │ Worker Node2 │
│ (processing) │       │ (processing) │
└──────────────┘       └──────────────┘
```

---

## 근거 및 대안 비교 (Rationale & Alternatives)

### 1. Celery 등 무거운 태스크 큐 및 Priority Queue 도입 배제
- Celery는 기본 우선순위(Priority)는 지원하나 완전한 수준의 라운드 로빈 스케줄링을 구현하려면 커스텀 Consumer Loop 구현이 필수적이며 연동 비용이 매우 높음.
- 또한, 본 프로젝트의 핵심인 FastStream 및 Redis Streams 기반 경량 비동기 설계를 대대적으로 전면 개편해야 하므로 리팩토링 대비 아키텍처 복잡성이 지나치게 가중됨.

### 2. Redis List 기반 Round-Robin (채택안)
- **구조적 극대화**: 복잡한 외부 코디네이션 프레임워크나 외부 종속성 없이 Redis 자체 원자적 연산만으로 구성되므로 레이턴시가 발생하지 않고 아키텍처가 단순함.
- **FastStream 생태계 보존**: FastStream의 핵심 기능인 에러 핸들러(`@retry`), DB 상태 추적, 역직렬화 메커니즘을 훼손하지 않고, **큐에 인입되는 순서(Interleaving)만을 앞단에서 재정렬**하므로 영향도가 원천 차단됨.
- **메모리 지속성 및 장애 복구성**: Staging 정보가 Redis 메모리에 영속화되므로, Worker 프로세스가 비정상 종료되거나 컨테이너가 교체되더라도 유실 없이 이전 지점부터 스케줄링이 즉시 재개됨.

---

## 파급 효과 (Consequences)

* **긍정적 효과**:
  - 특정 지식 베이스의 대량 파싱 작업 중에도 신규 지식 베이스의 파싱 요청이 즉시 교차 처리되어 사용자 응답성(UX) 극대화.
  - 파서 속성에 따라 가벼운 파싱(`native_text`)과 무거운 파싱(`docling`)의 워커 풀이 독립되어 CPU/GPU 병목 완화.
  - 외부 관리 컴포넌트 추가 없이 내장 Redis 오퍼레이션만으로 제어 가능하므로 시스템 복잡도가 낮음.
* **부정적 효과 및 완화 조치**:
  - 메시지가 Staging 단계를 추가적으로 거치므로 수 ms 수준의 디스패치 지연이 추가 발생함.
  - **완화 조치**: 본 연산인 문서 파싱에 소요되는 시간(최소 수 초~수십 초) 대비 디스패치 시간은 전체 파이프라인에서 무시할 수 있는 극미한 비중임.
