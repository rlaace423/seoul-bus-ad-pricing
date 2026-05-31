"""대화형 테스터: 모델을 1회만 로드(~15~20초) 후 좌표를 반복 입력받아 예측.
매번 uv run 하면 그때마다 로딩하므로, 여러 좌표를 시험할 땐 이걸 쓰세요.

실행:  uv run python model/try_predict.py
입력:  '위도 경도'  (예: 37.4979 127.0276)  ·  종료: q 또는 빈 줄
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from predict import PricePredictor

p = PricePredictor(verbose=True)
print('\n준비 완료! 좌표를 「위도 경도」로 입력하세요  (예: 37.4979 127.0276,  종료: q)')

while True:
    try:
        line = input('\n좌표> ').strip()
    except EOFError:
        break
    if not line or line.lower() in ('q', 'quit', 'exit'):
        break
    parts = line.replace(',', ' ').split()
    if len(parts) < 2:
        print('  형식: 위도 경도  (예: 37.4979 127.0276)')
        continue
    try:
        lat, lon = float(parts[0]), float(parts[1])
    except ValueError:
        print('  숫자로 입력해 주세요.')
        continue
    out = p.predict(lat, lon)
    lo, hi = out['오차범위_원']
    print(f"  예측 광고가: {out['예측가_원per면']:,}원/면   (80% 구간 {lo:,} ~ {hi:,}원)")
    print(f"  {out['자치구_근사']}(근사) · 최근접 학습정류장 {out['최근접학습정류장_m']}m")
    print('  주요 요인(SHAP):')
    for f, pct in out['top_factors']:
        print(f"    {f:<22}{pct:+.1f}%")

print('종료합니다.')
