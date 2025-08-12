#!/usr/bin/env python3

import os
import sys

# Try to import elevenlabs
try:
    from elevenlabs.client import ElevenLabs
    print("✅ ElevenLabs SDK imported successfully")
except ImportError:
    print("❌ ElevenLabs SDK not installed. Installing...")
    os.system("pip install elevenlabs")
    try:
        from elevenlabs.client import ElevenLabs
        print("✅ ElevenLabs SDK installed and imported successfully")
    except ImportError:
        print("❌ Failed to install ElevenLabs SDK. Please install manually: pip install elevenlabs")
        sys.exit(1)

# Get API key from environment or file
api_key = os.getenv("ELEVEN_API_KEY")
if not api_key:
    try:
        with open(".env", "r") as f:
            api_key = f.read().strip()
        print(f"✅ Read API key from .env file: {api_key[:5]}...{api_key[-5:]}")
    except:
        print("❌ Failed to read API key from .env file")
        sys.exit(1)

# Initialize client
print(f"Initializing ElevenLabs client with API key: {api_key[:5]}...{api_key[-5:]}")
client = ElevenLabs(api_key=api_key)

# Test API connection by listing voices
try:
    print("Testing API connection by listing voices...")
    response = client.voices.search()
    print(f"✅ API connection successful! Found {len(response.voices)} voices")
    
    # Print first voice details
    if response.voices:
        voice = response.voices[0]
        print(f"First voice: {voice.name} (ID: {voice.voice_id})")
    
    print("\nAPI key is valid and working correctly!")
except Exception as e:
    print(f"❌ API connection failed: {str(e)}")
    print("\nPossible issues:")
    print("1. Invalid API key")
    print("2. API key expired or revoked")
    print("3. Network connectivity issues")
    print("4. ElevenLabs service outage")
    sys.exit(1)

# Test voice ID used in the main script
VOICE_ID = "NOpBlnGInO9m6vDvFkFC"  # Grandpa Spuds Oxley voice
print(f"\nChecking if voice ID {VOICE_ID} is available...")

try:
    voice_found = False
    for voice in response.voices:
        if voice.voice_id == VOICE_ID:
            print(f"✅ Voice ID {VOICE_ID} ({voice.name}) is available on your account")
            voice_found = True
            break
    
    if not voice_found:
        print(f"❌ Voice ID {VOICE_ID} is NOT available on your account")
        print("Available voices:")
        for voice in response.voices:
            print(f"- {voice.name} (ID: {voice.voice_id})")
except Exception as e:
    print(f"❌ Error checking voice ID: {str(e)}")
