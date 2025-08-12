#!/usr/bin/env python3

import os
import sys
from elevenlabs.client import ElevenLabs
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test ElevenLabs API")
    parser.add_argument("--text", default="Hello, this is a test of the ElevenLabs API.", help="Text to convert to speech")
    parser.add_argument("--output", default="test_output.mp3", help="Output file path")
    parser.add_argument("--voice", default="NOpBlnGInO9m6vDvFkFC", help="Voice ID to use")
    parser.add_argument("--model", default="eleven_multilingual_v2", help="Model ID to use")
    args = parser.parse_args()
    
    # Get API key from environment
    api_key = os.getenv("ELEVEN_API_KEY")
    if not api_key:
        print("❌ No API key found in environment variable ELEVEN_API_KEY")
        sys.exit(1)
    
    print(f"Using API key: {api_key[:5]}...{api_key[-5:]}")
    print(f"Voice ID: {args.voice}")
    print(f"Model ID: {args.model}")
    print(f"Text: {args.text}")
    print(f"Output file: {args.output}")
    
    try:
        print("Initializing ElevenLabs client...")
        client = ElevenLabs(api_key=api_key)
        
        print("Converting text to speech...")
        audio = client.text_to_speech.convert(
            text=args.text,
            voice_id=args.voice,
            model_id=args.model
        )
        
        print("Writing audio to file...")
        with open(args.output, "wb") as f:
            f.write(audio)
        
        print(f"✅ Success! Audio saved to {args.output}")
        return 0
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
