"""
송파구 따릉이 OD 통행 흐름 및 대여소 시각화 맵 생성 스크립트
A대여소 -> B대여소 이동량 기반 동적 선 두께 및 색상 매핑
"""

import os
import folium
from folium import plugins
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MAPS_DIR = os.path.join(BASE_DIR, 'maps')
os.makedirs(MAPS_DIR, exist_ok=True)

stations_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_stations.csv'))
od_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_od_flow_summary.csv'))
trips_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_trips_sample.csv'))

# 대여소별 총 승차(출발) 및 하차(도착) 건수 계산
dep_counts = trips_df.groupby('대여대여소번호').size().to_dict()
arr_counts = trips_df.groupby('반납대여소번호').size().to_dict()

# 중심 좌표: 송파구청 / 잠실 중심
map_center = [37.5145, 127.1060]
m = folium.Map(
    location=map_center,
    zoom_start=13,
    control_scale=True
)

# 구글맵 타일 레이어 추가 (API 키 불필요)
folium.TileLayer(
    tiles='http://mt0.google.com/vt/lyrs=m&hl=ko&x={x}&y={y}&z={z}',
    attr='Google Maps',
    name='Google Maps (일반 도로)',
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    tiles='http://mt0.google.com/vt/lyrs=y&hl=ko&x={x}&y={y}&z={z}',
    attr='Google Satellite',
    name='Google Maps (위성 + 도로명)',
    overlay=False,
    control=True
).add_to(m)

folium.TileLayer(
    tiles='OpenStreetMap',
    attr='OpenStreetMap',
    name='OpenStreetMap',
    overlay=False,
    control=True
).add_to(m)

# 1. OD 흐름선 레이어 생성 (A대여소 != B대여소)
# 상위 주요 흐름선 필터링 (가독성과 웹 렌더링 성능 최적화: 통행량 상위 250개 경로)
od_inter = od_df[od_df['대여대여소번호'] != od_df['반납대여소번호']].copy()
od_top = od_inter.head(250)

flow_layer = folium.FeatureGroup(name="따릉이 이동 흐름 (A ➔ B PolyLine)", show=True)

for _, r in od_top.iterrows():
    p1 = [r['출발_위도'], r['출발_경도']]
    p2 = [r['도착_위도'], r['도착_경도']]
    cnt = int(r['이동건수'])
    weight = float(r['선두께'])
    color = str(r['선색상'])
    
    # 툴팁 HTML
    tooltip_html = f"""
    <div style='font-family: Pretendard, Apple SD Gothic Neo, sans-serif; font-size: 13px; line-height: 1.4; padding: 4px;'>
        <b style='color: #2b5c8f;'>출발:</b> {r['대여 대여소명']}<br/>
        <b style='color: #d9534f;'>도착:</b> {r['반납대여소명']}<br/>
        <hr style='margin: 4px 0;'/>
        <b>이동 건수:</b> <span style='color: {color}; font-weight: bold;'>{cnt}건</span><br/>
        <b>평균 소요시간:</b> {r['평균이용시간_분']:.1f}분<br/>
        <b>평균 이동거리:</b> {r['평균이동거리_M']:.0f} m
    </div>
    """
    
    folium.PolyLine(
        locations=[p1, p2],
        color=color,
        weight=weight,
        opacity=0.75,
        tooltip=tooltip_html
    ).add_to(flow_layer)

flow_layer.add_to(m)

# 2. 대여소 마커 레이어 생성
station_layer = folium.FeatureGroup(name="대여소 위치 및 이용량 (CircleMarker)", show=True)

max_total_usage = max([dep_counts.get(sid, 0) + arr_counts.get(sid, 0) for sid in stations_df['대여소번호']] or [1])

