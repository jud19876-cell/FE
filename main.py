import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
from PIL import Image, ImageDraw
import io

# --- [1. 기본 설정 및 상수] ---
RT_KCAL = 3024
PYEONG_TO_M2 = 3.3058

st.set_page_config(layout="wide", page_title="신세계푸드 인천공장 분석 시스템")

# --- [2. 로그인 시스템 함수] ---
def check_login():
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        st.markdown("<br><br>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns([1, 1, 1])
        with col2:
            st.title("🔒 시스템 접속")
            auth_id = st.text_input("아이디(ID)")
            auth_pw = st.text_input("비밀번호(Password)", type="password")
            
            if st.button("로그인", use_container_width=True):
                if auth_id == "admin" and auth_pw == "shinsegae123":
                    st.session_state.logged_in = True
                    st.rerun()
                else:
                    st.error("아이디 또는 비밀번호가 틀렸습니다.")
        return False
    return True

# --- [3. 유틸리티 함수] ---
def select_uc_specs(required_rt):
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

# --- [로그인 체크 후 메인 앱 실행] ---
if check_login():
    # --- [4. 데이터 초기화] ---
    if 'rooms' not in st.session_state:
        st.session_state.rooms = {
            "소성실": {"area": 25.0, "height": 3.5, "target": 25.0, "x": 400, "y": 800, "has_heat": True},
            "냉동창고": {"area": 15.0, "height": 3.0, "target": -18.0, "x": 900, "y": 150, "has_heat": False},
            "냉각실": {"area": 12.0, "height": 3.0, "target": 20.0, "x": 450, "y": 700, "has_heat": False},
            "내포장실": {"area": 20.0, "height": 2.8, "target": 18.0, "x": 480, "y": 480, "has_heat": False},
            "성형배합실": {"area": 18.0, "height": 3.2, "target": 22.0, "x": 800, "y": 550, "has_heat": True},
            "숙성실": {"area": 10.0, "height": 3.0, "target": 15.0, "x": 900, "y": 700, "has_heat": False}
        }
    
    # 분석 실행 여부 플래그 추가
    if 'analysis_done' not in st.session_state:
        st.session_state.analysis_done = False

    if 'eq_counts' not in st.session_state:
        st.session_state.eq_counts = {room: {eq: 0 for eq in ["로터리오븐", "터널오븐", "데크오븐", "발효기", "이가데치기"]} 
                                     for room, info in st.session_state.rooms.items() if info['has_heat']}

    # --- [5. 사이드바: 설정창] ---
    st.sidebar.title("🏢 신세계푸드 관리 보조창")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.session_state.analysis_done = False # 로그아웃 시 분석 상태도 초기화
        st.rerun()

    for room_name, info in st.session_state.rooms.items():
        with st.sidebar.expander(f"🏠 {room_name}"):
            info['area'] = st.number_input(f"면적(평)", 0.0, 500.0, float(info['area']), key=f"a_{room_name}")
            info['height'] = st.number_input(f"높이(m)", 0.0, 10.0, float(info['height']), key=f"h_{room_name}")
            info['target'] = st.number_input(f"목표온도(℃)", -50.0, 50.0, float(info['target']), key=f"t_{room_name}")
            
            if info['has_heat']:
                st.write("**🔥 설비 대수 입력**")
                for eq_type in st.session_state.eq_counts[room_name]:
                    st.session_state.eq_counts[room_name][eq_type] = st.number_input(
                        f"{eq_type}", 0, 50, st.session_state.eq_counts[room_name][eq_type], key=f"eq_{room_name}_{eq_type}"
                    )

    # --- [6. 메인 화면] ---
    st.title("🏭 신세계푸드 인천공장 통합 분석 시스템")
    
    col_btn, col_reset = st.columns([5, 1])
    with col_btn:
        # 버튼을 누르면 분석 플래그를 True로 변경
        if st.button("▶ 통합 데이터 분석 및 UC 자동 배치 실행", use_container_width=True, type="primary"):
            st.session_state.analysis_done = True
            
    with col_reset:
        if st.button("🔄 결과 초기화", use_container_width=True):
            for r in st.session_state.eq_counts:
                for e in st.session_state.eq_counts[r]: st.session_state.eq_counts[r][e] = 0
            st.session_state.analysis_done = False # 결과 초기화 시 수치 0화
            st.rerun()

    st.divider()

    # 리포트 데이터 생성
    report_list = []
    heat_map = {"로터리오븐": 1500, "터널오븐": 1800, "데크오븐": 1200, "발효기": 400, "이가데치기": 800}

    for name, info in st.session_state.rooms.items():
        vol = info['area'] * PYEONG_TO_M2 * info['height']
        
        # 분석 실행 전에는 모든 산출값을 0으로 고정
        if not st.session_state.analysis_done:
            required_rt = 0.0
            uc_cap = 0.0
            uc_count = 0
        else:
            active_heat = sum([st.session_state.eq_counts[name][eq] * heat_map[eq] for eq in heat_map]) if info['has_heat'] else 0
            required_rt = ((vol * (30 - info['target']) * 40) + active_heat) / RT_KCAL if vol > 0 else 0
            uc_cap, uc_count = select_uc_specs(required_rt)

        report_list.append({
            "공간": name, "체적(m³)": f"{vol:.1f}", "필요능력": f"{max(0.0, required_rt):.2f} RT",
            "UC 최적규격": f"{uc_cap} RT", "총 UC 대수": f"{uc_count} 대", "raw_rt": required_rt
        })

    st.subheader("📊 정밀 분석 리포트")
    st.table(pd.DataFrame(report_list).drop(columns=['raw_rt']))

    # 그래프는 추세 확인용이므로 상시 노출 (또는 필요 시 이것도 analysis_done에 연동 가능)
    st.subheader("📈 09:00~18:00 실별 온도 변화 추이")
    chart_data = pd.DataFrame(index=[f"{h:02d}:00" for h in range(9, 19)])
    for name, info in st.session_state.rooms.items():
        eq_sum = sum(st.session_state.eq_counts[name].values()) if info['has_heat'] else 0
        chart_data[name] = [round(info['target'] + (eq_sum * 1.5 if h != 12 else 0.5) + np.random.uniform(-0.1, 0.1), 1) for h in range(9, 19)]
    st.line_chart(chart_data)

    # 도면 및 UC 배치
    st.divider()
    st.subheader("🖼️ 도면 기반 UC 자동 배치 뷰")
    with st.expander("📂 도면 레이어 통합 업로드", expanded=True):
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1: f1 = st.file_uploader("1차: 구역 도면", type=['jpg','png','pdf'], key="up1")
        with col_f2: f2 = st.file_uploader("2차: 온도/명칭", type=['jpg','png','pdf'], key="up2")
        with col_f3: f3 = st.file_uploader("3차: 설비 배치", type=['jpg','png','pdf'], key="up3")

    img_base = load_drawing_file(f3) or load_drawing_file(f2) or load_drawing_file(f1)

    if img_base and st.session_state.analysis_done:
        drawn_img = img_base.copy()
        draw = ImageDraw.Draw(drawn_img, "RGBA")
        for room_res in report_list:
            name = room_res['공간']
            info = st.session_state.rooms[name]
            # 실제 분석 결과값으로 그리기
            u_cap, u_cnt = select_uc_specs(room_res['raw_rt'])
            if u_cnt > 0:
                for c in range(u_cnt):
                    ox, oy = info['x'] + (c * 35), info['y']
                    draw.rectangle([ox-15, oy-15, ox+15, oy+15], fill=(0, 0, 255, 180))
        st.image(drawn_img, caption="분석 완료 및 UC 자동 배치", use_container_width=True)
        st.balloons()
    elif img_base:
        st.image(img_base, caption="도면이 업로드되었습니다. 분석 실행 버튼을 누르세요.", use_container_width=True)
    else:
        st.info("도면을 업로드하고 분석 실행 버튼을 누르세요.")
