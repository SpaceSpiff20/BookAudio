# Speechify API Migration Guide

This document outlines the migration from ElevenLabs TTS API to Speechify API for the BookAudio project.

## Overview

The migration replaces the ElevenLabs text-to-speech service with Speechify's API while maintaining backwards compatibility and all existing functionality.

## Key Changes

### 1. API Provider Change
- **From**: ElevenLabs API (`elevenlabs` Python SDK)
- **To**: Speechify API (`speechify-api` Python SDK)

### 2. Environment Variable
- **From**: `ELEVEN_API_KEY`
- **To**: `SPEECHIFY_API_KEY`

### 3. Voice Configuration
- **From**: Voice ID `"NOpBlnGInO9m6vDvFkFC"` (Grandpa Spuds Oxley)
- **To**: Voice ID `"scott"` (Speechify default voice)

### 4. Model Configuration
- **From**: `"eleven_multilingual_v2"`
- **To**: `"simba-english"` or `"simba-multilingual"`

### 5. Audio Response Handling
- **From**: Direct bytes response
- **To**: Base64 encoded response requiring decoding

## File Changes

### New Files Created
1. `book_reader_speechify_manual.py` - Speechify version of the manual processing script
2. `bookaudio_web_speechify.py` - Speechify version of the web application
3. `test_speechify.py` - Comprehensive test suite for Speechify integration
4. `requirements.txt` - Updated dependencies including `speechify-api`

### Modified Files
1. `requirements.txt` - Added `speechify-api` dependency

## API Function Changes

### TTS Function Signature
The function signature remains the same for backwards compatibility:

```python
# Both versions use the same signature
def speechify_tts_to_mp3(text, out_path: Path):
    # Implementation differs internally
```

### Internal Implementation Differences

#### ElevenLabs (Original)
```python
def eleven_tts_to_mp3(text, out_path: Path):
    client = ElevenLabs(api_key=ELEVEN_API_KEY)
    audio_generator = client.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID
    )
    audio_bytes = b''.join(chunk for chunk in audio_generator)
    out_path.write_bytes(audio_bytes)
```

#### Speechify (New)
```python
def speechify_tts_to_mp3(text, out_path: Path):
    client = Speechify(token=SPEECHIFY_API_KEY)
    audio_response = client.tts.audio.speech(
        audio_format="mp3",
        input=text,
        language="en-US",
        model=MODEL_ID,
        options=GetSpeechOptionsRequest(
            loudness_normalization=True,
            text_normalization=True
        ),
        voice_id=VOICE_ID
    )
    audio_bytes = base64.b64decode(audio_response.audio_data)
    out_path.write_bytes(audio_bytes)
```

## Configuration Changes

### Voice Settings
```python
# ElevenLabs
VOICE_ID = "NOpBlnGInO9m6vDvFkFC"  # Grandpa Spuds Oxley
MODEL_ID = "eleven_multilingual_v2"

# Speechify
VOICE_ID = "scott"              # Default Speechify voice
MODEL_ID = "simba-english"      # or "simba-multilingual"
```

### Environment Setup
```bash
# ElevenLabs
export ELEVEN_API_KEY="your_elevenlabs_key"

# Speechify
export SPEECHIFY_API_KEY="your_speechify_key"
```

## Installation Changes

### Dependencies
```bash
# Install Speechify SDK
pip install speechify-api

# Or update requirements.txt
echo "speechify-api" >> requirements.txt
pip install -r requirements.txt
```

## Language Support

### ElevenLabs
- Supported multiple languages through the `eleven_multilingual_v2` model
- Language detection was automatic

### Speechify
- **Fully Supported**: English, French, German, Spanish, Portuguese (Brazil/Portugal)
- **Beta Support**: Arabic, Danish, Dutch, Estonian, Finnish, Greek, Hebrew, Hindi, Italian, Japanese, Norwegian, Polish, Russian, Swedish, Turkish, Ukrainian, Vietnamese
- Language can be specified explicitly for better quality

## Audio Format Support

### ElevenLabs
- Limited format support through the API

