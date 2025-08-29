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

# Import functions from the Speechify version script
from book_reader_speechify_manual import (
    ensure_dirs, get_exif_datetime, auto_rotate_deskew, 
    maybe_split_two_pages, ocr_ndarray, clean_text, 
    speechify_tts_to_mp3, combine_mp3s
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
        
        chapter_text = '\n'.join(filtered_paragraphs)
        if chapter_text.strip():
            chapters.append(chapter_text)
    
    return chapters

def process_images_to_text(image_files, book_name):
    """Process uploaded images to extract text."""
    text_files = []
    
    for i, file in enumerate(image_files):
        if file.filename == '':
            continue
            
        # Save uploaded file
        filename = secure_filename(f"{book_name}_page_{i+1:04d}.jpg")
        filepath = INBOX / filename
        file.save(str(filepath))
        
        # Process image
        bgr = cv2.imread(str(filepath))
        if bgr is None:
            continue
            
        thr = auto_rotate_deskew(bgr)
        parts = maybe_split_two_pages(thr)
        
        for part_i, part in enumerate(parts):
            page_id = f"{book_name}_p{i+1:04d}_{part_i+1}"
            work_img = WORK / f"{page_id}.png"
            cv2.imwrite(str(work_img), part)
            
            txt = ocr_ndarray(part)
            if txt:
                text_file = TEXT_DIR / f"{page_id}.txt"
                text_file.write_text(txt, encoding="utf-8")
                text_files.append({
                    'id': page_id,
                    'filename': text_file.name,
                    'text': txt
                })
    
    return text_files

def process_epub_to_text(epub_file, book_name):
    """Process uploaded EPUB file to extract text."""
    # Save uploaded file
    filename = secure_filename(f"{book_name}.epub")
    filepath = INBOX / filename
    epub_file.save(str(filepath))
    
    # Extract text from EPUB
    chapters = extract_text_from_epub(filepath)
    
    text_files = []
    for i, chapter_text in enumerate(chapters):
        page_id = f"{book_name}_chapter_{i+1:04d}"
        text_file = TEXT_DIR / f"{page_id}.txt"
        text_file.write_text(chapter_text, encoding="utf-8")
        text_files.append({
            'id': page_id,
            'filename': text_file.name,
            'text': chapter_text
        })
    
    return text_files

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload():
    book_name = request.form.get('book_name', 'untitled').strip()
    if not book_name:
        book_name = 'untitled'
    
    # Clean book name for file naming
    book_name = re.sub(r'[^\w\s-]', '', book_name).strip()
    book_name = re.sub(r'[-\s]+', '_', book_name)
    
    text_files = []
    
    # Check if images were uploaded
    if 'images' in request.files:
        image_files = request.files.getlist('images')
        if image_files and image_files[0].filename != '':
            text_files = process_images_to_text(image_files, book_name)
    
    # Check if EPUB was uploaded
    elif 'epub' in request.files:
        epub_file = request.files['epub']
        if epub_file and epub_file.filename != '':
            text_files = process_epub_to_text(epub_file, book_name)
    
    if not text_files:
        return jsonify({'error': 'No valid files uploaded'}), 400
    
    # Store book info in session or temporary storage
    book_data = {
        'name': book_name,
        'pages': text_files,
        'current_page': 0
    }
    
    # For simplicity, we'll store this in a temporary file
    # In production, you'd use a proper database or session management
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    book_file.write_text(json.dumps(book_data), encoding="utf-8")
    
    return jsonify({
        'success': True,
        'book_name': book_name,
        'total_pages': len(text_files),
        'redirect_url': url_for('editor', book_name=book_name)
    })

@app.route('/editor/<book_name>')
def editor(book_name):
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    if not book_file.exists():
        return redirect(url_for('index'))
    
    book_data = json.loads(book_file.read_text(encoding="utf-8"))
    return render_template('editor.html', book_data=book_data)

@app.route('/api/page/<book_name>/<int:page_num>')
def get_page(book_name, page_num):
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    if not book_file.exists():
        return jsonify({'error': 'Book not found'}), 404
    
    book_data = json.loads(book_file.read_text(encoding="utf-8"))
    
    if page_num < 0 or page_num >= len(book_data['pages']):
        return jsonify({'error': 'Page not found'}), 404
    
    page_data = book_data['pages'][page_num]
    return jsonify({
        'page_num': page_num,
        'total_pages': len(book_data['pages']),
        'text': page_data['text'],
        'page_id': page_data['id']
    })

@app.route('/api/save/<book_name>/<int:page_num>', methods=['POST'])
def save_page(book_name, page_num):
    data = request.get_json()
    new_text = data.get('text', '')
    
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    if not book_file.exists():
        return jsonify({'error': 'Book not found'}), 404
    
    book_data = json.loads(book_file.read_text(encoding="utf-8"))
    
    if page_num < 0 or page_num >= len(book_data['pages']):
        return jsonify({'error': 'Page not found'}), 404
    
    # Update text in book data
    book_data['pages'][page_num]['text'] = new_text
    
    # Save updated book data
    book_file.write_text(json.dumps(book_data), encoding="utf-8")
    
    # Also save to individual text file
    page_id = book_data['pages'][page_num]['id']
    text_file = TEXT_DIR / f"{page_id}.txt"
    text_file.write_text(new_text, encoding="utf-8")
    
    return jsonify({'success': True})

@app.route('/api/preview/<book_name>/<int:page_num>')
def preview_audio(book_name, page_num):
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    if not book_file.exists():
        return jsonify({'error': 'Book not found'}), 404
    
    book_data = json.loads(book_file.read_text(encoding="utf-8"))
    
    if page_num < 0 or page_num >= len(book_data['pages']):
        return jsonify({'error': 'Page not found'}), 404
    
    text = book_data['pages'][page_num]['text']
    if not text.strip():
        return jsonify({'error': 'No text to convert'}), 400
    
    # Generate preview audio
    preview_path = OUT / f"preview_{book_name}_p{page_num+1}.mp3"
    
    if speechify_tts_to_mp3(text, preview_path):
        return jsonify({
            'success': True,
            'audio_url': url_for('download_audio', filename=preview_path.name)
        })
    else:
        return jsonify({'error': 'Failed to generate audio'}), 500

@app.route('/api/generate/<book_name>')
def generate_full_audio(book_name):
    book_file = TEXT_DIR / f"{book_name}_book_data.json"
    if not book_file.exists():
        return jsonify({'error': 'Book not found'}), 404
    
    book_data = json.loads(book_file.read_text(encoding="utf-8"))
    
    mp3_paths = []
    
    for i, page in enumerate(book_data['pages']):
        text = page['text']
        if text.strip():
            mp3_path = OUT / f"{book_name}_p{i+1:04d}.mp3"
            if speechify_tts_to_mp3(text, mp3_path):
                mp3_paths.append(mp3_path)
    
    if mp3_paths:
        # Combine all MP3s
        combined_path = OUT / f"{book_name}_combined.mp3"
        combine_mp3s(mp3_paths, combined_path)
        
        return jsonify({
            'success': True,
            'audio_url': url_for('download_audio', filename=combined_path.name),
            'total_pages': len(mp3_paths)
        })
    else:
        return jsonify({'error': 'No audio generated'}), 500

@app.route('/download/<filename>')
def download_audio(filename):
    return send_from_directory(OUT, filename, as_attachment=True)

@app.route('/api/text-tools', methods=['POST'])
def text_tools():
    data = request.get_json()
    text = data.get('text', '')
    tool = data.get('tool', '')
    
    if tool == 'capitalize':
        # Capitalize first letter of each sentence
        import re
        sentences = re.split(r'([.!?]+)', text)
        result = ''
        for i in range(0, len(sentences), 2):
            if i < len(sentences):
                sentence = sentences[i].strip()
                if sentence:
                    result += sentence[0].upper() + sentence[1:] + ' '
                if i + 1 < len(sentences):
                    result += sentences[i + 1] + ' '
        text = result.strip()
    
    elif tool == 'fix_spaces':
        # Fix multiple spaces and spacing around punctuation
        import re
        text = re.sub(r'\s+', ' ', text)  # Multiple spaces to single
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)  # Remove spaces before punctuation
        text = re.sub(r'([.,!?;:])\s*([a-zA-Z])', r'\1 \2', text)  # Add space after punctuation
    
    elif tool == 'fix_hyphenation':
        # Fix common hyphenation issues
        import re
        text = re.sub(r'(\w+)-\s*\n\s*(\w+)', r'\1\2', text)  # Remove hyphens at line breaks
        text = re.sub(r'\s+', ' ', text)  # Clean up extra spaces
    
    elif tool == 'remove_line_breaks':
        # Remove line breaks within paragraphs
        import re
        text = re.sub(r'\n\s*\n', '\n\n', text)  # Preserve paragraph breaks
        text = re.sub(r'(?<!\n)\n(?!\n)', ' ', text)  # Remove single line breaks
        text = re.sub(r'\s+', ' ', text)  # Clean up extra spaces
    
    return jsonify({'text': text})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 