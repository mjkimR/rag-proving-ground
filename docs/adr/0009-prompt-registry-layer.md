# ADR-0009: 어댑터 패턴 기반의 프롬프트 레지스트리 레이어 (Prompt Registry Layer) 도입

* **작성일 (Date)**: 2026-06-25
* **상태 (Status)**: 제안됨 (Proposed)

---

## 맥락 (Context)
- 현재 `rag-proving-ground` 프로젝트의 LangGraph 파이프라인(예: `simple_rag.py`) 내부에는 LLM 지시문 및 시스템 프롬프트 템플릿이 하드코딩되어 있거나 분산되어 있음.
- 이로 인해 다음과 같은 문제점과 요구사항이 발생하고 있음:
  1. **실험 및 배포 오버헤드**: 프롬프트 엔지니어링 요소를 조금만 수정하려 해도 백엔드 소스코드를 변경하고 전체 시스템을 재배포해야 하므로, Ragas/DeepEval 기반의 RAG 성능 실험 주기(`rag-eval`)가 지연됨.
  2. **외부 LLMOps 솔루션(Langfuse) 결합 리스크**: Langfuse Prompt Hub는 훌륭한 UI와 버전 추적 기능을 제공하지만, 이를 서빙 인프라의 크리티컬 패스(Critical Path)에 직접 결합할 경우 Langfuse 서버 장애가 전체 LLM 생성 장애(SPOF)로 전파되는 리스크가 있음.
  3. **독립적인 프롬프트 형상 관리**: 외부 SaaS에 종속되지 않고, 기업 내부 인프라(S3 Compatible Storage / MinIO) 내에서 객체 버저닝(Object Versioning) 스펙을 활용해 프롬프트 히스토리를 안전하게 관리할 수 있어야 함.
  4. **고도화된 최적화 기법과의 호환성**: 향후 유전 알고리즘(GA) 기반 프롬프트 진화 튜닝이나, `DSPy`와 같은 컴파일 기반 프롬프트 최적화 프레임워크를 도입할 때 파이프라인 코드의 수정 없이 공급 레이어만 교체할 수 있는 유연한 구조가 필요함.

---

## 결정 (Decision)
> **요약**: `AGENTS.md`에 명시된 핵심 아키텍처 패턴(Parser 및 Vector Store 공급자 분리 아키텍처)을 프롬프트 영역에도 동일하게 적용하여, **추상화 계층 기반의 프롬프트 레지스트리 레이어**를 `packages/rag-core` 내에 구축함.

구체적인 설계 원칙은 다음과 같음:

### 2.1. 정형화된 디자인 패턴 적용
- `interface`, `registry`, `factory`, `instance` 구조를 엄격히 준수함.
- `packages/rag-core` 내에 타 어댑터 모듈(Parser, Vector Store 등)과 완벽하게 동일한 어댑터 패턴 패러다임을 공유하도록 설계하여 가독성과 유지보수성을 극대화함.

### 2.2. S3 Compatible + Versioning 우선 구현
- 기본적이고 안정적인 프롬프트 관리를 위해 S3 객체 버전 관리 API를 연동하는 `S3PromptProvider`를 최우선 구현함.
- 로컬 개발 환경(MinIO 등) 및 운영 환경에서 버킷 내의 객체 버저닝(Object Versioning)을 활성화하여 프롬프트의 이력을 추적 및 격리함.

### 2.3. Langfuse Hub Provider의 격리 및 Fallback 매커니즘
- `LangfusePromptProvider`를 별도로 구현하여 편리한 UI와 버전 추적 기능을 제공하되, 운영 인프라의 핵심 패스가 외부 SaaS 상태에 강결합되는 것을 차단함.
- **캐싱 전략**: 프롬프트 조회 시 매번 API 호출이 발생하는 오버헤드를 방지하기 위해 TTL(Time-To-Live, 기본 5분) 기반 캐싱을 내장하고, 필요한 경우 캐시를 수동으로 만료시킬 수 있는 Invalidation 인터페이스를 노출함.
- **로컬 폴백 설계**: S3/Langfuse 네트워크 연결이 모두 유실된 극한의 상황(Offline)에 대비하여, `packages/rag-core/src/rag_core/prompt/fallback/` 경로 내에 로컬 YAML 포맷으로 백업 프롬프트를 보관하고, 장애 감지 시 자동으로 로컬 파일에서 로드하는 Fallback 체인을 구현함.

### 2.4. 결과물 타입의 추상화 및 렌더링 유효성 검증
- 프롬프트 결과물은 단순 텍스트(`str`)뿐만 아니라, 향후 `dspy.Module` 등 구조화된 객체(`Any`)도 반환할 수 있도록 유연하게 설계함.
- **Chat Prompt 대응**: LangChain/LangGraph와의 자연스러운 통합을 위해, 시스템(System) 및 사용자(User) 메시지 세트 구조(`list[dict]` 혹은 `list[BaseMessage]`)로 파싱 및 가공하여 제공할 수 있도록 추상화 범위를 구성함.
- **스키마 검증**: 템플릿 렌더링 시점에 요구되는 필수 변수들이 정상적으로 주입되었는지 사전 검사하여, LLM 호출 단계로 넘어가기 전에 타입 및 포맷 오류를 조기 탐지(Fail-fast)하도록 보완함.

