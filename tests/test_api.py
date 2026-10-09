import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request
from pathlib import Path

@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg not found")
class ApiSmoke(unittest.TestCase):
    def test_upload_and_process(self):
        with tempfile.TemporaryDirectory() as folder:
            work=Path(folder)
            src=work/"input.mp4"
            subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i",
                            "color=c=red:s=128x72:r=10:d=1",
                            "-f","lavfi","-i","sine=f=450:d=1",
                            "-shortest","-c:v","mpeg4","-c:a","aac",str(src)],
                           check=True)
            with socket.socket() as s:
                s.bind(("127.0.0.1",0))
                port=s.getsockname()[1]
            env={**os.environ,"ZAX_PORT":str(port),"ZAX_DATA_DIR":str(work/"data"),
                 "ZAX_NO_BROWSER":"1"}
            proc=subprocess.Popen([sys.executable,"-m","zax_editor.server"],env=env,
                                  stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            base="http://127.0.0.1:"+str(port)
            def call(path,body=None,raw=False):
                headers={"Content-Type":"application/json"} if body and not raw else {}
                req=urllib.request.Request(base+path,data=body,headers=headers)
                try:
                    with urllib.request.urlopen(req,timeout=20) as r: return json.load(r)
                except urllib.error.HTTPError as exc:
                    raise AssertionError(exc.read().decode()) from exc
            try:
                for _ in range(40):
                    try:
                        self.assertTrue(call("/api/status")["ffmpeg"]);break
                    except Exception: time.sleep(.1)
                else: self.fail("server did not start")
                media=call("/api/upload?name=input.mp4",src.read_bytes(),True)
                job=call("/api/jobs",json.dumps({"action":"audio","media_id":media["id"],
                                                "options":{}}).encode())
                for _ in range(50):
                    task=next(x for x in call("/api/jobs") if x["id"]==job["id"])
                    if task["status"] in ("done","failed"):break
                    time.sleep(.15)
                self.assertEqual(task["status"],"done",task["error"])
                self.assertEqual(task["artifacts"][0]["name"],"extracted-audio.mp3")
            finally:
                proc.terminate()
                try: proc.wait(timeout=4)
                except subprocess.TimeoutExpired: proc.kill()

if __name__=="__main__":unittest.main()
