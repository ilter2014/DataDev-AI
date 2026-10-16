import urllib.request, urllib.error, json, traceback
url="http://127.0.0.1:8765/v1/chat"
body=json.dumps({"question":"Visuel Studio Code nedir?","language":"tr"},ensure_ascii=False).encode("utf-8")
req=urllib.request.Request(url,data=body,headers={"Content-Type":"application/json; charset=utf-8"},method="POST")
try:
 with urllib.request.urlopen(req,timeout=180) as r:
  print("HTTP",r.status)
  print(r.read().decode("utf-8"))
except urllib.error.HTTPError as e:
 print("HTTP",e.code)
 print("BODY",e.read().decode("utf-8",errors="replace"))
except Exception:
 traceback.print_exc()
