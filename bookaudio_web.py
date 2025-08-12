#!/usr/bin/env python3
import os
import json
import time
import re
import cv2
import numpy as np
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, redirect, url_for, send_from_directory
from werkzeug.utils import secure_filename
import ebooklib
from ebooklib import epub
from bs4 import BeautifulSoup

# Import functions from the existing script
from book_reader_eleven_manual import (
    ensure_dirs, get_exif_datetime, auto_rotate_deskew, 
    maybe_split_two_pages, ocr_ndarray, clean_text, 
    eleven_tts_to_mp3, combine_mp3s
)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.urandom(24)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB max upload

# Define paths
BASE = Path("/mnt/c/Users/Alex/Documents/Bookscan")
INBOX = BASE / "inbox"
WORK = BASE / "work"
OUT = BASE / "out"
TEXT_DIR = OUT / "text_files"

# Ensure directories exist
ensure_dirs()
TEXT_DIR.mkdir(exist_ok=True)

# Helper function to extract text from EPUB files
def extract_text_from_epub(epub_path):
    """Extract text content from an EPUB file with preserved paragraph formatting."""
    book = epub.read_epub(epub_path)
    chapter_items = []
    chapters = []
    
    # Get book title for filtering
    title = book.get_metadata('DC', 'title')
    title_text = title[0][0] if title else ""
    
    # Words that indicate non-content sections
    non_content_indicators = ['cover', 'title page', 'copyright', 'contents', 'table of contents', 
                             'endorsements', 'dedication', 'acknowledgments', 'back cover', 'back ads']
    
    # First collect all items in their original order to maintain proper sequence
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            # Parse HTML content
            soup = BeautifulSoup(item.get_content(), 'html.parser')
            
            # Try to identify chapter title/heading
            chapter_title = ""
            heading = soup.find(['h1', 'h2', 'h3'])
            if heading:
                chapter_title = heading.get_text(strip=True).lower()
            
            # Skip non-content sections based on title
            if any(indicator in chapter_title.lower() for indicator in non_content_indicators):
                continue
                
            # Store the item for processing in order
            chapter_items.append((item, soup, chapter_title))
    
    # Now process each chapter in the correct order
    for item, soup, chapter_title in chapter_items:
        # Process paragraphs to preserve formatting
        paragraphs = []
        
        # First handle headings separately to make them stand out
        headings = soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
        for heading in headings:
            text = heading.get_text(' ', strip=True)
            if text.strip():
                # Add extra newlines around headings
                paragraphs.append(text)
                # Add an empty line after heading
                paragraphs.append('')
        
        # Then handle paragraphs
        for p in soup.find_all(['p', 'div']):
            text = p.get_text(' ', strip=True)
            if text.strip():
                paragraphs.append(text)
        
        # Join paragraphs with double newlines to preserve paragraph breaks
        # and filter out any consecutive empty lines
        filtered_paragraphs = []
        prev_empty = False
        for p in paragraphs:
            if not p.strip():
                if not prev_empty:  # Only add one empty line at a time
                    filtered_paragraphs.append(p)
                    prev_empty = True
            else:
                filtered_paragraphs.append(p)
                prev_empty = False
                
        chapter_text = '\n\n'.join(filtered_paragraphs)
        
        # Skip if too short (likely not a content chapter)
        if len(chapter_text) < 100:
            continue
            
        # Skip if it looks like a table of contents (lots of page numbers)
        page_number_pattern = r'\s\d+\s*$'
        lines = chapter_text.split('\n')
        page_number_lines = sum(1 for line in lines if re.search(page_number_pattern, line))
        if page_number_lines > 5 and page_number_lines / len(lines) > 0.3:
            continue
        
        # Only add non-empty chapters that pass our filters
        if chapter_text.strip():
            chapters.append(chapter_text)
    
    return chapters

