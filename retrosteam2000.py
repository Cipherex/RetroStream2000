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
from PyQt5.QtCore import Qt, QThread, pyqtSignal

# Third-party imports
try:
    import spotipy
    from spotipy.oauth2 import SpotifyOAuth
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.mp4 import MP4
    from mutagen.id3 import ID3NoHeaderError
except ImportError as e:
    QMessageBox.critical(None, "Missing Package", f"Missing required package: {e}\n\nPlease run:\npip install spotipy mutagen PyQt5")
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
            title = str(audio.get('TIT2', [''])[0])
            artist = str(audio.get('TPE1', [''])[0])
            album = str(audio.get('TALB', [''])[0])
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
            title = audio.get('TITLE', [''])[0]
            artist = audio.get('ARTIST', [''])[0]
            album = audio.get('ALBUM', [''])[0]
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
            title = audio.get('\xa9nam', [''])[0]
            artist = audio.get('\xa9ART', [''])[0]
            album = audio.get('\xa9alb', [''])[0]
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
            if results['tracks']['items']:
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
            if title_only_results['tracks']['items']:
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
                if artist_results['tracks']['items']:
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
            user_id = self.sp.me()['id']
            playlist = self.sp.user_playlist_create(
                user=user_id,
                name=name,
                public=False,
                description=description
            )
            return playlist['id']
        except Exception:
            return None

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        try:
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

    def __init__(self, config):
        super().__init__()
        self.config = config

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

class Local2StreamGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Local2Stream - Music Transfer")
        self.setGeometry(100, 100, 750, 650)
        self.init_ui()
        self.spotify_config = None

    def init_ui(self):
        main_layout = QVBoxLayout()

        # Music Directory Group
        dir_group = QGroupBox("Music Directory")
        dir_layout = QHBoxLayout()
        self.dir_input = QLineEdit()
        self.dir_input.setPlaceholderText("Select your music folder...")
        self.dir_browse = QPushButton("Browse")
        self.dir_browse.clicked.connect(self.browse_directory)
        dir_layout.addWidget(self.dir_input)
        dir_layout.addWidget(self.dir_browse)
        dir_group.setLayout(dir_layout)
        main_layout.addWidget(dir_group)

        # Playlist and Spotify Group
        form_group = QGroupBox("Playlist & Spotify Credentials")
        form_layout = QFormLayout()
        self.playlist_input = QLineEdit()
        self.playlist_input.setPlaceholderText("e.g. Local2Stream Collection")
        self.client_id_input = QLineEdit()
        self.client_id_input.setPlaceholderText("Your Spotify Client ID")
        self.client_secret_input = QLineEdit()
        self.client_secret_input.setPlaceholderText("Your Spotify Client Secret")
        self.client_secret_input.setEchoMode(QLineEdit.Password)
        form_layout.addRow("Playlist Name:", self.playlist_input)
        form_layout.addRow("Spotify Client ID:", self.client_id_input)
        form_layout.addRow("Spotify Client Secret:", self.client_secret_input)
        form_group.setLayout(form_layout)
        main_layout.addWidget(form_group)

        # Start Transfer Button
        self.start_button = QPushButton("Start Transfer")
        self.start_button.clicked.connect(self.start_transfer)
        main_layout.addWidget(self.start_button)

        # Progress Bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        main_layout.addWidget(self.progress_bar)

        # Log Area
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        main_layout.addWidget(self.log_area, stretch=1)

        # Status Bar
        self.status_bar = QStatusBar()
        main_layout.addWidget(self.status_bar)

        self.setLayout(main_layout)

    def browse_directory(self):
        dir_path = QFileDialog.getExistingDirectory(self, "Select Music Directory")
        if dir_path:
            self.dir_input.setText(dir_path)

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
                'redirect_uri': 'http://localhost:8888/callback'
            }
        }
        # Try to authenticate before starting transfer
        handler = SpotifyHandler(config['spotify'])
        self.status_bar.showMessage("Authenticating with Spotify...", 2000)
        QApplication.setOverrideCursor(Qt.WaitCursor)
        result = handler.authenticate()
        QApplication.restoreOverrideCursor()
        if not result:
            self.status_bar.showMessage("❌ Spotify authentication failed.", 5000)
            QMessageBox.critical(self, "Spotify Authentication Failed", "Could not authenticate with Spotify. Please check your credentials.")
            return
        self.status_bar.showMessage("✅ Spotify authenticated! Starting transfer...", 2000)
        self.log_area.clear()
        self.progress_bar.setValue(0)
        self.start_button.setEnabled(False)
        self.worker = WorkerThread(config)
        self.worker.log_signal.connect(self.append_log)
        self.worker.progress_signal.connect(self.update_progress)
        self.worker.finished_signal.connect(self.transfer_finished)
        self.worker.error_signal.connect(self.show_error)
        self.worker.start()

    def append_log(self, message):
        self.log_area.append(message)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def transfer_finished(self):
        self.start_button.setEnabled(True)
        self.status_bar.showMessage("Transfer complete!", 5000)
        QMessageBox.information(self, "Done", "Music transfer complete!")

    def show_error(self, message):
        self.status_bar.showMessage("Error: " + message, 10000)
        QMessageBox.critical(self, "Error", message)
        self.start_button.setEnabled(True)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    os.environ["QT_LOGGING_RULES"] = "qt.font.*=false"
    window = Local2StreamGUI()
    window.show()
    sys.exit(app.exec_())