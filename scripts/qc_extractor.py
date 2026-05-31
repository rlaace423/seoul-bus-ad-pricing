"""QC: FeatureExtractor가 학습 테이블 피처를 재현하는지 검증.
학습 정류장 좌표 → 추출기 → 모델테이블 값과 피처별 대조(중앙/최대 절대오차, 상관).
좌표산출 피처는 거의 0 오차여야 함. NN대체(승하차/공시지가)는 notna 행에서 자기자신=최근접 → 일치.
실행: uv run python scripts/qc_extractor.py
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'model'))
import numpy as np
import pandas as pd
from feature_extractor import FeatureExtractor, ALL_FEATURES

df = pd.read_csv('data/seoul/모델테이블.csv', dtype={'ARS': str}).dropna(subset=['경도', '위도']).reset_index(drop=True)
# 학습 때와 동일한 플래그
df['flag_버스결측'] = df['승하차_일평균'].isna().astype(int)
df['flag_공시지가결측'] = df['공시지가_원per㎡'].isna().astype(int)
df['flag_역승하차결측'] = df['최근접역_승하차_일평균'].isna().astype(int)

fx = FeatureExtractor(verbose=True)
ex = fx.transform(df['위도'].to_numpy(), df['경도'].to_numpy())
print(f'\n검증 {len(df)}개 정류장, {len(ALL_FEATURES)}피처\n')
print(f'{"feature":<22}{"중앙|Δ|":>12}{"최대|Δ|":>14}{"상관":>8}{"비고":>8}')
worst = []
for c in ALL_FEATURES:
    a = pd.to_numeric(df[c], errors='coerce').to_numpy(float)
    b = pd.to_numeric(ex[c], errors='coerce').to_numpy(float)
    m = np.isfinite(a) & np.isfinite(b)
    if m.sum() == 0:
        print(f'{c:<22}{"(둘다 결측)":>34}'); continue
    d = np.abs(a[m] - b[m])
    corr = np.corrcoef(a[m], b[m])[0, 1] if a[m].std() > 0 and b[m].std() > 0 else float('nan')
    note = '플래그' if c.startswith('flag_') else ('NN' if c in ('승하차_일평균', '경유노선수', '공시지가_원per㎡') else '')
    print(f'{c:<22}{np.median(d):>12,.3f}{d.max():>14,.1f}{corr:>8.4f}{note:>8}')
    if not c.startswith('flag_') and corr < 0.999:
        worst.append((c, corr, d.max()))

print('\n' + ('⚠️ 상관<0.999 피처: ' + str(worst) if worst else '✅ 모든 좌표산출 피처 상관 ≥ 0.999 — 추출기 일관성 확인'))
