"""
피처 빌드 #2: 개별공시지가 (우선순위 2). 출처: V-World 데이터 API.
좌표 → LP_PA_CBND_BUBUN(연속지적도) point 질의 → 속성 jiga(개별공시지가, 원/㎡) 등.

사용:
  uv run python scripts/build_jiga_feature.py 30   # 샘플 30곳(자치구 분산) 게이트
  uv run python scripts/build_jiga_feature.py       # 전체 2,553곳

주의: 중앙차로 정류장은 좌표가 도로 위 → 도로필지/NOT_FOUND 가능. 샘플로 커버리지 확인 후 결정.
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KEY = os.environ["V_WORLD_DEVELOPER_KEY"]
DOMAIN = "bus.sings.dev"
COORDS = ROOT / "data/seoul/features/정류장_좌표.csv"
OUT = ROOT / "data/seoul/features/공시지가.csv"
URL = "https://api.vworld.kr/req/data"


def query_parcel(session, lon, lat):
    """좌표가 속한 필지 속성 반환. (jiga, pnu, jibun, addr, gosi_year) 또는 None들."""
    try:
        r = session.get(URL, params={
            "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
            "key": KEY, "domain": DOMAIN,
            "geomFilter": f"POINT({lon} {lat})", "crs": "EPSG:4326",
            "geometry": "false", "size": "5", "format": "json",
        }, headers={"Referer": f"https://{DOMAIN}"}, timeout=20)
        resp = r.json().get("response", {})
        if resp.get("status") == "OK":
            feats = resp.get("result", {}).get("featureCollection", {}).get("features", [])
            if feats:
                p = feats[0]["properties"]
                jiga = p.get("jiga")
                jiga = float(jiga) if jiga not in (None, "", "0") else (0.0 if jiga == "0" else None)
                return jiga, p.get("pnu"), p.get("jibun"), p.get("addr"), p.get("gosi_year"), resp.get("status")
        return None, None, None, None, None, resp.get("status")
    except Exception as e:
        return None, None, None, None, None, f"ERR:{type(e).__name__}"


def main():
    n_sample = int(sys.argv[1]) if len(sys.argv) > 1 else None
    df = pd.read_csv(COORDS, dtype={"ARS": str})
    df = df[df["경도"].notna()].copy()
    if n_sample:
        step = max(1, len(df) // n_sample)
        df = df.iloc[::step].head(n_sample).copy()
        print(f"● 샘플 모드: {len(df)}곳(자치구 분산)")
    else:
        print(f"● 전체 모드: {len(df):,}곳")

    s = requests.Session()
    rows = []
    t0 = time.time()
    for i, (_, r) in enumerate(df.iterrows(), 1):
        jiga, pnu, jibun, addr, gy, st = query_parcel(s, float(r["경도"]), float(r["위도"]))
        rows.append({"ARS": r["ARS"], "자치구": r["자치구"], "정류장이름": r["정류장이름"],
                     "공시지가_원per㎡": jiga, "PNU": pnu, "지번": jibun,
                     "공시지가_주소": addr, "공시연도": gy, "_status": st})
        if i % 100 == 0 or i == len(df):
            print(f"   {i}/{len(df)}  ({time.time()-t0:.0f}s)")
        time.sleep(0.08)  # 예의상 스로틀

    out = pd.DataFrame(rows)
    found = out["PNU"].notna().sum()
    jiga_ok = out["공시지가_원per㎡"].notna() & (out["공시지가_원per㎡"] > 0)
    print(f"\n● 필지 매칭: {found}/{len(out)} ({found/len(out):.1%})")
    print(f"● 공시지가>0: {jiga_ok.sum()}/{len(out)} ({jiga_ok.mean():.1%})")
    print(f"● status 분포: {out['_status'].value_counts().to_dict()}")
    if jiga_ok.sum():
        d = out.loc[jiga_ok, "공시지가_원per㎡"].describe(percentiles=[.1, .5, .9])
        print(f"● 공시지가(원/㎡): min {d['min']:,.0f} | p10 {d['10%']:,.0f} | "
              f"중앙 {d['50%']:,.0f} | p90 {d['90%']:,.0f} | max {d['max']:,.0f}")
    print("\n샘플 일부:")
    for _, r in out.head(12).iterrows():
        v = f"{r['공시지가_원per㎡']:,.0f}" if pd.notna(r['공시지가_원per㎡']) else "─"
        print(f"   {r['ARS']} {str(r['자치구']):<5} {str(r['지번'] or ''):<10} {v:>14} 원/㎡  [{r['_status']}]")

    if not n_sample:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        out.drop(columns="_status").to_csv(OUT, index=False, encoding="utf-8-sig")
        print(f"\n● 저장: {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
