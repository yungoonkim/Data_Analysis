"""
송파구 따릉이 개별 통행 흐름(OD Flow) 및 시간대별 인터랙티브 지도 생성 스크립트
- 단일 묶음 선 대신 개별 이동 흐름(AntPath 동적 애니메이션 & 시간대별 개별 경로) 표출
- 출근(07~09시), 퇴근(17~19시), 주간(11~15시), 야간(21~04시) 레이어 분리
- Google Maps (일반/위성) 및 OpenStreetMap 타일 지원
"""

import os
import folium
from folium import plugins
from folium.plugins import AntPath
import pandas as pd
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MAPS_DIR = os.path.join(BASE_DIR, 'maps')
os.makedirs(MAPS_DIR, exist_ok=True)

# 1. 데이터 로드
stations_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_stations.csv'), encoding='utf-8')
od_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_od_flow_summary.csv'), encoding='utf-8')
trips_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_trips_sample.csv'), encoding='utf-8')

# 대여소 좌표 딕셔너리
st_dict = stations_df.set_index('대여소번호')[['위도', '경도', '대여소명']].to_dict('index')

# 대여소별 총 승차(출발) 및 하차(도착) 건수
dep_counts = trips_df.groupby('대여대여소번호').size().to_dict()
arr_counts = trips_df.groupby('반납대여소번호').size().to_dict()

# 중심 좌표: 송파구청 / 잠실 중심
map_center = [37.5145, 127.1060]
m = folium.Map(
    location=map_center,
    zoom_start=13,
    control_scale=True
)

# 2. 배경 타일 레이어 구성
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

# 3. 개별 통행 흐름 레이어 생성 (단일 묶음 대신 개별 흐름선 표출)
od_inter = od_df[od_df['대여대여소번호'] != od_df['반납대여소번호']].copy()

# (1) AntPath 동적 애니메이션 레이어 (실시간 이동 궤적 효과)
antpath_layer = folium.FeatureGroup(name="✨ 전체 주요 개별 통행 흐름 (AntPath 동적 애니메이션)", show=True)
od_top = od_inter.head(150)

for _, r in od_top.iterrows():
    p1 = [r['출발_위도'], r['출발_경도']]
    p2 = [r['도착_위도'], r['도착_경도']]
    cnt = int(r['이동건수'])
    color = str(r['선색상'])
    
    tooltip_html = f"""
    <div style='font-family: Pretendard, sans-serif; font-size: 13px; line-height: 1.4; padding: 4px;'>
        <b style='color: #2b5c8f;'>출발:</b> {r['대여 대여소명']}<br/>
        <b style='color: #d9534f;'>도착:</b> {r['반납대여소명']}<br/>
        <hr style='margin: 4px 0;'/>
        <b>총 이동 건수:</b> <span style='color: {color}; font-weight: bold;'>{cnt}건</span><br/>
        <b>평균 소요시간:</b> {r['평균이용시간_분']:.1f}분 | <b>평균 거리:</b> {r['평균이동거리_M']:.0f} m
    </div>
    """
    
    # 묶음 선이 아닌 얇은 선(1.8px)에 움직이는 대시 파티클을 주어 개별 통행 느낌 구현
    AntPath(
        locations=[p1, p2],
        delay=1000,
        weight=2.0,
        color=color,
        pulse_color='#ffffff',
        opacity=0.75,
        dash_array=[10, 20],
        tooltip=tooltip_html
    ).add_to(antpath_layer)

antpath_layer.add_to(m)

# (2) 시간대별 개별 통행 흐름 레이어 헬퍼 함수
def create_hourly_flow_layer(name, hours, line_color, top_n=100, show=False):
    layer = folium.FeatureGroup(name=name, show=show)
    sub = trips_df[(trips_df['대여시간대'].isin(hours)) & (trips_df['대여대여소번호'] != trips_df['반납대여소번호'])]
    grouped = sub.groupby(['대여대여소번호', '대여 대여소명', '반납대여소번호', '반납대여소명']).agg(
        이동건수=('대여일시', 'count'),
        평균시간=('이용시간(분)', 'mean'),
        평균거리=('이용거리(M)', 'mean')
    ).reset_index().sort_values('이동건수', ascending=False).head(top_n)
    
    for _, r in grouped.iterrows():
        st1 = st_dict.get(r['대여대여소번호'])
        st2 = st_dict.get(r['반납대여소번호'])
        if st1 and st2:
            p1 = [st1['위도'], st1['경도']]
            p2 = [st2['위도'], st2['경도']]
            cnt = int(r['이동건수'])
            
            tooltip_html = f"""
            <div style='font-family: Pretendard, sans-serif; font-size: 13px; line-height: 1.4; padding: 4px;'>
                <span style='color: {line_color}; font-weight: bold;'>[{name.split()[0]}]</span><br/>
                <b>출발:</b> {r['대여 대여소명']}<br/>
                <b>도착:</b> {r['반납대여소명']}<br/>
                <hr style='margin: 4px 0;'/>
                <b>해당 시간대 이동:</b> <span style='color: {line_color}; font-weight: bold;'>{cnt}건</span><br/>
                <b>평균 소요:</b> {r['평균시간']:.1f}분 | <b>거리:</b> {r['평균거리']:.0f}m
            </div>
            """
            
            # 개별 이동 선으로 얇게 렌더링
            folium.PolyLine(
                locations=[p1, p2],
                color=line_color,
                weight=1.8,
                opacity=0.7,
                tooltip=tooltip_html
            ).add_to(layer)
            
    return layer

