import tempfile
import requests

url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
response = requests.get(url, stream=True)

if response.status_code == 200:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
        for chunk in response.iter_content(chunk_size=8192):
            tmp_file.write(chunk)
        print("✅ 임시파일 다운로드 완료:", tmp_file.name)
else:
    print(f"❌ 다운로드 실패: {response.status_code}")
