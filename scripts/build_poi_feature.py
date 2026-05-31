"""
피처 빌드 #4: 상권 POI (우선순위 3). 출처: 소상공인 상가정보 서울. API 호출 0 — 로컬 KDTree.
정류장 좌표마다 반경 내 점포 수:
  - POI_total_{100,300,500}m : 전체 점포 밀도(거리 그래디언트)
  - POI_{대분류}_300m         : 300m(도보권) 업종 구성
거리 계산: 등거리 투영(서울 중심)으로 m 변환 후 KDTree (도시 스케일 오차 <0.1%).
실행: uv run python scripts/build_poi_feature.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
STORES = ROOT / "data/seoul/raw/소상공인_상가_서울_202603.csv"
COORDS = ROOT / "data/seoul/features/정류장_좌표.csv"
OUT = ROOT / "data/seoul/features/POI_상권.csv"
RADII = [100, 300, 500]
CAT_RADIUS = 300          # 업종 구성은 도보권 300m 기준
LAT0, LON0 = 37.55, 126.98


def to_xy(lon, lat):
    x = (np.asarray(lon) - LON0) * 111320.0 * np.cos(np.radians(LAT0))
    y = (np.asarray(lat) - LAT0) * 110540.0
    return np.c_[x, y]


# ---- 상가 로드 ----
st = pd.read_csv(STORES, usecols=["경도", "위도", "상권업종대분류명", "시군구명"])
n0 = len(st)
st["경도"] = pd.to_numeric(st["경도"], errors="coerce")
st["위도"] = pd.to_numeric(st["위도"], errors="coerce")
st = st.dropna(subset=["경도", "위도", "상권업종대분류명"])
st = st[st["경도"].between(126.7, 127.2) & st["위도"].between(37.4, 37.7)]
print(f"● 상가 로드: {n0:,} → 유효좌표 {len(st):,}")
print("● 업종 대분류 구성:")
for c, n in st["상권업종대분류명"].value_counts().items():
    print(f"     {c:<14} {n:>7,}")

cats = list(st["상권업종대분류명"].value_counts().index)  # 빈도순
code = {c: i for i, c in enumerate(cats)}
store_cat = st["상권업종대분류명"].map(code).to_numpy()
tree = cKDTree(to_xy(st["경도"].to_numpy(), st["위도"].to_numpy()))

# ---- 정류장 ----
sp = pd.read_csv(COORDS, dtype={"ARS": str})
m = sp["경도"].notna()
stop_xy = to_xy(sp.loc[m, "경도"].astype(float).to_numpy(), sp.loc[m, "위도"].astype(float).to_numpy())
out = sp[["ARS", "자치구", "정류장이름"]].copy()
K = len(cats)

for r in RADII:
    idx = tree.query_ball_point(stop_xy, r)
    out.loc[m, f"POI_total_{r}m"] = [len(ix) for ix in idx]
    if r == CAT_RADIUS:
        catcnt = np.zeros((len(idx), K), int)
        for i, ix in enumerate(idx):
            if ix:
                catcnt[i] = np.bincount(store_cat[ix], minlength=K)
        for c, i in code.items():
            out.loc[m, f"POI_{c}_{r}m"] = catcnt[:, i]

int_cols = [c for c in out.columns if c.startswith("POI_")]
out[int_cols] = out[int_cols].astype("Int64")  # 결측 좌표 2곳은 <NA>
out.to_csv(OUT, index=False, encoding="utf-8-sig")

# ---- 리포트 ----
print(f"\n● 출력: {OUT.relative_to(ROOT)}  ({len(out):,}행, {len(int_cols)}개 POI 컬럼)")
for r in RADII:
    s = out[f"POI_total_{r}m"].dropna()
    print(f"   total_{r}m: 중앙 {s.median():.0f} (p10 {s.quantile(.1):.0f} ~ p90 {s.quantile(.9):.0f}, max {s.max()})")
print("\n상위 5개(300m 총 점포):")
top = out.dropna(subset=["POI_total_300m"]).nlargest(5, "POI_total_300m")
for _, r in top.iterrows():
    print(f"   {r['ARS']} {str(r['자치구']):<5} {str(r['정류장이름'])[:20]:<20} 300m {r['POI_total_300m']}개")
