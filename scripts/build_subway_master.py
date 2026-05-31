"""산출물 준비: 지하철 역마스터(좌표+승하차) 1회 캐시 → features/지하철_역마스터.csv.
build_subway_feature.py와 동일 소스(서울 열린데이터광장). 격자/예측함수가 칸마다
최근접역 거리·승하차를 계산할 때 재사용(매번 API fetch 회피).
실행: uv run python scripts/build_subway_master.py
"""
import os, sys, time
from collections import defaultdict
from pathlib import Path
import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KEY = os.environ.get("SEOUL_OPENAPI_KEY")
OUT = ROOT / "data/seoul/features/지하철_역마스터.csv"
BASE = "http://openapi.seoul.go.kr:8088"


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
    onoff, ndays, ok = defaultdict(float), defaultdict(int), 0
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
    print("✗ SEOUL_OPENAPI_KEY 없음"); sys.exit(2)

st = fetch_stations()
dates = [d.strftime("%Y%m%d") for d in pd.date_range("2026-03-01", "2026-04-30")]
ride = fetch_ridership(dates)
st["_nm"] = st["BLDN_NM"].map(norm_name)
st["역_승하차_일평균"] = st["_nm"].map(ride).round(0)
out = st[["BLDN_NM", "ROUTE", "LAT", "LOT", "역_승하차_일평균"]].rename(
    columns={"BLDN_NM": "역명", "LAT": "위도", "LOT": "경도"})
OUT.parent.mkdir(parents=True, exist_ok=True)
out.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"● 저장: {OUT.relative_to(ROOT)} ({len(out)}역, 승하차 매칭 {out['역_승하차_일평균'].notna().sum()})")