# Book state management
class BookState:
    def __init__(self):
        self.current_book = None
        self.pages = []
        self.processed_pages = []
        self.current_page_index = 0
        
    def load_book(self, book_name):
        self.current_book = book_name
        self.pages = []
        self.processed_pages = []
        self.current_page_index = 0
        
        # Load existing pages if any
        if (TEXT_DIR / book_name).exists():
            for text_file in sorted((TEXT_DIR / book_name).glob("*.txt")):
                self.pages.append({
                    "id": text_file.stem,
                    "text": text_file.read_text(encoding="utf-8"),
                    "processed": True
                })
            self.processed_pages = [p["id"] for p in self.pages]
        
    def add_page(self, page_id, text):
        self.pages.append({
            "id": page_id,
            "text": text,
            "processed": False
        })
        
    def update_page(self, page_id, text):
        for page in self.pages:
            if page["id"] == page_id:
                page["text"] = text
                break
                
    def mark_processed(self, page_id):
        for page in self.pages:
            if page["id"] == page_id:
                page["processed"] = True
                if page_id not in self.processed_pages:
                    self.processed_pages.append(page_id)
                break
                
    def get_page(self, page_id):
        for page in self.pages:
            if page["id"] == page_id:
                return page
        return None
        
    def get_current_page(self):
        if not self.pages or self.current_page_index >= len(self.pages):
            return None
        return self.pages[self.current_page_index]
        
    def next_page(self):
        if self.current_page_index < len(self.pages) - 1:
            self.current_page_index += 1
            return self.pages[self.current_page_index]
        return None
        
    def prev_page(self):
        if self.current_page_index > 0:
            self.current_page_index -= 1
            return self.pages[self.current_page_index]
        # Return the current page when at the beginning instead of None
        elif self.pages and self.current_page_index == 0:
            return self.pages[0]
        return None
        
    def save_all(self):
        if not self.current_book:
            return
            
        book_dir = TEXT_DIR / self.current_book
        book_dir.mkdir(exist_ok=True)
        
        for page in self.pages:
            page_file = book_dir / f"{page['id']}.txt"
            page_file.write_text(page["text"], encoding="utf-8")
            
        # Also create combined text file
        combined_text = "\n\n".join([page["text"] for page in self.pages])
        combined_file = book_dir / "combined.txt"
        combined_file.write_text(combined_text, encoding="utf-8")
        
    def get_progress(self):
        if not self.pages:
            return 0
        return int((len(self.processed_pages) / len(self.pages)) * 100)

# Initialize book state
book_state = BookState()

# Routes
@app.route('/audio/<path:filename>')
def serve_audio(filename):
    """Serve audio files"""
    # Split the path to determine if it's a preview or regular audio file
    parts = filename.split('/')
    if len(parts) > 1 and parts[0] == 'previews':
        # It's a preview audio file
        return send_from_directory(OUT / 'previews', parts[1])
    else:
        # It's a regular audio file
        book_name = parts[0]
        audio_file = '/'.join(parts[1:])
        return send_from_directory(OUT / book_name, audio_file)

@app.route('/')
def index():
    """Home page with book selection and upload options"""
    # Get list of existing books
    books = []
    if TEXT_DIR.exists():
        books = [d.name for d in TEXT_DIR.iterdir() if d.is_dir()]
    
    return render_template('index.html', books=books)

@app.route('/test_upload')
def test_upload():
    """Test page for EPUB upload"""
    return render_template('test_upload.html')

