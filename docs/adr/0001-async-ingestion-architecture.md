# ADR-0002: FastStream 기반 비동기 문서 인제스션 아키텍처 및 외부 자원 분리 설계

* **작성일 (Date)**: 2026-06-11
* **상태 (Status)**: 대체됨 ([ADR-0010](file:///Users/mj/workspace/playground/rag-proving-ground/docs/adr/0010-migration-from-redis-to-rabbitmq-broker.md))


## 맥락 (Context)
- RAG 문서 인제스션(파싱 → 청킹 → 임베딩)은 CPU/GPU 연산 부하가 매우 큰 작업임.
- API 서버에서 이를 동기적으로 처리할 경우 타임아웃 발생 및 API 워커 고갈로 인한 서비스 마비 위험이 상존함.
- 연산 부하를 분산하고 안정적인 문서 처리를 지원하기 위한 비동기 메시징 및 백그라운드 태스크 엔진 도입을 검토함.
- 비교 대상: Celery vs FastStream (Redis Streams).

## 결정 (Decision)
> **요약**: Celery 대비 가볍고 Asyncio 친화적인 **FastStream (Redis Streams Broker)을 채택**하고, 모든 고부하 작업을 API 서버 외부의 **독립된 워커 프로세스로 격리하여 비동기식 파이프라인으로 처리**하도록 설계함.

- CPU/GPU Bound가 발생하는 핵심 연산(파싱, 임베딩)을 외부 리소스로 취급하고, 이들을 **어댑터 패턴(Adapter Pattern)**으로 결합하여 비동기 파이프라인 서비스에서 순차 호출하도록 구성함.

## 근거 (Rationale)
1. **기술 스택 선정 (Celery 대비 FastStream의 이점)**:
   - Celery는 설정이 복잡하고 무거우며 Python 3.13 및 최신 비동기(Asyncio) 생태계와의 밀접한 통합에 오버헤드가 큼.
   - FastStream은 Asyncio/ASGI 환경과 완전히 융합되며, 데코레이터 기반 선언식 헨들러 지원으로 보일러플레이트 코드가 매우 적고 가벼움.
   - Redis Streams의 Consumer Group 및 보장된 메시지 전송 기능만으로 RAG 파이프라인 요건을 충분히 충족 가능함.
2. **물리적/논리적 자원 격리 (Resource Isolation)**:
   - Docling 파싱 및 로컬 대규모 임베딩 연산 시 발생하는 부하가 실시간 API 서버의 이벤트 루프를 간섭하거나 차단하지 않도록 완전 분리함.
   - 연산 부하 증가 시 API 서버와 Worker 인스턴스를 각각 다르게 독립적으로 스케일아웃(Scale-out)할 수 있는 인프라 유연성 확보.
3. **어댑터 기반의 느슨한 결합 (Loose Coupling via Adapters)**:
   - 파싱, 청킹, 임베딩, 스토리지(MinIO), 벡터 저장소(Qdrant) 등 각 단계를 중립적 인터페이스(어댑터)로 추상화함.
   - 비동기 워커 내부 파이프라인은 구체적인 타겟 구현체에 종속되지 않고 중립 어댑터를 비동기적으로 실행만 하는 구조를 취함.
4. **장애 복구 및 유실 방지 (Self-healing)**:
   - 처리 도중 워커가 다운되거나 예외 발생 시 메시지가 유실되지 않도록 Redis Streams의 Ack/Nack 생명주기 활용.
   - 워커 시작 시 5분 이상 `QUEUED` 상태에 머무는 미처리 문서를 자동 재발행하는 **Startup Recovery Routine**을 탑재하여 자가 복구 기능 내재화.

## 결과 (Consequences)
* **긍정적 효과**:
  - API 서버는 업로드 접수 즉시 HTTP 202 (Accepted)와 문서 ID를 반환하여 최상의 실시간 응답성 유지.
  - 파이프라인 단계별 상태 전이(`QUEUED → PARSING → CHUNKING → EMBEDDING → COMPLETED/FAILED`)가 DB에 명확히 기록되어 뛰어난 관측성 확보.
  - 모듈별로 격리된 어댑터 구조 덕분에 특정 파서나 임베딩 모델의 교체 테스트가 용이함.
* **부정적 효과 및 완화 조치**:
  - FastAPI 라이프사이클 외부에서 독립 워커가 실행되므로, FastAPI 내장 DI(`Depends`)를 공유할 수 없는 구조적 한계 발생.
  - **완화 조치**: `build_pipeline_service()` 수동 DI 팩토리(Manual Wiring Factory)를 구현하여 DB Repository 및 외부 리소스 서비스를 일관되게 조립함.
