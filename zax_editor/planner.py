"""Optional local Ollama intent-to-edit planner. Never executes AI-generated code."""
import json
import re
import urllib.error
import urllib.request
from .media import ACTIONS

SYSTEM="""You are a video edit planning assistant. Output ONLY a JSON object with
keys action, options, explanation. action MUST be one of:
silence, transcribe, burn, resize, compress, audio, scenes, thumbnail, denoise.
options is a small JSON object. Never include executable code, scripts,
paths, file names or shell commands. Prefer Arabic explanations.
For short vertical Reels use resize with ratio 9:16.
For quiet pauses use silence. For Arabic captions use transcribe language ar.
If user asks for an unsupported feature, explain the closest supported action.
"""

def validate(raw):
    if not isinstance(raw,dict): raise ValueError("AI response must be an object")
    action=raw.get("action")
    if action not in ACTIONS: raise ValueError("AI suggested an unsupported tool")
    opts=raw.get("options",{})
    if not isinstance(opts,dict): opts={}
    allowed={"threshold","minimum","padding","ratio","fit","crf",
             "language","model","scene_threshold","second"}
    opts={k:v for k,v in opts.items() if k in allowed and isinstance(v,(str,int,float))}
    return {"action":action,"options":opts,"explanation":str(raw.get("explanation",""))[:500]}

def plan(prompt,model="qwen2.5:3b"):
    prompt=str(prompt).strip()[:700]
    if not prompt: raise ValueError("Describe your desired edit")
    if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,64}",model):
        raise ValueError("Invalid Ollama model name")
    payload=json.dumps({"model":model,"stream":False,"format":"json",
                        "prompt":SYSTEM+"\nUSER:\n"+prompt}).encode()
    request=urllib.request.Request("http://127.0.0.1:11434/api/generate",
                                   payload,{"Content-Type":"application/json"})
    try:
        with urllib.request.urlopen(request,timeout=120) as response:
            data=json.load(response)
    except urllib.error.URLError as exc:
        raise RuntimeError("Ollama not available. Install Ollama and pull "+model) from exc
    try:
        raw=json.loads(data["response"])
    except (KeyError,TypeError,json.JSONDecodeError) as exc:
        raise RuntimeError("The local AI did not return valid JSON") from exc
    return validate(raw)
