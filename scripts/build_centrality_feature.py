"""
피처 빌드 #3: 중심지까지 거리 (우선순위 5). 다운로드·키 불필요 — 좌표만으로 계산.
서울 3도심(2030 서울도시기본계획): 한양도성(시청)·강남·영등포여의도.
각 정류장에서 3도심까지 거리 + 최근접 도심 거리(=도심 접근성).
실행: uv run python scripts/build_centrality_feature.py
"""
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
COORDS = ROOT / "data/seoul/features/정류장_좌표.csv"
OUT = ROOT / "data/seoul/features/중심지거리.csv"

# (위도, 경도). 서울 3도심 대표 좌표.
CENTERS = {
    "시청": (37.5663, 126.9779),   # 한양도성 도심(중구 시청)
    "강남": (37.4979, 127.0276),   # 강남역
    "여의도": (37.5219, 126.9245),  # 영등포·여의도 도심
}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


df = pd.read_csv(COORDS, dtype={"ARS": str})
m = df["경도"].notna()
lat = df.loc[m, "위도"].astype(float).values
lon = df.loc[m, "경도"].astype(float).values

out = df[["ARS", "자치구", "정류장이름"]].copy()
dist_cols = []
for name, (clat, clon) in CENTERS.items():
    col = f"거리_{name}_km"
    out.loc[m, col] = np.round(haversine_km(lat, lon, clat, clon), 3)
    dist_cols.append(col)
out.loc[m, "거리_도심최근접_km"] = out.loc[m, dist_cols].min(axis=1).round(3)

out.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"● 출력: {OUT.relative_to(ROOT)}  ({len(out):,}행, 좌표보유 {m.sum():,})")
d = out["거리_도심최근접_km"].describe(percentiles=[.1, .5, .9])
print(f"● 최근접 도심 거리(km): min {d['min']:.1f} | p10 {d['10%']:.1f} | "
      f"중앙 {d['50%']:.1f} | p90 {d['90%']:.1f} | max {d['max']:.1f}")
print("\n가까운 정류장 3 / 먼 정류장 3:")
sub = out.loc[m].sort_values("거리_도심최근접_km")
for _, r in pd.concat([sub.head(3), sub.tail(3)]).iterrows():
    print(f"   {r['ARS']} {str(r['자치구']):<5} {str(r['정류장이름'])[:20]:<20} "
          f"도심 {r['거리_도심최근접_km']:.1f}km")
