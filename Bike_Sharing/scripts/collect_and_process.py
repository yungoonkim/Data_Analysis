"""
서울시 공공자전거(따릉이) 송파구 데이터 수집 및 정제 스크립트
공공기관 공식 데이터: 서울 열린데이터광장(data.seoul.go.kr)
1. OA-13252: 서울시 공공자전거 대여소 정보
2. OA-15249: 서울시 공공자전거 대여소별 이용정보 (월별, 2021~2026년)
3. OA-15182: 서울시 공공자전거 대여이력 정보 (OD 이동경로, 시간대별, 요일별)
"""

import os
import io
import re
import time
import requests
import pandas as pd
import numpy as np

# 경로 설정 (Bike_Sharing 루트 기준)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, 'data')
MAPS_DIR = os.path.join(BASE_DIR, 'maps')
CHARTS_DIR = os.path.join(BASE_DIR, 'charts')

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(MAPS_DIR, exist_ok=True)
os.makedirs(CHARTS_DIR, exist_ok=True)

DOWNLOAD_URL = 'https://datafile.seoul.go.kr/bigfile/iot/inf/nio_download.do?&useCache=false'
HEADERS = {'Referer': 'https://data.seoul.go.kr/'}

def get_file_content(inf_id, seq, inf_seq='1'):
    data = {'infId': inf_id, 'seq': str(seq), 'infSeq': str(inf_seq), 'seqNo': ''}
    r = requests.post(DOWNLOAD_URL, data=data, headers=HEADERS, timeout=60)
    if r.status_code == 200 and len(r.content) > 500:
        return r.content
    raise RuntimeError(f"Download failed for {inf_id} seq {seq}: status {r.status_code}, len {len(r.content)}")

# -------------------------------------------------------------
# 1. 송파구 대여소 마스터 정보 수집 (OA-13252, seq 24)
# -------------------------------------------------------------
print("[1/3] 송파구 대여소 정보(OA-13252) 수집 중...")
st_content = get_file_content('OA-13252', '24', inf_seq='2')
df_st = pd.read_excel(io.BytesIO(st_content), skiprows=4)
df_st.columns = [
    '대여소번호', '대여소명', '자치구', '상세주소', '위도', '경도', 
    '설치시기', '거치대수_LCD', '거치대수_QR', '운영방식'
]
df_st['대여소번호'] = pd.to_numeric(df_st['대여소번호'], errors='coerce')
df_st['위도'] = pd.to_numeric(df_st['위도'], errors='coerce')
df_st['경도'] = pd.to_numeric(df_st['경도'], errors='coerce')
df_st['거치대수_LCD'] = pd.to_numeric(df_st['거치대수_LCD'], errors='coerce').fillna(0).astype(int)
df_st['거치대수_QR'] = pd.to_numeric(df_st['거치대수_QR'], errors='coerce').fillna(0).astype(int)
df_st['총거치대수'] = df_st['거치대수_LCD'] + df_st['거치대수_QR']

# 송파구 필터링
songpa_stations = df_st[df_st['자치구'] == '송파구'].dropna(subset=['대여소번호', '위도', '경도']).copy()
songpa_stations['대여소번호'] = songpa_stations['대여소번호'].astype(int)
songpa_stations['대여소명'] = songpa_stations['대여소명'].str.strip()

station_csv_path = os.path.join(DATA_DIR, 'songpa_stations.csv')
songpa_stations.to_csv(station_csv_path, index=False, encoding='utf-8-sig')
print(f" -> 송파구 대여소 {len(songpa_stations)}개 저장 완료: {station_csv_path}")

songpa_station_ids = set(songpa_stations['대여소번호'])
station_name_map = dict(zip(songpa_stations['대여소번호'], songpa_stations['대여소명']))
station_coord_map = dict(zip(songpa_stations['대여소번호'], zip(songpa_stations['위도'], songpa_stations['경도'])))

# -------------------------------------------------------------
# 2. 최근 5개년(2021 ~ 2026) 월별 수요 데이터 수집 (OA-15249)
# -------------------------------------------------------------
print("\n[2/3] 최근 5개년(2021~2026) 송파구 월별 수요 데이터(OA-15249) 수집 중...")
monthly_records = []

