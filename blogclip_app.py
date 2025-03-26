import streamlit as st
from langchain_community.document_loaders import PyPDFLoader
from openai import OpenAI
import os
import json
import time
import re

# API 키 기본값은 빈 문자열
DEFAULT_OPENAI_API_KEY = ""

st.set_page_config(page_title="BlogClip", page_icon="🎬", layout="wide")


def extract_text_from_pdf(uploaded_files):
    """업로드된 PDF에서 텍스트 추출"""
    try:
        # 임시 파일로 저장
        with open("temp.pdf", "wb") as f:
            f.write(uploaded_files.getbuffer())

        # PyPDFLoader로 텍스트 추출
        loader = PyPDFLoader("temp.pdf")
        pages = loader.load()
        text = "\n".join([page.page_content for page in pages])

        # 임시 파일 삭제
        os.remove("temp.pdf")
        return text
    except Exception as e:
        st.error(f"PDF 읽기 오류: {e}")
        return ""


def generate_video_script(
    text, num_pages=3, total_script_length=1000, model="gpt-4-turbo-preview"
):
    """GPT를 활용하여 블로그 제작을 위한 스크립트 생성"""
    if not text:
        return "스크립트를 생성할 내용이 없습니다."

    # 텍스트 길이 제한 (토큰 제한 고려)
    max_text_length = 3000  # 안전한 값으로 설정
    limited_text = text[:max_text_length]

    # 페이지당 스크립트 길이 계산
    per_page_length = total_script_length // num_pages

    prompt = f"""
    다음 문서의 내용을 바탕으로 블로그를 제작하기 위한 스크립트를 작성해 주세요.
    
    총 {num_pages}개의 페이지를 생성하고, 각 페이지마다 아래 형식을 따라주세요:
    
    # 페이지 제목: [제목]
    
    ## 페이지 스크립트:
    [상세 설명 스크립트]
    
    각 페이지는 서로 다른 주제나 측면을 다루되 전체적으로 논리적인 흐름을 가지도록 해주세요.
    각 페이지의 내용은 약 {per_page_length}자 내외로 작성하여 전체 스크립트가 약 {total_script_length}자가 되도록 해주세요.
    각 페이지별로 고객 대상으로 친절한 어투로 자세한 설명을 제공해 주세요.
    
    반드시 {num_pages}개의 페이지를 생성해 주세요.
    
    문서 내용:
    {limited_text}
    """
    try:
        # API 키 가져오기
        api_key = st.session_state.get("openai_api_key", DEFAULT_OPENAI_API_KEY)
        client = OpenAI(api_key=api_key)

        with st.spinner("블로그 스크립트 생성 중..."):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "당신은 블로그 제작 전문가입니다."},
                    {"role": "user", "content": prompt},
                ],
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"스크립트 생성 오류: {e}")
        return "블로그 스크립트 생성 실패"


