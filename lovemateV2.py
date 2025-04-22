#streamlit run profile_match_gui.py
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import streamlit as st
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
from PIL import Image
import base64
import html
import numpy as np
import json

def image_to_base64(img):
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_b64 = base64.b64encode(buffered.getvalue()).decode()
    return img_b64

# ---------------------------
# Google Sheets 연결
# ---------------------------
def load_sheet(sheet_name):
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    key_dict = st.secrets["google_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(key_dict), scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_url("https://docs.google.com/spreadsheets/d/1jnZqqmZB8zWau6CHqxm-L9fxlXDaWxOaJm6uDcE6WN0/edit")
    worksheet = sheet.worksheet(sheet_name)
    raw_values = worksheet.get_all_values()
    header = raw_values[1]
    data = raw_values[2:]
    df = pd.DataFrame(data, columns=header)
    return df

def get_drive_service():
    scope = ['https://www.googleapis.com/auth/drive.readonly']
    key_dict = st.secrets["google_service_account"]
    creds = ServiceAccountCredentials.from_json_keyfile_dict(dict(key_dict), scope)
    return build('drive', 'v3', credentials=creds)

def get_drive_image(file_id):
    service = get_drive_service()
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)
    image = Image.open(fh)
    image.thumbnail((200, 200))  # 크기 축소
    return image

def extract_drive_file_id(url):
    """
    다양한 Google Drive 공유 URL에서 파일 ID 추출
    """
    if "id=" in url:
        return url.split("id=")[-1].split("&")[0]
    elif "/file/d/" in url:
        return url.split("/file/d/")[-1].split("/")[0]
    return ""

# ---------------------------
# 매칭 로직
# ---------------------------
def match_members(df, match_data):
    target_df = df[df["회원 ID"] == match_data["memberId"]]
    if target_df.empty:
        st.warning("입력한 회원 ID에 해당하는 회원이 없습니다.")
        return pd.DataFrame()

    target = target_df.iloc[0]
    filtered = df.copy()

    numeric_fields = ["상태 FLAG", "본인(키)", "본인(나이)"]
    for field in numeric_fields:
        filtered[field] = pd.to_numeric(filtered[field], errors="coerce")

    filtered = filtered[
        (filtered["성별"] != target["성별"]) &
        (filtered["상태 FLAG"] >= 4) &
        (~filtered["매칭권"].fillna("").str.contains("시크릿"))
        ]

    # 채널 필터
    if match_data["channel"] and match_data["channel"] != ["전체"]:
        valid_channels = []
        channel_map = {"프립(F)": "F", "네이버(N)": "N", "프사오(O)": "O", "인스타(A)": "A", "기타(B)": "B", "기타2(C)": "C"}
        for ch in match_data["channel"]:
            if ch in channel_map:
                valid_channels.append(channel_map[ch])
        filtered = filtered[filtered["주문번호"].astype(str).str[0].isin(valid_channels)]

    if match_data["faces"]:
        filtered = filtered[filtered["등급(외모)"].isin(match_data["faces"])]

    if match_data["abilitys"]:
        filtered = filtered[filtered["등급(능력)"].isin(match_data["abilitys"])]

    if match_data["faceShape"] and match_data["faceShape"] != ["전체"]:
        filtered = filtered[filtered["본인(외모)"].isin(match_data["faceShape"])]

    cond = match_data["conditions"]
    try:
        if cond[0]:
            min_h, max_h = map(int, str(target["이상형(키)"]).replace(" ", "").split("~"))
            filtered = filtered[filtered["본인(키)"].between(min_h, max_h)]
    except:
        pass

    try:
        if cond[1]:
            min_y, max_y = map(int, str(target["이상형(나이)"]).replace(" ", "").split("~"))
            filtered = filtered[filtered["본인(나이)"].between(min_y, max_y)]
    except:
        pass

    condition_fields = [
        "이상형(사는 곳)", "이상형(학력)", "이상형(흡연)", "이상형(종교)",
        "이상형(회사 규모)", "이상형(근무 형태)", "이상형(음주)", "이상형(문신)"
    ]
    profile_fields = [
        "본인(거주지-분류)", "본인(학력)", "본인(흡연)", "본인(종교)",
        "본인(회사 규모)", "본인(근무 형태)", "본인(음주)", "본인(문신)"
    ]

    for i in range(2, 10):
        if cond[i]:
            try:
                ideals = set(map(str.strip, str(target[condition_fields[i - 2]]).split(',')))
                filtered = filtered[filtered[profile_fields[i - 2]].isin(ideals)]
            except:
                pass

    if match_data["afterDate"]:
        try:
            after_date = pd.to_datetime(match_data["afterDate"])
            filtered["설문 날짜"] = pd.to_datetime(filtered["설문 날짜"], errors="coerce")
            filtered = filtered[filtered["설문 날짜"] >= after_date]
        except:
            pass

    sent_ids = str(target.get("받은 프로필 목록", "")).split(",") if pd.notna(target.get("받은 프로필 목록")) else []
    sent_ids_set = set(sent_ids)
    filtered = filtered[~filtered["회원 ID"].astype(str).isin(sent_ids_set)]

    return filtered


