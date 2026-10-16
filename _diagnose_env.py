import importlib.util, os, platform, shutil, ctypes
print("Python:", platform.python_version())
print("OS:", platform.platform())
print("CPU:", platform.processor() or "unknown")
print("Logical CPUs:", os.cpu_count())
try:
 class MEMORYSTATUSEX(ctypes.Structure):
  _fields_ = [("dwLength",ctypes.c_ulong),("dwMemoryLoad",ctypes.c_ulong),("ullTotalPhys",ctypes.c_ulonglong),("ullAvailPhys",ctypes.c_ulonglong),("ullTotalPageFile",ctypes.c_ulonglong),("ullAvailPageFile",ctypes.c_ulonglong),("ullTotalVirtual",ctypes.c_ulonglong),("ullAvailVirtual",ctypes.c_ulonglong),("ullAvailExtendedVirtual",ctypes.c_ulonglong)]
 m=MEMORYSTATUSEX(); m.dwLength=ctypes.sizeof(m); ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
 print("RAM total GB:", round(m.ullTotalPhys/1024**3,1))
 print("RAM available GB:", round(m.ullAvailPhys/1024**3,1))
except Exception as e: print("RAM check error:", type(e).__name__)
print("C drive free GB:", round(shutil.disk_usage("C:/").free / (1024**3), 1))
for name in ("torch","fastapi","uvicorn","numpy","pydantic"):
 print(name + ":", bool(importlib.util.find_spec(name)))
try:
 import torch
 print("Torch version:", torch.__version__)
 print("CUDA available:", torch.cuda.is_available())
except Exception as e: print("Torch import error:", type(e).__name__, str(e)[:200])
