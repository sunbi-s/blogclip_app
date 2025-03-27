import streamlit as st
import tempfile
import requests
import os
import uuid
import time

st.title("📥 PDF 링크 다운로드 (사용자별 저장소 사용)")

# 사용자 고유 UUID 할당
if "user_id" not in st.session_state:
    st.session_state["user_id"] = str(uuid.uuid4())

user_id = st.session_state["user_id"]

# 사용자 전용 임시 디렉토리 생성
user_temp_dir = os.path.join(tempfile.gettempdir(), f"streamlit_{user_id}")
os.makedirs(user_temp_dir, exist_ok=True)

# 마지막 접근 시간 기록 (자동 정리를 위해)
with open(os.path.join(user_temp_dir, ".last_access"), "w") as f:
    f.write(str(time.time()))

# PDF 다운로드 입력창
url = st.text_input("📎 PDF 다운로드 링크를 입력하세요:")

if st.button("PDF 다운로드"):
    if not url:
        st.warning("⛔ 링크를 입력해주세요.")
    else:
        try:
            response = requests.get(url, stream=True)

            if response.status_code == 200:
                # 사용자 전용 경로에 저장
                pdf_filename = f"{uuid.uuid4()}.pdf"
                pdf_path = os.path.join(user_temp_dir, pdf_filename)

                with open(pdf_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)

                st.success("✅ PDF 다운로드 성공!")
                st.write(f"📂 저장 경로: `{pdf_path}`")

                # 다운로드 버튼
                with open(pdf_path, "rb") as f:
                    st.download_button(
                        label="📄 다운로드된 PDF 저장하기",
                        data=f,
                        file_name="downloaded.pdf",
                        mime="application/pdf",
                    )
            else:
                st.error(f"❌ 다운로드 실패 (상태 코드: {response.status_code})")
        except Exception as e:
            st.error(f"❌ 오류 발생: {str(e)}")
