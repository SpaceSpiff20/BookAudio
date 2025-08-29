import os
from pathlib import Path
from datetime import datetime

import cv2
import numpy as np
from PIL import Image
import pytesseract
import requests
from pydub import AudioSegment
import piexif
from speechify import Speechify
from speechify.tts import GetSpeechOptionsRequest
import base64

# ====== PATHS (Windows folders via WSL) ======
INBOX = Path("/mnt/c/Users/Alex/Documents/Bookscan/inbox")   # put your photos here
WORK  = Path("/mnt/c/Users/Alex/Documents/Bookscan/work")    # temp processed images
OUT   = Path("/mnt/c/Users/Alex/Documents/Bookscan/out")     # text + audio outputs

# ====== OCR / TTS CONFIG ======
LANGS = ["eng"]                 # add e.g. "fra","swa" later (install tesseract-ocr-fra, etc.)
TESS_CFG = r"--oem 1 --psm 3"
COMBINED = OUT / "book_combined.mp3"

SPEECHIFY_API_KEY = os.getenv("SPEECHIFY_API_KEY")  # set in shell
VOICE_ID = "scott"             # Speechify default voice
MODEL_ID = "simba-english"     # Use simba-multilingual for multi-language support

# ====== UTILITIES ======
def ensure_dirs():
    for p in (INBOX, WORK, OUT):
        p.mkdir(parents=True, exist_ok=True)