# 출근 피크 (07~09시)
morning_layer = create_hourly_flow_layer("🌅 아침 출근시간대 (07~09시) 개별 이동 흐름", [7, 8, 9], "#e31a1c", top_n=100, show=False)
morning_layer.add_to(m)

# 퇴근 피크 (17~19시)
evening_layer = create_hourly_flow_layer("🌆 저녁 퇴근시간대 (17~19시) 개별 이동 흐름", [17, 18, 19], "#ff7f00", top_n=100, show=False)
evening_layer.add_to(m)

# 주간/생활 (11~15시)
day_layer = create_hourly_flow_layer("☀️ 주간 일상/레저 (11~15시) 개별 이동 흐름", [11, 12, 13, 14, 15], "#33a02c", top_n=100, show=False)
day_layer.add_to(m)

# 야간/심야 (21~04시)
night_layer = create_hourly_flow_layer("🌙 야간/심야시간대 (21~04시) 개별 이동 흐름", [21, 22, 23, 0, 1, 2, 3, 4], "#984ea3", top_n=100, show=False)
night_layer.add_to(m)

# 4. 대여소 마커 레이어 생성
station_layer = folium.FeatureGroup(name="대여소 위치 및 이용량 (CircleMarker)", show=True)
max_total_usage = max([dep_counts.get(sid, 0) + arr_counts.get(sid, 0) for sid in stations_df['대여소번호']] or [1])

for _, st in stations_df.iterrows():
    sid = int(st['대여소번호'])
    dep = dep_counts.get(sid, 0)
    arr = arr_counts.get(sid, 0)
    tot = dep + arr
    net = arr - dep
    
    radius = 4.0 + 12.0 * np.sqrt(tot / max_total_usage) if max_total_usage > 0 else 5.0
    fill_color = '#1f78b4' if net > 20 else ('#e31a1c' if net < -20 else '#33a02c')
        
    popup_html = f"""
    <div style='font-family: Pretendard, sans-serif; font-size: 13px; width: 230px; line-height: 1.5;'>
        <h4 style='margin: 0 0 6px 0; color: #1a365d; border-bottom: 2px solid #cbd5e0; padding-bottom: 4px;'>
            {st['대여소명']}
        </h4>
        <b>대여소 번호:</b> {sid}번<br/>
        <b>위치:</b> {st['상세주소']}<br/>
        <b>총 거치대수:</b> {st['총거치대수']}대<br/>
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

# 5. 인터랙티브 범례(Legend) HTML 추가
legend_html = """
<div style="
    position: fixed; 
    bottom: 30px; right: 30px; width: 270px; height: auto;
    background-color: rgba(255, 255, 255, 0.95);
    border: 2px solid #718096;
    border-radius: 8px;
    z-index: 9999;
    font-size: 12px;
    font-family: Pretendard, sans-serif;
    padding: 12px 16px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
">
    <div style='font-size: 14px; font-weight: bold; margin-bottom: 8px; color: #1a202c;'>
        🚲 송파구 따릉이 개별 이동 범례
    </div>
    <div style='font-weight: bold; margin-bottom: 4px; color: #4a5568;'>[이동 흐름선 특징]</div>
    <div style='margin-bottom: 4px; color: #2d3748;'>
        ✨ <b>AntPath 동적 선:</b> 이동 방향으로 점선 파티클이 실시간 흐르듯 애니메이션 표출
    </div>
    <hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>
    <div style='font-weight: bold; margin-bottom: 4px; color: #4a5568;'>[시간대별 개별 이동 레이어 (우측 상단)]</div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #e31a1c; width: 20px; height: 3px; margin-right: 8px;'></span>
        <span>🌅 출근시간대 (07~09시)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #ff7f00; width: 20px; height: 3px; margin-right: 8px;'></span>
        <span>🌆 퇴근시간대 (17~19시)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 3px;'>
        <span style='background: #33a02c; width: 20px; height: 3px; margin-right: 8px;'></span>
        <span>☀️ 주간/레저 (11~15시)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 6px;'>
        <span style='background: #984ea3; width: 20px; height: 3px; margin-right: 8px;'></span>
        <span>🌙 야간/심야 (21~04시)</span>
    </div>
    <hr style='margin: 6px 0; border: none; border-top: 1px solid #e2e8f0;'/>
    <div style='font-weight: bold; margin-bottom: 4px; color: #4a5568;'>[대여소 마커 순유출입]</div>
    <div style='display: flex; align-items: center; margin-bottom: 2px;'>
        <span style='background: #e31a1c; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;'></span>
        <span>순유출 우세 (승차 > 하차)</span>
    </div>
    <div style='display: flex; align-items: center; margin-bottom: 2px;'>
        <span style='background: #1f78b4; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;'></span>
        <span>순유입 우세 (하차 > 승차)</span>
    </div>
    <div style='display: flex; align-items: center;'>
        <span style='background: #33a02c; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px;'></span>
        <span>균형 상태</span>
    </div>
</div>
"""
m.get_root().html.add_child(folium.Element(legend_html))
folium.LayerControl(collapsed=False).add_to(m)

out_map_path = os.path.join(MAPS_DIR, 'songpa_bike_od_flow_map.html')
m.save(out_map_path)
print(f"개별 통행 흐름 인터랙티브 지도 생성 완료: {out_map_path}")