for _, st in stations_df.iterrows():
    sid = int(st['대여소번호'])
    dep = dep_counts.get(sid, 0)
    arr = arr_counts.get(sid, 0)
    tot = dep + arr
    net = arr - dep # 양수: 순유입, 음수: 순유출
    
    # 원 크기: 이용량 비례 (min 4, max 16)
    radius = 4.0 + 12.0 * np.sqrt(tot / max_total_usage) if max_total_usage > 0 else 5.0
    
    # 순유입/유출 색상 구분
    if net > 20:
        fill_color = '#1f78b4' # 순도착(유입) 우세: 파랑
    elif net < -20:
        fill_color = '#e31a1c' # 순출발(유출) 우세: 빨강
    else:
        fill_color = '#33a02c' # 균형: 녹색
        
    popup_html = f"""
    <div style='font-family: Pretendard, Apple SD Gothic Neo, sans-serif; font-size: 13px; width: 230px; line-height: 1.5;'>
        <h4 style='margin: 0 0 6px 0; color: #1a365d; border-bottom: 2px solid #cbd5e0; padding-bottom: 4px;'>
            {st['대여소명']}
        </h4>
        <b>대여소 번호:</b> {sid}번<br/>
        <b>위치:</b> {st['상세주소']}<br/>
        <b>총 거치대수:</b> {st['총거치대수']}대 (QR {st['거치대수_QR']}대 / LCD {st['거치대수_LCD']}대)<br/>
        <hr style='margin: 6px 0; border: none; border-top: 1px dashed #cbd5e0;'/>
        <b>총 승차(대여):</b> <span style='color: #e31a1c; font-weight: bold;'>{dep:,}건</span><br/>
        <b>총 하차(반납):</b> <span style='color: #1f78b4; font-weight: bold;'>{arr:,}건</span><br/>
        <b>순 유출입:</b> <span style='font-weight: bold;'>{'+' if net>0 else ''}{net:,}건 ({'유입 우세' if net>20 else '유출 우세' if net<-20 else '균형'})</span>
    </div>
    """
    
    folium.CircleMarker(
        location=[st['위도'], st['경도']],
        radius=radius,
        color='#2d3748',
        weight=1.2,
        fill=True,
        fill_color=fill_color,
        fill_opacity=0.85,
        tooltip=f"{st['대여소명']} (총 이용 {tot:,}건)",
        popup=folium.Popup(popup_html, max_width=280)
    ).add_to(station_layer)

station_layer.add_to(m)

# 3. 범례(Legend) HTML 추가
legend_html = """
<div style="
    position: fixed; 
    bottom: 30px; right: 30px; width: 260px; height: auto;
    background-color: rgba(255, 255, 255, 0.95);
    border: 2px solid #718096;
    border-radius: 8px;
    z-index: 9999;
    font-size: 12px;
    font-family: Pretendard, Apple SD Gothic Neo, sans-serif;
    padding: 12px 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
">
    <div style='font-size: 14px; font-weight: bold; margin-bottom: 8px; color: #1a202c;'>
        🚲 송파구 따릉이 통행 범례
    </div>
    <div style='font-weight: bold; margin-bottom: 4px; color: #4a5568;'>[A ➔ B 이동량 선 두께 및 색상]</div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #d73027; width: 32px; height: 6px; display: inline-block; margin-right: 8px; border-radius: 3px;'></span>
        <span>100건 이상 (최다 통행)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #fc8d59; width: 32px; height: 4.5px; display: inline-block; margin-right: 8px; border-radius: 2px;'></span>
        <span>50 ~ 99건 (많음)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #fee08b; width: 32px; height: 3.5px; display: inline-block; margin-right: 8px; border-radius: 2px;'></span>
        <span>20 ~ 49건 (보통)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #91bfdb; width: 32px; height: 2.5px; display: inline-block; margin-right: 8px;'></span>
        <span>10 ~ 19건 (적음)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 8px;'>
        <span style='background: #4575b4; width: 32px; height: 1.5px; display: inline-block; margin-right: 8px;'></span>
        <span>10건 미만 (최소)</span>
    </div>
    <hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>
    <div style='font-weight: bold; margin-bottom: 4px; color: #4a5568;'>[대여소 마커 색상 (순유출입)]</div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #e31a1c; width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px;'></span>
        <span>순유출 우세 (승차 > 하차)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #1f78b4; width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px;'></span>
        <span>순유입 우세 (하차 > 승차)</span>
    </div>
    <div style='display: flex; align-items: center;'>
        <span style='background: #33a02c; width: 12px; height: 12px; border-radius: 50%; display: inline-block; margin-right: 8px;'></span>
        <span>균형 상태</span>
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))

folium.LayerControl(collapsed=False).add_to(m)

out_map_path = os.path.join(MAPS_DIR, 'songpa_bike_od_flow_map.html')
m.save(out_map_path)
print(f"인터랙티브 OD 흐름 지도 생성 완료: {out_map_path}")
