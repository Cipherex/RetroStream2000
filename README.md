# 🎵 RetroStream 2000 - Blast from the Past Edition

![RetroStream 2000](https://img.shields.io/badge/Era-Y2K_Aesthetic-00FF00?style=for-the-badge) ![Platform](https://img.shields.io/badge/Platform-Desktop-7CFC98?style=for-the-badge) ![Status](https://img.shields.io/badge/Status-Ready_to_Rock-FF6B00?style=for-the-badge)

## 🚀 Project Overview

RetroStream 2000 is a Y2K-themed music transfer application that bridges local music collections with modern streaming platforms. The application combines nostalgic desktop software aesthetics with contemporary functionality.

### Core Features
- *🎧 Smart Music Transfer*: Automatically transfers local music library to Spotify playlists
- *🧠 AI-Powered Matching*: Uses advanced fuzzy matching algorithms to find corresponding tracks
- *💾 Retro DOS Terminal*: Real-time logging with authentic scanline effects and command interface
- *📼 Cassette Deck UI*: Vintage-inspired interface with pixel-perfect fonts and neon colors
- *⚡ Modern Performance*: Fast, reliable transfers with progress tracking and error handling

---

## 🎯 Theme Implementation: "Blast from the Past"

### 📻 Retro Design Elements
- *Y2K Desktop Software*: Recreates the look and feel of early 2000s desktop applications
- *DOS Terminal Aesthetics*: Complete with ASCII art, scanlines, and retro command prompts
- *Cassette Deck Metaphor*: "LOAD TAPE" button and music deck-inspired UI elements
- *Pixel Fonts & Neon Colors*: Authentic VT323 monospace fonts with classic green-on-black terminals

### 🔧 Modern Implementation
- *AI-Powered Matching*: Sophisticated fuzzy string matching algorithms
- *Cloud Integration*: Connects to modern Spotify API for seamless playlist creation
- *Advanced Audio Processing*: Supports multiple audio formats (MP3, FLAC, M4A, etc.)
- *Real-time Progress Tracking*: Modern UX features wrapped in retro packaging

---

## 📦 Installation Guide

### Prerequisites
- Python 3.8 or higher
- Spotify Developer Account (for API credentials)

### Step 1: Clone the Repository
```bash
git clone https://github.com/cipherex/retromusic2000.git
cd retromusic2000
```

### Step 2: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Set Up Spotify API
1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your Client ID and Client Secret
4. Set redirect URI to: http://127.0.0.1:8888/callback

---

## 🎮 Usage Instructions

### Step 1: Launch RetroStream 2000
```bash
python retrosteam2000.py
```

### Step 2: Configure Your Setup
1. *Load Your Music*: Click "LOAD TAPE" and select your music directory
2. *Name Your Playlist*: Enter a name for your Spotify playlist
3. *Enter Spotify Credentials*: Input your Client ID and Client Secret

### Step 3: Start the Transfer
1. Click "Start Transfer" to begin processing
2. Monitor progress through the DOS terminal interface
3. View real-time statistics and transfer status
4. Stop anytime with the "Stop Transfer" button

### Step 4: Terminal Commands
The application includes various command-line features for enhanced interaction:
- Real-time progress logging
- Error reporting and handling
- Transfer statistics and summaries
- Interactive command interface

---

## 🧪 Testing the Application

### Quick Test Run
1. Create a small test folder with 5-10 music files
2. Use test Spotify credentials
3. Run a transfer to verify functionality
4. Check Spotify for the created playlist

### Supported Audio Formats
- MP3 (with ID3 tags)
- FLAC (with Vorbis comments)
- M4A/MP4 (with iTunes tags)
- Fallback filename parsing for unsupported formats

---

## 🎨 Technical Implementation

### Smart Matching Algorithm
- *Exact Matching*: Perfect track and artist matches
- *Fuzzy Matching*: Handles variations in spelling and formatting
- *Title-Only Fallback*: Finds tracks when artist info is missing
- *Artist-Based Search*: Searches by artist when track info is unclear

### Retro UI Features
- *Authentic Scanlines*: CSS-powered terminal effects
- *Blinking Cursor*: Real-time cursor animation
- *Marquee Status Bar*: Scrolling status updates
- *Digital Clock*: Live time display in retro style

### Modern Architecture
- *Threaded Processing*: Non-blocking UI during transfers
- *Progress Tracking*: Real-time progress updates
- *Error Handling*: Graceful failure recovery
- *Modular Design*: Clean separation of concerns

---

## 🚀 Future Enhancements

- *Multi-Platform Support*: Add Apple Music, YouTube Music integration
- *Advanced Filtering*: Genre-based playlist creation
- *Batch Processing*: Handle multiple directories simultaneously
- *Cloud Storage*: Save transfer history and statistics
- *Additional Retro Themes*: Windows 98, Mac OS Classic variants

---

## 📜 License

This project is licensed under the MIT License.

---

RetroStream 2000 - Bridging the past and future of music