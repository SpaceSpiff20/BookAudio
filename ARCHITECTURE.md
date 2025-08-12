# BookAudio: Architecture Plan

## 1. System Overview

BookAudio is designed as a modular pipeline system that processes book images into text and audio outputs. The architecture prioritizes simplicity, reliability, and extensibility while maintaining a low barrier to entry for users.

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│             │     │             │     │             │     │             │
│  Image      │────▶│  Image      │────▶│  Text       │────▶│  Audio      │
│  Acquisition│     │  Processing │     │  Extraction │     │  Generation │
│             │     │             │     │             │     │             │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                          │                   │                   │
                          ▼                   ▼                   ▼
                    ┌─────────────────────────────────────────────────┐
                    │                                                 │
                    │              File Management                    │
                    │                                                 │
                    └─────────────────────────────────────────────────┘
```

## 2. Component Architecture

### 2.1 Core Components

#### 2.1.1 Configuration Manager
- Handles all system settings and parameters
- Loads from config file with sensible defaults
- Provides centralized access to configuration values

#### 2.1.2 Image Processing Module
- Responsible for image preprocessing
- Handles rotation, deskewing, and enhancement
- Detects and splits two-page spreads
- Prepares images for optimal OCR performance

#### 2.1.3 OCR Engine
- Extracts text from processed images
- Supports multiple languages
- Handles text cleaning and normalization
- Provides confidence scores for extraction quality

#### 2.1.4 Text-to-Speech Service
- Interfaces with ElevenLabs API
- Manages API authentication and rate limiting
- Converts extracted text to audio
- Handles audio format conversion if needed

#### 2.1.5 File Manager
- Manages input/output directories
- Handles file naming conventions
- Tracks processing state for batch operations
- Combines individual audio files

### 2.2 Supporting Components

#### 2.2.1 Logger
- Provides consistent logging across components
- Supports different verbosity levels
- Records processing statistics and errors

#### 2.2.2 Error Handler
- Centralizes error management
- Implements retry strategies for transient failures
- Provides user-friendly error messages

## 3. Data Flow

### 3.1 Primary Processing Pipeline
1. User places images in the inbox directory
2. System loads and sorts images by EXIF timestamp
3. Each image is preprocessed and potentially split
4. OCR extracts text from each processed image
5. Text is sent to TTS service for audio generation
6. Individual audio files are created and combined
7. Final outputs (text and audio) are saved to output directory

### 3.2 Configuration Flow
1. System loads default configuration
2. User-provided settings override defaults
3. Configuration is validated
4. Components are initialized with appropriate settings

## 4. Technical Implementation

### 4.1 Module Structure
```
bookaudio/
├── __init__.py
├── config.py           # Configuration management
├── image_processor.py  # Image preprocessing functions
├── ocr_engine.py       # Text extraction functionality
├── tts_service.py      # ElevenLabs API integration
├── file_manager.py     # File and directory operations
├── utils/
│   ├── __init__.py
│   ├── logging.py      # Logging utilities
│   └── error_handler.py # Error management
└── main.py             # Entry point and orchestration
```

### 4.2 Key Interfaces

#### Configuration Interface
```python
class Config:
    def __init__(self, config_path=None)
    def get(self, key, default=None)
    def set(self, key, value)
    def save(self, path=None)
```

#### Image Processor Interface
```python
class ImageProcessor:
    def __init__(self, config)
    def process_image(self, image_path)
    def auto_rotate_deskew(self, image)
    def split_pages(self, image)
    def enhance_for_ocr(self, image)
```

#### OCR Engine Interface
```python
class OCREngine:
    def __init__(self, config)
    def extract_text(self, image, languages=None)
    def clean_text(self, text)
    def get_confidence(self)
```

#### TTS Service Interface
```python
class TTSService:
    def __init__(self, config)
    def text_to_speech(self, text, output_path)
    def combine_audio_files(self, file_paths, output_path)
```

#### File Manager Interface
```python
class FileManager:
    def __init__(self, config)
    def ensure_directories()
    def get_input_files()
    def save_processed_image(self, image, page_id)
    def save_text(self, text, append=False)
    def get_output_path(self, file_type, page_id=None)
```

## 5. External Dependencies

### 5.1 Core Libraries
- OpenCV (cv2): Image processing
- Tesseract (pytesseract): OCR engine
- Pillow (PIL): Image manipulation
- Requests: API communication
- Pydub: Audio processing

### 5.2 External Services
- ElevenLabs API: Text-to-speech conversion

## 6. Deployment Architecture

### 6.1 Current Deployment
- WSL2 Ubuntu environment
- Windows filesystem integration for input/output
- Command-line interface

### 6.2 Future Deployment Options
- Standalone Python package
- Docker container
- Web service with REST API
- GUI application

## 7. Security Considerations

- API key management via environment variables
- No persistent storage of sensitive information
- Input validation to prevent command injection

## 8. Performance Considerations

- Batch processing for efficiency
- Potential for parallel processing of images
- Caching of API responses for repeated text
- Optimized image preprocessing for speed

## 9. Scalability Path

### 9.1 Short-term Scaling
- Support for larger batch sizes
- Improved error recovery for long-running jobs
- Memory optimization for large books

### 9.2 Long-term Scaling
- Distributed processing architecture
- Cloud-based processing option
- Database backend for job tracking
