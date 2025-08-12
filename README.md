# BookAudio Web UI

A web-based interface for the BookAudio project that helps you convert books to audio with OCR text correction and ElevenLabs TTS.

## Features

- **User-friendly web interface** for managing book-to-audio conversion
- **Powerful text editor** with automatic correction tools for OCR text
- **Chunk management** for handling large books (300+ pages)
- **Text flow preservation** across pages
- **Audio preview** for immediate feedback
- **Batch processing** for large books
- **EPUB support** for direct conversion from e-books

## Requirements

### System Dependencies
- tesseract-ocr with English language support
- ffmpeg
- libgl1
- python3-pip

### Directory Structure
The application uses the following directory structure:
```
/mnt/c/Users/Alex/Documents/Bookscan/
├── inbox/    # Input images
├── work/     # Temporary processed images
└── out/      # Output text and audio files
    └── text_files/  # Individual text files for editing
```

## Installation

1. **Create and activate a Python virtual environment**:
   ```bash
   sudo apt install -y python3-venv
   python3 -m venv bookaudio-env
   source bookaudio-env/bin/activate
   ```

2. **Install required Python packages**:
   ```bash
   pip install flask pillow pytesseract opencv-python piexif requests pydub elevenlabs ebooklib beautifulsoup4
   ```

3. **Set up ElevenLabs API key**:
   ```bash
   export ELEVEN_API_KEY="your_api_key_here"
   ```

4. **Create the templates directory**:
   ```bash
   mkdir -p templates
   ```

## Running the Web UI

1. **Ensure your virtual environment is activated**:
   ```bash
   source bookaudio-env/bin/activate
   ```

2. **Start the web server**:
   ```bash
   python bookaudio_web.py
   ```

3. **Access the web interface** by opening a browser and navigating to:
   ```
   http://localhost:5000
   ```

## Usage Guide

### Converting a Book to Audio

1. **Upload Book**:
   - Enter a name for your book
   - Choose either:
     - **Images tab**: Drag and drop book images or click to select files
     - **EPUB tab**: Upload an EPUB e-book file
   - Click "Upload & Process"

2. **Edit Text**:
   - Navigate through pages using Previous/Next buttons
   - Use text tools to fix common OCR issues:
     - Capitalize Sentences
     - Fix Spaces
     - Fix Hyphenation
     - Remove Line Breaks
   - Use "Show Chunk Breaks" to see where text will be split for TTS
   - Save changes for each page

3. **Generate Audio**:
   - Click "Generate Audio" to process the entire book
   - Audio files will be saved to the output directory

## Supported File Formats

- **Images**: JPG, PNG, TIFF (processed with OCR)
- **EPUB**: Electronic book format (text extracted directly)

## Voice Configuration

The application uses the "Grandpa Spuds Oxley" voice (ID: NOpBlnGInO9m6vDvFkFC) from ElevenLabs for text-to-speech conversion.

## Troubleshooting

- **Authentication errors**: Ensure your ElevenLabs API key is correctly set in the environment
- **Missing dependencies**: Make sure all system dependencies are installed
- **File permissions**: Check that the application has write access to the directory structure
- **EPUB parsing issues**: Ensure your EPUB file is valid and not DRM-protected

## License

This project is for personal use only.