# ---------------------------
# Streamlit UI
# ---------------------------

st.set_page_config(page_title="회원 매칭 시스템", layout="wide")

st.title("\U0001F4CB 회원 프로필 매칭 시스템")

try:
    member_df = load_sheet("회원")
    profile_df = load_sheet("프로필")
except Exception as e:
    st.error("시트를 불러오는 데 실패했습니다: " + str(e))
    st.stop()

with st.sidebar:
    st.subheader("\U0001F50D 필터 설정")

    # 회원 ID 입력 + 회원 정보 조회 버튼 한 줄로
    id_col1, id_col2 = st.columns(2)
    memberId = id_col1.text_input("회원 ID 입력", "2795", label_visibility="collapsed")
    info_button = id_col2.button("\U0001F464 회원 정보 조회", use_container_width=True)

    # 채널 선택 + 얼굴형 선택 나란히
    ch_col1, ch_col2 = st.columns(2)
    channel_options = ["전체", "프립(F)", "네이버(N)", "프사오(O)", "인스타(A)", "기타(B)", "기타2(C)"]
    channel = ch_col1.multiselect("채널 선택", channel_options, default=["전체"])

    all_faceshapes = ["전체"] + sorted(member_df["본인(외모)"].dropna().unique().tolist())
    face_shape = ch_col2.multiselect("선호 얼굴형", all_faceshapes, default=["전체"])

    # 외모 등급 + 능력 등급 나란히
    grade_col1, grade_col2 = st.columns(2)
    face_order = ["상", "중상", "중", "중하", "하"]
    face_values = sorted(set(member_df["등급(외모)"].dropna()) - set(face_order))
    faces = grade_col1.multiselect("외모 등급", face_order + face_values)

    ability_order = ["상", "중", "하"]
    ability_values = sorted(set(member_df["등급(능력)"].dropna()) - set(ability_order))
    abilitys = grade_col2.multiselect("능력 등급", ability_order + ability_values)

    after_date = st.date_input("설문 이후 날짜 필터", value=None)

    st.markdown("**추가 필터:**")

    # ✅ 선택 조건 자동 반영
    selected_conditions = st.session_state.get("selected_conditions", [])

    cols = st.columns(4)
    conds = [
        cols[0].checkbox("키", value="키" in selected_conditions),
        cols[1].checkbox("나이", value="나이" in selected_conditions),
        cols[2].checkbox("거주지", value="거주지" in selected_conditions),
        cols[3].checkbox("학력", value="학력" in selected_conditions),
        cols[0].checkbox("흡연", value="흡연" in selected_conditions),
        cols[1].checkbox("종교", value="종교" in selected_conditions),
        cols[2].checkbox("회사 규모", value="회사 규모" in selected_conditions or "회사규모" in selected_conditions),
        cols[3].checkbox("근무 형태", value="근무 형태" in selected_conditions or "근무형태" in selected_conditions),
        cols[0].checkbox("음주", value="음주" in selected_conditions),
        cols[1].checkbox("문신", value="문신" in selected_conditions)
    ]

    match_button = st.button("\U0001F50E 프로필 추출")

if "member_info_triggered" not in st.session_state:
    st.session_state["member_info_triggered"] = False
if "selected_conditions" not in st.session_state:
    st.session_state["selected_conditions"] = []
if "match_triggered" not in st.session_state:
    st.session_state["match_triggered"] = False

if info_button:
    st.session_state["member_info_triggered"] = True

if match_button:
    st.session_state["match_triggered"] = True

# 회원 정보 조회 출력 컨테이너 (항상 위)
info_container = st.container()
# 프로필 추출 결과 출력 컨테이너 (항상 아래)
match_container = st.container()


