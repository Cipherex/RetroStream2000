"""
Local2Stream - Transfer your local music collection to streaming platforms
Supports: Spotify
Made by Aryan
"""

import sys
import os   
import time
import re
import difflib
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QWidget, QLabel, QLineEdit, QPushButton, QVBoxLayout, QHBoxLayout,
    QFileDialog, QTextEdit, QProgressBar, QMessageBox, QGroupBox, QFormLayout, QStatusBar
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, QSize, QTime, QUrl, QRect
from PyQt5.QtWidgets import QGraphicsDropShadowEffect
from PyQt5.QtGui import QColor, QFontDatabase, QFont, QIcon, QPixmap, QPainter, QTransform
from PyQt5.QtWidgets import QPlainTextEdit
from PyQt5.QtMultimedia import QSoundEffect

# Third-party imports
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.id3._util import ID3NoHeaderError
except ImportError as e:
    print(f"Missing required package: {e}")
    print("Please run: pip install spotipy mutagen PyQt5")
    sys.exit(1)

@dataclass
class TrackMetadata:
    title: str
    artist: str
    album: str
    file_path: str
    duration: Optional[int] = None

@dataclass
class MatchResult:
    track_id: str
    track_name: str
    artist_name: str
    match_type: str  # 'exact', 'fuzzy', 'title_only', 'artist_fallback'
    confidence: float
    platform: str

