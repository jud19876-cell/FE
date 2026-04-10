import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io

# --- [1. 기본 설정 및 상수] ---
RT_KCAL = 3024
PYEONG_TO_M2 = 3.3058

st.set_page_config(layout="wide", page_title="신세계푸드 인천공장 분석 시스템")

# --- [2. 로그인 시스템] ---
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
                if auth_id == "admin" and auth_pw == "1234":
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

# --- [메인 앱 실행] ---
if check_login():
    # --- [4. 데이터 초기화: 도면 인식 데이터 반영] ---
    if 'rooms' not in st.session_state:
        # 도면 '대경푸드빌 변경안 3층' 기준 실별 좌표 매핑 
        st.session_state.rooms = {
            "소성실": {"area": 25.0, "height": 3.5, "target": 25.0, "x": 280, "y": 880, "flow": "Right", "has_heat": True},
            "냉동창고": {"area": 15.0, "height": 3.0, "target": -18.0, "x": 820, "y": 120, "flow": "Down", "has_heat": False},
            "냉각실": {"area": 12.0, "height": 3.0, "target": 20.0, "x": 400, "y": 720, "flow": "Up", "has_heat": False},
            "내포장실": {"area": 20.0, "height": 2.8, "target": 18.0, "x": 510, "y": 470, "flow": "Left", "has_heat": False},
            "성형배합실": {"area": 18.0, "height": 3.2, "target": 22.0, "x": 780, "y": 620, "flow": "Left", "has_heat": True},
            "숙성실": {"area": 10.0, "height": 3.0, "target": 15.0, "x": 920, "y": 720, "flow": "Up", "has_heat": False}
        }
    
    if 'analysis_done' not in st.session_state:
        st.session_state.analysis_done = False

    # 도면 분석 기반 설비 초기값 
    if 'eq_counts' not in st.session_state:
        st.session_state.eq_counts = {
            "소성실": {"로타리 오븐": 12, "터널 오븐": 1, "데크 오븐": 5, "발효기": 0},
            "성형배합실": {"로타리 오븐": 0, "터널 오븐": 0, "데크 오븐": 0, "발효기": 2}
        }

    # --- [5. 사이드바: 설정창] ---
    st.sidebar.title("🏢 신세계푸드 관리 보조창")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.rerun()

    for room_name, info in st.session_state.rooms.items():
        with st.sidebar.expander(f"🏠 {room_name}"):
            info['area'] = st.number_input(f"면적(평)", 0.0, 500.0, float(info['area']), key=f"a_{room_name}")
            info['target'] = st.number_input(f"목표온도(℃)", -50.0, 50.0, float(info['target']), key=f"t_{room_name}")
            if info['has_heat']:
                st.write("**🔥 설비 설정**")
                for eq in st.session_state.eq_counts[room_name]:
                    st.session_state.eq_counts[room_name][eq] = st.number_input(f"{eq}", 0, 50, st.session_state.eq_counts[room_name][eq], key=f"eq_{room_name}_{eq}")

    # --- [6. 메인 화면] ---
    st.title("🏭 신세계푸드 인천공장 통합 분석 시스템")
    
    if st.button("▶ 통합 데이터 분석 및 UC 자동 배치 실행", use_container_width=True, type="primary"):
        st.session_state.analysis_done = True

    # 분석 리포트 계산
    report_list = []
    heat_map = {"로타리 오븐": 1500, "터널 오븐": 1800, "데크 오븐": 1200, "발효기": 400}
    for name, info in st.session_state.rooms.items():
        vol = info['area'] * PYEONG_TO_M2 * info['height']
        if not st.session_state.analysis_done:
            rt, u_cap, u_cnt = 0.0, 0.0, 0
        else:
            h_load = sum([st.session_state.eq_counts[name][eq] * heat_map[eq] for eq in heat_map]) if info['has_heat'] else 0
            rt = ((vol * (30 - info['target']) * 40) + h_load) / RT_KCAL if vol > 0 else 0
            u_cap, u_cnt = select_uc_specs(rt)
        
        report_list.append({
            "공간": name, "필요능력": f"{max(0.0, rt):.2f} RT",
            "UC 최적규격": f"{u_cap} RT", "필요 냉동기 수량": f"{u_cnt} 대", "총 UC 대수": f"{u_cnt} 대", "raw_rt": rt
        })

    st.subheader("📊 정밀 분석 리포트")
    st.table(pd.DataFrame(report_list).drop(columns=['raw_rt']))

    # --- [7. 도면 업로드 및 실시간 이미지 생성] ---
    st.divider()
    st.subheader("🖼️ 도면 기반 UC 자동 배치 뷰")
    uploaded_file = st.file_uploader("분석할 도면 업로드 (PDF/JPG/PNG)", type=['jpg','png','pdf'])
    img_base = load_drawing_file(uploaded_file)

    if img_base and st.session_state.analysis_done:
        # 도면 위에 직접 그리기 시작 
        working_img = img_base.copy()
        draw = ImageDraw.Draw(working_img, "RGBA")
        
        for room_res in report_list:
            name = room_res['공간']
            info = st.session_state.rooms[name]
            u_cap, u_cnt = select_uc_specs(room_res['raw_rt'])
            
            if u_cnt > 0:
                for c in range(u_cnt):
                    # 공학적 효율 배치 (벽면 기준 순차 배치)
                    ox, oy = info['x'] + (c * 40), info['y']
                    # 1. UC 본체 (진한 파란색)
                    draw.rectangle([ox-18, oy-12, ox+18, oy+12], fill=(0, 51, 153, 230), outline="white", width=2)
                    # 2. 기류 방향 화살표
                    f_len = 45
                    if info['flow'] == "Right": draw.line([(ox, oy), (ox+f_len, oy)], fill=(0, 204, 255, 200), width=4)
                    elif info['flow'] == "Down": draw.line([(ox, oy), (ox, oy+f_len)], fill=(0, 204, 255, 200), width=4)
                    elif info['flow'] == "Up": draw.line([(ox, oy), (ox, oy-f_len)], fill=(0, 204, 255, 200), width=4)
                    # 3. 데이터 패널 텍스트 (간이 표시)
                    draw.text((ox-20, oy+15), f"UC-{u_cap}RT", fill="blue")

        st.image(working_img, caption="시스템이 직접 생성한 UC 자동 배치 도면", use_container_width=True)
        st.balloons()
    elif img_base:
        st.image(img_base, caption="원본 도면", use_container_width=True)
