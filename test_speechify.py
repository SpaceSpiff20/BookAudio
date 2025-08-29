#!/usr/bin/env python3
"""
Comprehensive test suite for Speechify API migration.
Tests all aspects of the TTS functionality and ensures backwards compatibility.
"""

import os
import sys
import base64
import pytest
from pathlib import Path
import tempfile
import shutil

# Try to import speechify
try:
    from speechify import Speechify
    from speechify.tts import GetSpeechOptionsRequest
    print("✅ Speechify SDK imported successfully")
except ImportError:
    print("❌ Speechify SDK not installed. Installing...")
    os.system("pip install speechify-api")
    try:
        from speechify import Speechify
        from speechify.tts import GetSpeechOptionsRequest
        print("✅ Speechify SDK installed and imported successfully")
    except ImportError:
        print("❌ Failed to install Speechify SDK. Please install manually: pip install speechify-api")
        sys.exit(1)

# Import the functions we're testing
from book_reader_speechify_manual import speechify_tts_to_mp3, combine_mp3s

class TestSpeechifyMigration:
    """Test suite for Speechify API migration."""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment."""
        self.api_key = os.getenv("SPEECHIFY_API_KEY")
        if not self.api_key:
            pytest.skip("SPEECHIFY_API_KEY environment variable not set")
        
        # Create temporary directory for test outputs
        self.test_dir = Path(tempfile.mkdtemp())
        self.test_output = self.test_dir / "test_output.mp3"
        
        yield
        
        # Cleanup
        shutil.rmtree(self.test_dir)
    
    def test_api_connection(self):
        """Test basic API connection and authentication."""
        client = Speechify(token=self.api_key)
        
        # Test by listing voices
        voice_list = client.tts.voices.list()
        assert len(voice_list) > 0, "Should be able to list voices"
        print(f"✅ API connection successful! Found {len(voice_list)} voices")
    
    def test_default_voice_availability(self):
        """Test that the default voice 'scott' is available."""
        client = Speechify(token=self.api_key)
        voice_list = client.tts.voices.list()
        
        # Check if 'scott' voice is available
        scott_voice = None
        for voice in voice_list:
            for model in voice.models:
                if model.name == "scott":
                    scott_voice = voice
                    break
            if scott_voice:
                break
        
        assert scott_voice is not None, "Default voice 'scott' should be available"
        print(f"✅ Default voice 'scott' is available")
    
    def test_basic_tts_functionality(self):
        """Test basic text-to-speech conversion."""
        test_text = "Testing Speechify migration with basic functionality."
        
        success = speechify_tts_to_mp3(test_text, self.test_output)
        assert success, "TTS conversion should succeed"
        assert self.test_output.exists(), "Output file should be created"
        assert self.test_output.stat().st_size > 1000, "Audio file should have reasonable size"
        
        print(f"✅ Basic TTS test passed - file size: {self.test_output.stat().st_size} bytes")
    
    def test_empty_text_handling(self):
        """Test handling of empty or None text."""
        # Test empty string
        success = speechify_tts_to_mp3("", self.test_output)
        assert not success, "Empty text should not generate audio"
        
        # Test None
        success = speechify_tts_to_mp3(None, self.test_output)
        assert not success, "None text should not generate audio"
        
        print("✅ Empty text handling test passed")
    
    def test_long_text_handling(self):
        """Test handling of longer text passages."""
        long_text = """
        This is a longer text passage to test how the Speechify API handles 
        substantial amounts of text. It should be able to process multiple 
        sentences and paragraphs without issues. The audio output should be 
        coherent and well-formatted.
        
        This second paragraph tests paragraph breaks and formatting. The API 
        should maintain proper pacing and natural speech patterns even with 
        longer content.
        """
        
        success = speechify_tts_to_mp3(long_text, self.test_output)
        assert success, "Long text should be processed successfully"
        assert self.test_output.exists(), "Output file should be created"
        
        print(f"✅ Long text test passed - file size: {self.test_output.stat().st_size} bytes")
    
    def test_special_characters(self):
        """Test handling of special characters and punctuation."""
        special_text = "Testing special characters: !@#$%^&*()_+-=[]{}|;':\",./<>?`~"
        
        success = speechify_tts_to_mp3(special_text, self.test_output)
        assert success, "Special characters should be handled gracefully"
        
        print("✅ Special characters test passed")
    
    def test_multilingual_support(self):
        """Test multilingual model support."""
        # Test with simba-multilingual model
        client = Speechify(token=self.api_key)
        
        # Test English text
        english_text = "Hello, this is a test in English."
        audio_response = client.tts.audio.speech(
            audio_format="mp3",
            input=english_text,
            language="en-US",
            model="simba-multilingual",
            voice_id="scott"
        )
        
        assert audio_response.audio_data, "Should get audio data for English"
        
        # Test Spanish text
        spanish_text = "Hola, esto es una prueba en español."
        audio_response = client.tts.audio.speech(
            audio_format="mp3",
            input=spanish_text,
            language="es-ES",
            model="simba-multilingual",
            voice_id="scott"
        )
        
        assert audio_response.audio_data, "Should get audio data for Spanish"
        
        print("✅ Multilingual support test passed")
    
    def test_audio_formats(self):
        """Test different audio format support."""
        client = Speechify(token=self.api_key)
        test_text = "Testing different audio formats."
        
        formats = ["mp3", "wav", "aac", "ogg"]
        
        for audio_format in formats:
            audio_response = client.tts.audio.speech(
                audio_format=audio_format,
                input=test_text,
                language="en-US",
                model="simba-english",
                voice_id="scott"
            )
            
            assert audio_response.audio_data, f"Should get audio data for {audio_format} format"
            assert audio_response.audio_format == audio_format, f"Response format should match {audio_format}"
            
            # Decode and verify it's valid audio data
            audio_bytes = base64.b64decode(audio_response.audio_data)
            assert len(audio_bytes) > 100, f"Audio data should have reasonable size for {audio_format}"
        
        print("✅ Audio formats test passed")
    
    def test_voice_filtering(self):
        """Test voice filtering functionality."""
        client = Speechify(token=self.api_key)
        voice_list = client.tts.voices.list()
        
        def filter_voice_models(voices, *, gender=None, locale=None, tags=None):
            """
            Filter Speechify voices by gender, locale, and/or tags,
            and return the list of model IDs for matching voices.
            """
            results = []
            
            for voice in voices:
                # gender filter
                if gender and voice.gender.lower() != gender.lower():
                    continue
                
                # locale filter (check across models and languages)
                if locale:
                    if not any(
                        any(lang.locale == locale for lang in model.languages)
                        for model in voice.models
                    ):
                        continue
                
                # tags filter
                if tags:
                    if not all(tag in voice.tags for tag in tags):
                        continue
                
                # If we got here, the voice matches -> collect model ids
                for model in voice.models:
                    results.append(model.name)
            
            return results
        
        # Test filtering by gender
        male_voices = filter_voice_models(voice_list, gender="male")
        female_voices = filter_voice_models(voice_list, gender="female")
        
        assert len(male_voices) > 0, "Should find male voices"
        assert len(female_voices) > 0, "Should find female voices"
        
        # Test filtering by locale
        en_us_voices = filter_voice_models(voice_list, locale="en-US")
        assert len(en_us_voices) > 0, "Should find en-US voices"
        
        print("✅ Voice filtering test passed")
    
    def test_mp3_combination(self):
        """Test MP3 file combination functionality."""
        # Create multiple test audio files
        test_files = []
        test_texts = [
            "First audio segment for testing.",
            "Second audio segment for testing.",
            "Third audio segment for testing."
        ]
        
        for i, text in enumerate(test_texts):
            test_file = self.test_dir / f"test_{i}.mp3"
            success = speechify_tts_to_mp3(text, test_file)
            assert success, f"Should create test file {i}"
            test_files.append(test_file)
        
        # Combine the files
        combined_file = self.test_dir / "combined.mp3"
        combine_mp3s(test_files, combined_file)
        
        assert combined_file.exists(), "Combined file should be created"
        assert combined_file.stat().st_size > sum(f.stat().st_size for f in test_files), "Combined file should be larger than individual files"
        
        print(f"✅ MP3 combination test passed - combined file size: {combined_file.stat().st_size} bytes")
    
    def test_error_handling(self):
        """Test error handling for various failure scenarios."""
        # Test with invalid API key
        original_key = os.environ.get("SPEECHIFY_API_KEY")
        os.environ["SPEECHIFY_API_KEY"] = "invalid_key"
        
        success = speechify_tts_to_mp3("Test text", self.test_output)
        assert not success, "Should fail with invalid API key"
        
        # Restore original key
        if original_key:
            os.environ["SPEECHIFY_API_KEY"] = original_key
        else:
            del os.environ["SPEECHIFY_API_KEY"]
        
        print("✅ Error handling test passed")
    
    def test_backwards_compatibility(self):
        """Test that the new function signature is backwards compatible."""
        # The function should accept the same parameters as the original eleven_tts_to_mp3
        test_text = "Testing backwards compatibility."
        
        # Test with the same signature as the original function
        success = speechify_tts_to_mp3(test_text, self.test_output)
        assert success, "Function should work with original signature"
        
        print("✅ Backwards compatibility test passed")
    
    def test_performance(self):
        """Test performance with multiple concurrent requests."""
        import time
        import threading
        
        test_text = "Performance test text."
        results = []
        
        def generate_audio(thread_id):
            output_file = self.test_dir / f"perf_test_{thread_id}.mp3"
            start_time = time.time()
            success = speechify_tts_to_mp3(test_text, output_file)
            end_time = time.time()
            results.append({
                'thread_id': thread_id,
                'success': success,
                'duration': end_time - start_time
            })
        
        # Run multiple threads
        threads = []
        for i in range(3):
            thread = threading.Thread(target=generate_audio, args=(i,))
            threads.append(thread)
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Check results
        successful_requests = sum(1 for r in results if r['success'])
        assert successful_requests > 0, "At least some requests should succeed"
        
        avg_duration = sum(r['duration'] for r in results) / len(results)
        print(f"✅ Performance test passed - Average duration: {avg_duration:.2f}s")

def test_voice_availability():
    """Test that required voices are available."""
    api_key = os.getenv("SPEECHIFY_API_KEY")
    if not api_key:
        pytest.skip("SPEECHIFY_API_KEY environment variable not set")
    
    client = Speechify(token=api_key)
    voice_list = client.tts.voices.list()
    
    # Check for scott voice
    scott_found = False
    for voice in voice_list:
        for model in voice.models:
            if model.name == "scott":
                scott_found = True
                break
        if scott_found:
            break
    
    assert scott_found, "Default voice 'scott' should be available"
    print("✅ Voice availability test passed")

def test_model_availability():
    """Test that required models are available."""
    api_key = os.getenv("SPEECHIFY_API_KEY")
    if not api_key:
        pytest.skip("SPEECHIFY_API_KEY environment variable not set")
    
    client = Speechify(token=api_key)
    
    # Test both models
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
        assert audio_response.audio_data, "simba-english model should work"
    except Exception as e:
        pytest.fail(f"simba-english model failed: {e}")
    
    # Test simba-multilingual
    try:
        audio_response = client.tts.audio.speech(
            audio_format="mp3",
            input=test_text,
            language="en-US",
            model="simba-multilingual",
            voice_id="scott"
        )
        assert audio_response.audio_data, "simba-multilingual model should work"
    except Exception as e:
        pytest.fail(f"simba-multilingual model failed: {e}")
    
    print("✅ Model availability test passed")

if __name__ == "__main__":
    # Run tests if SPEECHIFY_API_KEY is available
    api_key = os.getenv("SPEECHIFY_API_KEY")
    if not api_key:
        print("❌ SPEECHIFY_API_KEY environment variable not set")
        print("Please set your Speechify API key and run again:")
        print("export SPEECHIFY_API_KEY='your_api_key_here'")
        sys.exit(1)
    
    print("🚀 Running Speechify migration tests...")
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    
    # Run pytest
    pytest.main([__file__, "-v"]) 