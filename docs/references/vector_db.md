# Vector Database Architecture & Integration Strategy

이 문서는 `rag-proving-ground` 프로젝트의 벡터 데이터베이스 선정 이유, 아키텍처 패턴, 개발 기준 및 향후 추가 구현 로드맵을 정리한 참조 문서입니다.

---

## 1. Vector DB 선정: Qdrant

본 프로젝트의 실험 및 서빙 스캐폴드 목적에 부합하도록 **Qdrant**를 기본 Vector DB 제공자로 선정했습니다.

### Qdrant 선정 배경
1. **극도로 가벼운 오버헤드:** Rust 기반으로 설계되어 로컬 컨테이너 구동 시 Idle 메모리가 50MB~100MB 수준에 불과합니다. (Milvus Standalone은 최소 1GB~2GB 점유)
2. **내장 웹 UI (Dashboard):** 컨테이너 기본 웹 대시보드(포트 `6333/dashboard`)가 내장되어 있어, 임베딩된 데이터와 페이로드, 매핑 상태를 브라우저에서 즉시 탐색할 수 있습니다.
3. **Schemaless Payload:** 임의의 JSON 페이로드 구조를 선언 없이 주입할 수 있어 다양한 파싱/청킹 메타데이터 실험에 적합합니다.
4. **Partition Key 지원:** 하나의 컬렉션을 공유하면서도 물리적으로 데이터를 안전하게 격리·라우팅 검색할 수 있는 네이티브 멀티테넌시를 제공합니다.

---

## 2. 환경 변수 구성 (`.env`)

Qdrant 어댑터의 Pydantic 설정 클래스(`QdrantSettings` 및 `VectorDBSettings`)는 아래의 환경 변수 규격을 따릅니다.

```bash
# ==============================================================================
# Vector Database Settings
# ==============================================================================
# 사용 가능한 프로바이더: none | qdrant | milvus
VECTOR_DB_PROVIDER=qdrant

# Qdrant 연결 설정 (VECTOR_DB_PROVIDER=qdrant 일 때 활성화)
VECTOR_DB_QDRANT_URL=http://localhost:6333
VECTOR_DB_QDRANT_API_KEY=
```

> [!NOTE]
> `VECTOR_DB_QDRANT_API_KEY`는 로컬 개발 환경(Docker)에서는 필수값이 아니며, 공백으로 둘 경우 인증 없이 연결하도록 처리되어 오버헤드를 줄입니다.

---

## 3. 핵심 아키텍처 패턴

### Pattern 1: Dynamic Probe (임베딩 차원 동적 조회)
LangChain의 `Embeddings` 인터페이스는 차원 정보(`dimension`) 속성을 제공하지 않으며, `models.yaml`에 따라 모델마다 벡터 차원수(예: 1536, 768 등)가 가변적입니다.
* **해결책:** 컬렉션 최초 생성 시, 더미 텍스트 `"dummy"`를 1회 임베딩(`embed_query("dummy")`)하여 반환된 벡터 리스트의 길이(`len()`)를 통해 차원을 동적으로 측정합니다.
* **이점:** 새로운 임베딩 모델이 추가되거나 교체되어도 하드코딩 매핑 테이블 수정 없이 100% 동적으로 자동 대응합니다.

### Pattern 2: Config Hash-based Collection (설정 해시 기반 컬렉션화)
지식 베이스(Knowledge Base)마다 물리적 컬렉션을 새로 생성하면 HNSW 인덱스 과다 생성으로 가상 환경 리소스 고갈(OOM 등)이 일어납니다. 반면 완전히 모든 것을 단일 컬렉션으로 묶기에는 임베딩 모델이나 인덱싱 설정이 다른 경우가 발생합니다.
* **해결책:** 물리적 벡터 공간에 영향을 주는 **인덱스 사양 설정 객체**를 직렬화하여 해시(SHA-256)를 구하고, 해당 해시값을 컬렉션 이름으로 사용합니다.

```python
import hashlib
import json

spec = {
    "embedding_model": "text-embedding-3-small",
    "distance": "cosine",
    "sparse_vector": False
}
serialized = json.dumps(spec, sort_keys=True)
spec_hash = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
collection_name = f"vector_store_{spec_hash}"
```
* **이점:** 동일한 임베딩 모델과 벡터 인덱스 사양을 가진 지식 베이스들은 자동으로 물리 컬렉션을 완벽하게 공유하고, 사양이 달라지는 경우에만 안전하게 새 컬렉션으로 격리됩니다.

### Pattern 3: Partition Key를 활용한 멀티테넌시 격리
단일 컬렉션을 공유할 때 다른 지식 베이스의 데이터가 침범하지 않도록 페이로드에 `knowledge_id` 필드를 주입하여 논리적 격리를 수행합니다.
* Qdrant의 `Partition Key` 인덱싱을 통해 `knowledge_id` 별로 세그먼트를 분할 라우팅함으로써 물리적인 컬렉션 분리와 다름없는 초고속 격리 검색 속도를 구현합니다.

---

## 4. 코드 베이스 구조 (`packages/rag-core`)

벡터 데이터베이스 어댑터는 다음과 같은 확장 구조로 정립되었습니다.

```
packages/rag-core/src/rag_core/adapters/vector_store/
├── __init__.py
├── config.py         # VectorDB 전역 및 프로바이더 Pydantic 설정 정의
├── interface.py      # VectorStoreProvider 공통 인터페이스 규격
├── registry.py       # 프로바이더별 클래스 동적 모듈 로더/레지스트리
├── factory.py        # 캐시 처리 및 LangChain VectorStore 연결 팩토리
├── instance.py       # Lifespan 동안 사용할 전역 싱글톤 인스턴스 관리자
├── lifespan.py       # FastAPI 구동 시 연결/해제 처리를 위한 lifespan 컨텍스트
└── providers/
    └── qdrant.py     # Qdrant Client 초기화 및 컬렉션 자동 생성 구현체
```

---

## 5. 향후 추가 작업 및 로드맵 (Roadmap)

### Task 1: `VectorStoreFactory` 내 해시 컬렉션 기능 추가
* [ ] 지식 베이스 생성/조회 요청 시, 선택된 임베딩 모델 및 거리 측정 파라미터를 기반으로 `VectorConfigSpec` 해시 컬렉션 이름을 생성하여 라우팅 처리.

### Task 2: Qdrant Partition Key 생성 로직 고도화
* [ ] 컬렉션 생성 직후 `create_payload_index`를 통하여 `metadata.knowledge_id` 필드를 `KEYWORD` 및 파티션 키 스키마로 인덱싱 처리하도록 `qdrant.py` 확장.

### Task 3: 백엔드 상태 검사(Health) 추가
* [ ] FastAPI `app/main.py` 또는 `health` 엔드포인트에 Qdrant 클라이언트 핑(Ping) 테스트를 연동하여 벡터 데이터베이스 서비스 동작 상태 시각화.

### Task 4: UI 연계 실험
* [ ] `apps/web` 프론트엔드 작업 영역에서 지식 데이터 청킹 업로드 시 지정한 Qdrant 해시 컬렉션 공간으로 안전하게 삽입되고, 대시보드상에서 문서 검색이 원활하게 되는지 통합 검증.