def get_exif_datetime(path: Path):
    """Sort primarily by EXIF DateTimeOriginal; fallback to file mtime."""
    try:
        exif = piexif.load(str(path))
        raw = exif["Exif"].get(piexif.ExifIFD.DateTimeOriginal) or exif["0th"].get(piexif.ImageIFD.DateTime)
        if raw:
            s = raw.decode() if isinstance(raw, bytes) else raw
            return datetime.strptime(s, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return datetime.fromtimestamp(path.stat().st_mtime)

def auto_rotate_deskew(bgr):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3,3), 0)
    thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    coords = np.column_stack(np.where(thr == 0))
    if coords.size:
        angle = cv2.minAreaRect(coords)[-1]
        angle = -(90 + angle) if angle < -45 else -angle
        (h,w) = thr.shape[:2]
        M = cv2.getRotationMatrix2D((w/2,h/2), angle, 1.0)
        thr = cv2.warpAffine(thr, M, (w,h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return thr

def maybe_split_two_pages(img):
    h, w = img.shape[:2]
    if w < 80: return [img]
    col_white = (img==255).sum(axis=0)
    mid  = col_white[w//2 - w//20 : w//2 + w//20].mean()
    left = col_white[w//4 - w//20 : w//4 + w//20].mean()
    right= col_white[3*w//4 - w//20: 3*w//4 + w//20].mean()
    if mid > 1.15*left and mid > 1.15*right:
        return [img[:, :w//2], img[:, w//2:]]
    return [img]

def clean_text(t):
    t = " ".join(t.split())
    t = t.replace("ﬁ","fi").replace("ﬂ","fl").strip()
    
    # Apply spell checking if the library is available
    try:
        from spellchecker import SpellChecker
        spell = SpellChecker()
        
        # Split text into words and correct each word
        words = t.split()
        corrected_words = []
        
        for word in words:
            # Preserve punctuation
            punctuation = ''
            if word and not word[-1].isalnum():
                punctuation = word[-1]
                word = word[:-1]
            
            # Only correct words that are misspelled and not proper nouns (capitalized)
            if word and not word[0].isupper() and word.lower() in spell:
                corrected = spell.correction(word)
                if corrected:
                    word = corrected
            
            corrected_words.append(word + punctuation)
        
        t = ' '.join(corrected_words)
    except ImportError:
        print("  · Note: Install 'pyspellchecker' for automatic spelling correction")
    
    return t

def ocr_ndarray(img):
    """OCR an image array and return cleaned text."""
    try:
        txt = pytesseract.image_to_string(img, lang="+".join(LANGS), config=TESS_CFG)
        return clean_text(txt)
    except Exception as e:
        print(f"    OCR error: {str(e)}")
        return ""

def speechify_tts_to_mp3(text, out_path: Path):
    """Convert text to speech using Speechify API and save as MP3."""
    if not text or not SPEECHIFY_API_KEY:
        return False
    
    try:
        # Initialize the Speechify client
        client = Speechify(token=SPEECHIFY_API_KEY)
        
        # Generate audio using the text-to-speech API
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
        
        # Decode base64 audio data
        audio_bytes = base64.b64decode(audio_response.audio_data)
        
        # Save the audio to the output path
        out_path.write_bytes(audio_bytes)
        return True
    except Exception as e:
        print(f"    Error calling Speechify API: {str(e)}")
        return False

def combine_mp3s(mp3_paths, out_path: Path):
    combined = AudioSegment.silent(duration=300)
    for p in mp3_paths:
        combined += AudioSegment.from_mp3(p) + AudioSegment.silent(duration=200)
    combined.export(out_path, format="mp3")

# ====== MAIN (manual run) ======
def main():
    ensure_dirs()
    
    # Ask user which mode to run in
    print("BookAudio Processing Options:")
    print("1. Full process (OCR + TTS in one go)")
    print("2. OCR only (extract text to edit later)")
    print("3. TTS only (convert existing text files to audio)")
    
    while True:
        mode = input("Select mode (1/2/3): ").strip()
        if mode in ["1", "2", "3"]:
            break
        print("Invalid selection. Please enter 1, 2, or 3.")
    
    if mode == "1":
        # Original full process
        full_process()
    elif mode == "2":
        # OCR only mode
        ocr_only()
    else:  # mode == "3"
        # TTS only mode
        tts_only()

def full_process():
    """Run the complete OCR + TTS pipeline in one go."""
    imgs = []
    for ext in ("*.jpg","*.jpeg","*.png","*.webp"):
        imgs += list(INBOX.glob(ext))
    imgs = sorted(imgs, key=get_exif_datetime)
    if not imgs:
        print("No images found in INBOX. Put photos in C:\\Users\\Alex\\Documents\\Bookscan\\inbox and run again.")
        return

    text_out = OUT / "book_text.txt"
    text_out.write_text("", encoding="utf-8")
    mp3s = []
    
    # Ask user if they want to review OCR text before TTS
    review_mode = input("Review OCR text before TTS conversion? (y/n): ").lower().startswith('y')

    for idx, p in enumerate(imgs, 1):
        print(f"[{idx}/{len(imgs)}] {p.name}")
        bgr = cv2.imread(str(p))
        if bgr is None:
            print("  (skip: unreadable image)")
            continue
        thr = auto_rotate_deskew(bgr)
        parts = maybe_split_two_pages(thr)

        for part_i, part in enumerate(parts, 1):
            page_id = f"p{idx:04d}_{part_i}"
            work_img = WORK / f"{page_id}.png"
            cv2.imwrite(str(work_img), part)

            txt = ocr_ndarray(part)
            if txt:
                # Manual review option
                if review_mode:
                    print(f"\n--- OCR Text for {page_id} ---\n{txt}\n")
                    edit = input("Edit text? (y/n): ").lower().startswith('y')
                    if edit:
                        print("Enter corrected text (type 'END' on a new line when finished):")
                        lines = []
                        while True:
                            line = input()
                            if line.strip() == 'END':
                                break
                            lines.append(line)
                        txt = '\n'.join(lines)
                
                # Append to combined text file
                with open(text_out, "a", encoding="utf-8") as f:
                    f.write(f"\n--- {page_id} ---\n{txt}\n")
                
                # Generate audio
                mp3_path = OUT / f"{page_id}.mp3"
                print(f"  Generating audio...")
                if speechify_tts_to_mp3(txt, mp3_path):
                    mp3s.append(mp3_path)
                    print(f"  ✓ Audio saved: {mp3_path.name}")
                else:
                    print(f"  ✗ Audio generation failed")
            else:
                print(f"  (skip: no text found)")

    # Combine all MP3s
    if mp3s:
        print(f"\nCombining {len(mp3s)} audio files...")
        combine_mp3s(mp3s, COMBINED)
        print(f"✓ Complete audio: {COMBINED}")
    else:
        print("No audio files generated.")

def ocr_only():
    """Extract text from images without generating audio."""
    imgs = []
    for ext in ("*.jpg","*.jpeg","*.png","*.webp"):
        imgs += list(INBOX.glob(ext))
    imgs = sorted(imgs, key=get_exif_datetime)
    if not imgs:
        print("No images found in INBOX.")
        return

    text_out = OUT / "book_text.txt"
    text_out.write_text("", encoding="utf-8")
    
    for idx, p in enumerate(imgs, 1):
        print(f"[{idx}/{len(imgs)}] {p.name}")
        bgr = cv2.imread(str(p))
        if bgr is None:
            print("  (skip: unreadable image)")
            continue
        thr = auto_rotate_deskew(bgr)
        parts = maybe_split_two_pages(thr)

        for part_i, part in enumerate(parts, 1):
            page_id = f"p{idx:04d}_{part_i}"
            work_img = WORK / f"{page_id}.png"
            cv2.imwrite(str(work_img), part)

            txt = ocr_ndarray(part)
            if txt:
                with open(text_out, "a", encoding="utf-8") as f:
                    f.write(f"\n--- {page_id} ---\n{txt}\n")
                print(f"  ✓ Text extracted: {page_id}")
            else:
                print(f"  (skip: no text found)")

    print(f"\n✓ Text extraction complete: {text_out}")

def tts_only():
    """Convert existing text files to audio."""
    text_files = list(OUT.glob("*.txt"))
    if not text_files:
        print("No text files found in OUT directory.")
        return

    print("Available text files:")
    for i, tf in enumerate(text_files, 1):
        print(f"{i}. {tf.name}")
    
    while True:
        try:
            choice = int(input("Select file number: ")) - 1
            if 0 <= choice < len(text_files):
                break
            print("Invalid selection.")
        except ValueError:
            print("Please enter a number.")

    text_file = text_files[choice]
    print(f"Processing: {text_file.name}")
    
    # Read text file
    content = text_file.read_text(encoding="utf-8")
    
    # Split into chunks (simple paragraph-based splitting)
    chunks = [chunk.strip() for chunk in content.split('\n\n') if chunk.strip()]
    
    mp3s = []
    for i, chunk in enumerate(chunks, 1):
        print(f"[{i}/{len(chunks)}] Processing chunk...")
        mp3_path = OUT / f"chunk_{i:04d}.mp3"
        if speechify_tts_to_mp3(chunk, mp3_path):
            mp3s.append(mp3_path)
            print(f"  ✓ Audio saved: {mp3_path.name}")
        else:
            print(f"  ✗ Audio generation failed")

    # Combine all MP3s
    if mp3s:
        print(f"\nCombining {len(mp3s)} audio files...")
        combine_mp3s(mp3s, COMBINED)
        print(f"✓ Complete audio: {COMBINED}")
    else:
        print("No audio files generated.")

if __name__ == "__main__":
    main() 