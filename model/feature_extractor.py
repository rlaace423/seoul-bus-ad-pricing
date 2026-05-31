"""임의 좌표(위도·경도) → 모델 32피처 재계산기.

빌드 스크립트(build_centrality/poi/subway/road_feature.py)의 계산을 그대로 재현해
신규 좌표에서도 동일 스케일의 피처를 만든다. 좌표산출 불가한 버스 승하차·경유노선수·
공시지가는 '최근접 학습정류장' 값으로 대체(공간 NN).

소스: data/seoul/raw/소상공인_상가_서울_*.csv, raw/osm_seoul_drive.graphml,
      features/지하철_역마스터.csv, 모델테이블.csv(NN 대체용 학습정류장).
무거운 로딩은 __init__ 1회. transform(lats, lons) → DataFrame[ALL_FEATURES].
"""
from __future__ import annotations
from pathlib import Path
import glob
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]

# build_model_table / model_utils 와 동일한 피처 순서 (원시 좌표 제외, 결측 플래그 포함)
ALL_FEATURES = [
    '승하차_일평균', '경유노선수', 'flag_버스결측',
    '공시지가_원per㎡', 'flag_공시지가결측',
    'POI_total_100m', 'POI_total_300m', 'POI_음식_300m', 'POI_소매_300m',
    'POI_과학·기술_300m', 'POI_수리·개인_300m', 'POI_교육_300m', 'POI_부동산_300m',
    'POI_시설관리·임대_300m', 'POI_예술·스포츠_300m', 'POI_보건의료_300m', 'POI_숙박_300m',
    'POI_total_500m',
    '거리_시청_km', '거리_강남_km', '거리_여의도_km', '거리_도심최근접_km',
    '최근접지하철_거리_m', '최근접역_승하차_일평균', 'flag_역승하차결측',
    '교차로수_300m', '가로망연장_300m', '간선도로연장_300m',
    '교차로수_500m', '가로망연장_500m', '간선도로연장_500m', '간선도로거리_m',
]

# 3도심 (build_centrality_feature 와 동일) — (위도, 경도)
CENTERS = {'시청': (37.5663, 126.9779), '강남': (37.4979, 127.0276), '여의도': (37.5219, 126.9245)}
# POI/지하철 등거리 투영 기준 (build_poi/subway 와 동일)
LAT0, LON0 = 37.55, 126.98
POI_RADII = [100, 300, 500]
POI_CATS = ['음식', '소매', '과학·기술', '수리·개인', '교육', '부동산',
            '시설관리·임대', '예술·스포츠', '보건의료', '숙박']
# 도로망 (build_road_feature 와 동일)
ROAD_RADII = [300, 500]
SAMPLE_M = 20
ARTERIAL = {'motorway', 'trunk', 'primary', 'secondary',
            'motorway_link', 'trunk_link', 'primary_link', 'secondary_link'}


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0088
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dphi = np.radians(lat2 - lat1)
    dlmb = np.radians(lon2 - lon1)
    a = np.sin(dphi / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dlmb / 2) ** 2
    return 2 * R * np.arcsin(np.sqrt(a))


def _to_xy(lon, lat):
    x = (np.asarray(lon, float) - LON0) * 111320.0 * np.cos(np.radians(LAT0))
    y = (np.asarray(lat, float) - LAT0) * 110540.0
    return np.c_[x, y]


def _is_arterial(hw):
    if isinstance(hw, str):
        return hw in ARTERIAL
    if isinstance(hw, (list, tuple, np.ndarray)):
        return any(h in ARTERIAL for h in hw)
    return False