with info_container:
    if st.session_state["member_info_triggered"]:
        target_member = member_df[member_df["회원 ID"] == memberId]
        if target_member.empty:
            st.warning("입력한 회원 ID에 해당하는 회원이 없습니다.")
        else:
            m = target_member.iloc[0]
            member_id_str = m.get("회원 ID", "")
            st.markdown(f"### 🔍 {member_id_str} 회원 기본 정보")

            info_rows = [
                ("프로필 ID", m.get("프로필 ID", "")),
                ("카톡 ID", f"{m.get('주문번호', '')}_{m.get('매칭권', '')}"),
                ("주문번호", m.get("주문번호", "")),
                ("매칭권", m.get("매칭권", "")),
                ("상태", m.get("상태 FLAG", "")),
                ("담당자", m.get("담당자", "")),
                ("등급(외모 - 능력)", f"{m.get('등급(외모)', '')} - {m.get('등급(능력)', '')}"),
                ("받은 프로필 수", m.get("받은 프로필 수", "")),
                ("선택 조건", m.get("선택 조건", "")),
                ("기존 회원", m.get("기존 회원", "")),
                ("비고", m.get("비고", "")),
                ("본인 얼굴상", m.get("본인(외모)", "")),
            ]

            for i in range(0, len(info_rows), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(info_rows):
                        label, value = info_rows[i + j]
                        cols[j].markdown(f"**{label}**: {value}")

            # 받은 프로필 목록
            if m.get("받은 프로필 목록", ""):
                with st.expander("📨 받은 프로필 목록 보기"):
                    st.markdown(m.get("받은 프로필 목록", ""))

            # 프로필 전달
            profile_text = m.get("이상형", "")
            with st.expander("📋 이상형 내용 보기"):
                st.code(profile_text, language="text")

            # 프로필 전달
            profile_text = m.get("프로필(전달)", "")
            with st.expander("📋 프로필(전달) 내용 보기"):
                st.code(profile_text, language="text")

            # 사진들 표시 (기존 방식 그대로 사용)
            photo_urls = str(m.get("본인 사진", "")).split(',')
            photo_cols = st.columns(min(5, len(photo_urls)))

            for i, url in enumerate(photo_urls[:5]):
                url = url.strip()
                file_id = extract_drive_file_id(url)

                if file_id:
                    try:
                        image = get_drive_image(file_id)
                        img_b64 = image_to_base64(image)
                        photo_cols[i].markdown(
                            f'<a href="{url}" target="_blank"><img src="data:image/png;base64,{img_b64}" style="width:130px;border-radius:10px;"/></a>',
                            unsafe_allow_html=True
                        )
                    except Exception as e:
                        photo_cols[i].warning(f"이미지 로드 실패")
                else:
                    photo_cols[i].warning("유효하지 않은 이미지 링크입니다.")

            st.markdown("---")

with match_container:
    if st.session_state["match_triggered"]:
        with st.spinner("매칭 중..."):
            match_data = {
                "memberId": memberId,
                "channel": channel,
                "faceShape": face_shape,
                "faces": faces,
                "abilitys": abilitys,
                "afterDate": after_date if after_date else None,
                "conditions": conds
            }

            result_df = match_members(member_df, match_data)
            st.subheader(f"📝 {memberId} 조건에 매칭된 총 회원 수: {len(result_df)}명")

            score_values = result_df["보내진 횟수"].fillna(0).astype(float)
            weights = 1 / (score_values + 1)
            top_ids = result_df.sample(n=min(4, len(result_df)), weights=weights, random_state=42)["회원 ID"].tolist()

            with st.expander("\U0001F4CB 조건에 매칭된 회원 리스트 보기 (클릭)"):
                st.dataframe(result_df[["회원 ID", "이름", "보내진 횟수"]].reset_index(drop=True), height=200)


        top_rows = result_df[result_df["회원 ID"].isin(top_ids)]
        matched_profiles = profile_df[profile_df["회원 ID"].isin(top_ids)]


        st.subheader(f"📄 {memberId} 조건에 매칭된 상세 프로필 (상위 4명)")
        columns = st.columns(4)
        for idx, member_id in enumerate(top_ids):
            match_row = matched_profiles[matched_profiles["회원 ID"] == member_id]
            score_row = top_rows[top_rows["회원 ID"] == member_id]
            member_row = member_df[member_df["회원 ID"] == member_id]
            if match_row.empty or score_row.empty or member_row.empty:
                continue
            row = match_row.iloc[0]
            score_info = score_row.iloc[0]

            with columns[idx]:
                주문번호 = member_row.iloc[0].get("주문번호", "")
                이름 = row.get("이름", "")
                보내진횟수 = score_info.get("보내진 횟수", "")

                st.markdown(f"**주문번호 및 이름:** {주문번호} / {이름}")
                st.markdown(f"**회원 ID:** {row.get('회원 ID', '')}")
                st.markdown(f"**프로필 ID:** {row.get('프로필 ID', '')}")
                st.markdown(f"**보내진 횟수:** {보내진횟수}")
                st.markdown(f"**얼굴상:** {row.get('본인(외모)', '')}")

                profile_text = row.get("프로필(전달)", "")
                with st.expander("프로필(전달) 보기"):
                    st.code(profile_text, language='text')

                photo_urls = str(row.get("본인 사진", "")).split(',')
                for i, url in enumerate(photo_urls):
                    url = url.strip()
                    if "drive.google.com" in url and "id=" in url:
                        file_id = url.split("id=")[-1].split("&")[0]
                        try:
                            image = get_drive_image(file_id)
                            img_b64 = image_to_base64(image)
                            st.markdown(
                                f'<a href="{url}" target="_blank"><img src="data:image/png;base64,{img_b64}" style="width:150px;border-radius:10px;"/></a>',
                                unsafe_allow_html=True
                            )
                        except Exception as e:
                            st.warning(f"이미지 로드 실패: {e}")
                    else:
                        st.warning("유효하지 않은 이미지 링크입니다.")
