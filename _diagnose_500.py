import traceback
import datadev_api as api
q = "Visuel Studio Code nedir?"
try:
 answer = api.make_local_draft(q, "tr")
 for n in range(1,4):
  print("ROUND", n, "draft", repr(answer), flush=True)
  result = api.core.groq_review(q, answer, language="tr")
  print("decision", result.get("decision"), "status", result.get("status"), flush=True)
  if result.get("status") != "ok" or result.get("decision") == "KEEP" or n == 3:
   if result.get("status") == "ok" and result.get("decision") == "KEEP":
    print("SAVED", api.save_groq_approved_example(q, answer, "tr", str(result.get("reason", ""))), flush=True)
   break
  coaching = "Groq değerlendirmesi: " + str(result.get("reason", "")) + "\nÖneri: " + str(result.get("final_answer", ""))
  answer = api.make_local_draft(q, "tr", coaching=coaching)
 print("DONE", flush=True)
except Exception:
 traceback.print_exc()