class FeatureExtractor:
    def __init__(self, root: Path = ROOT, verbose: bool = True):
        self.root = Path(root)
        self.v = verbose
        self._load_poi()
        self._load_subway()
        self._load_road()
        self._load_nn_impute()
        if self.v:
            print('● FeatureExtractor 준비 완료')

    def _log(self, *a):
        if self.v:
            print(*a)

    # ---- 상권 POI (소상공인 상가) ----
    def _load_poi(self):
        files = sorted(glob.glob(str(self.root / 'data/seoul/raw/소상공인_상가_서울_*.csv')))
        st = pd.read_csv(files[0], usecols=['경도', '위도', '상권업종대분류명'])
        st['경도'] = pd.to_numeric(st['경도'], errors='coerce')
        st['위도'] = pd.to_numeric(st['위도'], errors='coerce')
        st = st.dropna(subset=['경도', '위도', '상권업종대분류명'])
        st = st[st['경도'].between(126.7, 127.2) & st['위도'].between(37.4, 37.7)]
        self.poi_tree = cKDTree(_to_xy(st['경도'].to_numpy(), st['위도'].to_numpy()))
        self.poi_cat_tree = {}
        for c in POI_CATS:
            sub = st[st['상권업종대분류명'] == c]
            if len(sub) == 0:
                raise ValueError(f'POI 카테고리 미발견: {c}')
            self.poi_cat_tree[c] = cKDTree(_to_xy(sub['경도'].to_numpy(), sub['위도'].to_numpy()))
        self._log(f'● POI(주변 상가 점포): {self.poi_tree.n:,}개 로드 · 업종 {len(POI_CATS)}종')

    # ---- 지하철 역마스터 ----
    def _load_subway(self):
        sub = pd.read_csv(self.root / 'data/seoul/features/지하철_역마스터.csv')
        self.sub_tree = cKDTree(_to_xy(sub['경도'].to_numpy(), sub['위도'].to_numpy()))
        self.sub_ride = sub['역_승하차_일평균'].to_numpy()
        self._log(f'● 지하철 역: {self.sub_tree.n}개 로드 · 그중 {np.isfinite(self.sub_ride).sum()}개에 일평균 승하차(명/일) 매칭')

    # ---- 도로망 (OSM) ----
    def _load_road(self):
        import osmnx as ox
        import shapely
        from pyproj import Transformer
        G = ox.load_graphml(self.root / 'data/seoul/raw/osm_seoul_drive.graphml')
        G = ox.project_graph(G, to_crs='EPSG:5179')
        G = ox.convert.to_undirected(G)
        nodes, edges = ox.graph_to_gdfs(G)
        if 'street_count' in nodes.columns:
            sc = pd.to_numeric(nodes['street_count'], errors='coerce').fillna(0).to_numpy()
        else:
            import networkx as nx
            deg = dict(nx.Graph(G).degree())
            sc = np.array([deg.get(i, 0) for i in nodes.index])
        inter = nodes[sc >= 3]
        self.inter_tree = cKDTree(np.c_[inter.geometry.x.to_numpy(), inter.geometry.y.to_numpy()])
        geoms, hws = edges.geometry.to_numpy(), edges['highway'].to_numpy()
        Ls = shapely.length(geoms)
        xs, ys, ws, arts = [], [], [], []
        for geom, L, hw in zip(geoms, Ls, hws):
            if geom is None or L <= 0:
                continue
            n = max(int(round(L / SAMPLE_M)), 1)
            ds = (np.arange(n) + 0.5) * (L / n)
            pts = shapely.line_interpolate_point(geom, ds)
            xs.append(shapely.get_x(pts)); ys.append(shapely.get_y(pts))
            ws.append(np.full(n, L / n)); arts.append(np.full(n, _is_arterial(hw)))
        X, Y = np.concatenate(xs), np.concatenate(ys)
        self.W = np.concatenate(ws)
        self.A = np.concatenate(arts).astype(bool)
        self.edge_tree = cKDTree(np.c_[X, Y])
        self.art_tree = cKDTree(np.c_[X[self.A], Y[self.A]])
        self._tf = Transformer.from_crs('EPSG:4326', 'EPSG:5179', always_xy=True)
        self._log(f'● 도로망(OSM): 교차로 {self.inter_tree.n:,}개 · 도로 샘플점 {self.edge_tree.n:,}개')

    # ---- 좌표산출 불가 피처(승하차·노선수·공시지가) NN 대체 ----
    def _load_nn_impute(self):
        df = pd.read_csv(self.root / 'data/seoul/모델테이블.csv', dtype={'ARS': str})
        df = df.dropna(subset=['경도', '위도'])
        bd = df.dropna(subset=['승하차_일평균'])
        self.board_tree = cKDTree(_to_xy(bd['경도'].to_numpy(), bd['위도'].to_numpy()))
        self.board_val = bd[['승하차_일평균', '경유노선수']].to_numpy()
        jg = df.dropna(subset=['공시지가_원per㎡'])
        self.jiga_tree = cKDTree(_to_xy(jg['경도'].to_numpy(), jg['위도'].to_numpy()))
        self.jiga_val = jg['공시지가_원per㎡'].to_numpy()
        self._log(f'● NN대체(빈 좌표는 최근접 학습정류장 값 차용): 승하차 보유 {self.board_tree.n}곳 · 공시지가 보유 {self.jiga_tree.n}곳')

    # ---- 메인 ----
    def transform(self, lats, lons) -> pd.DataFrame:
        lats = np.asarray(lats, float); lons = np.asarray(lons, float)
        n = len(lats)
        out = pd.DataFrame(index=range(n))

        # 중심지거리
        for name, (clat, clon) in CENTERS.items():
            out[f'거리_{name}_km'] = np.round(_haversine_km(lats, lons, clat, clon), 3)
        out['거리_도심최근접_km'] = out[[f'거리_{k}_km' for k in CENTERS]].min(axis=1).round(3)

        # POI
        xy = _to_xy(lons, lats)
        for r in POI_RADII:
            out[f'POI_total_{r}m'] = [len(ix) for ix in self.poi_tree.query_ball_point(xy, r)]
        for c in POI_CATS:
            cnt = self.poi_cat_tree[c].query_ball_point(xy, 300)
            out[f'POI_{c}_300m'] = [len(ix) for ix in cnt]

        # 지하철
        dist, idx = self.sub_tree.query(xy, k=1)
        out['최근접지하철_거리_m'] = np.round(dist, 1)
        ride = self.sub_ride[idx]
        out['최근접역_승하차_일평균'] = np.round(ride, 0)
        out['flag_역승하차결측'] = (~np.isfinite(ride)).astype(int)

        # 도로망 (EPSG:5179)
        sx, sy = self._tf.transform(lons, lats)
        pxy = np.c_[sx, sy]
        for r in ROAD_RADII:
            iidx = self.inter_tree.query_ball_point(pxy, r)
            out[f'교차로수_{r}m'] = [len(ix) for ix in iidx]
            eidx = self.edge_tree.query_ball_point(pxy, r)
            out[f'가로망연장_{r}m'] = [round(float(self.W[ix].sum()), 0) for ix in eidx]
            out[f'간선도로연장_{r}m'] = [round(float(self.W[ix][self.A[ix]].sum()), 0) for ix in eidx]
        dart, _ = self.art_tree.query(pxy, k=1)
        out['간선도로거리_m'] = np.round(dart, 1)

        # NN 대체: 승하차·경유노선수·공시지가 (flag=0, 항상 값 공급)
        _, bidx = self.board_tree.query(xy, k=1)
        out['승하차_일평균'] = self.board_val[bidx, 0]
        out['경유노선수'] = self.board_val[bidx, 1]
        out['flag_버스결측'] = 0
        _, jidx = self.jiga_tree.query(xy, k=1)
        out['공시지가_원per㎡'] = self.jiga_val[jidx]
        out['flag_공시지가결측'] = 0

        return out[ALL_FEATURES]