# 파일 목록 매핑
seq_configs = [
    # (seq, format_type, year_hint)
    ('32', 'standard', None),      # 26.1-6
    ('31', 'standard', None),      # 25.7-12
    ('29', 'standard', None),      # 25.1-6
    ('28', 'standard', None),      # 24.7-12
    ('26', 'standard', None),      # 24.1-6
    ('25', 'standard', None),      # 23.7-12
    ('24', 'standard', None),      # 23.1-6
    ('21', 'excel_std', None),     # 22.7-12 (.xlsx)
    ('20', 'table_month', '202206'), # 22.6
    ('19', 'table_month', '202205'), # 22.5
    ('18', 'table_month', '202204'), # 22.4
    ('17', 'table_month', '202203'), # 22.3
    ('16', 'table_month', '202202'), # 22.2
    ('15', 'table_month', '202201'), # 22.1
    ('14', 'table_2021_h2', None),   # 21.7-12
    ('12', 'table_2021_h1', None),   # 21.2-6
    ('11', 'table_2020_2021', '202101') # 21.1
]

for seq, ftype, hint in seq_configs:
    try:
        content = get_file_content('OA-15249', seq, inf_seq='1')
        print(f" -> seq {seq} 처리 중 (크기: {len(content)/1024:.1f} KB, 타입: {ftype})...")
        
        if ftype == 'standard':
            # csv utf-8 or cp949
            for enc in ['cp949', 'utf-8', 'euc-kr']:
                try:
                    df = pd.read_csv(io.BytesIO(content), encoding=enc)
                    break
                except:
                    continue
            sub = df[df['자치구'] == '송파구'].copy()
            for _, r in sub.iterrows():
                st_str = str(r['대여소명']).strip()
                m = re.match(r'^(\d+)\.\s*(.*)', st_str)
                st_id = int(m.group(1)) if m else None
                name = m.group(2) if m else st_str
                monthly_records.append({
                    '기준년월': str(r['기준년월'])[:6],
                    '대여소번호': st_id,
                    '대여소명': name,
                    '자치구': '송파구',
                    '대여건수': pd.to_numeric(r['대여건수'], errors='coerce'),
                    '반납건수': pd.to_numeric(r['반납건수'], errors='coerce')
                })
                
        elif ftype == 'excel_std':
            df = pd.read_excel(io.BytesIO(content))
            sub = df[df['자치구'] == '송파구'].copy()
            for _, r in sub.iterrows():
                st_str = str(r['대여소명']).strip()
                m = re.match(r'^(\d+)\.\s*(.*)', st_str)
                st_id = int(m.group(1)) if m else None
                name = m.group(2) if m else st_str
                monthly_records.append({
                    '기준년월': str(r['기준년월'])[:6],
                    '대여소번호': st_id,
                    '대여소명': name,
                    '자치구': '송파구',
                    '대여건수': pd.to_numeric(r['대여건수'], errors='coerce'),
                    '반납건수': pd.to_numeric(r['반납건수'], errors='coerce')
                })
                
        elif ftype == 'table_month':
            # Row 5 header: 대여소 그룹, 팀명, 대여소 명, 대여 건수
            df = pd.read_csv(io.BytesIO(content), encoding='cp949', skiprows=5)
            # rename if needed
            cols = df.columns.tolist()
            grp_col = cols[0]
            name_col = cols[2]
            rent_col = cols[3]
            sub = df[df[grp_col] == '송파구'].copy()
            for _, r in sub.iterrows():
                st_str = str(r[name_col]).strip()
                m = re.match(r'^(\d+)\.\s*(.*)', st_str)
                st_id = int(m.group(1)) if m else None
                name = m.group(2) if m else st_str
                rent_val = pd.to_numeric(r[rent_col], errors='coerce')
                monthly_records.append({
                    '기준년월': hint,
                    '대여소번호': st_id,
                    '대여소명': name,
                    '자치구': '송파구',
                    '대여건수': rent_val,
                    '반납건수': np.nan # 구버전은 대여건수만 제공
                })
                
        elif ftype == 'table_2021_h2':
            # Row 2 is header
            df = pd.read_csv(io.BytesIO(content), encoding='cp949', skiprows=2)
            sub = df[df['대여소 그룹'] == '송파구'].copy()
            for _, r in sub.iterrows():
                st_str = str(r['대여소 명']).strip()
                m = re.match(r'^(\d+)\.\s*(.*)', st_str)
                st_id = int(m.group(1)) if m else None
                name = m.group(2) if m else st_str
                ym_str = str(r['대여 일자 / 월']).split('.')[0].strip()
                monthly_records.append({
                    '기준년월': ym_str,
                    '대여소번호': st_id,
                    '대여소명': name,
                    '자치구': '송파구',
                    '대여건수': pd.to_numeric(r['대여 건수'], errors='coerce'),
                    '반납건수': np.nan
                })
                
        elif ftype in ['table_2021_h1', 'table_2020_2021']:
            df = pd.read_csv(io.BytesIO(content), encoding='cp949')
            sub = df[df['대여소 그룹'] == '송파구'].copy()
            for _, r in sub.iterrows():
                ym_raw = str(r['대여 일자 / 월']).split('.')[0].strip()
                if hint and ym_raw != hint:
                    continue
                if not hint and not ym_raw.startswith('2021'):
                    continue
                st_str = str(r['대여소 명']).strip()
                m = re.match(r'^(\d+)\.\s*(.*)', st_str)
                st_id = int(m.group(1)) if m else None
                name = m.group(2) if m else st_str
                monthly_records.append({
                    '기준년월': ym_raw,
                    '대여소번호': st_id,
                    '대여소명': name,
                    '자치구': '송파구',
                    '대여건수': pd.to_numeric(r['대여 건수'], errors='coerce'),
                    '반납건수': np.nan
                })
    except Exception as e:
        print(f" ! seq {seq} 수집 중 예외 발생: {e}")

