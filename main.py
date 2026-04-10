import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
from PIL import Image
import io

# --- [1. 기본 설정 및 상수] ---
RT_KCAL = 3024
PYEONG_TO_M2 = 3.3058

st.set_page_config(layout="wide", page_title="신세계푸드 인천공장 분석 시스템")

# --- [2. 유틸리티 함수: UC 사양 선정 및 파일 로드] ---
def select_uc_specs(required_rt):
    """부하량에 따라 0.5RT ~ 30RT 중 가장 최적의 규격을 선택"""
    if required_rt <= 0: return 0.0, 0
    available_capacities = [30.0, 25.0, 20.0, 15.0, 10.0, 7.5, 5.0, 3.0, 2.0, 1.0, 0.5]
    best_cap, min_waste, best_count = 5.0, float('inf'), 1
    
    for cap in available_capacities:
        count = int(np.ceil(required_rt / cap))
        if count <= 8:
            waste = (cap * count) - required_rt
            if waste < min_waste:
                min_waste, best_cap, best_count = waste, cap, count
    return best_cap, best_count

def load_drawing_file(uploaded_file):
    if uploaded_file is not None:
        try:
            if uploaded_file.name.lower().endswith('.pdf'):
                doc = fitz.open(stream=uploaded_file.read(), filetype="pdf")
                page = doc.load_page(0)
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                return Image.open(io.BytesIO(pix.tobytes("png")))
            else:
                return Image.open(uploaded_file)
        except Exception as e:
            st.error(f"파일 오류: {e}")
    return None
import streamlit as st
# (기존 import문들...)

# --- [로그인 시스템] ---
def login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.title("🔒 신세계푸드 시스템 접속")
        auth_id = st.text_input("아이디")
        auth_pw = st.text_input("비밀번호", type="password")
        
        # 실제 운영시에는 아이디/비밀번호를 원하는 것으로 수정하세요
        if st.button("로그인"):
            if auth_id == "admin" and auth_pw == "shinsegae123":
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.error("아이디 또는 비밀번호가 잘못되었습니다.")
        return False
    return True

# 로그인 성공시에만 아래 메인 앱 실행
if login():
    # 여기에 제공해주신 기존 코드 전체를 넣습니다.
    # (st.title("🏭 신세계푸드 인천공장 통합 분석 시스템") 부터 끝까지)

# --- [3. 데이터 초기화] ---
if 'rooms' not in st.session_state:
    st.session_state.rooms = {
        "소성실": {"area": 25.0, "height": 3.5, "target": 25.0, "x": 400, "y": 800},
        "냉동창고": {"area": 15.0, "height": 3.0, "target": -18.0, "x": 900, "y": 150},
        "냉각실": {"area": 12.0, "height": 3.0, "target": 20.0, "x": 450, "y": 700},
        "내포장실": {"area": 20.0, "height": 2.8, "target": 18.0, "x": 480, "y": 480},
        "성형배합실": {"area": 18.0, "height": 3.2, "target": 22.0, "x": 800, "y": 550},
        "숙성실": {"area": 10.0, "height": 3.0, "target": 15.0, "x": 900, "y": 700}
    }
if 'eq_counts' not in st.session_state:
    st.session_state.eq_counts = {room: {eq: 0 for eq in ["로터리오븐", "터널오븐", "데크오븐", "발효기", "이가데치기"]} 
                                 for room in st.session_state.rooms}

# --- [4. 사이드바: 실별 상세 설정] ---
st.sidebar.title("🏢 신세계푸드 관리 보조창")
for room_name, info in st.session_state.rooms.items():
    with st.sidebar.expander(f"🏠 {room_name}"):
        info['area'] = st.number_input(f"면적(평)", 0.0, 500.0, float(info['area']), key=f"a_{room_name}")
        info['height'] = st.number_input(f"높이(m)", 0.0, 10.0, float(info['height']), key=f"h_{room_name}")
        info['target'] = st.number_input(f"목표온도(℃)", -50.0, 50.0, float(info['target']), key=f"t_{room_name}")
        st.write("**🔥 설비 대수 입력**")
        for eq_type in st.session_state.eq_counts[room_name]:
            st.session_state.eq_counts[room_name][eq_type] = st.number_input(
                f"{eq_type}", 0, 50, st.session_state.eq_counts[room_name][eq_type], key=f"eq_{room_name}_{eq_type}"
            )

