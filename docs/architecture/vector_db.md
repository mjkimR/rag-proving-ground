# RAG 지식 베이스 및 데이터 파이프라인 설계 문서

## 1. 개요 (Overview)

본 문서는 `rag-proving-ground` 프로젝트의 지식 베이스(Knowledge Base) 관리, 문서별 전처리 파이프라인 상태 제어, 그리고 Vector DB(Qdrant) 통합 전략을 다룹니다. 특히 글로벌 설정과 개별 문서 설정 간의 **상속(Inherit) 패턴**을 정의하고, **기존 파일 해시 캐싱 구조**와 연계하여 글로벌 설정 변경 시 발생하는 시스템 부하를 최소화하는 재처리 메커니즘을 수립합니다.

---

## 2. 데이터 모델 설계 (Database Architecture)

### 2.1 Core 테이블 구조

#### ① KnowledgeBase (지식 베이스 마스터)

지식 베이스의 글로벌 전처리 사양 및 벡터 인덱스 연동 기준을 정의합니다.

* **status**: `READY` | `RUNNING` | `FAILED` | `COMPLETED` | `DELETING`
* **KnowledgeEmbeddingConfig (JSON)**: 사용할 임베딩 모델 정보 및 거리 측정 메트릭 사양. `rag_core.embeddings.KnowledgeEmbeddingConfig` Pydantic 모델로 검증하며 현재 필드는 `model`, `distance`입니다.
* **embed_config_hash**: resolved `KnowledgeEmbeddingConfig`의 canonical payload(`model`, `distance`)를 SHA-256으로 직렬화한 16자리 해시값. Qdrant의 물리 컬렉션 ID 생성 주축으로 활용 (`vector_store_{hash}`)
* **KnowledgeDefaultChunkingConfig (JSON)**: 글로벌 기본 청킹 설정 (예: `chunk_size`, `chunk_overlap`)
* **KnowledgeDefaultParsingConfig (JSON)**: 글로벌 기본 문서 파싱 설정 (예: OCR 사용 여부, 전처리 룰)

#### ② KnowledgeBaseDocument (개별 문서 설정 및 상태)

지식 베이스에 소속된 개별 파일의 처리 상태 및 개별 최적화 설정을 관리합니다.

* **status**: `READY` | `PARSING` | `CHUNKING` | `EMBEDDING` | `FAILED` | `COMPLETED` | `PENDING_REPARSE` | `PENDING_RECHUNK` | `PENDING_REEMBED` | `DELETING`
* **document_info**: 파일명, 파일 크기, 원본 스토리지 경로 등 기본 메타데이터
* **file_hash**: 파일 내용 고유의 SHA-256 해시값. `parser_cache` 및 `knowledge` 디렉토리 식별용 주축 키로 활용됩니다.
* **KnowledgeChunkingConfig (Nullable, JSON)**: `rag_core.chunkers.ChunkingConfig` Pydantic 모델로 검증하는 개별 문서 커스텀 청킹 설정. `Null`일 경우 상위 KB 설정을 상속받음 (Override 패턴)
* **KnowledgeParsingConfig (Nullable, JSON)**: `rag_core.parsers.KnowledgeParsingConfig` Pydantic 모델로 검증하는 개별 문서 커스텀 파싱 설정. `Null`일 경우 상위 KB 설정을 상속받음 (Override 패턴)
* **document_info.parsing_config_hash**: resolved `KnowledgeParsingConfig`를 SHA-256으로 직렬화한 16자리 해시값. 지식 베이스(`knowledge`) 영역 내에는 현재 직접 사용되는 활성 파싱 결과물(`parsed_data.json`) 한 개만 보관하고, DB에 기록된 `parsing_config_hash`가 동일할 때만 파싱 과정을 스킵하고 즉시 재청킹(rechunk)으로 진입합니다. 파싱 설정이 변경되었을 경우에는 전역 파서 캐시(`parser_cache`)에서 캐시 히트 여부를 판별합니다.

---

### 2.2 이력 관리 및 비동기 작업 테이블 (ReadOnly / 비동기 큐 레이어)

* **이력 로그 (Read-Only)**: `KnowledgeParsingHistory`, `KnowledgeChunkingHistory`, `KnowledgeEmbeddingHistory` (모니터링 및 비용 추적용 감사 로그)
* **비동기 Job**: `KnowledgeParsingJob`, `KnowledgeChunkingJob`, `KnowledgeEmbeddingJob` (태스크 큐 백엔드 연동용 심볼. 실제 비동기 처리는 Taskiq의 Redis backend를 활용하여 분산 처리)

---

## 3. 파이프라인 단계별 부하 특성

### 3.1 작업 유형별 리소스 부하 프로필

#### ① 재파싱 (Re-Parsing) : High Load (고부하 작업)

