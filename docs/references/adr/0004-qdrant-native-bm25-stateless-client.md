# ADR-0004: Qdrant Native BM25 및 Stateless 클라이언트 아키텍처 도입

* **작성일 (Date)**: 2026-06-11

## 맥락 (Context)
- 본 프로젝트는 고성능 하이브리드 검색(Dense + Sparse)을 위해 한국어 형태소 분석기(Kiwipiepy) 기반의 BM25 모델을 도입하여 사용 중임.
- 기존 `KoreanMorphemeBM25Embeddings` 클라이언트는 내부적으로 문서의 통계를 저장하는 구조(`_fit_corpus` 및 전역 딕셔너리 사용)를 가지고 있어, 백엔드 워커(Worker) 노드가 스케일아웃되는 분산 환경에서 상태 동기화가 불가능함.
- LangChain에서 제공하는 Qdrant 래퍼 클래스는 추상화 레벨이 높아 Qdrant 1.15.2+ 버전부터 지원하는 네이티브 On-Server BM25 규격(예: `Modifier.IDF`)을 세밀하게 제어하거나 활용하기 어려움.
- 기존 Qdrant 어댑터 로직이 Kiwi 기반의 BM25 모델에 강하게 결합되어 있어, 타 언어 Sparse 모델 추가 시 확장이 어려운 상태(OCP 위배)임.
- 일각에서 Milvus 등 타 Vector DB로의 교체도 논의되었으나, 당분간 가볍고 효율적인 Qdrant를 유지하기로 합의함.

## 결정 (Decision)
> **요약**: BM25 임베딩 클라이언트를 **완전한 무상태(Stateless) 구조**로 전면 리팩토링하고, 상태 관리가 필요한 연산은 **Qdrant Native `Modifier.IDF`를 활용하는 서버 사이드 연산**으로 위임하기로 결정함.

- 생성 시점(`create_vector_store`)에 Qdrant의 네이티브 `Modifier.IDF` 속성을 부여하여, 서버가 코퍼스의 통계를 기반으로 동적인 가중치 연산을 수행하도록 통합함.
- 클라이언트에서는 내부 상태 저장 로직을 제거하고, 문서 길이 정규화 상수(`avg_length`)와 TF 포화도(Saturation) 공식을 수학적으로 정확히 선처리하도록 개편함.
- 어댑터가 모델 구현체에 상관없이 IDF 필요 여부를 판독할 수 있도록, `SparseEmbeddingModel` 인터페이스에 `requires_server_side_idf` 메타데이터 속성을 추가함.

## 근거 (Rationale)
1. **분산 워커 환경 대응 (Statelessness)**:
   - 검색 결과의 일관성을 유지하면서 워커 노드를 자유롭게 스케일아웃하기 위해서는 어플리케이션 레이어(클라이언트)가 상태를 가지지 않아야 함.
2. **개방-폐쇄 원칙 (OCP) 준수**:
   - `requires_server_side_idf` 속성과 `SparseEmbeddingRegistry`를 통한 동적 바인딩 구조를 통해, 향후 영어 등 새로운 Sparse 모델이 추가되더라도 기존 어댑터 코드를 수정하지 않고 확장이 가능함.
3. **효율적인 연산 분산**:
   - 코퍼스 전체 통계가 필요한 무거운 IDF 연산을 클라이언트가 아닌 Vector DB 서버로 이관하여 성능과 정확성을 모두 최적화함.

## 결과 (Consequences)
* **긍정적 효과**:
  - 클라이언트 무상태성을 확보하여 다중 프로세스/분산 서버 환경에서의 검색 정합성 보장.
  - Qdrant 최적화된 내부 모디파이어를 활용하여 쿼리 시점의 네트워크 오버헤드 감소 및 연산 속도 향상.
  - 신규 Sparse 모델 추가 시 유지보수 공수 대폭 절감.
* **부정적 효과 및 완화 조치**:
  - Qdrant 벤더의 특정 버전 스펙(v1.15.2+)에 로직이 종속되어 타 Vector DB 이식성이 감소함.
  - **완화 조치**: 현재 아키텍처 방향성 상 Qdrant를 유지하기로 결정했으므로 당장의 리스크는 낮음. 향후 Milvus 등으로 이전이 필요할 시, 해당 DB의 Sparse 처리 방식에 맞춘 신규 어댑터(Provider) 구현체를 인터페이스 하위에 격리하여 추가하는 방식으로 대응함.