def parse_script_pages(script, expected_page_count=3):
    """스크립트에서 페이지 제목과 내용을 추출하여 구조화"""
    # 정규식 패턴: '# 페이지 제목: ' 또는 '# ' 등으로 시작하는 제목 찾기
    title_patterns = [
        r"# 페이지 제목:\s*(.+)",
        r"#\s+페이지\s+\d+[:.]\s*(.+)",
        r"# (.+)",
    ]

    # 내용 패턴: '## 페이지 스크립트:' 또는 '## ' 등으로 시작하는 내용 찾기
    content_patterns = [
        r"## 페이지 스크립트:\s*\n([\s\S]+?)(?=\n# |$)",
        r"##\s+페이지\s+\d+[:.]\s*\n([\s\S]+?)(?=\n# |$)",
        r"## (.+)\n([\s\S]+?)(?=\n# |$)",
    ]

    pages = []
    titles = []

    # 먼저 제목을 찾습니다
    for pattern in title_patterns:
        titles = re.findall(pattern, script)
        if titles:
            break

    # 제목을 찾았다면 내용 추출
    if titles:
        # 스크립트를 페이지별로 분할
        page_blocks = re.split(r"\n# |\n#페이지 \d+[:.] ", script)
        if page_blocks[0].startswith("# ") or page_blocks[0].startswith("#페이지"):
            page_blocks[0] = page_blocks[0][page_blocks[0].find("\n") + 1 :]

        # 첫 번째 블록이 비어있거나 # 앞의 내용이라면 제거
        if not page_blocks[0].strip() or not page_blocks[0].strip().startswith("#"):
            page_blocks = page_blocks[1:]

        # 각 페이지 블록에서 내용 추출
        for i, block in enumerate(page_blocks):
            if i < len(titles):
                # 내용 찾기
                content = ""
                for pattern in content_patterns:
                    match = re.search(pattern, "# Dummy\n" + block)
                    if match:
                        if len(match.groups()) == 1:
                            content = match.group(1).strip()
                        elif len(match.groups()) == 2:
                            content = match.group(2).strip()
                        break

                # 내용을 찾지 못했다면 전체 블록을 내용으로 사용
                if not content and block.strip():
                    if "##" in block:
                        content = block[block.find("##") + 2 :].strip()
                    else:
                        content = block.strip()

                pages.append({"title": titles[i].strip(), "content": content})

    # 페이지 찾기에 실패하거나 예상 페이지 수와 다를 경우 보정
    if not pages or len(pages) != expected_page_count:
        st.warning(
            f"페이지 파싱 문제: {len(pages)}개 페이지가 추출되었지만, {expected_page_count}개가 필요합니다. 보정을 시도합니다."
        )

        # 페이지가 없거나 너무 적은 경우: 전체 콘텐츠를 강제로 나눔
        if len(pages) < expected_page_count:
            # 기존 페이지 유지
            existing_pages = pages.copy()
            pages = []

            # 실제 페이지 수가 0이면 전체 스크립트를 사용
            if len(existing_pages) == 0:
                # 스크립트를 대략적으로 나누기
                parts = []
                script_lines = script.split("\n")
                chunk_size = len(script_lines) // expected_page_count

                for i in range(expected_page_count):
                    start = i * chunk_size
                    end = (
                        start + chunk_size
                        if i < expected_page_count - 1
                        else len(script_lines)
                    )
                    parts.append("\n".join(script_lines[start:end]))

                # 나눈 부분으로 페이지 생성
                for i, part in enumerate(parts):
                    pages.append({"title": f"페이지 {i+1}", "content": part.strip()})
            else:
                # 기존 페이지 먼저 추가
                pages = existing_pages

                # 추가 페이지 필요
                remaining = expected_page_count - len(pages)
                for i in range(remaining):
                    pages.append(
                        {
                            "title": f"추가 페이지 {i+1}",
                            "content": f"이 콘텐츠는 {expected_page_count}개 페이지 요구사항을 충족하기 위해 자동 생성되었습니다.",
                        }
                    )

        # 페이지가 너무 많은 경우: 초과 페이지 제거
        elif len(pages) > expected_page_count:
            pages = pages[:expected_page_count]

    return pages


def generate_image_prompt_for_page(page, model="gpt-4-turbo-preview"):
    """페이지 내용에 맞는 이미지 생성 프롬프트 생성"""
    if not page or not page.get("content"):
        return "페이지 내용을 바탕으로 한 실사 이미지"

    # 콘텐츠 길이 제한
    content_preview = page["content"][:1500]  # 콘텐츠 길이 제한

    prompt = f"""
    아래 블로그 페이지의 내용을 분석하여,
    페이지를 초고화질 실사 사진처럼 표현할 수 있는 세부적이고 자세한 이미지 생성 프롬프트를 만들어 주세요.
    
    프롬프트는 다음과 같은 요소를 포함해야 합니다:
    1. 주요 피사체의 명확한 설명 (인물, 제품, 환경 등)
    2. 조명 조건 (자연광, 부드러운 조명, 극적인 조명 등)
    3. 촬영 각도 및 구도 (클로즈업, 전체 샷, 원근감 등)
    4. 색감 및 분위기 (밝고 활기찬, 차분하고 따뜻한 등)
    5. 고급 사진 효과 (얕은 심도, 선명한 디테일, 부드러운 배경 등)
    
    응답은 프롬프트 텍스트만 제공하세요. 설명이나 주석은 필요 없습니다.
    
    페이지 제목: {page['title']}
    
    페이지 내용:
    {content_preview}
    """
    try:
        # API 키 가져오기
        api_key = st.session_state.get("openai_api_key", DEFAULT_OPENAI_API_KEY)
        client = OpenAI(api_key=api_key)

        with st.spinner("이미지 프롬프트 생성 중..."):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 안전하고 정교하며 사실적인 이미지 생성 프롬프트를 작성하는 전문가입니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"이미지 프롬프트 생성 오류: {e}")
        return f"{page['title']}를 표현한 실사 이미지"