@app.route('/upload', methods=['POST'])
def upload_images():
    """Handle image upload and OCR processing"""
    if 'images' not in request.files:
        return jsonify({"error": "No images uploaded"}), 400
        
    book_name = request.form.get('book_name', 'new_book')
    book_name = secure_filename(book_name)
    
    # Create book directory
    book_dir = TEXT_DIR / book_name
    book_dir.mkdir(exist_ok=True)
    
    # Process uploaded images
    files = request.files.getlist('images')
    
    # Save images to inbox temporarily
    saved_images = []
    for file in files:
        if file.filename:
            filename = secure_filename(file.filename)
            file_path = INBOX / filename
            file.save(file_path)
            saved_images.append(file_path)
    
    # Sort images by EXIF date
    saved_images = sorted(saved_images, key=get_exif_datetime)
    
    # Initialize book state
    book_state.load_book(book_name)
    
    # Process each image
    for idx, img_path in enumerate(saved_images, 1):
        # Read and process image
        bgr = cv2.imread(str(img_path))
        if bgr is None:
            continue
            
        thr = auto_rotate_deskew(bgr)
        parts = maybe_split_two_pages(thr)
        
        for part_i, part in enumerate(parts, 1):
            page_id = f"p{idx:04d}_{part_i}"
            work_img = WORK / f"{page_id}.png"
            cv2.imwrite(str(work_img), part)
            
            # Perform OCR
            txt = ocr_ndarray(part)
            if txt:
                # Clean text
                txt = clean_text(txt)
                
                # Add to book state
                book_state.add_page(page_id, txt)
    
    # Save initial state
    book_state.save_all()
    
    # Redirect to editor
    return redirect(url_for('edit_book', book_name=book_name))

@app.route('/upload_epub', methods=['POST'])
def upload_epub():
    """Handle EPUB upload and text extraction"""
    if 'epub' not in request.files:
        return jsonify({"error": "No EPUB uploaded"}), 400
        
    book_name = request.form.get('book_name', 'new_book')
    book_name = secure_filename(book_name)
    
    # Create book directory
    book_dir = TEXT_DIR / book_name
    book_dir.mkdir(exist_ok=True)
    
    # Save EPUB to inbox temporarily
    epub_file = request.files['epub']
    epub_path = INBOX / secure_filename(epub_file.filename)
    epub_file.save(epub_path)
    
    # Extract text from EPUB
    chapters = extract_text_from_epub(epub_path)
    
    # Initialize book state
    book_state.load_book(book_name)
    
    # Add chapters to book state
    for idx, chapter in enumerate(chapters, 1):
        page_id = f"c{idx:04d}"
        book_state.add_page(page_id, chapter)
    
    # Save initial state
    book_state.save_all()
    
    # Redirect to editor
    return redirect(url_for('edit_book', book_name=book_name))

@app.route('/book/<book_name>')
def edit_book(book_name):
    """Book editor interface"""
    book_state.load_book(book_name)
    current_page = book_state.get_current_page()
    
    return render_template(
        'editor.html', 
        book_name=book_name,
        current_page=current_page,
        current_page_index=book_state.current_page_index,
        progress=book_state.get_progress(),
        total_pages=len(book_state.pages)
    )

@app.route('/api/page/<page_id>', methods=['GET'])
def get_page(page_id):
    """Get page content"""
    page = book_state.get_page(page_id)
    if page:
        return jsonify(page)
    return jsonify({"error": "Page not found"}), 404

@app.route('/api/page/<page_id>', methods=['POST'])
def update_page(page_id):
    """Update page content"""
    text = request.form.get('text', '')
    book_state.update_page(page_id, text)
    book_state.mark_processed(page_id)
    book_state.save_all()
    return jsonify({"success": True})

@app.route('/api/next_page', methods=['GET'])
def next_page():
    """Get next page"""
    page = book_state.next_page()
    if page:
        html = f'''
        <div id="editor-content" class="editor-container">
            <textarea id="editor-textarea" class="editor-textarea" data-page-id="{page['id']}">{page['text']}</textarea>
        </div>
        <script>
            document.getElementById('current-page-num').textContent = '{book_state.current_page_index + 1}';
            document.getElementById('total-pages').textContent = '{len(book_state.pages)}';
        </script>
        '''
        return html
    return "<div id='editor-content' class='editor-container'><div class='alert alert-warning'>No more pages.</div></div>", 404

