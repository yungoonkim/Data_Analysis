"""
구글맵 JavaScript API 기반 송파구 따릉이 OD 통행 시각화 HTML 생성기
(구글 공식 JS API 및 구글 네이티브 UI를 사용하는 독립형 웹 지도 파일)
"""

import os
import json
import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MAPS_DIR = os.path.join(BASE_DIR, 'maps')

stations_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_stations.csv'))
od_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_od_flow_summary.csv'))
trips_df = pd.read_csv(os.path.join(DATA_DIR, 'songpa_trips_sample.csv'))

dep_counts = trips_df.groupby('대여대여소번호').size().to_dict()
arr_counts = trips_df.groupby('반납대여소번호').size().to_dict()

# 정제된 대여소 데이터
stations_data = []
for _, st in stations_df.iterrows():
    sid = int(st['대여소번호'])
    dep = int(dep_counts.get(sid, 0))
    arr = int(arr_counts.get(sid, 0))
    stations_data.append({
        'id': sid,
        'name': st['대여소명'],
        'lat': float(st['위도']),
        'lng': float(st['경도']),
        'address': st['상세주소'],
        'racks': int(st['총거치대수']),
        'dep': dep,
        'arr': arr,
        'net': arr - dep
    })

# 상위 OD 통행 데이터 (A != B)
od_inter = od_df[od_df['대여대여소번호'] != od_df['반납대여소번호']].head(200)
flows_data = []
for _, r in od_inter.iterrows():
    flows_data.append({
        'from_name': r['대여 대여소명'],
        'to_name': r['반납대여소명'],
        'from_lat': float(r['출발_위도']),
        'from_lng': float(r['출발_경도']),
        'to_lat': float(r['도착_위도']),
        'to_lng': float(r['도착_경도']),
        'count': int(r['이동건수']),
        'weight': float(r['선두께']),
        'color': str(r['선색상']),
        'avg_time': round(float(r['평균이용시간_분']), 1),
        'avg_dist': round(float(r['평균이동거리_M']), 0)
    })

html_content = f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>구글맵 기반 서울시 송파구 따릉이 OD 통행 흐름 시각화</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        html, body, #map {{ width: 100%; height: 100%; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Malgun Gothic", sans-serif; }}
        
        /* 상단 컨트롤 바 */
        .top-banner {{
            position: absolute;
            top: 15px; left: 15px;
            background: rgba(255, 255, 255, 0.95);
            padding: 12px 18px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            z-index: 10;
            max-width: 460px;
        }}
        .top-banner h1 {{
            font-size: 16px;
            font-weight: 700;
            color: #1a202c;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .top-banner p {{
            font-size: 12px;
            color: #4a5568;
            margin-top: 4px;
            line-height: 1.4;
        }}
        .api-key-box {{
            margin-top: 8px;
            padding: 8px;
            background: #f7fafc;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            font-size: 11px;
        }}
        .api-key-box input {{
            width: 70%;
            padding: 4px 6px;
            border: 1px solid #cbd5e0;
            border-radius: 4px;
            font-size: 11px;
        }}
        .api-key-box button {{
            padding: 4px 10px;
            background: #3182ce;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
        }}
        
        /* 우측 하단 범례 */
        .legend-box {{
            position: absolute;
            bottom: 25px; right: 25px;
            background: rgba(255, 255, 255, 0.95);
            padding: 14px 18px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0,0,0,0.15);
            z-index: 10;
            font-size: 12px;
            width: 250px;
        }}
        .legend-title {{
            font-size: 13px;
            font-weight: bold;
            color: #2d3748;
            margin-bottom: 6px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            margin-bottom: 4px;
        }}
        .legend-bar {{
            height: 5px;
            border-radius: 2px;
            margin-right: 8px;
        }}
        .dot {{
            width: 10px; height: 10px;
            border-radius: 50%;
            margin-right: 8px;
            display: inline-block;
        }}
    </style>