df_monthly = pd.DataFrame(monthly_records)
# 대여소번호 매핑 보완 (이름으로 매핑)
name_to_id = {v: k for k, v in station_name_map.items()}
for idx, r in df_monthly[df_monthly['대여소번호'].isna()].iterrows():
    matched_id = name_to_id.get(r['대여소명'])
    if matched_id:
        df_monthly.at[idx, '대여소번호'] = matched_id

# 정렬 및 결측치 처리
df_monthly['대여소번호'] = pd.to_numeric(df_monthly['대여소번호'], errors='coerce')
df_monthly = df_monthly.dropna(subset=['대여소번호']).copy()
df_monthly['대여소번호'] = df_monthly['대여소번호'].astype(int)
df_monthly = df_monthly.sort_values(['기준년월', '대여소번호']).reset_index(drop=True)

monthly_csv_path = os.path.join(DATA_DIR, 'songpa_monthly_demand_2021_2026.csv')
df_monthly.to_csv(monthly_csv_path, index=False, encoding='utf-8-sig')
print(f" -> 최근 5개년(2021~2026) 송파구 월별 수요 {len(df_monthly)}개 레코드 저장 완료: {monthly_csv_path}")
print(f" -> 수집 기간: {df_monthly['기준년월'].min()} ~ {df_monthly['기준년월'].max()} (총 {df_monthly['기준년월'].nunique()}개월)")

# -------------------------------------------------------------
# 3. 송파구 대여이력(OD 통행 데이터) 수집 및 정제 (OA-15182, seq 150)
# -------------------------------------------------------------
print("\n[3/3] 송파구 대여이력 OD 통행 데이터(OA-15182) 수집 및 필터링 중...")
trip_content_stream = requests.post(
    DOWNLOAD_URL, 
    data={'infId': 'OA-15182', 'seq': '150', 'infSeq': '1', 'seqNo': ''},
    headers=HEADERS,
    stream=True
)

wrapper = io.TextIOWrapper(trip_content_stream.raw, encoding='cp949', errors='replace')
chunk_iter = pd.read_csv(wrapper, chunksize=100000, low_memory=False)

collected_trips = []
max_trips_needed = 80000 # 충분한 통계적 유의성을 가진 통행 샘플 확보
total_scanned = 0

for i, chunk in enumerate(chunk_iter):
    total_scanned += len(chunk)
    st_num = pd.to_numeric(chunk['대여 대여소번호'], errors='coerce')
    rt_num = pd.to_numeric(chunk['반납대여소번호'], errors='coerce')
    
    # 송파구 내부 통행 (출발 & 도착 모두 송파구)
    mask_internal = st_num.isin(songpa_station_ids) & rt_num.isin(songpa_station_ids)
    sub = chunk[mask_internal].copy()
    
    if len(sub) > 0:
        sub['대여대여소번호'] = st_num[mask_internal].astype(int)
        sub['반납대여소번호'] = rt_num[mask_internal].astype(int)
        collected_trips.append(sub[[
            '대여일시', '대여대여소번호', '대여 대여소명', 
            '반납일시', '반납대여소번호', '반납대여소명', 
            '이용시간(분)', '이용거리(M)'
        ]])
    
    print(f" -> {total_scanned:,}행 스캔 완료, 송파구 통행 {sum(len(x) for x in collected_trips):,}건 추출...")
    if sum(len(x) for x in collected_trips) >= max_trips_needed:
        break

df_trips = pd.concat(collected_trips, ignore_index=True)

# 시계열 및 파생 변수 생성
df_trips['대여일시'] = pd.to_datetime(df_trips['대여일시'], errors='coerce')
df_trips = df_trips.dropna(subset=['대여일시']).copy()
df_trips['대여시간대'] = df_trips['대여일시'].dt.hour
df_trips['대여요일'] = df_trips['대여일시'].dt.day_name()
df_trips['요일구분'] = df_trips['대여일시'].dt.dayofweek.map(lambda x: '주말' if x >= 5 else '평일')
df_trips['요일한글'] = df_trips['대여일시'].dt.dayofweek.map({
    0: '월요일', 1: '화요일', 2: '수요일', 3: '목요일', 4: '금요일', 5: '토요일', 6: '일요일'
})

