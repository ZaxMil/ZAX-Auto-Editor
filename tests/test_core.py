import json
import shutil
import tempfile
import unittest
from pathlib import Path
from zax_editor import media, captions

class TimelineTests(unittest.TestCase):
    def test_no_silence(self):
        self.assertEqual(media.kept_ranges("",5),[(0.0,5.0)])

    def test_pause_in_middle(self):
        log="[silencedetect] silence_start: 1.0\n[silencedetect] silence_end: 2.0 | silence_duration: 1"
        self.assertEqual(media.kept_ranges(log,3,.1),[(0.0,1.1),(1.9,3)])

    def test_silence_at_end(self):
        self.assertEqual(media.kept_ranges("silence_start: 2",3,0),[(0.0,2)])

    def test_timestamps(self):
        self.assertEqual(captions.stamp(3723.456),"01:02:03,456")
        self.assertEqual(captions.stamp(1.234,True),"00:00:01.234")

    def test_ai_plan_validation(self):
        from zax_editor.planner import validate
        self.assertEqual(validate({"action":"resize","options":{"ratio":"9:16","shell":"rm -rf /"}})["options"],{"ratio":"9:16"})
        with self.assertRaises(ValueError):
            validate({"action":"delete_all","options":{}})

    def test_caption_export(self):
        with tempfile.TemporaryDirectory() as d:
            files=captions.write_subtitles([{"start":0.5,"end":2.1,"text":"أهلا وسهلا"}],Path(d))
            self.assertEqual(len(files),3)
            self.assertIn("أهلا وسهلا",files[0].read_text(encoding="utf-8"))
            self.assertIn("WEBVTT",files[1].read_text(encoding="utf-8"))
            self.assertEqual(json.loads(files[2].read_text(encoding="utf-8"))[0]["start"],.5)

    @unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg missing")
    def test_ffmpeg_pipeline(self):
        with tempfile.TemporaryDirectory() as d:
            folder=Path(d);src=folder/"test.mp4"
            media.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","color=c=blue:s=128x72:r=12:d=2",
                       "-f","lavfi","-i","sine=f=500:d=2","-shortest","-c:v","mpeg4",
                       "-c:a","aac",src])
            meta=media.info(src)
            self.assertEqual(meta["width"],128)
            self.assertTrue(meta["audio"])
            for name in ("audio","thumbnail","compress","scenes","silence"):
                dest=folder/name;dest.mkdir()
                results=getattr(media,name)(src,dest,{})
                self.assertTrue(all(p.is_file() for p in results),name)
            self.assertTrue((folder/"silence"/"silence-cut.mp4").is_file())
            import xml.etree.ElementTree as ET
            xml=ET.parse(folder/"silence"/"premiere-timeline.xml")
            self.assertEqual(xml.getroot().tag,"xmeml")

if __name__=="__main__": unittest.main()