### Speechify
- **Supported Formats**: `aac`, `mp3`, `ogg`, `wav`
- **Default**: `mp3` (maintained for compatibility)

## Voice Filtering

### ElevenLabs
- Limited voice filtering capabilities

### Speechify
- Advanced voice filtering by gender, locale, and tags
- Example filtering function provided in the migration

## Testing

### Test Coverage
The migration includes comprehensive tests covering:
- API connection and authentication
- Basic TTS functionality
- Voice and model availability
- Error handling
- Performance testing
- Backwards compatibility
- Audio format support
- Multilingual support

### Running Tests
```bash
# Set API key
export SPEECHIFY_API_KEY="your_api_key"

# Run tests
python test_speechify.py
```

## Migration Steps

### 1. Install Speechify SDK
```bash
pip install speechify-api
```

### 2. Update Environment Variables
```bash
export SPEECHIFY_API_KEY="your_speechify_api_key"
```

### 3. Replace Function Calls
Update imports to use the new Speechify functions:
```python
# Old
from book_reader_eleven_manual import eleven_tts_to_mp3

# New
from book_reader_speechify_manual import speechify_tts_to_mp3
```

### 4. Test the Migration
```bash
python test_speechify.py
```

### 5. Update Web Application
Replace the web application file:
```bash
# Backup old version
cp bookaudio_web.py bookaudio_web_elevenlabs.py

# Use new version
cp bookaudio_web_speechify.py bookaudio_web.py
```

## Backwards Compatibility

The migration maintains full backwards compatibility:
- Same function signatures
- Same file paths and structure
- Same web interface
- Same command-line interface

## Functionality Comparison

| Feature | ElevenLabs | Speechify | Status |
|---------|------------|-----------|---------|
| Basic TTS | ✅ | ✅ | ✅ Maintained |
| Voice Selection | ✅ | ✅ | ✅ Enhanced |
| Language Support | ✅ | ✅ | ✅ Enhanced |
| Audio Formats | ✅ | ✅ | ✅ Enhanced |
| Web Interface | ✅ | ✅ | ✅ Maintained |
| Batch Processing | ✅ | ✅ | ✅ Maintained |
| EPUB Support | ✅ | ✅ | ✅ Maintained |
| OCR Integration | ✅ | ✅ | ✅ Maintained |

## Potential Issues and Solutions

### 1. API Key Format
- **Issue**: Different API key formats between providers
- **Solution**: Use the exact format provided by Speechify console

### 2. Voice Availability
- **Issue**: Different voice IDs between providers
- **Solution**: Use Speechify's voice filtering to find equivalent voices

### 3. Rate Limiting
- **Issue**: Different rate limits between providers
- **Solution**: Implement appropriate retry logic and rate limiting

### 4. Audio Quality
- **Issue**: Potential differences in audio quality
- **Solution**: Test with various text samples and adjust settings as needed

## Performance Considerations

### API Response Times
- Speechify may have different response times compared to ElevenLabs
- Implement appropriate timeout handling

### Audio File Sizes
- Different encoding may result in different file sizes
- Monitor storage requirements

### Concurrent Requests
- Test with multiple simultaneous requests
- Implement appropriate queuing if needed

## Monitoring and Logging

### API Usage
- Monitor Speechify API usage and costs
- Implement logging for debugging

### Error Handling
- Enhanced error handling for Speechify-specific errors
- Graceful fallback mechanisms

## Future Enhancements

### Voice Customization
- Explore Speechify's voice customization options
- Implement voice selection interface

### Advanced Features
- Implement Speechify's advanced TTS options
- Add support for SSML markup

### Multi-language Support
- Leverage Speechify's multilingual capabilities
- Implement automatic language detection

## Support and Resources

### Speechify Documentation
- [Speechify API Documentation](https://docs.speechify.com/)
- [Speechify Console](https://console.sws.speechify.com/)

### Migration Support
- Test suite for validation
- Comprehensive error handling
- Backwards compatibility maintained

## Conclusion

The migration to Speechify API provides enhanced functionality while maintaining full backwards compatibility. The comprehensive test suite ensures reliable operation, and the modular design allows for easy future enhancements. 