# 이상치 정제: 이용시간 0 이하 또는 240분 초과, 이용거리 0 이상
df_trips['이용시간(분)'] = pd.to_numeric(df_trips['이용시간(분)'], errors='coerce').fillna(0)
df_trips['이용거리(M)'] = pd.to_numeric(df_trips['이용거리(M)'], errors='coerce').fillna(0)
df_trips = df_trips[(df_trips['이용시간(분)'] > 1) & (df_trips['이용시간(분)'] <= 240)].copy()

trips_csv_path = os.path.join(DATA_DIR, 'songpa_trips_sample.csv')
df_trips.to_csv(trips_csv_path, index=False, encoding='utf-8-sig')
print(f" -> 정제된 송파구 통행 데이터 {len(df_trips):,}건 저장 완료: {trips_csv_path}")

# -------------------------------------------------------------
# 4. A대여소 -> B대여소 이동량(OD Flow) 매트릭스 집계
# -------------------------------------------------------------
print("\n[4] A대여소 -> B대여소 이동량(OD Matrix) 집계 중...")
# 제자리 반납(A->A)을 제외한 이동 통행 또는 전체 통행 집계
od_flow = df_trips.groupby([
    '대여대여소번호', '대여 대여소명', 
    '반납대여소번호', '반납대여소명'
]).agg(
    이동건수=('대여일시', 'count'),
    평균이용시간_분=('이용시간(분)', 'mean'),
    평균이동거리_M=('이용거리(M)', 'mean')
).reset_index()

# 좌표 매핑
od_flow['출발_위도'] = od_flow['대여대여소번호'].map(lambda x: station_coord_map.get(x, (np.nan, np.nan))[0])
od_flow['출발_경도'] = od_flow['대여대여소번호'].map(lambda x: station_coord_map.get(x, (np.nan, np.nan))[1])
od_flow['도착_위도'] = od_flow['반납대여소번호'].map(lambda x: station_coord_map.get(x, (np.nan, np.nan))[0])
od_flow['도착_경도'] = od_flow['반납대여소번호'].map(lambda x: station_coord_map.get(x, (np.nan, np.nan))[1])

od_flow = od_flow.dropna(subset=['출발_위도', '출발_경도', '도착_위도', '도착_경도']).copy()
od_flow = od_flow.sort_values('이동건수', ascending=False).reset_index(drop=True)

# 시각화용 선 두께(weight) 및 색상 구간(color tier) 할당
# 사용자 요청: "사용량이 적으면 얇은 선, 사용량이 많으면 두꺼운 선, 적당하게 선의 색상 구별"
min_cnt = od_flow['이동건수'].min()
max_cnt = od_flow['이동건수'].max()

def calc_weight(cnt):
    # Log scale or quantile-based weight between 1.0 and 8.0
    return float(np.clip(1.2 + 6.8 * (np.log1p(cnt) / np.log1p(max_cnt)), 1.2, 8.0))

def calc_color(cnt):
    # Quantiles / thresholds
    if cnt >= 100:
        return '#d73027' # 최다: 짙은 붉은색 (Crimson)
    elif cnt >= 50:
        return '#fc8d59' # 많음: 주황색 (Orange)
    elif cnt >= 20:
        return '#fee08b' # 중간: 황금색 (Gold/Yellow)
    elif cnt >= 10:
        return '#91bfdb' # 적음: 하늘색 (Light Blue)
    else:
        return '#4575b4' # 매우적음: 짙은 파랑 (Blue)

od_flow['선두께'] = od_flow['이동건수'].apply(calc_weight)
od_flow['선색상'] = od_flow['이동건수'].apply(calc_color)

od_csv_path = os.path.join(DATA_DIR, 'songpa_od_flow_summary.csv')
od_flow.to_csv(od_csv_path, index=False, encoding='utf-8-sig')
print(f" -> 송파구 OD 경로 {len(od_flow):,}개 집계 완료: {od_csv_path}")
print(f" -> 상위 5개 최다 통행 경로:")
for _, r in od_flow.head(5).iterrows():
    print(f"    * {r['대여 대여소명']} -> {r['반납대여소명']}: {r['이동건수']}건 (평균 {r['평균이용시간_분']:.1f}분, {r['평균이동거리_M']:.0f}m)")

print("\n전체 공공데이터 수집 및 정제 작업이 성공적으로 완료되었습니다!")
