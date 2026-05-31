"""
키 게이트: 카카오/V-World 키가 실제로 작동하는지 정류장 좌표 1곳으로 스모크 테스트.
대량 호출(POI 2,553×N, 공시지가 2,553) 전에 키+엔드포인트+권한(활용API)+도메인 검증.
키 값은 절대 출력하지 않는다.
실행: uv run python scripts/smoke_keys.py
"""
import os
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
KAKAO = os.environ.get("KAKAO_DEVELOPER_PLATFORM_KEY")
VWORLD = os.environ.get("V_WORLD_DEVELOPER_KEY")
DOMAIN = "bus.sings.dev"  # V-World 서비스URL로 등록한 값

print("● 키 로드:")
print(f"   KAKAO  : {'OK' if KAKAO else '없음'} (len={len(KAKAO) if KAKAO else 0})")
print(f"   VWORLD : {'OK' if VWORLD else '없음'} (len={len(VWORLD) if VWORLD else 0})")

# ---- 테스트용 실제 좌표 1곳(을지로입구.로얄호텔 02156, 없으면 첫 행) ----
master = pd.read_excel(ROOT / "data/seoul/서울시버스정류소위치정보(20260506).xlsx", dtype=str)
ars_col = next(c for c in master.columns if "ARS" in c.upper())
x_col = next(c for c in master.columns if "X" in c.upper() and ("좌표" in c or "경도" in c or c.upper() == "X"))
y_col = next(c for c in master.columns if "Y" in c.upper() and ("좌표" in c or "위도" in c or c.upper() == "Y"))
row = master[master[ars_col].astype(str).str.zfill(5) == "02156"]
row = row.iloc[0] if len(row) else master.iloc[0]
lon, lat = float(row[x_col]), float(row[y_col])
name = row[next(c for c in master.columns if "명" in c)]
print(f"\n● 테스트 좌표: ARS {row[ars_col]} {name}  (lon={lon}, lat={lat})\n")

# ---- 1) 카카오 로컬: 반경 300m 편의점(CS2) 개수 ----
print("── 카카오 로컬 API (POI) ──")
try:
    r = requests.get(
        "https://dapi.kakao.com/v2/local/search/category.json",
        headers={"Authorization": f"KakaoAK {KAKAO}"},
        params={"category_group_code": "CS2", "x": lon, "y": lat, "radius": 300, "size": 1},
        timeout=15,
    )
    print(f"   HTTP {r.status_code}")
    if r.status_code == 200:
        total = r.json().get("meta", {}).get("total_count")
        print(f"   ✓ 작동. 반경300m 편의점(CS2) total_count = {total}")
    else:
        print(f"   ✗ 실패: {r.text[:300]}")
except Exception as e:
    print(f"   ✗ 예외: {e}")

# ---- 2) V-World 데이터 API: 좌표가 속한 필지(PNU/지번) 조회 ----
print("\n── V-World 데이터 API (필지/공시지가 경로) ──")
try:
    r = requests.get(
        "https://api.vworld.kr/req/data",
        params={
            "service": "data", "request": "GetFeature", "data": "LP_PA_CBND_BUBUN",
            "key": VWORLD, "domain": DOMAIN,
            "geomFilter": f"POINT({lon} {lat})", "crs": "EPSG:4326",
            "geometry": "false", "size": "5", "format": "json",
        },
        headers={"Referer": f"https://{DOMAIN}"},
        timeout=20,
    )
    print(f"   HTTP {r.status_code}")
    try:
        resp = r.json().get("response", {})
        status = resp.get("status")
        print(f"   status = {status}")
        if status == "OK":
            feats = resp.get("result", {}).get("featureCollection", {}).get("features", [])
            print(f"   ✓ 작동. 필지 {len(feats)}개 반환")
            if feats:
                p = feats[0].get("properties", {})
                print(f"     PNU={p.get('pnu')}  지번={p.get('jibun')}  주소={p.get('addr') or p.get('ag_geom')}")
                print(f"     속성 키: {list(p.keys())}")
        else:
            print(f"   ✗ status≠OK: {str(resp)[:400]}")
    except Exception:
        print(f"   원문: {r.text[:400]}")
except Exception as e:
    print(f"   ✗ 예외: {e}")
