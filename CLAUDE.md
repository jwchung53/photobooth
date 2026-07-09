# Emotion Photo Booth - Project Context

## 프로젝트 개요
윈도우 기반 키오스크형 포토부스 앱.
USB 웹캠으로 다중 인원 촬영 → 얼굴별 감정 분석 → 감정별 프레임 합성 → 인쇄.

## 기술 스택
- Python 3.11, uv 패키지 관리
- GUI: PyQt6
- 카메라: OpenCV (cv2.CAP_DSHOW 백엔드 필수)
- 얼굴 검출: RetinaFace
- 감정 분석: DeepFace (7감정)
- 이미지 합성: Pillow
- 인쇄: pywin32
- 사운드: pygame.mixer

## 감정 → 프레임 매핑
DeepFace 7감정을 6개 프레임 카테고리로 재매핑:
- happy → joy (기쁨: 꽃, 폭죽, 따뜻한 톤)
- surprise → wow (놀람: 별, 반짝이)
- sad → calm (슬픔: 블루)
- angry, disgust → cool (분노: 다크 + 불꽃)
- neutral → chill (무표정: 미니멀 자연톤)
- fear → fear (두려움: 신비·판타지 컨셉, 보라빛)

원칙: 6개 카테고리 모두 사용자에게 긍정적으로 보이도록 (fear도 판타지 컨셉으로 재해석).

## 프로젝트 구조
photobooth/
├── CLAUDE.md
├── pyproject.toml
├── config.yaml
├── main.py
├── phase1_pipeline.py
├── src/
│   ├── init.py
│   ├── camera/
│   │   └── init.py
│   ├── analysis/
│   │   └── init.py
│   ├── compose/
│   │   └── init.py
│   ├── print/
│   │   └── init.py
│   ├── ui/
│   │   └── init.py
│   └── utils/
│       ├── init.py
│       ├── logger.py
│       ├── config.py
│       └── sound.py
├── assets/
│   ├── frames/
│   └── sounds/
├── output/
└── logs/
## 코딩 규칙
- 모든 새 모듈은 단독 실행 가능하게 작성 (`if __name__ == "__main__":` 테스트 코드)
- 외부 리소스(카메라, 프린터)는 try/except + 로깅 필수
- QThread 사용 시 pyqtSignal로만 UI 통신
- 사용자 표시 텍스트는 한국어
- 코드 주석은 한국어 OK, docstring은 영어
- 함수/변수명은 영어 snake_case
- 매직 넘버는 config.yaml 또는 모듈 상단 상수로

## 키오스크 운영 원칙
1. UI는 절대 멈추지 않는다 — 무거운 작업은 모두 QThread
2. 모든 화면은 60초 무입력 시 대기 화면으로 복귀
3. 종료는 관리자 키 조합(Ctrl+Shift+Q)으로만
4. 에러는 사용자에게 친절하게 — 기술적 에러 메시지 노출 금지

## 개발 단계 (Phase)
- **Phase 1** (오늘 목표): 콘솔 MVP — 캡처→분석→합성→파일 저장
- Phase 2: PyQt 5개 화면 스켈레톤
- Phase 3: 카메라 스레드 + 라이브 프리뷰 + 카운트다운
- Phase 4: 분석 스레드 통합 + 진행 애니메이션
- Phase 5: 인쇄 모듈 통합
- Phase 6: 키오스크 모드
- Phase 7: 디자인 정리
- Phase 8: 현장 테스트
- Phase 9: PyInstaller 패키징

## Claude Code 작업 규칙
1. 새 파일 작성 전 위 프로젝트 구조에 맞는 위치 확인
2. 의존성 추가 시 `uv add <package>` 명령 제안
3. 한 번에 한 Phase만 작업, 다음으로 넘어가기 전 사용자 확인
4. config.yaml에 들어갈 값은 하드코딩하지 말고 별도 안내
5. 각 모듈은 단독 테스트 가능하게 (`if __name__ == "__main__":`)

## 환경
- OS: Windows 11
- 카메라: USB 웹캠
- 프린터: 포토 프린터 (모델 추후 확정, 4x6 또는 6x4 인치)
- 화면: 풀HD 모니터 가정