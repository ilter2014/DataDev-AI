import json
import urllib.request
from pathlib import Path

base = Path(__file__).resolve().parent
key = (base / "groq_api_key.txt").read_text(encoding="utf-8").strip()
if not key:
    print("RESULT=NO_KEY")
    raise SystemExit(2)

payload = {
    "model": "openai/gpt-oss-20b",
    "messages": [
        {"role": "system", "content": "You are DataDev AI. Reply briefly in Turkish."},
        {"role": "user", "content": "Sadece 'DataDev AI bağlantısı başarılı.' yaz."}
    ],
    "max_tokens": 80
}
req = urllib.request.Request(
    "https://api.groq.com/openai/v1/chat/completions",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
    method="POST"
)
try:
    with urllib.request.urlopen(req, timeout=25) as response:
        data = json.loads(response.read().decode("utf-8"))
        answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        print("RESULT=OK")
        print("HTTP_STATUS=" + str(response.status))
        print("MODEL=" + str(data.get("model", "unknown")))
        print("ANSWER=" + str(answer)[:300].replace("\n", " "))
except Exception as e:
    # Deliberately avoid printing headers, request objects, or key.
    code = getattr(e, "code", None)
    print("RESULT=FAIL")
    if code is not None:
        print("HTTP_STATUS=" + str(code))
        try:
            body = e.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            err = data.get("error", {})
            print("ERROR_TYPE=" + str(err.get("type", "unknown")))
            print("ERROR_CODE=" + str(err.get("code", "unknown")))
            print("ERROR_MESSAGE=" + str(err.get("message", "request failed"))[:240])
        except Exception:
            print("ERROR_MESSAGE=Response could not be safely parsed")
    else:
        print("ERROR_TYPE=" + type(e).__name__)
        print("ERROR_MESSAGE=Connection failed or timed out")
