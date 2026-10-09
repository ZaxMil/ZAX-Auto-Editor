"""Small FFmpeg primitives for local video processing."""
import json
import re
import subprocess
from pathlib import Path

EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mp3", ".wav", ".m4a", ".flac"}
ACTIONS = {"silence", "transcribe", "burn", "resize", "compress", "audio", "scenes", "thumbnail", "denoise"}
RATIOS = {"9:16": (720,1280), "16:9": (1280,720), "1:1": (1080,1080), "4:5": (864,1080)}

def run(args, cwd=None):
    p = subprocess.run([str(x) for x in args], cwd=cwd, text=True,
                       errors="replace", stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode:
        raise RuntimeError((p.stderr or p.stdout)[-1200:])
    return p.stdout + "\n" + p.stderr

def info(src):
    raw = run(["ffprobe","-v","error","-show_entries",
               "format=duration,size:stream=codec_type,width,height","-of","json",src])
    data = json.loads(raw)
    v = next((s for s in data.get("streams",[]) if s.get("codec_type")=="video"),{})
    f = data.get("format",{})
    return {"duration":float(f.get("duration",0)), "bytes":int(f.get("size",0)),
            "width":v.get("width"), "height":v.get("height"),
            "audio":any(s.get("codec_type")=="audio" for s in data.get("streams",[]))}

def kept_ranges(log, length, padding=.12):
    events = re.findall(r"silence_(start|end):\s*([0-9.]+)",log)
    pauses, start = [], None
    for kind, value in events:
        t = max(0., min(length,float(value)))
        if kind=="start": start = t
        elif start is not None:
            pauses.append((max(0.,start+padding), min(length,t-padding)))
            start = None
    if start is not None: pauses.append((max(0.,start+padding),length))
    ranges, cursor = [], 0.
    for a,b in sorted(pauses):
        a = max(cursor,a)
        if a-cursor >= .08: ranges.append((round(cursor,3),round(a,3)))
        cursor = max(cursor,b)
    if length-cursor >= .08: ranges.append((round(cursor,3),round(length,3)))
    return ranges

def silence(src, out, options):
    meta = info(src)
    if not (meta["width"] and meta["audio"]): raise ValueError("Video with audio required")
    db = max(-60,min(-15,float(options.get("threshold",-35))))
    minimum = max(.15,min(2.,float(options.get("minimum",.35))))
    pad = max(0.,min(.4,float(options.get("padding",.12))))
    log = run(["ffmpeg","-hide_banner","-i",src,"-af",
               f"silencedetect=noise={db}dB:d={minimum}","-f","null","-"])
    spans = kept_ranges(log,meta["duration"],pad)
    if not spans: raise ValueError("No audible segments found")
    if len(spans)>120: raise ValueError("More than 120 cuts; increase minimum silence")
    graph = ""
    for i,(a,b) in enumerate(spans):
        graph += f"[0:v]trim=start={a}:end={b},setpts=PTS-STARTPTS[v{i}];"
        graph += f"[0:a]atrim=start={a}:end={b},asetpts=PTS-STARTPTS[a{i}];"
    graph += "".join(f"[v{i}][a{i}]" for i in range(len(spans)))
    graph += f"concat=n={len(spans)}:v=1:a=1[v][a]"
    target=out/"silence-cut.mp4"
    run(["ffmpeg","-y","-v","error","-i",src,"-filter_complex",graph,
         "-map","[v]","-map","[a]","-c:v","libx264","-preset","veryfast",
         "-crf","22","-c:a","aac",target])
    manifest=out/"cut-list.json"
    manifest.write_text(json.dumps({"kept_ranges_seconds":spans,
                                     "original_duration":meta["duration"]},indent=2))
    return [target,manifest]

def resize(src,out,options):
    ratio=options.get("ratio","9:16")
    if ratio not in RATIOS: raise ValueError("Unsupported ratio")
    w,h=RATIOS[ratio]
    mode=options.get("fit","crop")
    if mode=="crop":
        vf=f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1"
    elif mode=="pad":
        vf=f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    else: raise ValueError("Unsupported fit mode")
    target=out/"formatted.mp4"
    run(["ffmpeg","-y","-v","error","-i",src,"-vf",vf,
         "-c:v","libx264","-preset","veryfast","-crf","23",
         "-c:a","aac",target])
    return [target]

def compress(src,out,options):
    crf=max(18,min(36,int(options.get("crf",28))))
    target=out/"compressed.mp4"
    run(["ffmpeg","-y","-v","error","-i",src,"-c:v","libx264",
         "-preset","fast","-crf",str(crf),"-c:a","aac","-b:a","128k",target])
    return [target]

def audio(src,out,options):
    target=out/"extracted-audio.mp3"
    run(["ffmpeg","-y","-v","error","-i",src,"-vn","-c:a",
         "libmp3lame","-q:a","3",target])
    return [target]

def scenes(src,out,options):
    import csv
    value=max(.1,min(.9,float(options.get("scene_threshold",.35))))
    log=run(["ffmpeg","-hide_banner","-i",src,"-vf",
             f"select=gt(scene\\,{value}),showinfo","-an","-f","null","-"])
    times=sorted(set(round(float(t),3) for t in re.findall(r"pts_time:([0-9.]+)",log)))
    j=out/"scenes.json"
    j.write_text(json.dumps({"threshold":value,"cut_times_seconds":times},indent=2))
    c=out/"scenes.csv"
    with c.open("w",newline="") as f:
        w=csv.writer(f);w.writerow(["scene","time_seconds"])
        w.writerows((i,t) for i,t in enumerate(times,1))
    return [j,c]

def thumbnail(src,out,options):
    t=max(0.,min(36000.,float(options.get("second",1))))
    target=out/"thumbnail.jpg"
    run(["ffmpeg","-y","-v","error","-ss",str(t),"-i",src,
         "-frames:v","1","-q:v","2",target])
    return [target]

def denoise(src,out,options):
    target=out/"denoised.mp4"
    run(["ffmpeg","-y","-v","error","-i",src,"-c:v","copy",
         "-af","afftdn=nf=-25","-c:a","aac",target])
    return [target]

def burn(src,out,options,subtitle=None):
    import shutil
    if subtitle is None: raise ValueError("Generate or upload an SRT subtitle first")
    if subtitle.suffix.lower() not in (".srt",".vtt",".ass"):
        raise ValueError("Subtitle must be SRT, VTT or ASS")
    target_sub=out/("captions"+subtitle.suffix.lower())
    shutil.copyfile(subtitle,target_sub)
    target=out/"captioned.mp4"
    style="FontName=Arial,FontSize=22,Outline=2,Shadow=1,Alignment=2,MarginV=55"
    run(["ffmpeg","-y","-v","error","-i",src,"-vf",
         f"subtitles={target_sub.name}:force_style='{style}'",
         "-c:v","libx264","-preset","veryfast","-crf","23","-c:a","aac",target],cwd=out)
    return [target]