</head>
<body>

    <div class="top-banner">
        <h1>🚲 송파구 따릉이 OD 통행 흐름 (Google Maps)</h1>
        <p>A대여소 ➔ B대여소 이동량 기반 동적 선 두께 및 색상 매핑 시각화</p>
        <div class="api-key-box">
            <b>구글 API 키 설정 (선택사항):</b><br/>
            <input type="text" id="customApiKey" placeholder="Google Maps API Key 입력..." />
            <button onclick="applyApiKey()">적용</button>
            <span style="color:#718096; display:block; margin-top:2px;">* 키가 없어도 개발용 모드로 기본 로드됩니다.</span>
        </div>
    </div>

    <div class="legend-box">
        <div class="legend-title">📊 통행량 범례 (A ➔ B PolyLine)</div>
        <div class="legend-item"><span class="legend-bar" style="background:#d73027; width:28px; height:7px;"></span> 100건 이상 (최다 통행)</div>
        <div class="legend-item"><span class="legend-bar" style="background:#fc8d59; width:28px; height:5px;"></span> 50 ~ 99건 (많음)</div>
        <div class="legend-item"><span class="legend-bar" style="background:#fee08b; width:28px; height:4px;"></span> 20 ~ 49건 (보통)</div>
        <div class="legend-item"><span class="legend-bar" style="background:#91bfdb; width:28px; height:2.5px;"></span> 10 ~ 19건 (적음)</div>
        <div class="legend-item"><span class="legend-bar" style="background:#4575b4; width:28px; height:1.5px;"></span> 10건 미만 (최소)</div>
        <hr style="margin: 8px 0; border: none; border-top: 1px solid #e2e8f0;"/>
        <div class="legend-title">📍 대여소 마커 (순유출입)</div>
        <div class="legend-item"><span class="dot" style="background:#e31a1c;"></span> 순유출 우세 (승차 > 하차)</div>
        <div class="legend-item"><span class="dot" style="background:#1f78b4;"></span> 순유입 우세 (하차 > 승차)</div>
        <div class="legend-item"><span class="dot" style="background:#33a02c;"></span> 균형 상태</div>
    </div>

    <div id="map"></div>

    <script>
        const stationsData = {json.dumps(stations_data, ensure_ascii=False)};
        const flowsData = {json.dumps(flows_data, ensure_ascii=False)};

        let map;
        let infoWindow;

        function initMap() {{
            const center = {{ lat: 37.5145, lng: 127.1060 }};
            map = new google.maps.Map(document.getElementById('map'), {{
                center: center,
                zoom: 13,
                mapTypeId: 'roadmap',
                fullscreenControl: true,
                mapTypeControl: true,
                streetViewControl: true
            }});

            infoWindow = new google.maps.InfoWindow();

            // 1. OD 통행 흐름선 렌더링 (PolyLine)
            flowsData.forEach(flow => {{
                const polyline = new google.maps.Polyline({{
                    path: [
                        {{ lat: flow.from_lat, lng: flow.from_lng }},
                        {{ lat: flow.to_lat, lng: flow.to_lng }}
                    ],
                    geodesic: true,
                    strokeColor: flow.color,
                    strokeOpacity: 0.75,
                    strokeWeight: flow.weight,
                    map: map
                }});

                polyline.addListener('mouseover', (e) => {{
                    infoWindow.setContent(`
                        <div style="padding:6px; font-family:sans-serif; font-size:12px; line-height:1.4;">
                            <b style="color:#2b5c8f;">출발:</b> ${{flow.from_name}}<br/>
                            <b style="color:#d9534f;">도착:</b> ${{flow.to_name}}<br/>
                            <hr style="margin:4px 0;"/>
                            <b>이동 건수:</b> <span style="color:${{flow.color}}; font-weight:bold;">${{flow.count}}건</span><br/>
                            <b>평균 시간:</b> ${{flow.avg_time}}분 | <b>평균 거리:</b> ${{flow.avg_dist}}m
                        </div>
                    `);
                    infoWindow.setPosition(e.latLng);
                    infoWindow.open(map);
                }});
            }});

            // 2. 대여소 마커 렌더링 (Circle)
            stationsData.forEach(st => {{
                const tot = st.dep + st.arr;
                const net = st.net;
                const fillColor = net > 20 ? '#1f78b4' : (net < -20 ? '#e31a1c' : '#33a02c');
                const radius = Math.max(45, Math.min(220, 45 + Math.sqrt(tot) * 4));

                const circle = new google.maps.Circle({{
                    strokeColor: '#2d3748',
                    strokeOpacity: 0.8,
                    strokeWeight: 1.5,
                    fillColor: fillColor,
                    fillOpacity: 0.8,
                    map: map,
                    center: {{ lat: st.lat, lng: st.lng }},
                    radius: radius
                }});

                circle.addListener('click', () => {{
                    infoWindow.setContent(`
                        <div style="padding:6px; font-family:sans-serif; font-size:13px; line-height:1.5;">
                            <h4 style="margin:0 0 4px 0; color:#1a365d;">${{st.name}} (${{st.id}}번)</h4>
                            <b>위치:</b> ${{st.address}}<br/>
                            <b>총 거치대수:</b> ${{st.racks}}대<br/>
                            <hr style="margin:4px 0;"/>
                            <b>승차(대여):</b> <span style="color:#e31a1c; font-weight:bold;">${{st.dep.toLocaleString()}}건</span><br/>
                            <b>하차(반납):</b> <span style="color:#1f78b4; font-weight:bold;">${{st.arr.toLocaleString()}}건</span><br/>
                            <b>순유출입:</b> ${{net > 0 ? '+' : ''}}${{net.toLocaleString()}}건 (${{net > 20 ? '유입 우세' : (net < -20 ? '유출 우세' : '균형')}})
                        </div>
                    `);
                    infoWindow.setPosition({{ lat: st.lat, lng: st.lng }});
                    infoWindow.open(map);
                }});
            }});
        }}

        function applyApiKey() {{
            const key = document.getElementById('customApiKey').value.trim();
            if (key) {{
                const script = document.createElement('script');
                script.src = `https://maps.googleapis.com/maps/api/js?key=${{key}}&callback=initMap&libraries=geometry`;
                script.async = true;
                document.head.appendChild(script);
            }}
        }}

        // 기본 로드 (API 키 파라미터가 없거나 기본 로드 시)
        const urlParams = new URLSearchParams(window.location.search);
        const apiKey = urlParams.get('key') || '';
        const script = document.createElement('script');
        script.src = apiKey 
            ? `https://maps.googleapis.com/maps/api/js?key=${{apiKey}}&callback=initMap&libraries=geometry`
            : `https://maps.googleapis.com/maps/api/js?callback=initMap&libraries=geometry`;
        script.async = true;
        document.head.appendChild(script);
    </script>
</body>
</html>
"""

output_path = os.path.join(MAPS_DIR, 'songpa_google_maps_flow.html')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"구글맵 JavaScript API 독립형 지도 생성 완료: {output_path}")
