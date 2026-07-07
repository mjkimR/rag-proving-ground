# ADR-0010: Taskiq 메시지 브로커의 Redis에서 RabbitMQ로의 전환 및 결과 저장소(Result Backend) 이원화

* **작성일 (Date)**: 2026-06-26
* **상태 (Status)**: 승인됨 (Accepted)
* **구현 노트**: 본문 2.1의 "단일 `kb_ingest` 큐 통합"은 이후 스테이지별 3개 큐(`kb_ingest_parse` / `kb_ingest_chunk` / `kb_ingest_embed`, 각 `x-max-priority` 적용)로 변경 구현됨 (`apps/backend/app/worker/broker.py`).

---

## 맥락 (Context)
- 본 결정 사항은 이전의 Redis Streams 기반 설계([ADR-0001](file:///Users/mj/workspace/playground/rag-proving-ground/docs/adr/0001-async-ingestion-architecture.md)) 및 Redis List 기반 우선순위 큐 설계([ADR-0006](file:///Users/mj/workspace/playground/rag-proving-ground/docs/adr/0006-parser-scheduling-and-fair-queue.md))를 완전히 대체합니다.
- 현재 `rag-proving-ground` 프로젝트는 비동기 백그라운드 태스크 처리를 위해 Taskiq 기반의 워커(`apps/backend/app/worker`)를 운영 중이며, 메시지 브로커로 Redis List Queue(`PriorityListQueueBroker` 활용)를 사용하고 있음.
- 파이프라인이 고도화됨에 따라 다음과 같은 한계와 문제점이 발생함:
  1. **메시지 브로커로서 Redis의 기능적 한계**: Redis는 본질적으로 인메모리 Key-Value 스토어이며 전문적인 메시지 큐(Message Queue)가 아님. 따라서 우선순위 큐(Priority Queue), 동적 라우팅, 지연 메시지, 데드 레터(Dead Letter) 등 복잡한 MQ 기능을 도입하려 할 때마다 애플리케이션 계층에서 복잡한 워크어라운드(Workaround)를 직접 구현해야 하는 리스크가 존재함.
  2. **파서 및 임베딩 모델 확장 시 동적 큐 관리의 어려움**:
     - [ADR-0006](file:///Users/mj/workspace/playground/rag-proving-ground/docs/adr/0006-parser-scheduling-and-fair-queue.md)에 따라 파서 엔진별(Docling, native_text) 속도 차이로 인한 병목(Head-of-Line Blocking)을 방지하기 위해 파서별 전용 큐 격리 및 스케줄러를 도입했으나, 임베딩 모델이나 다른 태스크 엔진이 동적으로 추가되는 경우 Redis에서는 이를 명확하고 유연하게 라우팅하기가 매우 어려움.
     - 임베딩 모델별 큐(`embedding.task.openai`, `embedding.task.bge-m3` 등)를 격리하려면 애플리케이션 시작 시점에 큐 목록을 직접 생성하고 바인딩해야 하는 복잡한 공수가 수반됨.
  3. **개발 생산성 저하**: 브로커의 태생적 한계로 인해 발생하는 에러를 대응하고 스케줄러 코드를 유지보수하는 데 상당한 개발 리소스가 낭비됨.

---

## 결정 (Decision)
> **요약**: Taskiq의 백그라운드 태스크 관리를 위한 메시지 브로커를 기존 Redis에서 **RabbitMQ(`taskiq-aio-pika`)**로 전면 전환하고, 태스크 실행 결과 저장소(Result Backend)는 속도가 빠르고 TTL 제어가 용이한 **Redis(`RedisAsyncResultBackend`)**로 유지하여 역할을 명확히 분리(이원화)함.

구체적인 설계 및 구현 방향은 다음과 같음:

### 2.1. RabbitMQ 메시지 브로커 도입 및 단일 우선순위 큐 통합
- `apps/backend/app/worker/broker.py`의 브로커 객체를 기존 Redis List 기반에서 `taskiq-aio-pika` 패키지의 `AioPikaBroker`로 교체함.
- **단일 우선순위 큐 통합**: Redis 환경에서의 5개 물리 큐(`kb_ingest:critical` 등)를 하나의 `"kb_ingest"` 큐로 통일함. 이를 위해 RabbitMQ 선언 시 `"x-queue-type": "classic"` 및 `"x-max-priority": 5` 아규먼트를 설정하여 RabbitMQ 엔진 레벨에서 메시지 헤더의 우선순위 값에 따라 네이티브로 작업을 정렬 및 배분하도록 설계함 (Quorum 큐는 우선순위 기능 미지원으로 Classic 큐 강제 적용).
- **호환성 유지**: Taskiq는 브로커 추상화 계층이 잘 정의되어 있으므로, 백엔드의 비동기 태스크 선언(`@broker.task`)이나 LangGraph, API 단에서의 태스크 호출부 코드 수정을 최소화함.


### 2.2. 결과 저장소(Result Backend)로의 Redis 유지
- RabbitMQ를 결과 저장소로 사용하는 것은 불필요하게 큐 인프라에 오버헤드를 줄 수 있으므로, 처리 결과 및 상태 값 적재는 기존과 동일하게 Redis(`RedisAsyncResultBackend`, 2시간 TTL 설정 포함)를 활용함.
- 브로커(RabbitMQ)와 결과 저장소(Redis)의 책임을 명확히 이원화하여 시스템 전반의 성능과 안정성을 극대화함.

### 2.3. 인프라 오케스트레이션 통합
- `infra/services/docker-compose.yml` 서비스 정의에 `rabbitmq:3-management` 컨테이너를 추가함.
- 15672 포트를 통해 RabbitMQ Management UI 웹 콘솔을 로컬 개발 환경에서 즉시 접근할 수 있도록 노출하여 큐 모니터링 편의성을 대폭 향상함.
- 기존 `.env.example` 및 `justfile` 개발 환경 초기화 스크립트(`just init`)에 RabbitMQ 연결 정보를 반영함.

---

## 근거 및 대안 비교 (Rationale & Alternatives)

### 1. Redis 기반 동적 바인딩 극대화 안 (배제)
- **개요**: Redis 브로커를 유지하고 기동 시점에 DB/설정 파일에서 모델 목록을 읽어 큐를 프로그래밍 방식으로 동적 할당하여 바인딩하는 구조.
- **배제 이유**: 구현에 드는 난이도가 높고, Redis 자체의 라우팅 제어 한계로 인해 코드가 파편화되며, 복잡한 커스텀 스케줄러의 유지보수 비용이 신규 인프라(RabbitMQ) 도입 비용을 상회함.

### 2. Kafka 도입 안 (배제)
- **개요**: 엔터프라이즈 이벤트 스트리밍 시스템인 Apache Kafka 도입.
- **배제 이유**: Kafka는 대용량 스트리밍 및 로그 수집 처리에 최적화되어 있으나, 개별 백그라운드 태스크 단위의 세밀한 제어(개별 태스크 재시도, 지연 실행, 우선순위 배분 등)가 까다롭고, 컨테이너 리소스를 많이 소모하여 소규모/중규모 백그라운드 워커 환경에는 오버엔지니어링임.

### 3. RabbitMQ 도입 안 (채택)
- **채택 이유**: 전통적이고 검증된 AMQP 표준 메시지 브로커로, 토픽 익스체인지(`Topic Exchange`)를 통한 유연한 동적 라우팅이 원활하고, 우선순위 큐를 엔진 레벨에서 네이티브 지원함. 비즈니스 요구사항 변화(임베딩 모델 추가, 파서 다각화)에 따른 큐 확장이 매우 용이하며, 이미 Taskiq 생태계 내에서 `taskiq-aio-pika` 플러그인을 통해 완벽히 검증된 안정성을 지님.

---

## 파급 효과 (Consequences)

* **긍정적 효과**:
  - **유연한 라우팅 및 동적 확장**: 임베딩 모델의 동적 큐 격리(`embedding.task.*`)를 AMQP 와일드카드 토픽 익스체인지 설계를 통해 매끄럽게 처리할 수 있음.
  - **개발 복잡도 감소**: 동적 스케줄링이나 우선순위 큐를 위해 작성했던 복잡한 Redis 커스텀 코드들을 걷어내고, 인프라의 네이티브 기능을 활용해 깔끔한 구조 유지.
  - **모니터링 강화**: RabbitMQ Management UI를 통해 실시간으로 큐 메시지 인입량, 처리 속도, 워커 연결 상태 확인 가능.
* **부정적 효과 및 완화 조치**:
  - **인프라 종속성 추가**: 기존 서비스(Postgres, Qdrant, Redis 등)에 RabbitMQ라는 인프라 컴포넌트가 하나 더 증가함.
  - **완화 조치**: `docker-compose.yml` 및 `justfile`을 통해 신규 설치 오버헤드를 완전 자동화하고, 단일 브로커(AMQP)와 결과 저장소(Redis) 전략을 엄격히 고수하여 복잡도 증가를 최소화함.
