import streamlit as st
import tempfile
import requests
import os

st.title("📥 PDF 링크 다운로드 테스트")

# 사용자로부터 다운로드 링크 입력
url = st.text_input("PDF 다운로드 링크를 입력하세요:")

# 다운로드 버튼
if st.button("PDF 다운로드"):
    if not url:
        st.warning("⛔ 링크를 입력해주세요.")
    else:
        try:
            # 임시 파일 생성
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                response = requests.get(url, stream=True)

                if response.status_code == 200:
                    for chunk in response.iter_content(chunk_size=8192):
                        tmp_file.write(chunk)
                    tmp_file_path = tmp_file.name

                    st.success("✅ 다운로드 완료!")
                    st.write(f"임시 파일 경로: `{tmp_file_path}`")

                    # 다운로드 버튼 추가
                    with open(tmp_file_path, "rb") as f:
                        st.download_button(
                            label="📎 다운로드된 PDF 저장하기",
                            data=f,
                            file_name="downloaded.pdf",
                            mime="application/pdf",
                        )
                else:
                    st.error(f"❌ 다운로드 실패: 상태 코드 {response.status_code}")

        except Exception as e:
            st.error(f"오류 발생: {str(e)}")


