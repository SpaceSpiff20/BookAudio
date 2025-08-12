# Make the setup script executable
chmod +x setup.sh

# Run the setup script to create directories
./setup.sh

# Install python3-pip (needed for Python packages)
sudo apt install -y python3-pip

# Install required Python packages
pip3 install pillow pytesseract opencv-python piexif requests pydub

# Set the ElevenLabs API key (use your actual key)
export ELEVEN_API_KEY="sk_beab21b8a6a49b9165aaed3e8ee8cc1a044ddce29sk_beab21b8a6a49b9165aaed3e8ee8cc1a044ddce2983a5419"

# Run the BookAudio script
python3 book_reader_eleven_manual.py
