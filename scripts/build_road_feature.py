"""
피처 빌드 #6: 도로망 (우선순위 4·6). 출처: OpenStreetMap (osmnx 2.x, 1회 fetch).
서울 정류장 bbox+버퍼의 drive 네트워크를 한 번 받아(키 불필요) 로컬 계산.
정류장 좌표마다 반경(300/500m) 내:
  - 교차로수_{r}m    : 교차로(차로 3갈래+ 노드) 수 — 가로망 조밀도/보행 활성 프록시
  - 가로망연장_{r}m  : 도로 총연장(m) — 가로망 밀도
  - 간선도로연장_{r}m: 간선도로(motorway/trunk/primary/secondary) 연장(m) — 대로 노출
  - 간선도로거리_m   : 최근접 간선도로까지 거리(m) — 대로 접근성 (반경 무관)
계산: 엣지를 ~20m 점으로 샘플(가중치=구간길이) → 기존 POI와 동일한 KDTree 반경질의.
      미터 계산은 EPSG:5179(국가표준) 투영. fetch는 raw/osm_seoul_drive.graphml에 캐시.
실행: uv run python scripts/build_road_feature.py
"""
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from pyproj import Transformer
from shapely.geometry import box
import shapely
import osmnx as ox

ROOT = Path(__file__).resolve().parents[1]
COORDS = ROOT / "data/seoul/features/정류장_좌표.csv"
OUT = ROOT / "data/seoul/features/도로망.csv"
CACHE = ROOT / "data/seoul/raw/osm_seoul_drive.graphml"
RADII = [300, 500]
SAMPLE_M = 20            # 엣지 샘플 간격(m) — 길이 근사 오차 <2%
BUF_DEG = 0.02          # 정류장 bbox 버퍼(~2km): 경계 정류장 반경원 truncation 방지
ARTERIAL = {"motorway", "trunk", "primary", "secondary",
            "motorway_link", "trunk_link", "primary_link", "secondary_link"}


def is_arterial(hw):
    if isinstance(hw, str):
        return hw in ARTERIAL
    if isinstance(hw, (list, tuple, np.ndarray)):
        return any(h in ARTERIAL for h in hw)
    return False


# ---- 정류장 좌표 ----
sp = pd.read_csv(COORDS, dtype={"ARS": str})
m = sp["경도"].notna() & sp["위도"].notna()
lon = sp.loc[m, "경도"].astype(float).to_numpy()
lat = sp.loc[m, "위도"].astype(float).to_numpy()
print(f"● 정류장: {len(sp):,} (좌표보유 {m.sum():,} / 결측 {(~m).sum()})")

# ---- OSM drive 네트워크 1회 fetch (캐시 재사용) ----
if CACHE.exists():
    print(f"● OSM 캐시 로드: {CACHE.relative_to(ROOT)}")
    G = ox.load_graphml(CACHE)
else:
    poly = box(lon.min() - BUF_DEG, lat.min() - BUF_DEG, lon.max() + BUF_DEG, lat.max() + BUF_DEG)
    print(f"● OSM fetch(drive) — Overpass 호출 (bbox {poly.bounds})…")
    G = ox.graph_from_polygon(poly, network_type="drive")
    ox.save_graphml(G, CACHE)
    print(f"● 캐시 저장: {CACHE.relative_to(ROOT)}")

# ---- 투영(EPSG:5179) + 무방향(양방향 중복 길이 제거) ----
G = ox.project_graph(G, to_crs="EPSG:5179")
G = ox.convert.to_undirected(G)
nodes, edges = ox.graph_to_gdfs(G)
print(f"● 그래프: 노드 {len(nodes):,} · 엣지(무방향) {len(edges):,}")

# ---- 교차로(차로 3갈래+) ----
if "street_count" in nodes.columns:
    sc = pd.to_numeric(nodes["street_count"], errors="coerce").fillna(0).to_numpy()
else:
    import networkx as nx
    deg = dict(nx.Graph(G).degree())
    sc = np.array([deg.get(i, 0) for i in nodes.index])