### 2.5. 환경 변수 및 설정 관리 (Configuration Boundary)
- `AGENTS.md`에 명시된 규칙에 맞게 프롬프트 레지스트리의 작동 상태(Provider 종류, S3 버킷 설정, 현재 활성화된 프롬프트 버전 등)를 `.env` 파일과 연동함.
- 이를 위해 `rag-core` 내에 `pydantic-settings` 기반의 `PromptSettings` 클래스를 구현하고, `@lru_cache` 팩토리를 통해 안전하게 주입받는 구조로 개발함.

---

## Future Extensions (추후 확장 방향)
어댑터 패턴의 도입으로 인해 비즈니스 로직(LangGraph 노드)의 손상 없이 다음과 같은 프롬프트 엔지니어링 고도화 기법을 플러그인 형태로 수용할 수 있음.

### 1. 유전 알고리즘 기반 프롬프트 진화 (Prompt Evolution)
- **메커니즘**: `experiments/` 환경에서 `S3PromptProvider`를 기반으로 수많은 프롬프트 변이(Mutation) 세대를 생성하여 S3에 고유 Version ID로 적재함.
- **평가 및 진화**: 각 Version ID별 Ragas 점수(`rag-eval`)를 산출하고, 점수가 높은 우수 가중치 조합을 교차(Crossover)시켜 최종 세대의 프롬프트를 자동으로 찾아냄. 최적화 완료 후 최종 승리한 Version ID만 백엔드 환경 변수에 주입하여 운영에 즉시 적용함.

### 2. 컴파일 기반 프롬프트 최적화 (`DSPy`)
- **개요**: 프롬프트를 고정된 텍스트가 아닌, 학습 가능한 파라미터가 포함된 '코드 객체'로 다룸.
- **확장 방향**: `DSPyPromptProvider`를 추가하여 S3 또는 로컬 디스크에 직렬화(Serialize)되어 저장된 DSPy 컴파일 가중치 파일(`.json`)을 로드함.
- `get_prompt()`의 반환 타입을 `dspy.Module` 객체로 추상화하여, LangGraph 파이프라인 내부에서는 텍스트 포맷팅 대신 컴파일된 프로그램 모듈을 직접 실행하는 구조로 자연스럽게 진화할 수 있음.

---

## 근거 및 대안 비교 (Rationale & Alternatives)

### 1. Langfuse Prompt Hub 단일 크리티컬 패스 연결 배제
- Langfuse Prompt Hub를 직접 런타임의 동기 호출 패스(Sync Critical Path)에 연결할 경우, Langfuse 클라우드 또는 온프레미스 인프라 장애 발생 시 전체 LLM 추론이 마비되는 단일 장애점(SPOF)이 됨.
- 따라서, 캐싱 계층의 신중한 설계 및 오프라인 YAML/S3 기반 Fallback을 필수적으로 가져가야 신뢰도 높은 프로덕션 수준의 RAG를 유지할 수 있음.

### 2. 파이프라인 내 프롬프트 하드코딩 유지 배제
- 파이프라인 내에 프롬프트를 하드코딩할 경우, 템플릿 수정 시마다 Git 커밋, 빌드, 백엔드 배포 등의 긴 주기가 소요되므로 실험 주기가 급격하게 저하됨.
- 또한, 다양한 프롬프트 변이를 조합하여 Ragas 평가 벤치마크를 돌려보아야 하는 `rag-eval` 모듈의 오프라인 평가 자동화 효율이 떨어짐.

---

## 파급 효과 (Consequences)

* **긍정적 효과**:
  - **SPOF 제거**: 운영 인프라의 핵심 패스가 외부 SaaS(Langfuse) 상태에 강결합되지 않으며, S3 버저닝 혹은 로컬 백업을 통해 100% 장애 격리가 가능함.
  - **실험 속도 극대화**: 소스코드 수정과 컨테이너 빌드 없이 S3 내의 프롬프트 파일 버전을 바꾸거나 환경 변수(`PROMPT_VERSION`) 조정만으로 신속한 A/B 테스트 및 `rag-eval` 평가 러너 실행이 가능함.
  - **일관된 개발 아키텍처**: `rag-core` 내의 타 모듈(Parser, Vector Store 등)과 완벽하게 동일한 어댑터 패턴 패러다임을 공유하므로 코드의 가독성과 유지보수성이 높음.
* **부정적 효과 및 완화 조치**:
  - **추상화 비용**: 단순 하드코딩에 비해 인터페이스 정의 및 팩토리 클래스 조립을 위한 초기 구현 공수가 발생함.
  - **스토리지 관리**: S3 호환 스토리지(MinIO 등)에 버킷 생성 및 Object Versioning 권한 설정 등의 Infra 관리가 동반됨.
