# 로컬 개발 및 환경 설정 가이드 (Local Development Guide)

본 문서는 `RAG Proving Ground` 프로젝트의 로컬 개발 환경 구성, 주요 CLI 명령어(`just`), 그리고 인프라 서비스 관리에 대해 설명합니다.

---

## 1. 요구 사양 (Prerequisites)

로컬 개발 및 검증을 위해 아래 소프트웨어들의 설치가 필요합니다.

- **OS**: macOS / Linux (WSL2 권장)
- **Python**: `>= 3.13` (패키지 관리자로 [uv](https://github.com/astral-sh/uv) 필수 사용)
- **Node.js**: `>= 24.0.0` (패키지 관리자로 `npm >= 11.0.0` 사용)
- **Docker & Docker Compose**: 로컬 백엔드 인프라(DB, Vector DB, Redis, S3 Mock) 및 로컬 모델 서빙 구동용

---

## 2. 작업 공간 초기화 (Initialization)

전체 워크스페이스(Python 백엔드 패키지 및 React 프론트엔드 의존성)를 일괄 빌드 및 초기화합니다.

```bash
# 전체 모듈 초기화
just init all

# 백엔드만 초기화
just init backend

# 프론트엔드만 초기화
just init web
```

---

## 3. 개발 서버 구동 (Running in Development)

`just dev` 명령어로 FastAPI 백엔드, React 프론트엔드, Aegra(LangGraph) 서버, 그리고 Taskiq 비동기 워커를 한 번에 실행할 수 있습니다.

```bash
# 전체 서비스 통합 구동 (FastAPI + React + Aegra + Taskiq)
just dev all

# 백엔드 관련 프로세스만 구동
just dev backend

# 프론트엔드만 구동
just dev web
```

> [!TIP]
> 비동기 작업을 처리하는 **Taskiq Worker**만 개별로 구동하여 집중 디버깅하고 싶은 경우에는 아래 명령어를 실행하십시오.
> ```bash
> just worker
> ```

---

## 4. 로컬 인프라 및 모델 서빙 제어

Docker Compose를 이용해 백엔드 지원 서비스 및 로컬 LLM/임베딩 서빙 서비스를 실행하고 내릴 수 있습니다.

### 4.1. 외부 인프라 서비스 (Postgres, Qdrant, MinIO, Redis 등)
```bash
# 로컬 인프라 구동 (macOS / CPU 모드)
just up

# 로컬 인프라 구동 (Linux / GPU 모드)
just up-gpu

# 로컬 인프라 중지 및 정리
just down
```

### 4.2. 로컬 모델 서비스 (Ollama, TEI)
```bash
# Ollama 및 TEI 임베딩/Rerank 모델 구동
just models-up

# 로컬 모델 서비스 중지
just models-down
```

---

## 5. 코드 품질 및 검증 (Linting & Testing)

코드 변경 사항이 있을 때 CI 파이프라인에서 오류가 나지 않도록 로컬에서 사전 검증을 수행합니다.

### 5.1. 포맷터 및 린터 구동 (Ruff & ESLint)
```bash
# 전체 포맷팅 및 린트 자동 교정
just lint all
```

### 5.2. 정적 타입 검증 (Pyright & TypeScript Build)
```bash
# 전체 정적 타입 체크
just check all
```

### 5.3. 테스트 스위트 실행
```bash
# 전체 백엔드 pytest 실행
just test all

# 특정 테스트 파일 집중 실행
just test-file apps/backend/tests/unit/test_storage/test_attachments.py
```

### 5.4. 통합 검증 (Lint -> Check -> Test)
```bash
# 커밋 또는 푸시 전 로컬 무결성 검증
just verify all
```

---

## 6. API 변경 시 프론트엔드 클라이언트 재생성

FastAPI의 백엔드 스키마나 라우터(Router)에 변경이 생겼을 경우, 프론트엔드에서 참조하는 API 클라이언트를 수동으로 빌드/갱신하고 변경 사항을 Git에 함께 커밋해야 합니다.

```bash
# OpenAPI Client 및 hooks 컴포넌트 자동 빌드
just gen-ui-api
```
