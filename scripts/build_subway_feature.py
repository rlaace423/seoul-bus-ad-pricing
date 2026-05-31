"""
피처 빌드 #5: 지하철 (우선순위 1-C). 출처: 서울 열린데이터광장 API (키 .env SEOUL_OPENAPI_KEY).
  - subwayStationMaster : 역 783개(전 노선) 좌표 → 정류장별 최근접 역 거리(m)/역명/호선
  - CardSubwayStatsNew  : 역별 승하차(3~4월) → 최근접 역의 일평균 승하차(이용객 규모)
조인(좌표역명 ↔ 승하차역명)은 괄호·공백 제거 정규화로 매칭.
실행: uv run python scripts/build_subway_feature.py
"""
import os
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from dotenv import load_dotenv
from scipy.spatial import cKDTree

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KEY = os.environ.get("SEOUL_OPENAPI_KEY")
COORDS = ROOT / "data/seoul/features/정류장_좌표.csv"
OUT = ROOT / "data/seoul/features/지하철근접.csv"
LAT0, LON0 = 37.55, 126.98
BASE = "http://openapi.seoul.go.kr:8088"


def to_xy(lon, lat):
    x = (np.asarray(lon, float) - LON0) * 111320.0 * np.cos(np.radians(LAT0))
    y = (np.asarray(lat, float) - LAT0) * 110540.0
    return np.c_[x, y]


def norm_name(s):
    return str(s).split("(")[0].strip().replace(" ", "")


def fetch_stations():
    data = requests.get(f"{BASE}/{KEY}/json/subwayStationMaster/1/1000/", timeout=30).json()["subwayStationMaster"]
    if data["RESULT"]["CODE"] != "INFO-000":
        raise RuntimeError(data["RESULT"])
    df = pd.DataFrame(data["row"])
    df["LAT"] = pd.to_numeric(df["LAT"], errors="coerce")
    df["LOT"] = pd.to_numeric(df["LOT"], errors="coerce")
    return df.dropna(subset=["LAT", "LOT"]).reset_index(drop=True)


def fetch_ridership(dates):
    """역명(정규화) → 일평균 승하차(승차+하차, 호선 합산·일 평균)."""
    onoff = defaultdict(float)
    ndays = defaultdict(int)
    ok = 0
    s = requests.Session()
    for d in dates:
        try:
            r = s.get(f"{BASE}/{KEY}/json/CardSubwayStatsNew/1/1000/{d}/", timeout=25).json()
            info = r.get("CardSubwayStatsNew", {})
            if info.get("RESULT", {}).get("CODE") != "INFO-000":
                continue
            seen = set()
            for row in info["row"]:
                nm = norm_name(row["SBWY_STNS_NM"])
                onoff[nm] += float(row["GTON_TNOPE"]) + float(row["GTOFF_TNOPE"])
                seen.add(nm)
            for nm in seen:
                ndays[nm] += 1
            ok += 1
        except Exception:
            pass
        time.sleep(0.05)
    print(f"● 승하차 수집: {ok}/{len(dates)}일 성공, 역명 {len(onoff)}개")
    return {nm: onoff[nm] / ndays[nm] for nm in onoff if ndays[nm]}


if not KEY:
    print("✗ SEOUL_OPENAPI_KEY 가 .env 에 없습니다.")
    sys.exit(2)

# 1) 역 좌표 + 승하차
st = fetch_stations()
print(f"● 역 좌표: {len(st)}행 (고유 역명 {st['BLDN_NM'].nunique()}개, 호선 {st['ROUTE'].nunique()})")
dates = [d.strftime("%Y%m%d") for d in pd.date_range("2026-03-01", "2026-04-30")]
ride = fetch_ridership(dates)
st["_nm"] = st["BLDN_NM"].map(norm_name)
st["역_승하차_일평균"] = st["_nm"].map(ride)
matched = st["역_승하차_일평균"].notna().sum()
print(f"● 좌표역 ↔ 승하차 매칭: {matched}/{len(st)} (고유역명 {st.loc[st['역_승하차_일평균'].notna(),'_nm'].nunique()})")

# 2) 정류장별 최근접 역
tree = cKDTree(to_xy(st["LOT"].to_numpy(), st["LAT"].to_numpy()))
sp = pd.read_csv(COORDS, dtype={"ARS": str})
m = sp["경도"].notna()
dist, idx = tree.query(to_xy(sp.loc[m, "경도"], sp.loc[m, "위도"]), k=1)

out = sp[["ARS", "자치구", "정류장이름"]].copy()
out.loc[m, "최근접지하철_거리_m"] = np.round(dist, 1)
out.loc[m, "최근접역명"] = st["BLDN_NM"].to_numpy()[idx]
out.loc[m, "최근접역호선"] = st["ROUTE"].to_numpy()[idx]
out.loc[m, "최근접역_승하차_일평균"] = np.round(st["역_승하차_일평균"].to_numpy()[idx], 0)
out.to_csv(OUT, index=False, encoding="utf-8-sig")

d = out["최근접지하철_거리_m"].describe(percentiles=[.1, .5, .9])
print(f"\n● 출력: {OUT.relative_to(ROOT)} ({len(out):,}행)")
print(f"● 최근접 거리(m): min {d['min']:.0f} | 중앙 {d['50%']:.0f} | p90 {d['90%']:.0f} | max {d['max']:.0f}")
rd = out["최근접역_승하차_일평균"].dropna()
print(f"● 최근접역 승하차 일평균(명): 중앙 {rd.median():,.0f} | p90 {rd.quantile(.9):,.0f} | max {rd.max():,.0f}")
print(f"● 승하차 결측(정류장): {out.loc[m,'최근접역_승하차_일평균'].isna().sum()}")
print("\n최근접역 승하차 상위 3:")
for _, r in out.dropna(subset=["최근접역_승하차_일평균"]).nlargest(3, "최근접역_승하차_일평균").iterrows():
    print(f"   {r['ARS']} {str(r['정류장이름'])[:18]:<18} → {r['최근접역명']} {r['최근접역_승하차_일평균']:,.0f}명/일")
