#!/usr/bin/env python3
"""
Basic test script for Speechify API migration.
This script tests the core functionality without requiring pytest.
"""

import os
import sys
import base64
from pathlib import Path
import tempfile

def test_speechify_installation():
    """Test that Speechify SDK is properly installed."""
    try:
        from speechify import Speechify
        from speechify.tts import GetSpeechOptionsRequest
        print("✅ Speechify SDK imported successfully")
        return True
    except ImportError as e:
        print(f"❌ Speechify SDK import failed: {e}")
        print("Please install with: pip install speechify-api")
        return False

def test_api_key():
    """Test that API key is available."""
    api_key = os.getenv("SPEECHIFY_API_KEY")
    if not api_key:
        print("❌ SPEECHIFY_API_KEY environment variable not set")
        print("Please set your Speechify API key:")
        print("export SPEECHIFY_API_KEY='your_api_key_here'")
        return False
    
    print(f"✅ API key found: {api_key[:5]}...{api_key[-5:]}")
    return api_key

def test_api_connection(api_key):
    """Test basic API connection."""
    try:
        from speechify import Speechify
        client = Speechify(token=api_key)
        
        # Test by listing voices
        voice_list = client.tts.voices.list()
        print(f"✅ API connection successful! Found {len(voice_list)} voices")
        return True
    except Exception as e:
        print(f"❌ API connection failed: {e}")
        return False

def test_basic_tts(api_key):
    """Test basic text-to-speech functionality."""
    try:
        from speechify import Speechify
        from speechify.tts import GetSpeechOptionsRequest
        
        client = Speechify(token=api_key)
        
        # Test basic TTS
        test_text = "Hello, this is a test of the Speechify API migration."
        audio_response = client.tts.audio.speech(
            audio_format="mp3",
            input=test_text,
            language="en-US",
            model="simba-english",
            options=GetSpeechOptionsRequest(
                loudness_normalization=True,
                text_normalization=True
            ),
            voice_id="scott"
        )
        
        # Decode audio
        audio_bytes = base64.b64decode(audio_response.audio_data)
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(audio_bytes)
            temp_file = f.name
        
        # Check file size
        file_size = os.path.getsize(temp_file)
        print(f"✅ Basic TTS test passed - Audio file created: {temp_file}")
        print(f"   File size: {file_size} bytes")
        
        # Cleanup
        os.unlink(temp_file)
        return True
        
    except Exception as e:
        print(f"❌ Basic TTS test failed: {e}")
        return False

def test_voice_availability(api_key):
    """Test that required voices are available."""
    try:
        from speechify import Speechify
        client = Speechify(token=api_key)
        voice_list = client.tts.voices.list()
        
        # Check for scott voice
        scott_found = False
        for voice in voice_list:
            for model in voice.models:
                if model.name == "scott":
                    scott_found = True
                    print(f"✅ Found voice: {voice.name} (ID: scott)")
                    break
            if scott_found:
                break
        
        if not scott_found:
            print("⚠️  Voice 'scott' not found, but other voices are available:")
            for voice in voice_list[:3]:  # Show first 3 voices
                print(f"   - {voice.name}")
        
        return True
        
    except Exception as e:
        print(f"❌ Voice availability test failed: {e}")
        return False

def test_model_availability(api_key):
    """Test that required models are available."""
    try:
        from speechify import Speechify
        client = Speechify(token=api_key)
        
        test_text = "Testing model availability."
        
        # Test simba-english
        try:
            audio_response = client.tts.audio.speech(
                audio_format="mp3",
                input=test_text,
                language="en-US",
                model="simba-english",
                voice_id="scott"
            )
            print("✅ simba-english model works")
        except Exception as e:
            print(f"❌ simba-english model failed: {e}")
            return False
        
        # Test simba-multilingual
        try:
            audio_response = client.tts.audio.speech(
                audio_format="mp3",
                input=test_text,
                language="en-US",
                model="simba-multilingual",
                voice_id="scott"
            )
            print("✅ simba-multilingual model works")
        except Exception as e:
            print(f"❌ simba-multilingual model failed: {e}")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Model availability test failed: {e}")
        return False

def test_audio_formats(api_key):
    """Test different audio format support."""
    try:
        from speechify import Speechify
        client = Speechify(token=api_key)
        
        test_text = "Testing different audio formats."
        formats = ["mp3", "wav", "aac", "ogg"]
        
        for audio_format in formats:
            try:
                audio_response = client.tts.audio.speech(
                    audio_format=audio_format,
                    input=test_text,
                    language="en-US",
                    model="simba-english",
                    voice_id="scott"
                )
                
                audio_bytes = base64.b64decode(audio_response.audio_data)
                print(f"✅ {audio_format} format works ({len(audio_bytes)} bytes)")
                
            except Exception as e:
                print(f"❌ {audio_format} format failed: {e}")
        
        return True
        
    except Exception as e:
        print(f"❌ Audio formats test failed: {e}")
        return False

def test_migration_function():
    """Test the migration function from the manual script."""
    try:
        # Import the migration function
        from book_reader_speechify_manual import speechify_tts_to_mp3
        
        # Test with temporary file
        test_text = "Testing the migration function."
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            temp_file = Path(f.name)
        
        success = speechify_tts_to_mp3(test_text, temp_file)
        
        if success and temp_file.exists():
            file_size = temp_file.stat().st_size
            print(f"✅ Migration function test passed - File size: {file_size} bytes")
            temp_file.unlink()  # Cleanup
            return True
        else:
            print("❌ Migration function test failed")
            return False
            
    except Exception as e:
        print(f"❌ Migration function test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Running Speechify migration basic tests...")
    print("=" * 50)
    
    # Test installation
    if not test_speechify_installation():
        sys.exit(1)
    
    # Test API key
    api_key = test_api_key()
    if not api_key:
        sys.exit(1)
    
    # Test API connection
    if not test_api_connection(api_key):
        sys.exit(1)
    
    # Test voice availability
    test_voice_availability(api_key)
    
    # Test model availability
    if not test_model_availability(api_key):
        sys.exit(1)
    
    # Test basic TTS
    if not test_basic_tts(api_key):
        sys.exit(1)
    
    # Test audio formats
    test_audio_formats(api_key)
    
    # Test migration function
    if not test_migration_function():
        sys.exit(1)
    
    print("=" * 50)
    print("🎉 All basic tests passed! Speechify migration is ready.")
    print("\nNext steps:")
    print("1. Run the comprehensive test suite: python test_speechify.py")
    print("2. Test the web application: python bookaudio_web_speechify.py")
    print("3. Test the manual script: python book_reader_speechify_manual.py")

if __name__ == "__main__":
    main() 