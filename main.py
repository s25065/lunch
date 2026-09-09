import calendar
import datetime
import re
import requests
import streamlit as st

# ==========================================
# 0. 기본 설정 및 상수 정의
# ==========================================
st.set_page_config(
    page_title="학교 급식 달력 (수요일)",
    page_icon="🍱",
    layout="wide"
)

# 알레르기 번호 -> 식재료 매핑 사전 (1~19번)
ALLERGY_MAP = {
    "1": "난류", "2": "우유", "3": "메밀", "4": "땅콩", "5": "대두",
    "6": "밀", "7": "고등어", "8": "게", "9": "새우", "10": "돼지고기",
    "11": "복숭아", "12": "토마토", "13": "아황산류", "14": "호두", "15": "닭고기",
    "16": "쇠고기", "17": "오징어", "18": "조개류", "19": "잣"
}


# ==========================================
# 1. 헬퍼 함수
# ==========================================
def convert_allergy_numbers(text):
    """메뉴 텍스트 안의 알레르기 번호 (예: 1.2.5.)를 실제 식재료 이름으로 변환합니다."""
    def replace_match(match):
        nums = match.group(0).strip('.').split('.')
        names = [ALLERGY_MAP.get(n, n) for n in nums if n in ALLERGY_MAP]
        return f" ({', '.join(names)})" if names else ""

    # 메뉴명 뒤에 붙는 숫자 패턴(예: .1.2.5.) 감지
    return re.sub(r'(\.\d+)+', replace_match, text)


@st.cache_data(ttl=3600)
def fetch_meal_info(api_key, edu_code, school_code, year, month):
    """NEIS API를 호출하여 한 달치 급식 데이터를 가져옵니다."""
    # 해당 월의 시작일과 말일 계산
    _, last_day = calendar.monthrange(year, month)
    from_ymd = f"{year}{month:02d}01"
    to_ymd = f"{year}{month:02d}{last_day:02d}"

    url = "https://open.neis.go.kr/hub/mealServiceDietInfo"
    params = {
        "KEY": api_key,
        "Type": "json",
        "pIndex": 1,
        "pSize": 100,
        "ATPT_OFCDC_SC_CODE": edu_code,
        "SD_SCHUL_CODE": school_code,
        "MLSV_FROM_YMD": from_ymd,
        "MLSV_TO_YMD": to_ymd
    }

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        # API 응답 결과 확인
        if "mealServiceDietInfo" in data:
            return data["mealServiceDietInfo"][1]["row"], None
        elif "RESULT" in data:
            # INFO-200: 해당 조건의 데이터가 없는 경우
            if data["RESULT"]["CODE"] == "INFO-200":
                return [], None
            return None, f"API 오류: {data['RESULT']['MESSAGE']} ({data['RESULT']['CODE']})"
        else:
            return None, "알 수 없는 응답 구조입니다."
            
    except requests.exceptions.RequestException as e:
        return None, f"통신 네트워크 오류가 발생했습니다: {e}"


# ==========================================
# 2. 사이드바 구성
# ==========================================
st.sidebar.title("⚙️ 설정")

# NEIS API Key 검증
api_key = st.secrets.get("NEIS_KEY")
if not api_key:
    st.error("⚠️ `st.secrets['NEIS_KEY']` 설정이 존재하지 않습니다.")
    st.info("`.streamlit/secrets.toml` 파일에 `NEIS_KEY = '발급받은키'`를 입력해 주세요.")
    st.stop()

# 학교 정보 입력 (기본값 설정)
st.sidebar.subheader("🏫 학교 정보")
edu_code = st.sidebar.text_input("시도교육청코드", value="J10", help="예: 서울 B10, 경기 J10 등")
school_code = st.sidebar.text_input("표준학교코드", value="7530851", help="학교 고유 코드 7자리")

st.sidebar.divider()

# 알레르기 변환 토글
convert_allergy = st.sidebar.toggle("알레르기 식품명으로 변환", value=False)

# 알레르기 안내 표
with st.sidebar.expander("ℹ️ 알레르기 번호 안내표"):
    st.markdown("\n".join([f"- **{k}**: {v}" for k, v in ALLERGY_MAP.items()]))


# ==========================================
# 3. 메인 화면 - 상단 컨트롤러
# ==========================================
st.title("🍱 수요일 급식 달력")

# 오늘 날짜 정보
today = datetime.date.today()

col1, col2, col3, col4 = st.columns([1, 1, 2, 1])

with col1:
    selected_year = st.selectbox("연도 선택", range(today.year - 1, today.year + 2), index=1)

with col2:
    selected_month = st.selectbox("월 선택", range(1, 13), index=today.month - 1)

with col3:
    meal_filter = st.radio(
        "급식 종류",
        ["전체 보기", "중식만 보기", "석식만 보기"],
        horizontal=True
    )

with col4:
    only_wednesday = st.checkbox("수요일만 보기", value=True)

st.divider()