* **트리거 조건:** 글로벌 파싱 설정(`KnowledgeDefaultParsingConfig`)이 변경되었거나, 완전히 새로운 파일이 업로드된 경우
* **작업 특성:** 무거운 파일 I/O, PDF 레이아웃 분석, OCR 등의 CPU/GPU 집약적 연산이 수행됩니다.
* **캐시 제어:** 파싱 설정이 변경되거나 신규 파일 업로드 시, 전역 캐시 `parser_cache/{file_hash}/{parse_config_hash}/`를 먼저 조회하여 기존에 동일 설정으로 파싱된 아티팩트가 있는지 검사합니다. 전역 캐시 히트 시 물리 파싱은 생략되며, 캐시 미스 시에만 실제 파싱 서버를 호출하여 물리적 재파싱을 수행합니다.

#### ② 재청킹 및 재임베딩 (Re-Chunking & Re-Embedding) : Low Load (저부하 작업)

* **트리거 조건:** 글로벌 청킹 설정(`KnowledgeDefaultChunkingConfig`)만 변경되어 파싱 스킵이 가능한 경우
* **작업 특성:** 가장 무거운 '파싱' 단계를 전면 생략합니다. 이미 추출되어 저장되어 있는 순수 텍스트(Raw Text)를 즉시 메모리로 로드하여 문자열 분할(Chunking)과 배치 벡터화(Embedding)만 수행합니다.
* **시스템 영향:** 연산 비용이 매우 낮아 수백 건의 문서를 일괄 처리하더라도 API Rate Limit만 관리하면 동기식 처리나 가벼운 백그라운드 스레드로 즉시 소화 가능합니다.

---

## 4. 글로벌 설정 변경 시 UX 및 파이프라인 전이 시나리오

운영자가 KB 설정 화면에서 설정을 변경할 때, 시스템은 '무엇을 변경했는가'를 감지하여 유연하게 대응합니다.

### 4.1 설정 변경 유형에 따른 시스템 동작 구조

| 설정 변경 유형 | 예상 부하 및 대응 전략 |
| --- | --- |
| **청킹 설정만 수정**<br><br>(예: Chunk Size 변경) | **Low Load**<br><br>비동기 작업 큐 시스템 없이도 즉각적인 일괄 재처리 허용 가능 |
| **파싱 설정 수정**<br><br>(예: OCR 엔진 변경) | **High Load**<br><br>동기 처리 시 타임아웃 위험. 비동기 Taskiq Job 시스템 완비 후 개방 권장 |

### 4.2 사용자 선택 옵션

기본값을 변경하는 시점에 시스템은 부하 특성을 반영하여 안내 문구를 가변적으로 표출합니다.

* *청킹 변경 시:* "청킹 설정만 변경되어 파싱 과정 없이 빠르게 재처리가 완료됩니다."
* *파싱 변경 시:* "파싱 설정이 변경되어 전체 문서를 처음부터 다시 분석하므로 시간이 다소 소요될 수 있습니다."
* **옵션 A (신규 적용):** 기존 문서는 유지하고, 향후 추가될 새 문서에만 변경된 설정을 상속함: 과거 config 기준으로 'Null 값을 채워버리는(Freeze)' 방식 & 해당 부분 안내 필요
* **옵션 B (상속 문서 재처리):** 개별 커스텀 설정이 없는(Null인) 문서만 타겟팅하여 설정 유형에 따라 `PENDING_RECHUNK` 또는 `PENDING_REPARSE`로 전이함.
* **옵션 C (강제 일괄 적용):** KB 내 모든 문서의 커스텀 설정을 초기화하고 전원 재처리 상태로 전이함.
* **임베딩 설정 변경:** 문서별 override가 없는 KB 레벨 설정이므로 기존 문서는 `PENDING_REEMBED`로 전이함. 기존 문서 freeze가 불가능하므로 신규 적용 옵션은 허용하지 않음.

UI 편의성을 위해
- '기본값으로 초기화(Reset to Default - 다시 Null로 만듦)' 할 수 있는 액션 버튼을 제공하면 좋음

### 4.3 삭제 및 감사 로그 정책

* **삭제 처리:** KB/문서 삭제는 먼저 DB row를 `DELETING` 상태로 전이하고 transaction을 커밋한 뒤, Vector DB 및 Object Storage cleanup을 transaction 밖에서 수행함. 외부 cleanup 실패 시 DB row는 삭제하지 않고 `FAILED`로 전이하여 재시도 가능하게 유지함.
* **이력 로그:** `KnowledgeParsingHistory`, `KnowledgeChunkingHistory`, `KnowledgeEmbeddingHistory`는 pipeline 내부에서만 생성하는 read-only audit log로 취급함. 외부 API는 list/get만 제공함.
