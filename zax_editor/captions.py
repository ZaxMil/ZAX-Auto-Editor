"""Optional offline speech-to-text with faster-whisper."""
import json
from pathlib import Path
from .media import run

def stamp(seconds, vtt=False):
    ms=max(0,round(seconds*1000))
    h,r=divmod(ms,3600000);m,r=divmod(r,60000);s,ms=divmod(r,1000)
    return f"{h:02}:{m:02}:{s:02}{'.' if vtt else ','}{ms:03}"

def write_subtitles(parts,folder):
    srt=folder/"captions.srt";vtt=folder/"captions.vtt"
    transcript=folder/"transcript.json"
    s,v=[],["WEBVTT",""]
    for i,p in enumerate(parts,1):
        txt=" ".join(p["text"].split())
        if not txt: continue
        a,b=p["start"],p["end"]
        s.append(f"{i}\n{stamp(a)} --> {stamp(b)}\n{txt}\n")
        v.append(f"{stamp(a,True)} --> {stamp(b,True)}\n{txt}\n")
    srt.write_text("\n".join(s),encoding="utf-8")
    vtt.write_text("\n".join(v),encoding="utf-8")
    transcript.write_text(json.dumps(parts,ensure_ascii=False,indent=2),encoding="utf-8")
    return [srt,vtt,transcript]

def transcribe(src,out,options):
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise RuntimeError("AI subtitles need: pip install -r requirements-ai.txt") from exc
    model=options.get("model","base")
    if model not in ("tiny","base","small","medium"): raise ValueError("Invalid model")
    lang=options.get("language","auto")
    if lang not in ("auto","ar","en","fr","es","de"): lang="auto"
    wav=out/"speech.wav"
    run(["ffmpeg","-y","-v","error","-i",src,"-vn","-ar","16000","-ac","1",wav])
    engine=WhisperModel(model,device="cpu",compute_type="int8")
    segments,_=engine.transcribe(str(wav),language=None if lang=="auto" else lang,
                                  vad_filter=True,word_timestamps=True)
    parts=[]
    for segment in segments:
        words=[w for w in (segment.words or []) if w.word.strip()]
        if not words:
            parts.append({"start":segment.start,"end":segment.end,"text":segment.text.strip()})
            continue
        batch=[]
        for word in words:
            if batch and (len(batch)>=6 or word.end-batch[0].start>3.2
                          or len(" ".join(x.word for x in batch))+len(word.word)>44):
                parts.append({"start":batch[0].start,"end":batch[-1].end,
                              "text":" ".join(x.word.strip() for x in batch)})
                batch=[]
            batch.append(word)
        if batch:
            parts.append({"start":batch[0].start,"end":batch[-1].end,
                          "text":" ".join(x.word.strip() for x in batch)})
    wav.unlink(missing_ok=True)
    if not parts: raise ValueError("No speech detected")
    return write_subtitles(parts,out)