# ==========================================
# 4. 데이터 조회 및 정리
# ==========================================
try:
    meal_data_list, error_msg = fetch_meal_info(
        api_key, edu_code, school_code, selected_year, selected_month
    )

    if error_msg:
        st.error(f"📡 API 통신 오류가 발생했습니다.\n\n{error_msg}")
        st.stop()

    # 날짜별, 급식 종류별 데이터 매핑
    meals_by_date = {}
    for row in meal_data_list:
        date_str = row["MLSV_YMD"]
        meal_type = row["MMEAL_SC_NM"]  # 조식, 중식, 석식 등
        
        # BR태그 제거 및 줄바꿈 처리
        raw_dish = row["DDISH_NM"].replace("<br/>", "\n")
        
        if convert_allergy:
            raw_dish = convert_allergy_numbers(raw_dish)

        if date_str not in meals_by_date:
            meals_by_date[date_str] = {}
        
        meals_by_date[date_str][meal_type] = raw_dish.split("\n")

except Exception as e:
    st.error(f"💻 데이터 처리 중 화면 구성 오류가 발생했습니다: {e}")
    st.stop()


# ==========================================
# 5. 달력 화면 렌더링
# ==========================================
try:
    # 월~금(0~4) 기준 주간 달력 생성
    cal = calendar.Calendar(firstweekday=0)
    month_days = cal.monthdayscalendar(selected_year, selected_month)

    # 요일 헤더 표시 (월~금)
    weekdays = ["월", "화", "수", "목", "금"]
    cols = st.columns(5)
    for idx, day_name in enumerate(weekdays):
        if day_name == "수":
            cols[idx].markdown("<h4 style='text-align: center; color: #1E88E5;'>수 (선택)</h4>", unsafe_allow_html=True)
        else:
            style = "opacity: 0.3;" if only_wednesday else ""
            cols[idx].markdown(f"<h4 style='text-align: center; {style}'>{day_name}</h4>", unsafe_allow_html=True)

    # 주별 달력 카드 생성
    for week in month_days:
        cols = st.columns(5)
        
        # 월요일부터 금요일까지(인덱스 0~4)만 순회
        for idx in range(5):
            day = week[idx]
            is_wednesday = (idx == 2)  # 월=0, 화=1, 수=2, 목=3, 금=4
            
            with cols[idx]:
                if day == 0:
                    # 빈 날짜 칸
                    st.html("<div style='border: 1px solid #ddd; border-radius: 8px; padding: 10px; min-height: 150px; background-color: #f9f9f9;'></div>")
                    continue

                # '수요일만 보기' 옵션이 켜져 있고 수요일이 아닌 경우 흐리게 처리
                if only_wednesday and not is_wednesday:
                    st.html(f"""
                    <div style='border: 1px dashed #e0e0e0; border-radius: 8px; padding: 10px; min-height: 180px; background-color: #fafafa; opacity: 0.25;'>
                        <div style='color: #aaa;'><b>{day}일</b></div>
                    </div>
                    """)
                    continue

                date_obj = datetime.date(selected_year, selected_month, day)
                date_key = date_obj.strftime("%Y%m%d")
                
                # 오늘 여부 확인
                is_today = (date_obj == today)
                today_badge = " <span style='background-color:#ff4b4b; color:white; padding:2px 6px; border-radius:4px; font-size:12px;'>TODAY</span>" if is_today else ""
                
                header_html = f"<b>{day}일</b>{today_badge}"
                content_html = ""
                
                # 해당 날짜에 데이터가 있는지 확인
                if date_key in meals_by_date:
                    day_meals = meals_by_date[date_key]
                    
                    # 필터 적용
                    filtered_types = []
                    if meal_filter == "중식만 보기":
                        filtered_types = ["중식"]
                    elif meal_filter == "석식만 보기":
                        filtered_types = ["석식"]
                    else:
                        filtered_types = list(day_meals.keys())
                        
                    has_meal = False
                    for m_type in filtered_types:
                        if m_type in day_meals:
                            has_meal = True
                            # 급식 유형별 색상 배정
                            if m_type == "중식":
                                badge_color = "#1E88E5" # 파란색
                            elif m_type == "석식":
                                badge_color = "#E53935" # 빨간색
                            else:
                                badge_color = "#43A047" # 초록색 (조식 등)
                                
                            content_html += f"<div style='margin-top:6px;'><span style='color:{badge_color}; font-weight:bold;'>[{m_type}]</span></div>"
                            
                            # 메뉴 목록을 줄 단위로 나열
                            for dish in day_meals[m_type]:
                                if dish.strip():
                                    content_html += f"<div style='font-size:13px; line-height:1.4;'>• {dish.strip()}</div>"
                    
                    if not has_meal:
                        content_html += "<div style='color: #888; font-size:12px; margin-top:10px;'>해당 식단 없음</div>"
                else:
                    content_html += "<div style='color: #aaa; font-size:12px; margin-top:10px;'>급식 없음</div>"

                # 테두리 및 카드 스타일 (오늘 날짜 및 수요일 스타일 적용)
                border_style = "2px solid #1E88E5" if is_wednesday else "1px solid #e0e0e0"
                card_style = f"border: {border_style}; background-color: #ffffff;"
                if is_today:
                    card_style = "border: 2px solid #ff4b4b; background-color: #fff0f0;"

                st.html(f"""
                <div style='{card_style} border-radius: 8px; padding: 10px; min-height: 180px; margin-bottom: 10px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);'>
                    <div>{header_html}</div>
                    <hr style='margin: 6px 0;'>
                    {content_html}
                </div>
                """)

except Exception as e:
    st.error(f"🖥️ 화면 렌더링 도중 예외가 발생했습니다: {e}")
