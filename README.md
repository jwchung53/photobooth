# Emotion Photo Booth

윈도우 기반 키오스크형 감정 포토부스 앱.
USB 웹캠으로 다중 인원을 촬영 → 얼굴별 감정 분석 → 감정별 프레임 합성 → 인쇄합니다.

## 기술 스택

- **Python 3.11** / [uv](https://github.com/astral-sh/uv) 패키지 관리
- **GUI**: PyQt6
- **카메라**: OpenCV (`cv2.CAP_DSHOW` 백엔드)
- **얼굴 검출**: RetinaFace
- **감정 분석**: DeepFace (7감정, TensorFlow CPU)
- **이미지 합성**: Pillow
- **인쇄**: pywin32
- **사운드**: pygame.mixer

## 감정 → 프레임 매핑

DeepFace 7감정을 5개 프레임 카테고리로 재매핑합니다.

| DeepFace 감정      | 프레임 카테고리 | 컨셉               |
| ------------------ | --------------- | ------------------ |
| happy              | joy             | 꽃, 폭죽, 따뜻한 톤 |
| surprise           | wow             | 별, 반짝이         |
| sad                | calm            | 블루               |
| angry, disgust     | cool            | 다크 + 불꽃        |
| fear, neutral      | chill           | 미니멀 자연톤      |

> 원칙: 모든 감정 결과가 사용자에게 긍정적으로 보이도록 한다.

## 설치

```powershell
# uv 설치 후
uv sync                    # 런타임 의존성 설치
uv sync --extra dev        # 개발 의존성(pytest, ruff) 포함
```

## 실행

```powershell
uv run python main.py
```

## 설정

모든 튜닝 값은 [`config.yaml`](config.yaml)에서 관리합니다 (카메라 해상도, 출력 폴더, 로깅 레벨 등).

## 개발 단계

- **Phase 1**: 콘솔 MVP — 캡처 → 분석 → 합성 → 파일 저장
- Phase 2~9: PyQt 화면, 카메라 스레드, 인쇄, 키오스크 모드, 패키징

자세한 내용은 [`CLAUDE.md`](CLAUDE.md) 참고.
