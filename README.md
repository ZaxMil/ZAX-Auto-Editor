# ZAX Auto Editor

Free, open-source, local-first video editing studio with an Arabic-friendly dashboard.
Python standard library + FFmpeg. No Electron or cloud account required.

**Status: v0.1 MVP.** A working local video-processing tool, NOT a finished native Premiere/After Effects extension.

## Available tools

| Tool | Result |
|---|---|
| Automatic silence cutting | Edited MP4 + JSON cut list + experimental FCP7 XML timeline |
| Offline AI transcription (optional) | Arabic/English SRT, VTT and JSON |
| Burn subtitles | MP4 with SRT/VTT/ASS captions |
| Reframe for social | 9:16, 16:9, 1:1, 4:5, crop or pad |
| Compress MP4 | H.264 with quality setting |
| Extract sound | MP3 |
| Scene detection | Cut times in CSV and JSON |
| Thumbnail export | JPEG image |
| Audio denoise | Cleaned MP4 |

The app stores uploads, job history and exports in a local .local directory, excluded from Git. The web server binds only to 127.0.0.1, not the public network.

## Windows installation

1. Install Python 3.11 or 3.12 from https://www.python.org/downloads/ . Enable Add Python to PATH.
2. Install FFmpeg from Windows Terminal: winget install Gyan.FFmpeg . Reopen Terminal afterward.
3. On GitHub choose Code > Download ZIP. Extract the folder.
4. Double-click scripts/start-windows.bat.
5. If necessary open http://127.0.0.1:8765 .

The basic nine tools require no extra Python packages; FFmpeg is mandatory.

For offline AI captions, open Terminal in the project directory and run:
    python -m pip install -r requirements-ai.txt

The first transcription downloads the selected model once. CPU-only processing may be slow on older hardware.

Optional AI assistant: install Ollama from https://ollama.com , run
    ollama pull qwen2.5:3b
and use the assistant panel to describe the edit in Arabic. The AI only selects a supported tool and proposes settings; you review them and start the task. Ollama weights require disk space and RAM.

## Linux installation

Install Python 3 and FFmpeg, then execute:
    bash scripts/start-linux.sh

## Usage

1. Upload a supported video or audio file.
2. Pick an editing tool and its settings.
3. Select Start. The job queue processes one media job at a time.
4. Download the output from the activity panel.
5. For burned subtitles, first create captions with the AI transcription tool or upload an SRT file.

## Adobe compatibility

Exported MP4 can be imported manually into Premiere Pro or After Effects.

An experimental helper script lives at adobe/import_to_after_effects.jsx.
In After Effects use File > Scripts > Run Script File to choose the .jsx,
then select one of the exported MP4s.

Adobe-native Premiere panel, effects animation and full AI editing agent
are not implemented yet. Adobe is a trademark of Adobe Inc. This project
is independent from and not endorsed by Adobe.

## Security and limitations

- Binds only to localhost. DO NOT expose port 8765 publicly.
- Maximum 2 GB per upload. One processing worker at a time.
- No multi-user login. Do not use as a public SaaS application.
- The selected Whisper model is downloaded on first use.
- Uploaded media and outputs remain on the host machine, not a cloud service.
- Windows startup and Adobe integration need Windows/Adobe validation.
- No ChatGPT/Claude API fees included or bypassed.

## Run the tests

    python -m unittest discover -s tests -v

The included tests run locally. FFmpeg integration tests run when FFmpeg is available.

License: MIT.
