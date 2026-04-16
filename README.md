# 서울시 노인 경제 취약층 시각화 앱 실행 방법

## 1) 준비물
- Python 설치
- 이 폴더 전체 다운로드

## 2) 폴더 구조
아래처럼 되어 있으면 됩니다.

```
seoul_streamlit_app/
├─ app.py
├─ requirements.txt
├─ README_KR.md
└─ data/
   ├─ 고령자현황_내국인_구별_2024.csv
   ├─ 2024_서울시_국민기초생활수급자_일반+생계+의료+구별_65세이상.csv
   ├─ 독거노인_총.csv
   ├─ 독거노인_저소득.csv
   └─ 독거노인_기초수급.csv
```

## 3) 설치
터미널(명령 프롬프트)에서 이 폴더로 이동한 뒤 아래 명령어를 입력합니다.

### Windows
```bash
cd 다운로드받은폴더경로\seoul_streamlit_app
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Mac / Linux
```bash
cd 다운로드받은폴더경로/seoul_streamlit_app
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4) 실행
```bash
streamlit run app.py
```

실행하면 브라우저가 열리면서 대시보드가 보입니다.

## 5) 앱에서 볼 수 있는 것
- 색상 지도: 자치구별 취약도 비교
- 버블맵: 규모와 비율을 동시에 확인
- 표: 정렬해서 순위 확인
- 산점도: 지표 간 관계 확인

## 6) 가장 쉬운 발표용 해석
- 색이 진한 곳 = 선택한 지표가 높은 구
- 버블이 큰 곳 = 인원 수가 많은 구
- 표 상위권 = 실제 숫자도 높은 구
- 산점도 오른쪽 위 = 규모도 크고 비율도 높은 구

## 7) 배포까지 해보고 싶다면
터미널에서 GitHub에 올린 뒤 Streamlit Community Cloud에 연결하면 무료 배포가 가능합니다.