inter = nodes[sc >= 3]
inter_xy = np.c_[inter.geometry.x.to_numpy(), inter.geometry.y.to_numpy()]
print(f"● 교차로(≥3갈래): {len(inter):,} / 전체노드 {len(nodes):,}")

# ---- 엣지 → 점 샘플(가중치=구간길이, 간선여부) ----
geoms = edges.geometry.to_numpy()
hws = edges["highway"].to_numpy()
Ls = shapely.length(geoms)
xs, ys, ws, arts = [], [], [], []
for geom, L, hw in zip(geoms, Ls, hws):
    if geom is None or L <= 0:
        continue
    n = max(int(round(L / SAMPLE_M)), 1)
    ds = (np.arange(n) + 0.5) * (L / n)
    pts = shapely.line_interpolate_point(geom, ds)
    xs.append(shapely.get_x(pts))
    ys.append(shapely.get_y(pts))
    ws.append(np.full(n, L / n))
    arts.append(np.full(n, is_arterial(hw)))
X, Y = np.concatenate(xs), np.concatenate(ys)
W = np.concatenate(ws)
A = np.concatenate(arts).astype(bool)
print(f"● 도로 샘플점: {len(X):,}  (총연장 {W.sum()/1000:,.0f}km · 간선 {W[A].sum()/1000:,.0f}km)")

# ---- KDTree ----
edge_tree = cKDTree(np.c_[X, Y])
inter_tree = cKDTree(inter_xy)
art_tree = cKDTree(np.c_[X[A], Y[A]])

# ---- 정류장 투영(EPSG:5179) ----
tf = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
sx, sy = tf.transform(lon, lat)
stop_xy = np.c_[sx, sy]

out = sp[["ARS", "자치구", "정류장이름"]].copy()
for r in RADII:
    iidx = inter_tree.query_ball_point(stop_xy, r)
    out.loc[m, f"교차로수_{r}m"] = [len(ix) for ix in iidx]
    eidx = edge_tree.query_ball_point(stop_xy, r)
    out.loc[m, f"가로망연장_{r}m"] = [float(W[ix].sum()) for ix in eidx]
    out.loc[m, f"간선도로연장_{r}m"] = [float(W[ix][A[ix]].sum()) for ix in eidx]
dist_art, _ = art_tree.query(stop_xy, k=1)
out.loc[m, "간선도로거리_m"] = dist_art

# ---- 정리(정수/반올림) + 컬럼 순서 ----
for r in RADII:
    out[f"교차로수_{r}m"] = out[f"교차로수_{r}m"].astype("Int64")
    out[f"가로망연장_{r}m"] = out[f"가로망연장_{r}m"].round(0)
    out[f"간선도로연장_{r}m"] = out[f"간선도로연장_{r}m"].round(0)
out["간선도로거리_m"] = out["간선도로거리_m"].round(1)
cols = ["ARS", "자치구", "정류장이름"]
for r in RADII:
    cols += [f"교차로수_{r}m", f"가로망연장_{r}m", f"간선도로연장_{r}m"]
cols += ["간선도로거리_m"]
out = out[cols]
out.to_csv(OUT, index=False, encoding="utf-8-sig")

# ---- 리포트 ----
feat = [c for c in cols if c not in ("ARS", "자치구", "정류장이름")]
print(f"\n● 출력: {OUT.relative_to(ROOT)}  ({len(out):,}행, {len(feat)}피처)")
for c in feat:
    s = pd.to_numeric(out[c], errors="coerce").dropna()
    na = out[c].isna().sum()
    print(f"   {c:<16} 중앙 {s.median():>8,.0f}  (p10 {s.quantile(.1):>7,.0f} ~ p90 {s.quantile(.9):>8,.0f}, max {s.max():>8,.0f})  결측 {na}")
print("\n상위 5(교차로수_300m):")
top = out.dropna(subset=["교차로수_300m"]).nlargest(5, "교차로수_300m")
for _, r in top.iterrows():
    print(f"   {r['ARS']} {str(r['자치구']):<5} {str(r['정류장이름'])[:16]:<16} "
          f"교차로 {r['교차로수_300m']:>2} · 간선 {r['간선도로연장_300m']:>5.0f}m · 간선거리 {r['간선도로거리_m']:>5.0f}m")
