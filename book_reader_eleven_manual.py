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
from elevenlabs.client import ElevenLabs

# ====== PATHS (Windows folders via WSL) ======
INBOX = Path("/mnt/c/Users/Alex/Documents/Bookscan/inbox")   # put your photos here
WORK  = Path("/mnt/c/Users/Alex/Documents/Bookscan/work")    # temp processed images
OUT   = Path("/mnt/c/Users/Alex/Documents/Bookscan/out")     # text + audio outputs

# ====== OCR / TTS CONFIG ======
LANGS = ["eng"]                 # add e.g. "fra","swa" later (install tesseract-ocr-fra, etc.)
TESS_CFG = r"--oem 1 --psm 3"
COMBINED = OUT / "book_combined.mp3"

ELEVEN_API_KEY = os.getenv("ELEVEN_API_KEY")  # set in shell
VOICE_ID = "NOpBlnGInO9m6vDvFkFC"             # ElevenLabs 'Grandpa Spuds Oxley'
MODEL_ID = "eleven_multilingual_v2"

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

def ocr_ndarray(img, langs=LANGS):
    for lang in langs:
        txt = pytesseract.image_to_string(Image.fromarray(img), lang=lang, config=TESS_CFG)
        txt = clean_text(txt)
        if len(txt) > 20:
            return txt
    return txt

def eleven_tts_to_mp3(text, out_path: Path):
    if not text or not ELEVEN_API_KEY:
        return False
    
    try:
        # Initialize the client exactly as in the test script
        client = ElevenLabs(api_key=ELEVEN_API_KEY)
        
        # Generate audio using the text-to-speech API
        audio_generator = client.text_to_speech.convert(
            text=text,
            voice_id=VOICE_ID,
            model_id=MODEL_ID
        )
        
        # Convert generator to bytes
        audio_bytes = b''.join(chunk for chunk in audio_generator)
        
        # Save the audio to the output path
        out_path.write_bytes(audio_bytes)
        return True
    except Exception as e:
        print(f"    Error calling ElevenLabs API: {str(e)}")
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
                            if line == "END":
                                break
                            lines.append(line)
                        if lines:
                            txt = "\n".join(lines)
                
                with open(text_out, "a", encoding="utf-8") as f:
                    f.write(txt + "\n\n")
                mp3_path = OUT / f"{page_id}.mp3"
                print(f"  · OCR {page_id}: {len(txt)} chars → ElevenLabs TTS …")
                if eleven_tts_to_mp3(txt, mp3_path):
                    mp3s.append(mp3_path)
                else:
                    print("    (TTS failed — check ELEVEN_API_KEY)")
            else:
                print("  · No readable text on this part.")

    if mp3s:
        print("Combining MP3s …")
        combine_mp3s(mp3s, OUT / "book_combined.mp3")
        print("\n✅ Done.")
        print(f"Text → {text_out}")
        print(f"Combined MP3 → {OUT / 'book_combined.mp3'}")
    else:
        print("No audio generated — check image quality/lighting.")

def ocr_only():
    """Extract OCR text to individual files for later editing."""
    imgs = []
    for ext in ("*.jpg","*.jpeg","*.png","*.webp"):
        imgs += list(INBOX.glob(ext))
    imgs = sorted(imgs, key=get_exif_datetime)
    if not imgs:
        print("No images found in INBOX. Put photos in C:\\Users\\Alex\\Documents\\Bookscan\\inbox and run again.")
        return

    # Create a text directory for individual text files
    text_dir = OUT / "text_files"
    text_dir.mkdir(exist_ok=True)
    
    # Also create the combined text file
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
                # Save to individual text file
                text_file = text_dir / f"{page_id}.txt"
                text_file.write_text(txt, encoding="utf-8")
                
                # Also append to the combined file
                with open(text_out, "a", encoding="utf-8") as f:
                    f.write(txt + "\n\n")
                
                print(f"  · OCR {page_id}: {len(txt)} chars → Saved to {text_file}")
            else:
                print("  · No readable text on this part.")
    
    print("\n✅ OCR processing complete.")
    print(f"Individual text files → {text_dir}")
    print(f"Combined text file → {text_out}")
    print("\nYou can now edit the text files in your preferred editor.")
    print("After editing, run this script again and select option 3 to convert text to audio.")

def tts_only():
    """Convert existing text files to audio."""
    # Look for text files in the text_files directory
    text_dir = OUT / "text_files"
    if not text_dir.exists() or not list(text_dir.glob("*.txt")):
        print(f"No text files found in {text_dir}")
        print("Run the script with option 2 first to extract OCR text.")
        return
    
    text_files = sorted(list(text_dir.glob("*.txt")))
    print(f"Found {len(text_files)} text files to process.")
    
    mp3s = []
    for text_file in text_files:
        page_id = text_file.stem
        print(f"Processing {page_id}...")
        
        # Read the edited text file
        txt = text_file.read_text(encoding="utf-8")
        if txt:
            mp3_path = OUT / f"{page_id}.mp3"
            print(f"  · TTS {page_id}: {len(txt)} chars → ElevenLabs TTS …")
            if eleven_tts_to_mp3(txt, mp3_path):
                mp3s.append(mp3_path)
            else:
                print("    (TTS failed — check ELEVEN_API_KEY)")
    
    if mp3s:
        print("Combining MP3s …")
        combine_mp3s(mp3s, OUT / "book_combined.mp3")
        print("\n✅ Done.")
        print(f"Combined MP3 → {OUT / 'book_combined.mp3'}")
    else:
        print("No audio generated — check text files.")

if __name__ == "__main__":
    main()