class AudioMetadataExtractor:
    SUPPORTED_FORMATS = ['.mp3', '.flac', '.m4a', '.mp4', '.wav', '.ogg']

    @staticmethod
    def extract_metadata(file_path: str) -> Optional[TrackMetadata]:
        try:
            file_ext = Path(file_path).suffix.lower()
            if file_ext == '.mp3':
                return AudioMetadataExtractor._extract_mp3_metadata(file_path)
            elif file_ext == '.flac':
                return AudioMetadataExtractor._extract_flac_metadata(file_path)
            elif file_ext in ['.m4a', '.mp4']:
                return AudioMetadataExtractor._extract_mp4_metadata(file_path)
            else:
                return AudioMetadataExtractor._extract_from_filename(file_path)
        except Exception:
            return AudioMetadataExtractor._extract_from_filename(file_path)

    @staticmethod
    def _extract_mp3_metadata(file_path: str) -> Optional[TrackMetadata]:
        try:
            audio = MP3(file_path)
            title = str(audio.get('TIT2', [''])[0]) if audio.get('TIT2') else ''
            artist = str(audio.get('TPE1', [''])[0]) if audio.get('TPE1') else ''
            album = str(audio.get('TALB', [''])[0]) if audio.get('TALB') else ''
            duration = int(audio.info.length) if audio.info else None
            return TrackMetadata(
                title=title or AudioMetadataExtractor._get_title_from_filename(file_path),
                artist=artist or AudioMetadataExtractor._get_artist_from_filename(file_path),
                album=album,
                file_path=file_path,
                duration=duration
            )
        except (ID3NoHeaderError, Exception):
            return AudioMetadataExtractor._extract_from_filename(file_path)

    @staticmethod
    def _extract_flac_metadata(file_path: str) -> Optional[TrackMetadata]:
        try:
            audio = FLAC(file_path)
            title = audio.get('TITLE', [''])[0] if audio.get('TITLE') else ''
            artist = audio.get('ARTIST', [''])[0] if audio.get('ARTIST') else ''
            album = audio.get('ALBUM', [''])[0] if audio.get('ALBUM') else ''
            duration = int(audio.info.length) if audio.info else None
            return TrackMetadata(
                title=title or AudioMetadataExtractor._get_title_from_filename(file_path),
                artist=artist or AudioMetadataExtractor._get_artist_from_filename(file_path),
                album=album,
                file_path=file_path,
                duration=duration
            )
        except Exception:
            return AudioMetadataExtractor._extract_from_filename(file_path)

    @staticmethod
    def _extract_mp4_metadata(file_path: str) -> Optional[TrackMetadata]:
        try:
            audio = MP4(file_path)
            title = audio.get('\xa9nam', [''])[0] if audio.get('\xa9nam') else ''
            artist = audio.get('\xa9ART', [''])[0] if audio.get('\xa9ART') else ''
            album = audio.get('\xa9alb', [''])[0] if audio.get('\xa9alb') else ''
            duration = int(audio.info.length) if audio.info else None
            return TrackMetadata(
                title=title or AudioMetadataExtractor._get_title_from_filename(file_path),
                artist=artist or AudioMetadataExtractor._get_artist_from_filename(file_path),
                album=album,
                file_path=file_path,
                duration=duration
            )
        except Exception:
            return AudioMetadataExtractor._extract_from_filename(file_path)

    @staticmethod
    def _extract_from_filename(file_path: str) -> TrackMetadata:
        filename = Path(file_path).stem
        if ' - ' in filename:
            parts = filename.split(' - ', 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        else:
            artist = ""
            title = filename
        return TrackMetadata(
            title=title,
            artist=artist,
            album="",
            file_path=file_path
        )

    @staticmethod
    def _get_title_from_filename(file_path: str) -> str:
        return Path(file_path).stem.split(' - ')[-1].strip()

    @staticmethod
    def _get_artist_from_filename(file_path: str) -> str:
        filename = Path(file_path).stem
        if ' - ' in filename:
            return filename.split(' - ')[0].strip()
        return ""

class SpotifyHandler:
    def __init__(self, config: dict):
        self.config = config
        self.sp = None

    def authenticate(self) -> bool:
        try:
            scope = "playlist-modify-public playlist-modify-private"
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=self.config['client_id'],
                client_secret=self.config['client_secret'],
                redirect_uri=self.config['redirect_uri'],
                scope=scope,
                open_browser=True
            ))
            user = self.sp.me()
            return True
        except Exception:
            return False

    @staticmethod
    def clean_string(text: str) -> str:
        if not text:
            return ""
        text = re.sub(r'\([^)]*\)', '', text)
        text = re.sub(r'\[[^\]]*\]', '', text)
        text = re.sub(r'\s*-\s*', ' ', text)
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip().lower()

    def _fuzzy_match(self, a: str, b: str) -> float:
        a_clean = self.clean_string(a)
        b_clean = self.clean_string(b)
        ratio = difflib.SequenceMatcher(None, a_clean, b_clean).ratio()
        if a_clean in b_clean or b_clean in a_clean:
            ratio = max(ratio, 0.85)
        a_alnum = re.sub(r'[^a-zA-Z0-9]', '', a_clean)
        b_alnum = re.sub(r'[^a-zA-Z0-9]', '', b_clean)
        ratio = max(ratio, difflib.SequenceMatcher(None, a_alnum, b_alnum).ratio())
        return ratio

    def search_track(self, metadata: TrackMetadata) -> Optional[MatchResult]:
        if not self.sp:
            return None
        try:
            title = metadata.title
            artist = metadata.artist
            if not title:
                return None
            search_title = self.clean_string(title)
            search_artist = self.clean_string(artist)

            # 1. Exact search: track+artist
            if artist:
                query = f'track:"{title}" artist:"{artist}"'
            else:
                query = f'track:"{title}"'
            results = self.sp.search(q=query, type='track', limit=50)
            if results and results.get('tracks') and results['tracks'].get('items'):
                # Exact match
                for track in results['tracks']['items']:
                    track_title = self.clean_string(track['name'])
                    track_artist = self.clean_string(track['artists'][0]['name'])
                    if (track_title == search_title and 
                        (not search_artist or track_artist == search_artist)):
                        return MatchResult(
                            track_id=track['id'],
                            track_name=track['name'],
                            artist_name=track['artists'][0]['name'],
                            match_type='exact',
                            confidence=1.0,
                            platform='spotify'
                        )
                # Fuzzy match (track+artist)
                best_match = None
                best_score = 0
                for track in results['tracks']['items']:
                    track_title = track['name']
                    track_artist = track['artists'][0]['name']
                    title_score = self._fuzzy_match(track_title, title)
                    artist_score = 1.0
                    if artist:
                        artist_score = self._fuzzy_match(track_artist, artist)
                    combined_score = (title_score * 0.7) + (artist_score * 0.3)
                    if combined_score > best_score and combined_score > 0.5:
                        best_score = combined_score
                        best_match = track
                if best_match:
                    return MatchResult(
                        track_id=best_match['id'],
                        track_name=best_match['name'],
                        artist_name=best_match['artists'][0]['name'],
                        match_type='fuzzy',
                        confidence=best_score,
                        platform='spotify'
                    )
            # 2. Search by title only (no artist)
            title_only_results = self.sp.search(q=f'track:"{title}"', type='track', limit=50)
            if title_only_results and title_only_results.get('tracks') and title_only_results['tracks'].get('items'):
                best_match = None
                best_score = 0
                for track in title_only_results['tracks']['items']:
                    track_title = track['name']
                    title_score = self._fuzzy_match(track_title, title)
                    if title_score > best_score and title_score > 0.5:
                        best_score = title_score
                        best_match = track
                if best_match:
                    return MatchResult(
                        track_id=best_match['id'],
                        track_name=best_match['name'],
                        artist_name=best_match['artists'][0]['name'],
                        match_type='title_only',
                        confidence=best_score,
                        platform='spotify'
                    )
            # 3. Search by artist only, fuzzy match title
            if artist:
                artist_results = self.sp.search(q=f'artist:"{artist}"', type='track', limit=50)
                if artist_results and artist_results.get('tracks') and artist_results['tracks'].get('items'):
                    best_match = None
                    best_score = 0
                    for track in artist_results['tracks']['items']:
                        track_title = track['name']
                        title_score = self._fuzzy_match(track_title, title)
                        if title_score > best_score and title_score > 0.45:
                            best_score = title_score
                            best_match = track
                    if best_match:
                        return MatchResult(
                            track_id=best_match['id'],
                            track_name=best_match['name'],
                            artist_name=best_match['artists'][0]['name'],
                            match_type='artist_fallback',
                            confidence=best_score,
                            platform='spotify'
                        )
            return None
        except Exception:
            return None

    def create_playlist(self, name: str, description: str = "") -> Optional[str]:
        try:
            if not self.sp:
                return None
            user_info = self.sp.me()
            if not user_info:
                return None
            user_id = user_info.get('id')
            if not user_id:
                return None
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=False,
                description=description
            )
            return playlist.get('id') if playlist else None
        except Exception:
            return None

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        try:
            if not self.sp:
                return False
            track_uris = [f"spotify:track:{track_id}" for track_id in track_ids]
            batch_size = 100
            for i in range(0, len(track_uris), batch_size):
                batch = track_uris[i:i + batch_size]
                self.sp.playlist_add_items(playlist_id, batch)
                time.sleep(0.1)
            return True
        except Exception:
            return False

class WorkerThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finished_signal = pyqtSignal()
    error_signal = pyqtSignal(str)
    # Add stop_requested flag
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.stop_requested = False

    def run(self):
        try:
            self.transfer_music()
        except Exception as e:
            self.error_signal.emit(str(e))
        finally:
            self.finished_signal.emit()

    def transfer_music(self):
        music_dir = self.config['music_directory']
        playlist_name = self.config['playlist_name']
        spotify_config = self.config['spotify']

        self.log_signal.emit(f"📁 Scanning directory: {music_dir}")
        music_files = []
        for root, dirs, files in os.walk(music_dir):
            for file in files:
                if any(file.lower().endswith(ext) for ext in AudioMetadataExtractor.SUPPORTED_FORMATS):
                    music_files.append(os.path.join(root, file))
        total_files = len(music_files)
        self.log_signal.emit(f"🎵 Found {total_files} music files")
        if total_files == 0:
            self.error_signal.emit("No music files found in the selected directory.")
            return

        handler = SpotifyHandler(spotify_config)
        if not handler.authenticate():
            self.error_signal.emit("Spotify authentication failed during transfer.")
            return

        description = f"Auto-generated by Local2Stream - {total_files} files processed on {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        playlist_id = handler.create_playlist(playlist_name, description)
        if not playlist_id:
            self.error_signal.emit("Failed to create Spotify playlist.")
            return
        self.log_signal.emit(f"✅ Created playlist: {playlist_name}")

        track_ids = []
        found_exact = 0
        found_fuzzy = 0
        found_title = 0
        found_artist = 0
        not_found = 0

        for i, file_path in enumerate(music_files):
            if self.stop_requested:
                self.log_signal.emit("⏹️ Transfer stopped by user. Only processed tracks will be added to playlist.")
                break
            self.progress_signal.emit(int((i+1)/total_files*100))
            metadata = AudioMetadataExtractor.extract_metadata(file_path)
            if not metadata:
                self.log_signal.emit(f"❌ Could not extract metadata: {os.path.basename(file_path)}")
                not_found += 1
                continue
            self.log_signal.emit(f"🔍 Searching: {metadata.artist} - {metadata.title}")
            match = handler.search_track(metadata)
            if match:
                track_ids.append(match.track_id)
                if match.match_type == 'exact':
                    found_exact += 1
                    self.log_signal.emit(f"✅ [Exact] {match.artist_name} - {match.track_name}")
                elif match.match_type == 'fuzzy':
                    found_fuzzy += 1
                    self.log_signal.emit(f"🔍 [Fuzzy] {match.artist_name} - {match.track_name}")
                elif match.match_type == 'title_only':
                    found_title += 1
                    self.log_signal.emit(f"🔍 [Title Only] {match.artist_name} - {match.track_name}")
                elif match.match_type == 'artist_fallback':
                    found_artist += 1
                    self.log_signal.emit(f"🔍 [Artist Fallback] {match.artist_name} - {match.track_name}")
            else:
                not_found += 1
                self.log_signal.emit(f"❌ Not found: {metadata.artist} - {metadata.title}")

        if not track_ids:
            self.error_signal.emit("No tracks matched on Spotify.")
            return
        self.log_signal.emit(f"Adding {len(track_ids)} tracks to playlist...")
        if handler.add_tracks_to_playlist(playlist_id, track_ids):
            self.log_signal.emit("🎉 All tracks added to playlist successfully!")
        else:
            self.error_signal.emit("Failed to add tracks to playlist.")

        self.log_signal.emit("\n==== SUMMARY ====")
        self.log_signal.emit(f"Total files: {total_files}")
        self.log_signal.emit(f"Exact matches: {found_exact}")
        self.log_signal.emit(f"Fuzzy matches: {found_fuzzy}")
        self.log_signal.emit(f"Title only matches: {found_title}")
        self.log_signal.emit(f"Artist fallback matches: {found_artist}")
        self.log_signal.emit(f"Not found: {not_found}")
        if total_files > 0:
            success_rate = ((found_exact + found_fuzzy + found_title + found_artist) / total_files) * 100
            self.log_signal.emit(f"Success rate: {success_rate:.1f}%")