# --- [5. 메인 레이아웃: 분석 제어 및 리포트] ---
st.title("🏭 신세계푸드 인천공장 통합 분석 시스템")

# 분석 실행 버튼 복구
col_btn, col_reset = st.columns([5, 1])
with col_btn:
    run_analysis = st.button("▶ 통합 데이터 분석 실행", use_container_width=True, type="primary")
with col_reset:
    if st.button("🔄 결과 초기화", use_container_width=True):
        for r in st.session_state.eq_counts:
            for e in st.session_state.eq_counts[r]: st.session_state.eq_counts[r][e] = 0
        st.rerun()

st.divider()

# 리포트와 그래프 영역
st.subheader("📊 정밀 분석 리포트")
report_list = []
heat_map = {"로터리오븐": 1500, "터널오븐": 1800, "데크오븐": 1200, "발효기": 400, "이가데치기": 800}

for name, info in st.session_state.rooms.items():
    vol = info['area'] * PYEONG_TO_M2 * info['height']
    active_heat = sum([st.session_state.eq_counts[name][eq] * heat_map[eq] for eq in heat_map])
    required_rt = ((vol * (30 - info['target']) * 40) + active_heat) / RT_KCAL if vol > 0 else 0
    uc_cap, uc_count = select_uc_specs(required_rt)

    report_list.append({
        "공간": name, "체적(m³)": f"{vol:.1f}", "필요능력": f"{max(0.0, required_rt):.2f} RT",
        "UC 최적규격": f"{uc_cap} RT", "총 UC 대수": f"{uc_count} 대"
    })
st.table(pd.DataFrame(report_list))

# --- [6. 타임라인 분석 (09:00 ~ 18:00)] ---
st.subheader("📈 09:00~18:00 실별 온도 변화 추이 분석")
chart_data = pd.DataFrame(index=[f"{h:02d}:00" for h in range(9, 19)])
for name, info in st.session_state.rooms.items():
    eq_sum = sum(st.session_state.eq_counts[name].values())
    chart_data[name] = [round(info['target'] + (eq_sum * 1.5 if h != 12 else 0.5) + np.random.uniform(-0.1, 0.1), 1) for h in range(9, 19)]

g_col, t_col = st.columns([2, 1])
with g_col:
    st.line_chart(chart_data)
with t_col:
    st.write("**시간대별 온도 요약(℃)**")
    st.dataframe(chart_data.T)

# 분석 완료 효과
if run_analysis:
    st.balloons()
    st.success("데이터 통합 분석이 완료되었습니다. 최적의 유니트쿨러(UC) 배치안을 확인하세요.")

# --- [7. 하단 레이아웃: 도면 레이어 관리] ---
st.divider()
st.subheader("🖼️ 도면 레이어 통합 관리")

with st.expander("📂 도면 업로드 (1차:구역 / 2차:온도 / 3차:설비)", expanded=True):
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1: f1 = st.file_uploader("1차: 구역 도면", type=['jpg','png','pdf'], key="up1")
    with col_f2: f2 = st.file_uploader("2차: 온도/명칭", type=['jpg','png','pdf'], key="up2")
    with col_f3: f3 = st.file_uploader("3차: 설비 배치", type=['jpg','png','pdf'], key="up3")

img_base = load_drawing_file(f3) or load_drawing_file(f2) or load_drawing_file(f1)

if img_base:
    st.image(img_base, caption="현재 분석 중인 도면 레이어", use_container_width=True)
else:
    st.info("상단 업로드 관리바에서 도면 파일을 등록해 주세요.")