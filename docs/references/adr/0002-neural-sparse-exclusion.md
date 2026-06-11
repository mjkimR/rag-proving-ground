# ADR-0001: Neural Sparse Model 배제 및 렉시컬 검색(BM25)으로의 대체

* **작성일 (Date)**: 2026-06-11

## 맥락 (Context)
- RAG 파이프라인에서 검색(Retrieval) 품질을 보완하기 위해 Dense Retrieval 외에 Sparse Retrieval 모듈 도입 검토.
- 이에 따라 아래 두 가지 대안을 검토함.
  1. SPLADE 또는 기타 학습 기반 Neural Sparse Embedding Model 사용
  2. 전통적인 BM25 및 형태소 분석기 기반의 Lexical Sparse Retrieval 사용

## 결정 (Decision)
> **요약**: Neural Sparse 모델은 성능 향상 폭에 비해 추가 인프라 구축 및 서빙 비용이 과도하여 **가성비(ROI)가 낮다고 판단하고 전면 배제함**.

- 비용 대비 가성비 및 서빙 복잡성을 고려하여 **Neural Sparse 모델을 완전히 배제하고, BM25 기반 렉시컬 검색을 Sparse 모듈로 사용하기로 결정함**.
- BM25의 키워드 매칭 한계는 **Query Rewrite / Query Expansion** 및 **Reranker** 연동을 통해 우회 해결함.

## 근거 (Rationale)
1. **서빙 및 인프라 비용 부담**:
   - Neural Sparse Embedding Model(예: SPLADE)은 임베딩 생성 시 무거운 딥러닝 인코더 서빙 인프라가 필수적임.
   - 반면 BM25는 전처리 단계에서 텍스트 토큰화(한국어 형태소 분석기)만 거치면 Qdrant의 내장 sparse 인덱스 기능을 통해 추가적인 대형 인코더 서빙 없이 가볍게 운영 가능함.
2. **초기 구축 및 관리 복잡도**:
   - Neural Sparse는 corpus 통계에 종속적인 임베딩 모델 학습이나 추가적인 토크나이저 정렬 작업이 수반되어 초기 셋업 복잡도가 매우 높음.
   - BM25는 이미 잘 알려진 수식 기반 렉시컬 점수 계산이며, 한국어 전처리를 위한 형태소 분석기(Kiwipiepy 등) 패키징만으로 즉시 구동 가능함.
3. **가성비 (성능 개선 폭 미비)**:
   - 관련 벤치마크 및 리서치 결과, Neural Sparse 도입 시 Dense + BM25 하이브리드 조합 대비 유의미한 검색 성능 향상을 입증하기 어려움.
   - 인프라 서빙 비용과 연동 작업 부하를 고려할 때 가성비가 매우 낮다고 판단함.
4. **대안책의 유효성**:
   - BM25의 오타 및 동의어 매칭 실패 한계는 무거운 인코더 모델을 추가 서빙하기보다 **Query Rewrite(질의 재작성) 및 Query Expansion(사전 기반 확장)** 기술을 프론트/그래프 레벨에서 활용함으로써 저비용으로 해결 가능함.

## 결과 (Consequences)
* **긍정적 효과**:
  - 추가적인 GPU 인스턴스 서빙 비용 절감 및 아키텍처 단순성 유지.
  - Vector DB(Qdrant) 내의 Sparse 벡터 서빙 레이어가 단순한 BM25 토큰 매핑으로 수렴되어 관리가 용이해짐.
  - 검색 고도화 리소스가 복잡한 모델 서빙 대신 Query Rewrite 등의 흐름 제어(Graph Layer)에 집중되어 실험 반복 속도가 빨라짐.
* **부정적 효과 및 완화 조치**:
  - 키워드 불일치에 대한 우려가 존재하므로, BM25 단독 검색에 의존하지 않고 반드시 Dense + BM25 하이브리드 검색 후 Reranker를 결합하는 파이프라인을 엄격히 적용함.
  - 동의어/약어 검색 보완을 위해 BM25의 쿼리 전처리 단계에 Query Expansion 노드를 개발하여 recall을 보강함.
