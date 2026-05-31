"""7단계: 격자 사전계산 테이블 → model/grid_250m.csv.
- 서울 마스터 정류소 bbox에 250m 격자 생성.
- 실제 버스정류소(마스터 11,250) 400m 이내 칸만 유지(강·산 등 무의미 칸 제외).
- 각 칸: predict_batch → 예측가·오차범위·위치별 SHAP top5(2층위)·최근접학습정류장 거리·신뢰도.
실행: uv run python scripts/build_grid.py [cell_m] [mask_m]
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'model'))
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from feature_extractor import _to_xy
from predict import PricePredictor

CELL_M = int(sys.argv[1]) if len(sys.argv) > 1 else 250
MASK_M = int(sys.argv[2]) if len(sys.argv) > 2 else 400
LAT0 = 37.55

# ---- 마스터 정류소 ----
m = pd.read_excel('data/seoul/서울시버스정류소위치정보(20260506).xlsx', dtype=str)
mlon = pd.to_numeric(m['X좌표'], errors='coerce')
mlat = pd.to_numeric(m['Y좌표'], errors='coerce')
ok = mlon.between(126.6, 127.3) & mlat.between(37.3, 37.8)
mlon, mlat = mlon[ok].to_numpy(), mlat[ok].to_numpy()
master_tree = cKDTree(_to_xy(mlon, mlat))
print(f'● 마스터 정류소 {len(mlon):,}  bbox lon[{mlon.min():.3f},{mlon.max():.3f}] lat[{mlat.min():.3f},{mlat.max():.3f}]')

# ---- 250m 격자 ----
step_lat = CELL_M / 110540.0
step_lon = CELL_M / (111320.0 * np.cos(np.radians(LAT0)))
lat_g = np.arange(mlat.min(), mlat.max() + step_lat, step_lat)
lon_g = np.arange(mlon.min(), mlon.max() + step_lon, step_lon)
LA, LO = np.meshgrid(lat_g, lon_g)
clat, clon = LA.ravel(), LO.ravel()
print(f'● 격자 {CELL_M}m: {len(lat_g)}×{len(lon_g)} = {clat.size:,} 후보 칸')

# ---- 마스터 정류소 MASK_M 이내만 ----
d, _ = master_tree.query(_to_xy(clon, clat), k=1)
keep = d <= MASK_M
clat, clon = clat[keep], clon[keep]
print(f'● 정류소 {MASK_M}m 이내 유지: {clat.size:,} 칸 ({keep.mean()*100:.0f}%)')

# ---- 예측 ----
p = PricePredictor(verbose=True)
print('● 격자 예측 중...')
grid = p.predict_batch(clat, clon, top_n=5)

# 신뢰도 등급(최근접 학습정류장 거리)
dd = grid['최근접학습정류장_m'].to_numpy()
grid['신뢰도'] = np.where(dd < 250, '상', np.where(dd < 700, '중', '하'))

out = 'model/grid_250m.csv' if CELL_M == 250 else f'model/grid_{CELL_M}m.csv'
grid.to_csv(out, index=False, encoding='utf-8-sig')

# ---- 리포트 ----
pr = grid['예측가_원per면']
print(f'\n● 저장: {out}  ({len(grid):,}칸 × {grid.shape[1]}열)')
print(f'● 예측가(원/면): 중앙 {pr.median():,.0f}  (p10 {pr.quantile(.1):,.0f} ~ p90 {pr.quantile(.9):,.0f}, '
      f'min {pr.min():,.0f} ~ max {pr.max():,.0f})')
print(f'● 신뢰도: ' + ' / '.join(f'{k} {v}' for k, v in grid['신뢰도'].value_counts().items()))
print('● top1 요인 빈도:')
for k, v in grid['top1_피처'].value_counts().head(6).items():
    print(f'    {k:<18} {v:>5} 칸 ({v/len(grid)*100:.0f}%)')
