# ADR-0005: IR(중간 표현) 레이어 구조 고도화 및 시각적 검증 워크벤치 도입

* **작성일 (Date)**: 2026-06-15

## 맥락 (Context)
- 본 프로젝트는 모듈화된 RAG 파이프라인의 구축을 위해 파서의 출력을 추상화한 독자적인 중간 표현(IR) 계층(`ParsedDocument`, `ParsedElement`)을 사용하고 있음.
- 기존 IR은 텍스트 중심의 단일 차원 배열 구조(Flat List)로 되어 있어, 문서 내부의 제목(Heading) 간 계층적 논리 트리나 다중 페이지 바운딩 박스(Bounding Box), 복잡한 행/열 병합이 포함된 표(Table) 등의 풍부한 레이아웃 구조를 온전히 보존하지 못하는 한계가 존재함.
- 이에 따라 고급 청커(Semantic/Hierarchical Chunker)와 리트리버가 표의 구조나 부모 섹션의 문맥을 활용하기 어렵고, 프론트엔드에서 원본 PDF 좌표와 파싱 결과를 시각적으로 대조/검증할 수 있는 디버깅 도구가 미비하여 파싱 정합성 추적이 어려웠음.
- Azure AI Document Intelligence의 스키마를 벤치마킹하는 설계안이 제안되었으며, 특정 벤더 SDK에 종속되지 않는 독자 IR 개선 및 웹 UI 시각화 가속기 개발이 필요했음.

## 결정 (Decision)
> **요약**: Azure AI Document Intelligence의 설계 개념을 벤치마킹하여, 특정 SDK 의존성 없이 독자적인 Pydantic 모델을 구성하여 IR을 구조적으로 확장하고, 이를 웹 상에서 동기화하여 검증할 수 있는 **인터랙티브 검증 워크벤치(Visual Verification UI)**를 프론트엔드에 통합하기로 결정함.

- **백엔드 구조 및 알고리즘 고도화**:
  - `ParsedElement` 스키마 내에 논리적 문서 역할을 의미하는 `logical_role` 필드 및 표 구조 메타데이터인 `table_data` (Pydantic `TableGridData`, `TableCellData` 모델 활용)를 도입함.
  * HTML `content`와 `table_data`를 병행 보존하여, LLM 프롬프트용 마크업 데이터와 프론트엔드 인스펙터용 격자 구조를 동시에 제공함.
  * Docling normalizer 단계에서 **Heading Stack 알고리즘**을 구현해 제목(Heading)의 깊이와 출현 순서에 따라 본문 요소들의 `parent_id`와 `children_ids`를 계산하여 동적 계층 트리를 구축하도록 개선함.
- **프론트엔드 양방향 동기화 및 Table Inspector 개발**:
  - `PdfPreview` 컴포넌트가 `provenance` 배열 전체를 순회하도록 개선하여 하나의 논리적 요소가 걸쳐 있는 **다중 페이지 하이라이팅(Multi-page Highlighting)**을 완벽히 지원함.
  - 레이아웃 종류에 최적화된 **역할 기반 컬러 코딩**(Heading: Slate Blue, Table: Emerald Green, Footnote: Peach Orange, Image: Violet Purple)을 하이라이트에 매핑함.
  * `ElementsExplorer` 컴포넌트 내에 문서 계층 구조를 한눈에 볼 수 있는 **Tree Outline 탭**과 타입별 조회가 가능한 **Filter List 탭**을 제공하고, 특정 요소 선택 시 부모 경로를 역추적해 트리 폴더를 자동 확장(Auto-Expand)하는 동기화 메커니즘을 구축함.
  - 표 상세 항목에 스프레드시트 구조의 **Table Grid Inspector**를 탑재하고, 마우스 호버 시 해당 셀의 PDF 바운딩 박스만 동적으로 하이라이트하도록 구성함.

## 근거 (Rationale)
1. **특정 벤더 종속성 배제 (Provider Agnostic)**:
   - Azure SDK 모델을 직접 IR 타입으로 활용하지 않고 자체 Pydantic 정의로 격리함으로써, 추후 다른 파서(Upstage AI, LlamaParse 등)를 연동하더라도 공통 어댑터 매핑 구조만 추가하면 다운스트림 파이프라인의 오염 없이 작동 가능함.
2. **청킹 및 검색 정확도 향상**:
   - `logical_role`과 heading 기반의 부모-자식 트리 계층 구조를 활용해, 청크 구성 단계에서 상위 제목의 맥락을 자동으로 덧붙이거나 표 내부 데이터 간의 인접성 해석이 용이해짐.
3. **개발자 생산성 및 디버깅 가시성 극대화**:
   - 병합된 표의 정합성 유실 여부와 제목의 오분류 여부를 PDF 좌표 오버레이와 그리드 뷰어를 통해 시각적으로 1초 만에 확인/대조할 수 있어, 전처리 및 인제스션 품질 검증 속도가 비약적으로 단축됨.
4. **리액트 렌더링 최적화**:
   - 컴포넌트의 활성 요소 변경에 따른 트리 자동 확장 로직을 `useEffect` 내의 비동기 업데이트가 아닌 렌더링 단계(render-phase)에서 이전 상태값과의 동적 비교를 통해 직접 반영(derived state)함으로써 불필요한 레이아웃 플래시와 렌더 캐스케이딩을 원천 차단함.

## 결과 (Consequences)
* **긍정적 효과**:
  - 다차원 문서 레이아웃의 풍부한 기하/논리 정보 보존 및 계층 청킹 아키텍처 토대 마련.
  - 프론트엔드의 세련되고 인터랙티브한 디버깅 워크벤치를 제공하여 파싱 안정성 모니터링 편의성 제고.
  - ESLint 및 TypeScript 컴파일러 에러 없는 완전한 형식 안정성(Type-safety) 확보.
* **부정적 효과 및 완화 조치**:
  - 표의 격자 데이터 및 좌표 메타데이터를 추가 전달함에 따라 파싱 파일의 직렬화 JSON 용량이 증가함.
  - **완화 조치**: RAG 파이프라인 성능에 미치는 텍스트 임베딩/검색 품질 개선 편익이 용량 대비 훨씬 크므로 수용 가능한 오버헤드이며, 추후 필요시 REST API 상에서 압축 전송 혹은 필드 필터링을 도입할 수 있음.