def generate_image_for_page(page, image_style="실사 스타일"):
    """페이지에 대한 이미지 생성"""
    if not page or not page.get("image_prompt"):
        return {"url": None, "prompt": "프롬프트 생성 실패"}

    # 이미지 스타일에 따른 스타일 지시 문구
    style_prompts = {
        "실사 스타일": " Create a hyper-realistic photograph with extreme detail. Use professional photography techniques with natural lighting, perfect focus, and authentic textures. The image should look indistinguishable from a high-end camera photo with 8K resolution. Include subtle details like skin pores, fabric texture, or surface reflections where appropriate. Use photorealistic color grading with naturalistic environment.",
        "동화책 스타일": " in a soft, illustrated storybook style, warm and cozy colors.",
        "수채화 스타일": " as a delicate watercolor painting with soft colors and gentle brushstrokes.",
        "3D 렌더링": " as a colorful 3D rendered scene with soft lighting and gentle shadows.",
        "일러스트레이션": " as a clean, modern illustration with vibrant colors and simple shapes.",
    }

    # 기본 스타일 설정
    style_prompt = style_prompts.get(image_style, style_prompts["실사 스타일"])

    # API 키 가져오기
    api_key = st.session_state.get("openai_api_key", DEFAULT_OPENAI_API_KEY)
    client = OpenAI(api_key=api_key)

    try:
        prompt_text = page["image_prompt"]
        full_prompt = prompt_text + style_prompt

        with st.spinner(f"'{page['title']}' 이미지 생성 중..."):
            response = client.images.generate(
                model="dall-e-3", prompt=full_prompt, n=1, size="1024x1024"
            )
        return {"prompt": prompt_text, "url": response.data[0].url}
    except Exception as e:
        error_msg = str(e)
        st.error(f"이미지 생성 오류: {error_msg}")

        # 만약 프롬프트 길이 문제라면
        if (
            "maximum context length" in error_msg.lower()
            or "too long" in error_msg.lower()
        ):
            truncated_prompt = prompt_text[:500]  # 프롬프트 길이 제한
            try:
                full_prompt = truncated_prompt + style_prompt
                with st.spinner(f"'{page['title']}' 이미지 재시도 중..."):
                    response = client.images.generate(
                        model="dall-e-3", prompt=full_prompt, n=1, size="1024x1024"
                    )
                return {"prompt": truncated_prompt, "url": response.data[0].url}
            except Exception as retry_error:
                st.error(f"이미지 재생성 오류: {str(retry_error)}")

        return {"prompt": prompt_text, "url": None}


# 다운로드 함수
def download_file(content, filename):
    """파일 다운로드 처리 - 상태 초기화 방지"""
    st.session_state.download_clicked = True
    st.success(f"'{filename}' 다운로드가 시작되었습니다!")


