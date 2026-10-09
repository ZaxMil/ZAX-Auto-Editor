"""Localhost-only video editing API using Python standard library."""
import json
import mimetypes
import os
import sqlite3
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from . import media, captions

ROOT=Path(__file__).resolve().parents[1]
DATA=Path(os.environ.get("ZAX_DATA_DIR",str(ROOT/".local"))).resolve()
WEB=ROOT/"web"
PORT=int(os.environ.get("ZAX_PORT","8765"))
POOL=ThreadPoolExecutor(max_workers=1)
MAX_UPLOAD=2*1024**3
(DATA/"uploads").mkdir(parents=True,exist_ok=True)
(DATA/"exports").mkdir(parents=True,exist_ok=True)

def db():
    c=sqlite3.connect(DATA/"editor.sqlite",timeout=30)
    c.row_factory=sqlite3.Row
    return c

def rows(sql,args=()):
    with db() as c:
        return [dict(r) for r in c.execute(sql,args).fetchall()]

def single(sql,args=()):
    result=rows(sql,args)
    return result[0] if result else None

def initialize():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS media(
          id TEXT PRIMARY KEY,name TEXT NOT NULL,path TEXT NOT NULL,details TEXT,created REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS jobs(
          id TEXT PRIMARY KEY,media_id TEXT,action TEXT,status TEXT,options TEXT,
          error TEXT,created REAL,finished REAL)""")
        c.execute("""CREATE TABLE IF NOT EXISTS artifacts(
          id TEXT PRIMARY KEY,job_id TEXT,path TEXT NOT NULL,name TEXT NOT NULL)""")
        c.execute("UPDATE jobs SET status='failed',error='Interrupted by restart' WHERE status IN ('queued','running')")

def process_job(job_id):
    job=single("SELECT * FROM jobs WHERE id=?",(job_id,))
    with db() as c: c.execute("UPDATE jobs SET status='running' WHERE id=?",(job_id,))
    try:
        opts=json.loads(job["options"])
        src=None
        if job["media_id"]:
            item=single("SELECT * FROM media WHERE id=?",(job["media_id"],))
            if not item: raise ValueError("Media not found")
            src=Path(item["path"])
        out=DATA/"exports"/job_id
        out.mkdir(exist_ok=True)
        action=job["action"]
        subtitle=None
        if action=="burn":
            subtitle_id=opts.get("subtitle_id")
            a=single("SELECT * FROM artifacts WHERE id=?",(subtitle_id,))
            m=single("SELECT * FROM media WHERE id=?",(subtitle_id,))
            if a: subtitle=Path(a["path"])
            elif m: subtitle=Path(m["path"])
        if action=="transcribe": outputs=captions.transcribe(src,out,opts)
        elif action=="burn": outputs=media.burn(src,out,opts,subtitle)
        elif action in media.ACTIONS: outputs=getattr(media,action)(src,out,opts)
        else: raise ValueError("Unknown action")
        with db() as c:
            for p in outputs:
                p=Path(p).resolve()
                if not p.is_file() or not p.is_relative_to(out.resolve()):
                    raise RuntimeError("Export path invalid")
                c.execute("INSERT INTO artifacts VALUES(?,?,?,?)",
                          (uuid.uuid4().hex,job_id,str(p),p.name))
            c.execute("UPDATE jobs SET status='done',finished=? WHERE id=?",(time.time(),job_id))
    except Exception as exc:
        with db() as c:
            c.execute("UPDATE jobs SET status='failed',error=?,finished=? WHERE id=?",
                      (str(exc)[-1500:],time.time(),job_id))

class Handler(BaseHTTPRequestHandler):
    def reply(self,status,data):
        raw=json.dumps(data,ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type","application/json; charset=utf-8")
        self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(raw)

    def fail(self,status,message):
        self.reply(status,{"error":message})

    def json_body(self):
        n=int(self.headers.get("Content-Length","0"))
        if n<=0 or n>65536: raise ValueError("Invalid JSON size")
        return json.loads(self.rfile.read(n))

    def permitted(self):
        origin=self.headers.get("Origin","")
        return not origin or origin in ("http://127.0.0.1:"+str(PORT),
                                       "http://localhost:"+str(PORT))

    def do_GET(self):
        parsed=urlsplit(self.path);path=parsed.path
        query=parse_qs(parsed.query)
        if path=="/api/status":
            import shutil
            self.reply(200,{"ffmpeg":bool(shutil.which("ffmpeg")),
                            "ffprobe":bool(shutil.which("ffprobe")),
                            "actions":sorted(media.ACTIONS)})
            return
        if path=="/api/media":
            items=rows("SELECT id,name,details,created FROM media ORDER BY created DESC LIMIT 200")
            for item in items: item["details"]=json.loads(item["details"] or "{}")
            self.reply(200,items);return
        if path=="/api/jobs":
            jobs=rows("SELECT * FROM jobs ORDER BY created DESC LIMIT 100")
            for j in jobs:
                j["options"]=json.loads(j["options"] or "{}")
                j["artifacts"]=rows("SELECT id,name FROM artifacts WHERE job_id=?",(j["id"],))
            self.reply(200,jobs);return
        if path in ("/api/source","/api/file"):
            ident=query.get("id",[""])[0]
            if path=="/api/source":
                item=single("SELECT path,name FROM media WHERE id=?",(ident,))
            else:
                item=single("SELECT path,name FROM artifacts WHERE id=?",(ident,))
            if not item: self.fail(404,"Not found");return
            file=Path(item["path"])
            if not file.is_file(): self.fail(404,"File missing");return
            # Stream media and support browser Range requests.
            total=file.stat().st_size
            range_header=self.headers.get("Range","")
            start,end=0,total-1
            if range_header.startswith("bytes="):
                import re
                match=re.fullmatch(r"bytes=(\d+)-(\d*)",range_header)
                if not match: self.fail(416,"Invalid range");return
                start=int(match.group(1))
                end=min(total-1,int(match.group(2))) if match.group(2) else end
                if start>end or start>=total: self.fail(416,"Out of range");return
            status=206 if range_header else 200
            self.send_response(status)
            self.send_header("Content-Type",mimetypes.guess_type(file.name)[0] or "application/octet-stream")
            self.send_header("Accept-Ranges","bytes")
            self.send_header("Content-Length",str(end-start+1))
            if status==206: self.send_header("Content-Range",f"bytes {start}-{end}/{total}")
            self.send_header("X-Content-Type-Options","nosniff")
            self.end_headers()
            with file.open("rb") as f:
                f.seek(start);left=end-start+1
                while left>0:
                    chunk=f.read(min(left,256*1024))
                    if not chunk: break
                    try: self.wfile.write(chunk)
                    except (BrokenPipeError,ConnectionResetError): break
                    left-=len(chunk)
            return
        if path=="/": path="/index.html"
        if path not in ("/index.html","/style.css","/app.js"):
            self.fail(404,"Unknown endpoint");return
        content=(WEB/path.lstrip("/")).read_bytes()
        self.send_response(200)
        self.send_header("Content-Type",mimetypes.guess_type(path)[0] or "text/plain")
        self.send_header("Content-Length",str(len(content)))
        self.send_header("X-Content-Type-Options","nosniff")
        self.send_header("Content-Security-Policy","default-src 'self'; img-src 'self' data:; media-src 'self'; style-src 'self'; script-src 'self'")
        self.end_headers();self.wfile.write(content)

    def do_POST(self):
        if not self.permitted(): self.fail(403,"Cross-site request blocked");return
        path=urlsplit(self.path).path
        try:
            if path=="/api/upload":
                self.upload();return
            if path=="/api/jobs":
                data=self.json_body()
                action=data.get("action")
                media_id=data.get("media_id")
                if action not in media.ACTIONS: raise ValueError("Invalid action")
                if not isinstance(media_id,str): raise ValueError("Select media")
                item=single("SELECT * FROM media WHERE id=?",(media_id,))
                if not item: raise ValueError("Media not found")
                if action!="burn" and Path(item["path"]).suffix.lower() in (".srt",".vtt",".ass"):
                    raise ValueError("Choose a video or audio file")
                opts=data.get("options") or {}
                if not isinstance(opts,dict): raise ValueError("Invalid options")
                ident=uuid.uuid4().hex
                with db() as c:
                    c.execute("INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)",
                              (ident,media_id,action,"queued",json.dumps(opts),"",time.time(),None))
                POOL.submit(process_job,ident)
                self.reply(202,{"id":ident,"status":"queued"});return
            self.fail(404,"Unknown endpoint")
        except (ValueError,KeyError,TypeError,json.JSONDecodeError) as exc:
            self.fail(400,str(exc))
        except Exception as exc:
            self.fail(500,str(exc)[-500:])

    def upload(self):
        from urllib.parse import unquote
        name=unquote(parse_qs(urlsplit(self.path).query).get("name",[""])[0])
        name=Path(name.replace("\\","/")).name[:150]
        suffix=Path(name).suffix.lower()
        if suffix not in media.EXTS | {".srt",".ass",".vtt"}:
            raise ValueError("File type not supported")
        n=int(self.headers.get("Content-Length","0"))
        if n<1 or n>MAX_UPLOAD: raise ValueError("File must be under 2GB")
        ident=uuid.uuid4().hex
        target=DATA/"uploads"/(ident+suffix)
        remaining=n
        try:
            with target.open("wb") as f:
                while remaining:
                    chunk=self.rfile.read(min(1024*1024,remaining))
                    if not chunk: raise ValueError("Incomplete upload")
                    f.write(chunk);remaining-=len(chunk)
            details=({"subtitle":True,"bytes":n} if suffix in (".srt",".ass",".vtt")
                     else media.info(target))
            with db() as c:
                c.execute("INSERT INTO media VALUES(?,?,?,?,?)",
                          (ident,name,str(target),json.dumps(details),time.time()))
        except Exception:
            target.unlink(missing_ok=True)
            raise
        self.reply(201,{"id":ident,"name":name,"details":details})

def main():
    initialize()
    import webbrowser
    if not __import__("shutil").which("ffmpeg") or not __import__("shutil").which("ffprobe"):
        print("FFmpeg and ffprobe are required. See README.md")
    server=ThreadingHTTPServer(("127.0.0.1",PORT),Handler)
    server.daemon_threads=True
    url=f"http://127.0.0.1:{PORT}"
    print(f"ZAX Auto Editor running at {url}",flush=True)
    if os.environ.get("ZAX_NO_BROWSER")!="1": webbrowser.open(url)
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()

if __name__=="__main__": main()