class RetroStatusBar(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setStyleSheet("""
            QWidget {
                background-color: #181C1A;
                border-top: 2px solid #7CFC98;
                border-bottom: 2px solid #7CFC98;
            }
        """)
        layout = QHBoxLayout()
        layout.setContentsMargins(8, 0, 8, 0)
        layout.setSpacing(16)

        # Marquee label
        self.marquee_label = QLabel()
        self.marquee_label.setStyleSheet("color: #7CFC98; font-family: 'VT323', monospace; font-size: 18px;")
        self.marquee_label.setFixedHeight(28)
        self.marquee_text = ""
        self.marquee_pos = 0
        self.marquee_timer = QTimer(self)
        self.marquee_timer.timeout.connect(self.scroll_marquee)
        self.marquee_timer.start(80)
        layout.addWidget(self.marquee_label, stretch=2)

        # Digital clock
        self.clock_label = QLabel()
        self.clock_label.setStyleSheet("color: #00ccff; font-family: 'VT323', monospace; font-size: 22px; background: #000; border: 2px inset #7CFC98; padding: 2px 12px; border-radius: 6px;")
        self.clock_label.setFixedWidth(120)
        self.clock_timer = QTimer(self)
        self.clock_timer.timeout.connect(self.update_clock)
        self.clock_timer.start(1000)
        self.update_clock()
        layout.addWidget(self.clock_label, stretch=0)

        # Blinking indicator label (REC/PLAY)
        self.message_label = QLabel()
        self.message_label.setStyleSheet("color: #E8E8E8; font-family: 'VT323', monospace; font-size: 18px; padding-left: 12px;")
        self.message_label.setFixedHeight(28)
        layout.addWidget(self.message_label, stretch=2)
        self.setLayout(layout)

        self._indicator_mode = None  # 'REC', 'PLAY', or None
        self._indicator_visible = True
        self._indicator_timer = QTimer(self)
        self._indicator_timer.timeout.connect(self._blink_indicator)

    def set_marquee(self, text):
        self.marquee_text = text + "   "
        self.marquee_pos = 0
        self.marquee_label.setText(self.marquee_text)

    def scroll_marquee(self):
        if not self.marquee_text:
            return
        display_len = 48
        text = self.marquee_text
        if len(text) < display_len:
            self.marquee_label.setText(text)
            return
        pos = self.marquee_pos % len(text)
        shown = (text + text)[pos:pos+display_len]
        self.marquee_label.setText(shown)
        self.marquee_pos += 1

    def update_clock(self):
        self.clock_label.setText(QTime.currentTime().toString('hh:mm:ss'))

    def show_message(self, text, kind=None, duration=5000):
        # Only update marquee for error/success/complete
        if kind == 'error':
            self.set_marquee(f"❌ {text}")
        elif kind == 'success':
            self.set_marquee(f"✅ {text}")
        else:
            self.set_marquee(text)
        # message_label is now only for indicator, not used here

    def set_indicator(self, mode):
        # mode: 'REC', 'PLAY', or None
        self._indicator_mode = mode
        self._indicator_visible = True
        if mode == 'REC':
            self.message_label.setStyleSheet("color: #ff4444; font-family: 'VT323', monospace; font-size: 18px; padding-left: 12px; font-weight: bold;")
            self._indicator_timer.start(500)
        elif mode == 'PLAY':
            self.message_label.setStyleSheet("color: #7CFC98; font-family: 'VT323', monospace; font-size: 18px; padding-left: 12px; font-weight: bold;")
            self._indicator_timer.start(700)
        else:
            self._indicator_timer.stop()
            self.message_label.setText("")
            return
        self._update_indicator_text()

    def clear_indicator(self):
        self._indicator_mode = None
        self._indicator_timer.stop()
        self.message_label.setText("")

    def _blink_indicator(self):
        self._indicator_visible = not self._indicator_visible
        self._update_indicator_text()

    def _update_indicator_text(self):
        if not self._indicator_mode:
            self.message_label.setText("")
            return
        if self._indicator_visible:
            if self._indicator_mode == 'REC':
                self.message_label.setText("● REC")
            elif self._indicator_mode == 'PLAY':
                self.message_label.setText("▶ PLAY")
        else:
            self.message_label.setText("")

class Local2StreamGUI(QWidget):
    def __init__(self):
        super().__init__()
        # Set app window icon
        self.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), 'icons', '1.png')))
        self.setWindowTitle("🎵 RetroStream 2000 - Blast from the Past Edition")
        self.setGeometry(100, 100, 750, 650)
        self.setObjectName("mainWindow")
        self.init_ui()
        self.spotify_config = None
        self.apply_retro_stylesheet()
        # Always open maximized
        self.showMaximized()

    def apply_retro_stylesheet(self):
        # Lively retro palette: brighter green, lighter gray, energetic but classic
        retro_stylesheet = """
        QWidget#mainWindow {
            background-color: #202624;
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            border: 1px solid #7CFC98;
            background-image: repeating-linear-gradient(
                to bottom,
                #202624 0px,
                #202624 2px,
                #232A26 3px,
                #202624 4px
            );
        }
        QGroupBox {
            border: 1px solid #7CFC98;
            border-radius: 5px;
            margin-top: 10px;
            background: #232A26;
            font-family: 'VT323', 'Courier New', monospace;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 8px;
            color: #7CFC98;
            font-weight: bold;
            font-size: 26px;
            font-family: 'VT323', 'Courier New', monospace;
        }
        QLineEdit {
            background: #181C1A;
            color: #E8E8E8;
            border: 1px solid #7CFC98;
            border-radius: 3px;
            font-family: 'VT323', 'Courier New', monospace;
            font-size: 16px;
            padding: 6px 10px;
        }
        QGroupBox#playlistGroup QLineEdit, QGroupBox#playlistGroup QLabel {
            font-size: 14px;
            padding: 3px 6px;
        }
        QGroupBox#playlistGroup {
            font-size: 15px;
        }
        QPushButton {
            background: #202624;
            border: 1px solid #7CFC98;
            border-radius: 4px;
            min-width: 120px;
            padding: 8px 18px;
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            font-size: 16px;
            font-weight: bold;
        }
        QPushButton:hover {
            background: #232A26;
        }
        QProgressBar {
            background: #181C1A;
            border: 1px solid #7CFC98;
            border-radius: 4px;
            text-align: center;
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            font-size: 16px;
        }
        QProgressBar::chunk {
            background: #7CFC98;
            border-radius: 2px;
        }
        QTextEdit {
            background: #181C1A;
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            font-size: 16px;
            border: 1px solid #7CFC98;
            border-radius: 4px;
            padding: 8px 10px;
        }
        QScrollBar:vertical {
            background: #232A26;
            width: 14px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:vertical {
            background: #7CFC98;
            min-height: 24px;
            border-radius: 6px;
        }
        QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
            background: #202624;
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
        QScrollBar:horizontal {
            background: #232A26;
            height: 14px;
            margin: 0px 0px 0px 0px;
        }
        QScrollBar::handle:horizontal {
            background: #7CFC98;
            min-width: 24px;
            border-radius: 6px;
        }
        QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
            background: #202624;
            width: 0px;
        }
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
            background: none;
        }
        QStatusBar {
            background: #202624;
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            /* border-top: 1px solid #7CFC98; */
            font-size: 16px;
            margin-bottom: 0px;
            padding-bottom: 0px;
        }
        QLabel {
            color: #E8E8E8;
            font-family: 'VT323', 'Courier New', monospace;
            font-size: 18px;
        }
        """
        self.setStyleSheet(retro_stylesheet)
        # Ensure all main buttons are always wide enough
        self.dir_browse.setMinimumWidth(120)
        self.dir_browse.setStyleSheet("padding: 8px 18px;")
        self.start_button.setMinimumWidth(140)
        self.start_button.setStyleSheet("padding: 8px 18px;")
        # Make Playlist & Spotify Credentials group and contents compact
        self.form_group.setObjectName("playlistGroup")
        self.playlist_input.setStyleSheet("font-size: 14px; padding: 3px 6px;")
        self.client_id_input.setStyleSheet("font-size: 14px; padding: 3px 6px;")
        self.client_secret_input.setStyleSheet("font-size: 14px; padding: 3px 6px;")

    def init_ui(self):
        # Load and set the VT323 pixel font globally
        font_id = QFontDatabase.addApplicationFont("fonts/VT323-Regular.ttf")
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            retro_font = QFont(families[0], 13)
            QApplication.setFont(retro_font)
        main_layout = QVBoxLayout()

        # --- SPINNING VINYL/CASSETTE ANIMATION (hidden by default) ---
        self.spinner_label = QLabel()
        self.spinner_label.setAlignment(Qt.AlignCenter if hasattr(Qt, 'AlignCenter') else 0x0004)
        self.spinner_pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'icons', '5.png'))
        self.spinner_angle = 0
        self.spinner_timer = QTimer(self)
        self.spinner_timer.timeout.connect(self.rotate_spinner)
        if not self.spinner_pixmap.isNull():
            self.spinner_label.setPixmap(self.spinner_pixmap.scaled(64, 64, getattr(Qt, 'KeepAspectRatio', 0x01), getattr(Qt, 'SmoothTransformation', 0x01)))
        self.spinner_label.setVisible(False)
        main_layout.addWidget(self.spinner_label)

        # Retro logo and Local2Stream title side by side (move to top)
        logo_text_layout = QHBoxLayout()
        logo_label = QLabel()
        logo_pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'icons', '1.png'))
        if not logo_pixmap.isNull():
            logo_label.setPixmap(logo_pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        logo_text_layout.addWidget(logo_label)
        # Reduce distance between logo and text
        logo_text_layout.addSpacing(6)
        # --- RETRO TITLE AS QPIXMAP ---
        # Render RetroStream 2000 with VT323 font to a pixmap for crisp retro look
        title_text = "RetroStream 2000"
        font_size = 38  # Smaller size
        if families:
            retro_font = QFont(families[0], font_size, QFont.Bold)
        else:
            retro_font = QFont("Courier New", font_size, QFont.Bold)
        # Calculate text size
        temp_label = QLabel()
        temp_label.setFont(retro_font)
        metrics = temp_label.fontMetrics()
        text_width = metrics.width(title_text)
        text_height = metrics.height()
        pixmap = QPixmap(text_width + 12, text_height + 12)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        painter.setFont(retro_font)
        # Draw shadow for retro effect
        painter.setPen(QColor("#222"))
        for dx, dy in [(2,2),(1,1)]:
            painter.drawText(6+dx, text_height+dy, title_text)
        # Draw main text
        painter.setPen(QColor("#00ccff"))
        painter.drawText(6, text_height, "RetroStream ")
        painter.setPen(QColor("#7CFC98"))
        painter.drawText(6 + metrics.width("RetroStream "), text_height, "2000")
        painter.end()
        title_label = QLabel()
        title_label.setPixmap(pixmap)
        logo_text_layout.addWidget(title_label)
        logo_text_layout.setAlignment(Qt.AlignCenter)
        main_layout.addLayout(logo_text_layout)
        main_layout.addSpacing(2)  # Small gap after title

        # --- RETRO TAGLINE (ICON + TEXT + EMOJI, VT323 FONT) ---
        badge_layout = QHBoxLayout()
        badge_layout.addStretch(1)  # Left stretch for centering
        # Add 3.png icon before the badge label
        badge_icon_label = QLabel()
        badge_icon_pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'icons', '3.png'))
        if not badge_icon_pixmap.isNull():
            badge_icon_label.setPixmap(badge_icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        badge_layout.addWidget(badge_icon_label)
        # Add spacing between icon and text
        badge_layout.addSpacing(8)
        badge_label = QLabel("Made with ❤️ with touch of the 90s")
        badge_label.setFont(QFont(families[0], 18) if families else QFont("Courier New", 18))
        badge_label.setStyleSheet("color:#ff6b00;font-family:'VT323',monospace;")
        badge_label.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        badge_layout.addWidget(badge_label)
        badge_layout.addStretch(1)  # Right stretch for centering
        main_layout.addLayout(badge_layout)
        main_layout.addSpacing(6)  # Small gap after badge

        # Music Directory Group (Retro Cassette Deck Style)
        dir_group = QGroupBox("Music Directory (Cassette Deck)")
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Select your music folder...")
        # 'LOAD TAPE' button with 6.png as icon, compact style
        self.dir_browse = QPushButton("LOAD TAPE")
        tape_icon_path = os.path.join(os.path.dirname(__file__), 'icons', '6.png')
        if os.path.exists(tape_icon_path):
            icon = QIcon(tape_icon_path)
            self.dir_browse.setIcon(icon)
            self.dir_browse.setIconSize(QSize(36, 36))
        self.dir_browse.setFixedHeight(32)
        self.dir_browse.setFixedWidth(160)
        self.dir_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_browse)
        dir_group.setLayout(dir_layout)
        # Add icon to group box (decorative label) - now use 5.png
        self.dir_icon_label = QLabel()
        self.dir_icon_pixmap = QPixmap(os.path.join(os.path.dirname(__file__), 'icons', '5.png'))
        self.dir_icon_angle = 0
        self.dir_icon_timer = QTimer(self)
        self.dir_icon_timer.timeout.connect(self.rotate_dir_icon)
        if not self.dir_icon_pixmap.isNull():
            self.dir_icon_label.setPixmap(self.dir_icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            dir_layout.insertWidget(0, self.dir_icon_label)
        main_layout.addWidget(dir_group)
        # Add extra spacing between Music Directory and Playlist/Spotify group
        main_layout.addSpacing(16)

        # Playlist and Spotify Group
        self.form_group = QGroupBox("Playlist & Spotify Credentials")
        self.form_layout = QVBoxLayout()
        # Playlist Name (full width)
        playlist_row = QFormLayout()
        self.playlist_input = QLineEdit()
        self.playlist_input.setPlaceholderText("e.g. Local2Stream Collection")
        playlist_row.addRow("Playlist Name:", self.playlist_input)
        self.form_layout.addLayout(playlist_row)
        # Client ID and Secret side by side, left and right
        creds_row = QHBoxLayout()
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Your Spotify Client ID")
        self.client_id_input.setMinimumWidth(480)
        self.client_id_input.setMaximumWidth(750)
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Your Spotify Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.Password)
        self.client_secret_input.setMinimumWidth(480)
        self.client_secret_input.setMaximumWidth(750)
        # Left side: Spotify Client ID
        creds_row.addWidget(QLabel("Spotify Client ID:"))
        creds_row.addWidget(self.client_id_input)
        # Stretch in the middle
        creds_row.addStretch(1)
        # Right side: Spotify Client Secret
        creds_row.addWidget(QLabel("Spotify Client Secret:"))
        creds_row.addWidget(self.client_secret_input)
        self.form_layout.addLayout(creds_row)
        self.form_group.setLayout(self.form_layout)
        main_layout.addWidget(self.form_group)
        # Add minimal spacing after Playlist & Spotify Credentials
        main_layout.addSpacing(6)

        # Start Transfer and Stop Transfer Buttons - use 4.png, compact style
        button_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Transfer")
        start_icon_path = os.path.join(os.path.dirname(__file__), 'icons', '4.png')
        if os.path.exists(start_icon_path):
            icon = QIcon(start_icon_path)
            self.start_button.setIcon(icon)
            self.start_button.setIconSize(QSize(24, 24))
        self.start_button.setFixedHeight(32)
        self.start_button.setFixedWidth(220)
        self.start_button.clicked.connect(self.start_transfer)
        button_layout.addWidget(self.start_button)
        # Add Stop Transfer button on the right
        self.stop_button = QPushButton("Stop Transfer")
        stop_icon_path = os.path.join(os.path.dirname(__file__), 'icons', '2.png')
        if os.path.exists(stop_icon_path):
            stop_icon = QIcon(stop_icon_path)
            self.stop_button.setIcon(stop_icon)
            self.stop_button.setIconSize(QSize(24, 24))
        self.stop_button.setFixedHeight(32)
        self.stop_button.setFixedWidth(220)
        self.stop_button.setEnabled(False)
        self.stop_button.clicked.connect(self.stop_transfer)
        button_layout.addWidget(self.stop_button)
        main_layout.addLayout(button_layout)
        # Add minimal spacing after Start/Stop Transfer
        main_layout.addSpacing(6)

        # Progress Bar with 2.png icon just after the percentage text
        progress_layout = QHBoxLayout()
        self.progress_bar = RetroVUMeter()
        self.progress_bar.setValue(0)
        progress_layout.addWidget(self.progress_bar)
        main_layout.addLayout(progress_layout)
        # Add minimal spacing after Progress Bar
        main_layout.addSpacing(6)

        # Log Area (remove 3.png icon from here)
        log_layout = QHBoxLayout()
        self.log_area = DOSTerminal()
        self.log_area.setReadOnly(True)
        log_layout.addWidget(self.log_area, stretch=1)
        main_layout.addLayout(log_layout)

        # Status Bar (remove icon)
        self.status_bar = RetroStatusBar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if dir_path:
            self.dir_input.setText(dir_path)

    def rotate_spinner(self):
        if self.spinner_pixmap.isNull():
            return
        self.spinner_angle = (self.spinner_angle + 15) % 360
        transform = QTransform().rotate(self.spinner_angle)
        rotated = self.spinner_pixmap.transformed(transform, getattr(Qt, 'SmoothTransformation', 0x01))
        self.spinner_label.setPixmap(rotated.scaled(64, 64, getattr(Qt, 'KeepAspectRatio', 0x01), getattr(Qt, 'SmoothTransformation', 0x01)))

    def start_spinner(self):
        self.spinner_label.setVisible(True)
        self.spinner_angle = 0
        self.spinner_timer.start(40)
        self.rotate_spinner()

    def stop_spinner(self):
        self.spinner_timer.stop()
        self.spinner_label.setVisible(False)

    def rotate_dir_icon(self):
        if self.dir_icon_pixmap.isNull():
            return
        self.dir_icon_angle = (self.dir_icon_angle + 15) % 360
        transform = QTransform().rotate(self.dir_icon_angle)
        rotated = self.dir_icon_pixmap.transformed(transform, Qt.SmoothTransformation)
        self.dir_icon_label.setPixmap(rotated.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def start_dir_icon_spin(self):
        self.dir_icon_angle = 0
        self.dir_icon_timer.start(40)
        self.rotate_dir_icon()

    def stop_dir_icon_spin(self):
        self.dir_icon_timer.stop()
        # Reset to original
        if not self.dir_icon_pixmap.isNull():
            self.dir_icon_label.setPixmap(self.dir_icon_pixmap.scaled(32, 32, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def start_transfer(self):
        music_dir = self.dir_input.text().strip()
        playlist_name = self.playlist_input.text().strip()
        client_id = self.client_id_input.text().strip()
        client_secret = self.client_secret_input.text().strip()
        if not music_dir or not playlist_name or not client_id or not client_secret:
            QMessageBox.warning(self, "Missing Fields", "Please fill in all fields before starting.")
            return
        config = {
            'music_directory': music_dir,
            'playlist_name': playlist_name,
            'platforms': ['spotify'],
            'spotify': {
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': 'http://127.0.0.1:8888/callback'
            }
        }
        handler = SpotifyHandler(config['spotify'])
        self.status_bar.set_marquee("Authenticating with Spotify...")
        QApplication.setOverrideCursor(Qt.WaitCursor)
        result = handler.authenticate()
        QApplication.restoreOverrideCursor()
        if not result:
            self.status_bar.show_message("Spotify authentication failed.", kind='error', duration=7000)
            QMessageBox.critical(self, "Spotify Authentication Failed", "Could not authenticate with Spotify. Please check your credentials.")
            return
        self.status_bar.set_marquee("Spotify authenticated! Starting transfer...")
        self.status_bar.show_message("Spotify authenticated!", kind='success', duration=2000)
        self.status_bar.set_indicator('REC')
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.start_dir_icon_spin()  # Start spinning cassette
        self.worker = WorkerThread(config)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.transfer_finished)
        self.worker.error_signal.connect(self.show_error)
        self.worker.stop_requested = False
        self.worker.start()

    def stop_transfer(self):
        if hasattr(self, 'worker') and self.worker.isRunning():
            self.worker.stop_requested = True
            self.stop_button.setEnabled(False)
            self.status_bar.set_marquee("Stopping transfer...")
            self.status_bar.clear_indicator()
            self.stop_dir_icon_spin()  # Stop spinning cassette

    def append_log(self, message):
        self.log_area.append(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def transfer_finished(self):
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.status_bar.set_marquee("Transfer complete!")
        self.status_bar.show_message("Transfer complete!", kind='success', duration=5000)
        self.status_bar.set_indicator('PLAY')
        self.stop_dir_icon_spin()  # Stop spinning cassette

    def show_error(self, message):
        self.status_bar.show_message(message, kind='error', duration=10000)
        self.status_bar.set_indicator('PLAY')
        QMessageBox.critical(self, "Error", message)
        self.start_button.setEnabled(True)
        self.stop_dir_icon_spin()  # Stop spinning cassette

class RetroVUMeter(QProgressBar):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setMinimum(0)
        self.setMaximum(100)
        self.setTextVisible(False)
        self.led_count = 16  # Number of LED bars
        self.led_levels = [0] * self.led_count
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.animate)
        self.timer.start(80)
        self.target_level = 0
        self.last_value = 0

    def setValue(self, value):
        super().setValue(value)
        self.target_level = int((value / 100) * self.led_count)
        self.last_value = value
        self.update()

    def animate(self):
        # Animate the LED bars to bounce up/down toward the target level
        for i in range(self.led_count):
            if i < self.target_level:
                # Add some random bounce for retro effect
                self.led_levels[i] = min(self.led_levels[i] + (1 if self.led_levels[i] < 8 else 0), 8)
            else:
                self.led_levels[i] = max(self.led_levels[i] - 1, 0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        rect = self.rect()
        bar_width = rect.width() // self.led_count
        led_height = rect.height() // 9
        margin = 4
        for i in range(self.led_count):
            for j in range(8):
                led_rect = QRect(
                    rect.x() + i * bar_width + margin // 2,
                    rect.bottom() - (j + 1) * led_height - margin,
                    bar_width - margin,
                    led_height - 2
                )
                if j < self.led_levels[i]:
                
                    # All LEDs are high-contrast bright green
                    color = QColor('#00FF00')
                    painter.setBrush(color)
                    painter.setPen(QColor('#222'))
                else:
                    painter.setBrush(QColor('#222'))
                    painter.setPen(QColor('#111'))
                painter.drawRect(led_rect)
        # Draw retro border
        painter.setPen(QColor('#7CFC98'))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(rect.adjusted(0, 0, -1, -1))
        # Draw percentage text in VT323 font
        percent = int(self.value())
        text = f"{percent}%"
        font = QFont("VT323", 18, QFont.Bold)
        painter.setFont(font)
        metrics = painter.fontMetrics()
        text_width = metrics.width(text)
        text_height = metrics.height()
        painter.setPen(QColor('#7CFC98'))
        painter.drawText((rect.width() - text_width) // 2, (rect.height() + text_height) // 2 - 6, text)
        painter.end()

class DOSTerminal(QPlainTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.cursor_visible = True
        self.cursor_timer = QTimer()
        self.cursor_timer.timeout.connect(self.toggle_cursor)
        self.cursor_timer.start(500)  # Blink every 500ms
        # Set a reliable monospace font
        font = QFont("Consolas")
        font.setStyleHint(QFont.Monospace)
        font.setPointSize(13)
        self.setFont(font)
        self.setStyleSheet("""
            QPlainTextEdit {
                background-color: #000000;
                color: #00FF00;
                border: 2px solid #00FF00;
                border-radius: 0px;
                padding: 8px;
                selection-background-color: #00FF00;
                selection-color: #000000;
            }
        """)
        self.setup_ascii_header()
        
    def setup_ascii_header(self):
        ascii_art = """╔══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════════╗
║ ██████╗ ███████╗████████╗██████╗  ██████╗ ███████╗████████╗██████╗ ███████╗ █████╗ ███╗   ███╗██████╗  ██████╗  ██████╗  ██████╗ ║
║ ██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔════╝██╔══██╗████╗ ████║╚════██╗██╔═████╗██╔═████╗██╔═████╗ ║
║ ██████╔╝█████╗     ██║   ██████╔╝██║  ██║███████╗   ██║   ██████╔╝█████╗  ███████║██╔████╔██║ █████╔╝██║██╔██║██║██╔██║██║██╔██║ ║
║ ██╔══██╗██╔══╝     ██║   ██╔══██╗██║  ██║╚════██║   ██║   ██╔══██╗██╔══╝  ██╔══██║██║╚██╔╝██║██╔═══╝ ████╔╝██║████╔╝██║████╔╝██║ ║
║ ██║  ██║███████╗   ██║   ██║  ██║██████╔╝███████║   ██║   ██║  ██║███████╗██║  ██║██║ ╚═╝ ██║███████╗╚██████╔╝╚██████╔╝╚██████╔╝ ║
║ ╚═╝  ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝╚═╝     ╚═╝╚══════╝ ╚═════╝  ╚═════╝  ╚═════╝  ║
║                                          RETROSTREAM2000 - DOS TERMINAL      ╔═══════════════════════════════════════════════════╝
║                                                                              ║
║  C:\\> RETROSTREAM.EXE /MUSIC_TRANSFER /PLATFORM=SPOTIFY                      ║
║  Initializing fuzzy matching algorithms...                                   ║
║  Ready for transfer sequence...                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝"""
        self.appendPlainText(ascii_art)
        
    def toggle_cursor(self):
        self.cursor_visible = not self.cursor_visible
        self.viewport().update()
        
    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Draw scanline overlay
        painter = QPainter(self.viewport())
        painter.setPen(QColor(0, 255, 0, 30))  # Semi-transparent green
        
        # Draw horizontal scanlines
        for y in range(0, self.height(), 2):
            painter.drawLine(0, y, self.width(), y)
            
        # Draw blinking cursor at the end (thicker)
        if self.cursor_visible:
            cursor_rect = self.cursorRect()
            painter.setPen(QColor(0, 255, 0))
            # Draw a 3px wide vertical bar for the cursor
            for dx in range(3):
                painter.drawLine(cursor_rect.x() + dx, cursor_rect.y(),
                                 cursor_rect.x() + dx, cursor_rect.y() + cursor_rect.height())
        
        painter.end()
        
    def append(self, text):
        # Preserve emojis while adding DOS-style formatting
        if text.startswith("✅") or text.startswith("❌") or text.startswith("🔍") or text.startswith("📁") or text.startswith("🎵"):
            # Keep emojis as they are
            self.appendPlainText(text)
        else:
            # Add DOS prompt for regular messages
            self.appendPlainText(f"C:\\> {text}")
        
        # Auto-scroll to bottom
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

if __name__ == "__main__":
    app = QApplication(sys.argv)
    os.environ["QT_LOGGING_RULES"] = "qt.font.*=false"
    window = Local2StreamGUI()
    window.show()
    sys.exit(app.exec_())