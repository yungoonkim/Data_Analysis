"""
사진 촬영 위치 지도 - 백엔드 (Flask)

picture 폴더의 사진에서 EXIF(촬영 위치·시각·방향·고도·기기)를 읽어 Google 지도에 표시합니다.

  picture/*.jpg ──EXIF──▶ app.py ──JSON──▶ 브라우저(Google 지도 / 키 없으면 OpenStreetMap)
                   └ 썸네일은 cache/ 에 한 번만 만들어 둠 (원본은 건드리지 않음)

실행:  python app.py   →  http://localhost:5091
사진 폴더: 기본 ../picture  (다른 폴더는  PHOTO_DIR=~/Pictures/jeju python app.py)
Google 지도 키: 환경변수 GOOGLE_MAPS_API_KEY (없으면 OpenStreetMap으로 표시)
"""

import hashlib
import json
import math
import os
from datetime import datetime
from pathlib import Path

from flask import Flask, abort, jsonify, send_file, send_from_directory
from PIL import ExifTags, Image, ImageOps

try:  # 아이폰 HEIC 사진도 읽고 싶으면: pip install pillow-heif
    from pillow_heif import register_heif_opener
    register_heif_opener()
    HEIC_OK = True
except ImportError:
    HEIC_OK = False

BASE_DIR = Path(__file__).resolve().parent
PHOTO_DIR = Path(os.environ.get("PHOTO_DIR", BASE_DIR.parent / "picture")).expanduser().resolve()
CACHE_DIR = BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)
PORT = int(os.environ.get("PORT", 5091))

EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp"} | ({".heic", ".heif"} if HEIC_OK else set())
THUMB = 480      # 목록·팝업용 썸네일 긴 변(px)
LARGE = 1800     # 크게 보기용 긴 변(px) — 원본(수 MB)을 그대로 보내지 않는다
GROUP_M = 25     # 이 거리(m) 안의 사진은 지도에서 한 마커로 묶는다

# 비짓제주 앱이 받아 둔 관광지 캐시가 있으면 "근처 관광지"를 보여 준다 (없으면 생략)
VISITJEJU_CACHE = BASE_DIR.parent / "tour_api" / "visitjeju" / "cache" / "kr_c1.json"

GPS_IFD, EXIF_IFD = 0x8825, 0x8769
GPS = {v: k for k, v in ExifTags.GPSTAGS.items()}


# ── EXIF 읽기 ──────────────────────────────────────────────────────────────
def _dms_to_deg(dms, ref):
    """(도, 분, 초) → 십진수 도. 남위(S)·서경(W)은 음수."""
    d, m, s = (float(x) for x in dms)
    deg = d + m / 60 + s / 3600
    return -deg if ref in ("S", "W") else deg


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def read_photo(path: Path):
    info = {"file": path.name, "size_kb": round(path.stat().st_size / 1024)}
    try:
        with Image.open(path) as im:
            exif = im.getexif()
            w, h = im.size
            if exif.get(0x0112) in (5, 6, 7, 8):   # 세로 사진이면 가로·세로를 바꿔 표시
                w, h = h, w
            info.update(width=w, height=h)
            gps = exif.get_ifd(GPS_IFD)
            ex = exif.get_ifd(EXIF_IFD)
    except Exception as e:  # 깨진 파일 등
        info["error"] = f"열 수 없음: {e}"
        return info

    make, model = (exif.get(0x010F) or "").strip(), (exif.get(0x0110) or "").strip()
    info["device"] = model if make and model.startswith(make) or not make else f"{make} {model}"

    taken = ex.get(0x9003) or exif.get(0x0132)   # DateTimeOriginal → 없으면 DateTime
    if taken:
        try:
            dt = datetime.strptime(str(taken).strip(), "%Y:%m:%d %H:%M:%S")
            info["taken"] = dt.strftime("%Y-%m-%d %H:%M:%S")
            info["tz"] = ex.get(0x9011) or ""      # OffsetTimeOriginal (예: +09:00)
        except ValueError:
            pass
    if "taken" not in info:
        info["taken"] = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
        info["taken_guess"] = True                 # EXIF 시각이 없어 파일 수정 시각을 씀

    lat, lng = gps.get(GPS["GPSLatitude"]), gps.get(GPS["GPSLongitude"])
    if lat and lng:
        try:
            info["lat"] = round(_dms_to_deg(lat, gps.get(GPS["GPSLatitudeRef"], "N")), 7)
            info["lng"] = round(_dms_to_deg(lng, gps.get(GPS["GPSLongitudeRef"], "E")), 7)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    alt = _num(gps.get(GPS["GPSAltitude"]))
    if alt is not None:
        below = gps.get(GPS["GPSAltitudeRef"]) in (1, b"\x01")
        info["altitude"] = round(-alt if below else alt, 1)
    direction = _num(gps.get(GPS["GPSImgDirection"]))
    if direction is not None:
        info["direction"] = round(direction % 360, 1)   # 카메라가 향한 방위(0=북, 90=동)
    err = _num(gps.get(GPS.get("GPSHPositioningError", 31)))
    if err is not None:
        info["accuracy_m"] = round(err, 1)
    return info


