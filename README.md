# MaChap Chapter Editor

MaChap is a simple desktop video chapter editor designed to detect and manage chapters based on black frames, using FFmpeg as the underlying engine.

This is a learning project, and I'm still figuring things out as I go. The code isn't perfect, and I'm sure there's a better way to do a lot of what I've written. Feedback, suggestions, and improvements are welcome.

## What It Does

- Loads common video formats like AVI, MKV, and MP4
- Scans videos for black frames
- Automatically identifies likely chapter locations based on black segments
- Displays chapter markers visually on a timeline
- Allows manual chapter creation at the current playback time
- Allows removal of chapters near the current playback time
- Exports chapter information in mkvmerge-compatible text format

## Planned Features

- A chapter list panel to view, jump to, or delete chapters
- A batch scan queue for detecting black frames in multiple files
- A queue for exporting videos with embedded chapter data
- UI options to customize blackdetect sensitivity

## Requirements

- Python 3.10+
- FFmpeg installed and accessible via command line
- PySide6 (Qt for Python)

## How to Run

1. Install dependencies: ` pip install -r requirements.txt `

2. Run the app: ` python3 main.py`

## Contributing

This project was built as a way to learn desktop app development and work with video tools. I'm learning as I go and welcome any kind of constructive feedback. If you have ideas, fixes, or suggestions, feel free to open an issue or a pull request.

– [trebory6](https://github.com/trebory6)
