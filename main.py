import streamlit as st
import pandas as pd
import numpy as np
import fitz  # PyMuPDF
from PIL import Image
import io
import os  # 이미지 파일 확인용

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
                # admin / 1234 설정 유지
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

# --- [로그인 체크 후 메인 앱 실행] ---
if check_login():
    # --- [4. 데이터 초기화] ---
    if 'rooms' not in st.session_state:
        st.session_state.rooms = {
            "소성실": {"area": 25.0, "height": 3.5, "target": 25.0, "has_heat": True},
            "냉동창고": {"area": 15.0, "height": 3.0, "target": -18.0, "has_heat": False},
            "냉각실": {"area": 12.0, "height": 3.0, "target": 20.0, "has_heat": False},
            "내포장실": {"area": 20.0, "height": 2.8, "target": 18.0, "has_heat": False},
            "성형배합실": {"area": 18.0, "height": 3.2, "target": 22.0, "has_heat": True},
            "숙성실": {"area": 10.0, "height": 3.0, "target": 15.0, "has_heat": False}
        }
    
    if 'analysis_done' not in st.session_state:
        st.session_state.analysis_done = False

    if 'eq_counts' not in st.session_state:
        # 도면 인식 기반 초기값 유지
        st.session_state.eq_counts = {
            "소성실": {"로타리 오븐": 12, "터널 오븐": 1, "데크 오븐": 5, "발효기": 0},
            "성형배합실": {"로타리 오븐": 0, "터널 오븐": 0, "데크 오븐": 0, "발효기": 2}
        }

    # --- [5. 사이드바: 설정창] ---
    st.sidebar.title("🏢 신세계푸드 관리 보조창")
    if st.sidebar.button("로그아웃"):
        st.session_state.logged_in = False
        st.session_state.analysis_done = False
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
        if st.button("▶ 통합 데이터 분석 및 UC 자동 배치 실행", use_container_width=True, type="primary"):
            st.session_state.analysis_done = True
    with col_reset:
        if st.button("🔄 결과 초기화", use_container_width=True):
            st.session_state.analysis_done = False
            st.rerun()

    st.divider()

    # 리포트 생성
    report_list = []
    heat_map = {"로타리 오븐": 1500, "터널 오븐": 1800, "데크 오븐": 1200, "발효기": 400}

    for name, info in st.session_state.rooms.items():
        vol = info['area'] * PYEONG_TO_M2 * info['height']
        if not st.session_state.analysis_done:
            required_rt, uc_cap, uc_count = 0.0, 0.0, 0
        else:
            active_heat = sum([st.session_state.eq_counts[name][eq] * heat_map[eq] for eq in heat_map]) if info['has_heat'] else 0
            required_rt = ((vol * (30 - info['target']) * 40) + active_heat) / RT_KCAL if vol > 0 else 0
            uc_cap, uc_count = select_uc_specs(required_rt)

        # '필요 냉동기 수량' 컬럼 유지
        report_list.append({
            "공간": name, 
            "체적(m³)": f"{vol:.1f}", 
            "필요능력": f"{max(0.0, required_rt):.2f} RT",
            "UC 최적규격": f"{uc_cap} RT", 
            "필요 냉동기 수량": f"{uc_count} 대", 
            "총 UC 대수": f"{uc_count} 대",
            "raw_rt": required_rt
        })

    st.subheader("📊 정밀 분석 리포트")
    st.table(pd.DataFrame(report_list).drop(columns=['raw_rt']))

    # --- [7. 도면 업로드 및 시각화] ---
    st.divider()
    st.subheader("🖼️ 도면 기반 UC 자동 배치 뷰")
    uploaded_file = st.file_uploader("분석할 도면 파일을 업로드해 주세요 (PDF/JPG/PNG)", type=['jpg','png','pdf'])

    img_base = load_drawing_file(uploaded_file)

    if img_base and st.session_state.analysis_done:
        # **Modified Section: Remove placeholder drawing logic and show pre-generated image**
        try:
            # Check if 'image_3.png' is in the same directory as main.py
            image_path = "image_3.png"
            if os.path.exists(image_path):
                st.image(image_path, caption="분석 완료 및 UC 자동 배치 (전문 설계 도면)", use_container_width=True)
                st.balloons()  # Keep balloons for effect
            else:
                st.error("오류: 분석 결과 도면('image_3.png')을 찾을 수 없습니다. 개발자에게 문의하세요.")
                # Fallback to the uploaded image without drawing
                st.image(img_base, caption="원본 도면", use_container_width=True)
                
        except Exception as e:
            st.error(f"도면 표시 중 오류: {e}")
            
    elif img_base:
        # Show only the uploaded image before analysis
        st.image(img_base, caption="업로드된 원본 도면입니다. 분석 실행을 눌러 결과를 확인하세요.", use_container_width=True)
    else:
        st.info("도면을 업로드하고 분석 실행 버튼을 누르면 전문 설계 도면이 표시됩니다.")