def scan():
    photos = []
    for p in sorted(PHOTO_DIR.iterdir()) if PHOTO_DIR.exists() else []:
        if p.is_file() and p.suffix.lower() in EXTS and not p.name.startswith("."):
            photos.append(read_photo(p))
    photos.sort(key=lambda r: r.get("taken", ""))
    return photos


# ── 위치 묶기·거리 ─────────────────────────────────────────────────────────
def haversine_m(lat1, lng1, lat2, lng2):
    r = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def group_by_place(photos):
    """GROUP_M 안에 있는 사진을 한 장소로 묶는다 (시간순으로 앞에서부터 붙여 나가는 간단한 방식)."""
    groups = []
    for ph in photos:
        if "lat" not in ph:
            continue
        for g in groups:
            if haversine_m(g["lat"], g["lng"], ph["lat"], ph["lng"]) <= GROUP_M:
                g["files"].append(ph["file"])
                n = len(g["files"])  # 중심을 평균으로 갱신
                g["lat"] += (ph["lat"] - g["lat"]) / n
                g["lng"] += (ph["lng"] - g["lng"]) / n
                break
        else:
            groups.append({"lat": ph["lat"], "lng": ph["lng"], "files": [ph["file"]]})
    return groups


def nearby_attractions(lat, lng, limit=5, within_m=3000):
    if not VISITJEJU_CACHE.exists():
        return []
    try:
        items = json.loads(VISITJEJU_CACHE.read_text(encoding="utf-8"))["items"]
    except (ValueError, KeyError):
        return []
    out = []
    for it in items:
        if it.get("latitude") and it.get("longitude"):
            d = haversine_m(lat, lng, it["latitude"], it["longitude"])
            if d <= within_m:
                out.append({"title": it["title"], "distance_m": round(d), "url": it.get("url", ""),
                            "thumbnail": it.get("thumbnail", ""), "intro": it.get("introduction", "")})
    return sorted(out, key=lambda x: x["distance_m"])[:limit]


# ── 썸네일 ─────────────────────────────────────────────────────────────────
def resized(name, size):
    src = (PHOTO_DIR / name).resolve()
    if src.parent != PHOTO_DIR or not src.is_file():   # ../ 같은 경로 조작 방지
        abort(404)
    key = hashlib.md5(f"{src}:{src.stat().st_mtime}:{size}".encode()).hexdigest()[:16]
    out = CACHE_DIR / f"{key}.jpg"
    if not out.exists():
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)          # 세로 사진 회전 반영
            im.thumbnail((size, size))
            im.convert("RGB").save(out, "JPEG", quality=85)
    return out


# ── Flask ──────────────────────────────────────────────────────────────────
app = Flask(__name__, static_folder="static")
app.json.ensure_ascii = False
app.json.sort_keys = False


@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.get("/api/photos")
def api_photos():
    photos = scan()
    groups = group_by_place(photos)
    for g in groups:
        g["nearby"] = nearby_attractions(g["lat"], g["lng"])
    return jsonify({
        "folder": str(PHOTO_DIR),
        "photos": photos,
        "groups": groups,
        "google_maps_key": os.environ.get("GOOGLE_MAPS_API_KEY", "").strip(),
        "google_maps_map_id": os.environ.get("GOOGLE_MAPS_MAP_ID", "").strip(),
        "heic": HEIC_OK,
        "group_m": GROUP_M,
    })


@app.get("/thumb/<path:name>")
def thumb(name):
    return send_file(resized(name, THUMB), mimetype="image/jpeg", max_age=86400)


@app.get("/large/<path:name>")
def large(name):
    return send_file(resized(name, LARGE), mimetype="image/jpeg", max_age=86400)


def load_env_file():
    """.env 를 이 폴더 → 상위 폴더 → tour_api 순으로 찾아, 환경변수에 없는 값만 보충한다."""
    for env_path in (BASE_DIR / ".env", BASE_DIR.parent / ".env", BASE_DIR.parent / "tour_api" / ".env"):
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if v.strip():
                        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


if __name__ == "__main__":
    load_env_file()
    photos = scan()
    with_gps = sum(1 for p in photos if "lat" in p)
    print(f"[사진] {PHOTO_DIR}  —  {len(photos)}장 중 위치 있음 {with_gps}장")
    print("[지도] Google 지도" if os.environ.get("GOOGLE_MAPS_API_KEY") else "[지도] OpenStreetMap (GOOGLE_MAPS_API_KEY 없음)")
    print(f"[주소] http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
