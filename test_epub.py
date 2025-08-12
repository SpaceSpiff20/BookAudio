#!/usr/bin/env python3
"""
Test script for EPUB extraction and processing in BookAudio
"""
import os
import sys
from pathlib import Path
from bookaudio_web import extract_text_from_epub, TEXT_DIR, BookState

def main():
    if len(sys.argv) < 3:
        print("Usage: python test_epub.py <epub_file_path> <book_name>")
        return 1
    
    epub_path = sys.argv[1]
    book_name = sys.argv[2]
    
    if not os.path.exists(epub_path):
        print(f"Error: EPUB file not found: {epub_path}")
        return 1
    
    print(f"Processing EPUB: {epub_path}")
    print(f"Book name: {book_name}")
    
    # Extract text from EPUB
    chapters = extract_text_from_epub(epub_path)
    print(f"Successfully extracted {len(chapters)} chapters")
    
    # Preview first chapter
    if chapters:
        print(f"First chapter preview: {chapters[0][:200]}...")
    else:
        print("No chapters found")
        return 1
    
    # Create book directory
    book_dir = TEXT_DIR / book_name
    book_dir.mkdir(exist_ok=True)
    print(f"Created book directory: {book_dir}")
    
    # Initialize book state
    book_state = BookState()
    book_state.load_book(book_name)
    
    # Add chapters to book state
    for idx, chapter in enumerate(chapters, 1):
        page_id = f"c{idx:04d}"
        book_state.add_page(page_id, chapter)
        print(f"Added chapter {idx} as page {page_id}")
    
    # Save book state
    book_state.save_all()
    print(f"Saved {len(chapters)} chapters to {book_dir}")
    print(f"Book is ready for editing at: http://localhost:5002/book/{book_name}")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