@app.route('/api/prev_page', methods=['GET'])
def prev_page():
    """Get previous page"""
    page = book_state.prev_page()
    if page:
        html = f'''
        <div id="editor-content" class="editor-container">
            <textarea id="editor-textarea" class="editor-textarea" data-page-id="{page['id']}">{page['text']}</textarea>
        </div>
        <script>
            document.getElementById('current-page-num').textContent = '{book_state.current_page_index + 1}';
            document.getElementById('total-pages').textContent = '{len(book_state.pages)}';
        </script>
        '''
        return html
    # Return 200 status even when at the first page, just show a message
    return "<div id='editor-content' class='editor-container'><div class='alert alert-info'>You are at the first page.</div></div>", 200

@app.route('/api/preview_audio', methods=['POST'])
def preview_audio():
    """Generate audio preview for a single page or text snippet"""
    data = request.json
    if not data or not data.get('text'):
        return jsonify({"error": "Text required", "success": False}), 400
        
    text = data.get('text')
    page_id = data.get('page_id', 'preview')
    
    # Create temp directory for audio previews if it doesn't exist
    preview_dir = OUT / "previews"
    preview_dir.mkdir(exist_ok=True)
    
    # Generate a unique filename for this preview
    timestamp = int(time.time())
    preview_filename = f"preview_{page_id}_{timestamp}.mp3"
    preview_path = preview_dir / preview_filename
    
    # Generate audio using the preferred voice (Grandpa Spuds Oxley)
    try:
        # Use only the first 500 characters for preview to keep it quick
        preview_text = text[:500]
        if eleven_tts_to_mp3(preview_text, preview_path):
            # Return the URL to the generated audio file
            return jsonify({
                "success": True,
                "audio_url": f"/audio/previews/{preview_filename}"
            })
        else:
            return jsonify({"error": "Failed to generate audio", "success": False}), 500
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

@app.route('/api/generate_audio', methods=['POST'])
def generate_audio():
    """Generate audio for the current book"""
    book_name = request.form.get('book_name')
    if not book_name:
        return jsonify({"error": "Book name required"}), 400
        
    # Load book if not already loaded
    if book_state.current_book != book_name:
        book_state.load_book(book_name)
    
    # Create output directory for audio
    audio_dir = OUT / book_name
    audio_dir.mkdir(exist_ok=True)
    
    # Generate audio for each page
    mp3s = []
    for page in book_state.pages:
        page_id = page["id"]
        txt = page["text"]
        
        if txt:
            mp3_path = audio_dir / f"{page_id}.mp3"
            if eleven_tts_to_mp3(txt, mp3_path):
                mp3s.append(mp3_path)
    
    # Combine all MP3s
    if mp3s:
        combined_path = audio_dir / "book_combined.mp3"
        combine_mp3s(mp3s, combined_path)
        return jsonify({
            "success": True,
            "audio_path": str(combined_path),
            "page_count": len(mp3s)
        })
    
    return jsonify({"error": "No audio generated"}), 400

@app.route('/api/chunk_text', methods=['POST'])
def chunk_text():
    """Chunk text to avoid TTS limitations"""
    text = request.form.get('text', '')
    max_chars = int(request.form.get('max_chars', 5000))
    
    # Split text into sentences
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = ""
    
    for sentence in sentences:
        # If adding this sentence would exceed max_chars, start a new chunk
        if len(current_chunk) + len(sentence) > max_chars:
            chunks.append(current_chunk)
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += " " + sentence
            else:
                current_chunk = sentence
    
    # Add the last chunk if it's not empty
    if current_chunk:
        chunks.append(current_chunk)
    
    return jsonify({"chunks": chunks})

@app.route('/download/<path:filename>')
def download_file(filename):
    """Download generated files"""
    return send_file(Path(filename), as_attachment=True)

if __name__ == '__main__':
    import argparse
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='BookAudio Web UI')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    parser.add_argument('--host', type=str, default='0.0.0.0', help='Host to run the server on')
    args = parser.parse_args()
    
    # Run the app
    app.run(debug=True, host=args.host, port=args.port)