def main():
    st.title("📚 BlogClip🎬")
    st.subheader("PDF를 스크립트와 멋진 이미지 시퀀스로 변환하세요")

    # 세션 상태 초기화
    if "openai_api_key" not in st.session_state:
        st.session_state.openai_api_key = ""

    if "selected_model" not in st.session_state:
        st.session_state.selected_model = "gpt-4-turbo"

    if "processing_done" not in st.session_state:
        st.session_state.processing_done = False

    if "raw_script" not in st.session_state:
        st.session_state.raw_script = ""

    if "pages" not in st.session_state:
        st.session_state.pages = []

    if "download_clicked" not in st.session_state:
        st.session_state.download_clicked = False

    # 사이드바에 API 키 입력 및 모델 선택 추가
    with st.sidebar:
        st.header("설정")

        # API 키 입력
        api_key_input = st.text_input(
            "OpenAI API 키",
            value=st.session_state.openai_api_key,
            type="password",
            help="OpenAI API 키를 입력하세요. 이전에 입력한 경우 자동으로 불러옵니다.",
        )

        # 입력값 저장
        if api_key_input:
            st.session_state.openai_api_key = api_key_input

        # LLM 모델 선택
        st.subheader("LLM 모델 선택")
        selected_model = st.selectbox(
            "사용할 모델",
            ["gpt-3.5-turbo", "gpt-4", "gpt-4-turbo"],
            index=2,  # 기본값으로 gpt-4-turbo 선택
            help="텍스트 생성에 사용할 OpenAI 모델을 선택하세요.",
        )

        # 모델 선택 저장
        st.session_state.selected_model = selected_model

        st.divider()

        st.header("PDF 업로드")
        uploaded_files = st.file_uploader(
            "PDF 파일을 업로드하세요",
            type="pdf",
            accept_multiple_files=True,  # 여러 파일 업로드 허용
        )

        if uploaded_files is not None:
            st.success("PDF 업로드 완료!")
            st.image("https://cdn-icons-png.flaticon.com/512/337/337946.png", width=100)

            # 설정 옵션
            st.subheader("옵션 설정")
            num_pages = st.slider("생성할 페이지 수", 1, 10, 3, 1)
            script_length = st.slider("페이지당 스크립트 길이 (자)", 100, 1000, 300, 50)
            total_length = script_length * num_pages
            st.caption(f"총 스크립트 길이: 약 {total_length}자")

            image_style = st.selectbox(
                "이미지 스타일",
                [
                    "실사 스타일",
                    "동화책 스타일",
                    "수채화 스타일",
                    "3D 렌더링",
                    "일러스트레이션",
                ],
            )

            # API 키 확인
            if not st.session_state.openai_api_key:
                st.warning("OpenAI API 키를 입력해주세요.")
                process_button = False
            else:
                # 처리 시작 버튼
                process_button = st.button("✨ 변환 시작", use_container_width=True)

                # 버튼 클릭 시 세션 상태 초기화
                if process_button:
                    st.session_state.processing_done = False
                    st.session_state.raw_script = ""
                    st.session_state.pages = []
        else:
            process_button = False
            num_pages = 3  # 기본값
            script_length = 300  # 기본값
            image_style = "실사 스타일"  # 기본값
            st.info("먼저 PDF 파일을 업로드해주세요.")
            st.markdown(
                """
            ### 사용 방법
            1. OpenAI API 키를 입력하세요
            2. 사용할 LLM 모델을 선택하세요
            3. PDF 파일을 업로드하세요
            4. 페이지 수, 스크립트 길이와 이미지 스타일을 선택하세요
            5. '변환 시작' 버튼을 클릭하세요
            6. 결과를 확인하고 다운로드하세요
            """
            )

    # 메인 섹션
    if uploaded_files is not None and (
        process_button or st.session_state.processing_done
    ):
        # 처리가 완료되지 않았거나 새로운 처리 요청이 있을 경우에만 실행
        if not st.session_state.processing_done or process_button:
            # 진행 상황 표시 컨테이너
            progress_container = st.container()
            with progress_container:
                text = extract_text_from_pdf(uploaded_files)
                if not text:
                    st.error("PDF에서 텍스트를 추출할 수 없습니다.")
                    return

                # 선택된 모델로 스크립트 생성
                selected_model = st.session_state.selected_model
                total_script_length = script_length * num_pages
                raw_script = generate_video_script(
                    text, num_pages, total_script_length, selected_model
                )
                if not raw_script or "실패" in raw_script:
                    st.error("블로그 스크립트 생성에 실패했습니다.")
                    return

                # 세션에 원본 스크립트 저장
                st.session_state.raw_script = raw_script

                # 스크립트를 페이지별로 파싱 (예상 페이지 수 전달)
                pages = parse_script_pages(raw_script, num_pages)

                # 각 페이지에 대한 이미지 프롬프트 생성
                progress_bar = st.progress(0)
                status_text = st.empty()

                for i, page in enumerate(pages):
                    status_text.text(f"페이지 {i+1}/{len(pages)} 처리 중...")
                    progress_bar.progress(
                        (i) / len(pages) / 2
                    )  # 전체 진행의 절반은 프롬프트 생성

                    # 이미지 프롬프트 생성
                    page["image_prompt"] = generate_image_prompt_for_page(
                        page, selected_model
                    )

                    # 이미지 생성
                    progress_bar.progress(
                        0.5 + (i) / len(pages) / 2
                    )  # 후반부는 이미지 생성
                    image_result = generate_image_for_page(page, image_style)
                    page["image_url"] = image_result["url"]

                    # 이미지 생성 사이 간격
                    time.sleep(0.5)

                progress_bar.progress(1.0)
                status_text.text("페이지 생성 완료!")
                time.sleep(0.5)
                status_text.empty()
                progress_bar.empty()

                # 세션에 페이지 저장
                st.session_state.pages = pages

                # 처리 완료 상태 업데이트
                st.session_state.processing_done = True

        # 결과 표시 (처리 완료 상태일 때)
        if st.session_state.processing_done:
            # 페이지 탭 생성
            page_tabs = ["📊 전체 보기"] + [
                f"📄 페이지 {i+1}" for i in range(len(st.session_state.pages))
            ]
            tabs = st.tabs(page_tabs)

            # 전체 보기 탭
            with tabs[0]:
                st.markdown("## 📑 블로그 페이지 요약")

                # 전체 스크립트 다운로드 버튼
                st.download_button(
                    "전체 스크립트 다운로드",
                    st.session_state.raw_script,
                    file_name="blog_script.txt",
                    mime="text/plain",
                    on_click=download_file,
                    args=(st.session_state.raw_script, "blog_script.txt"),
                    key="full_script_download",
                )

                # 페이지 목록 표시
                for i, page in enumerate(st.session_state.pages):
                    with st.expander(f"페이지 {i+1}: {page['title']}"):
                        # 2열 레이아웃
                        col1, col2 = st.columns([2, 1])

                        with col1:
                            st.markdown(f"### {page['title']}")
                            st.markdown(page["content"])
                            st.text_area(
                                "이미지 프롬프트",
                                page["image_prompt"],
                                height=100,
                                key=f"prompt_summary_{i}",
                            )

                        with col2:
                            if page["image_url"]:
                                st.image(
                                    page["image_url"],
                                    caption=f"페이지 {i+1} 이미지",
                                    use_container_width=True,
                                )
                            else:
                                st.error("이미지 생성 실패")

                # 전체 결과 다운로드 옵션
                st.markdown("### 📥 전체 결과 다운로드")

                # 결과를 JSON으로 변환
                result_data = {
                    "raw_script": st.session_state.raw_script,
                    "pages": [
                        {
                            "title": page["title"],
                            "content": page["content"],
                            "image_prompt": page["image_prompt"],
                            "image_url": page["image_url"],
                        }
                        for page in st.session_state.pages
                    ],
                }

                result_json = json.dumps(result_data, indent=2, ensure_ascii=False)

                # 다운로드 버튼
                st.download_button(
                    "전체 결과 JSON 다운로드",
                    result_json,
                    file_name="blog_creation_results.json",
                    mime="application/json",
                    on_click=download_file,
                    args=(result_json, "blog_creation_results.json"),
                    key="result_download",
                )

            # 개별 페이지 탭
            for i in range(len(st.session_state.pages)):
                with tabs[i + 1]:
                    page = st.session_state.pages[i]

                    # 페이지 제목
                    st.markdown(f"# {page['title']}")

                    # 2열 레이아웃
                    col1, col2 = st.columns([3, 2])

                    with col1:
                        st.markdown("### 페이지 내용")
                        st.markdown(page["content"])

                        # 페이지 스크립트 다운로드
                        page_content = f"# {page['title']}\n\n{page['content']}"
                        st.download_button(
                            "페이지 스크립트 다운로드",
                            page_content,
                            file_name=f"page_{i+1}_script.txt",
                            mime="text/plain",
                            on_click=download_file,
                            args=(page_content, f"page_{i+1}_script.txt"),
                            key=f"page_{i+1}_download",
                        )

                    with col2:
                        st.markdown("### 페이지 이미지")
                        if page["image_url"]:
                            st.image(
                                page["image_url"],
                                caption=page["title"],
                                use_container_width=True,
                            )
                        else:
                            st.error("이미지 생성 실패")

                        st.markdown("### 이미지 프롬프트")
                        st.text_area(
                            "프롬프트",
                            page["image_prompt"],
                            height=150,
                            key=f"prompt_detail_{i}",
                        )

        # 다운로드 성공 메시지 표시
        if st.session_state.download_clicked:
            st.success("파일이 성공적으로 다운로드되었습니다!")
            # 다음 다운로드를 위해 상태 재설정
            st.session_state.download_clicked = False


if __name__ == "__main__":
    main()
