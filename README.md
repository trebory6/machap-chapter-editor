# MaChap Chapter Editor

MaChap is a simple desktop video chapter editor designed to detect and manage chapters based on black frames, using FFmpeg as the underlying engine.

This is a learning project, and I'm still figuring things out as I go. The code isn't perfect, and I'm sure there's a better way to do a lot of what I've written. Feedback, suggestions, and improvements are welcome.

---

## Features

- Scans video files and identifies likely chapter locations based on black segments.
- Adjustable detection settings: minimum black duration, pixel ratio, luminance threshold.
- Displays video alongside a visual chapter timeline.
- Chapter list shows all detected and manual chapters with timestamps.
- Allows manual creation and deletion of chapters via the timeline or buttons.
- Batch file import for scanning, reviewing, and exporting chapters across multiple files.
- (WIP) Export support for `.mp4`, `.mkv`, and `.txt` chapter formats (MKVmerge-compatible).

---

## How to Use

### Editing a Single File:

1. Click **Load Video**.
2. Use default detection settings or open **Scan Settings** to adjust parameters.
3. Click **Detect Black Frames**. (This may take a few seconds to a few minutes depending on the file.)
4. Use the chapter list on the right to jump to chapters. Press `Delete` or click **Remove Chapter** to remove unwanted chapters.
5. Navigate frames using the arrow keys or frame buttons.
6. Add chapters manually by clicking **Add Chapter Here** or pressing the `A` key.
7. (WIP) Click **Export File** or **Add to Export Queue** to prepare a file for output with chapters.

### Batch Import and Scan:

1. Click **Open Queue Manager**.
2. Click **Load Files** and select multiple video files.
3. Adjust scan settings if needed.
4. Click **Scan All Files**. A loading dialog will appear.
5. After scanning, double-click a file to open it in the main editor with its chapters preloaded.
6. Make any manual adjustments as needed.
7. (WIP) Click **Export File** or **Add to Export Queue** to prepare a file for output with chapters.

---

## Settings Explanation

- **Minimum Black Seconds**: The minimum duration for a black frame sequence to be considered a chapter boundary.
- **Black Pixel Ratio**: How much of the frame must be dark to count as a black frame.
- **Black Pixel Threshold**: How dark a pixel has to be to qualify as “black.”
- **Scan Time Windows**: Time ranges (formatted as `HH:MM:SS:HH:MM:SS`, comma-separated) to restrict detection to specific portions of the video.
- **Export Format**: Choose between `.mp4`, `.mkv`, or `.txt (MKVmerge)`.

---

## Keyboard Shortcuts

- **Spacebar** — Play/Pause
- **Left Arrow** — Step one frame backward
- **Right Arrow** — Step one frame forward
- **M** — Mute/Unmute
- **A** — Add chapter at current time
- **Delete** — Remove selected chapter in the list

---

## WIP (Work in Progress)

- Export functionality:
  - Embed chapters directly into `.mp4` or `.mkv`
  - Convert and re-encode AVI/WMV files to selected format with settings to maintain visual quality and similar file size
- Export queue processing
- Settings persistence across sessions

---

## Roadmap

- **Video Splitter Mode**: Automatically split video into segments based on chapter markers. Useful for cutting out commercial blocks.
- **Profiles**: Save and switch between different scan/export presets.

---

## Known Bugs

- Keyboard shortcuts remain active even when focus is on other windows (e.g. settings).

---

## Requirements

- Python 3.10+
- FFmpeg installed and accessible via command line
- PySide6 (Qt for Python)

---

## How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
2. Launch the app:
   ```bash
   python3 main.py

## Contributing

This project was built as a way to learn desktop app development and work with video tools. I'm learning as I go and welcome any kind of constructive feedback. If you have ideas, fixes, or suggestions, feel free to open an issue or a pull request.

– [trebory6](https://github.com/trebory6)

---

## Acknowledgments

The chapter detection logic used in this project is derived from [mkchap](https://github.com/jasongdove/mkchap), and this tool is designed with use alongside [ErsatzTV](https://github.com/ErsatzTV/ErsatzTV) to inject commercials at chapter points.

Thanks to [@jasongdove](https://github.com/jasongdove) for both projects and for his work making these kinds of tools possible.
