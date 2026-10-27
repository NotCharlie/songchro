import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
from songchro.music_metadata import (
    TrackMetadata,
    Mp3TrackMetadata,
    Mp4TrackMetadata,
    metadata_wrapper,
    for_file,
    MetadataError,
)
from mutagen import MutagenError


class TestTrackMetadata:
    def test_filename(self, tmp_path):
        mp3_metadata = MagicMock()
        mp3_metadata.tags = {}
        mp3_metadata.info.sample_rate = 44100
        from mutagen.mp3 import MP3
        mp3_metadata.__class__ = MP3
        tm = Mp3TrackMetadata(tmp_path / "song.mp3", mp3_metadata)
        assert tm.filename == str(tmp_path / "song.mp3")

    def test_abstract_properties_raise(self, tmp_path):
        tm = TrackMetadata(tmp_path / "song.mp3")
        with pytest.raises(NotImplementedError):
            _ = tm.title
        with pytest.raises(NotImplementedError):
            _ = tm.artist


class TestMp3TrackMetadata:
    @pytest.fixture
    def mp3_metadata(self, tmp_path):
        from mutagen.mp3 import MP3
        from mutagen.id3 import TPOS, TRCK

        disc_tag = TPOS()
        disc_tag.text = ["1"]
        
        track_tag = TRCK()
        track_tag.text = ["3"]
        
        title_tag = MagicMock(text=["Test Song"])
        artist_tag = MagicMock(text=["Test Artist"])
        album_tag = MagicMock(text=["Test Album"])
        album_artist_tag = MagicMock(text=["Album Artist"])
        bpm_tag = MagicMock(text=["120"])

        metadata = MagicMock()
        metadata.tags = {
            "TIT2": title_tag,
            "TPE1": artist_tag,
            "TALB": album_tag,
            "TPE2": album_artist_tag,
            "TPOS": disc_tag,
            "TRCK": track_tag,
            "TBPM": bpm_tag,
        }
        metadata.info.sample_rate = 44100
        metadata.__class__ = MP3
        tm = Mp3TrackMetadata(tmp_path / "song.mp3", metadata)
        return tm

    def test_title(self, mp3_metadata):
        assert mp3_metadata.title == "Test Song"

    def test_artist(self, mp3_metadata):
        assert mp3_metadata.artist == "Test Artist"

    def test_album_title(self, mp3_metadata):
        assert mp3_metadata.album_title == "Test Album"

    def test_album_artist(self, mp3_metadata):
        assert mp3_metadata.album_artist == "Album Artist"

    def test_disc_number(self, mp3_metadata):
        assert mp3_metadata.disc_number == 1

    def test_track_number(self, mp3_metadata):
        assert mp3_metadata.track_number == 3

    def test_beats_per_minute(self, mp3_metadata):
        assert mp3_metadata.beats_per_minute == 120

    def test_sample_rate(self, mp3_metadata):
        assert mp3_metadata.sample_rate == 44100

    def test_bits_per_sample(self, mp3_metadata):
        assert mp3_metadata.bits_per_sample == 0

    def test_missing_tags(self, tmp_path):
        metadata = MagicMock()
        metadata.tags = {}
        metadata.info.sample_rate = 44100
        tm = Mp3TrackMetadata(tmp_path / "song.mp3", metadata)
        assert tm.title is None
        assert tm.artist is None


class TestMp4TrackMetadata:
    @pytest.fixture
    def mp4_metadata(self, tmp_path):
        metadata = MagicMock()
        metadata.tags = {
            "\u00a9nam": ["Test Song"],
            "\u00a9ART": ["Test Artist"],
            "\u00a9alb": ["Test Album"],
            "aART": ["Album Artist"],
            "disk": [(1, 3)],
            "trkn": [(5, 10)],
            "tmpo": [120],
        }
        metadata.info.bits_per_sample = 16
        metadata.info.sample_rate = 44100
        tm = Mp4TrackMetadata(tmp_path / "song.m4a", metadata)
        return tm

    def test_title(self, mp4_metadata):
        assert mp4_metadata.title == "Test Song"

    def test_artist(self, mp4_metadata):
        assert mp4_metadata.artist == "Test Artist"

    def test_album_title(self, mp4_metadata):
        assert mp4_metadata.album_title == "Test Album"

    def test_album_artist(self, mp4_metadata):
        assert mp4_metadata.album_artist == "Album Artist"

    def test_disc_number(self, mp4_metadata):
        assert mp4_metadata.disc_number == 1

    def test_track_number(self, mp4_metadata):
        assert mp4_metadata.track_number == 5

    def test_beats_per_minute(self, mp4_metadata):
        assert mp4_metadata.beats_per_minute == [120]

    def test_sample_rate(self, mp4_metadata):
        assert mp4_metadata.sample_rate == 44100

    def test_bits_per_sample(self, mp4_metadata):
        assert mp4_metadata.bits_per_sample == 16


class TestMetadataWrapper:
    def test_wraps_mp3(self, tmp_path):
        from mutagen.mp3 import MP3
        
        class MockMP3(MP3):
            def __init__(self):
                pass
        
        mp3_obj = MockMP3()
        result = metadata_wrapper(tmp_path / "song.mp3", mp3_obj)
        assert isinstance(result, Mp3TrackMetadata)

    def test_wraps_mp4(self, tmp_path):
        from mutagen.mp4 import MP4
        
        class MockMP4(MP4):
            def __init__(self):
                pass
        
        mp4_obj = MockMP4()
        result = metadata_wrapper(tmp_path / "song.m4a", mp4_obj)
        assert isinstance(result, Mp4TrackMetadata)


class TestForFile:
    def test_success(self, tmp_path):
        from mutagen.mp3 import MP3
        
        class MockMP3(MP3):
            def __init__(self):
                pass
        
        mp3_obj = MockMP3()
        
        with patch("songchro.music_metadata.mutagen.File", return_value=mp3_obj):
            result = for_file("song.mp3", str(tmp_path))
            assert isinstance(result, Mp3TrackMetadata)

    def test_mutagen_error(self, tmp_path):
        with patch("songchro.music_metadata.mutagen.File", side_effect=MutagenError("bad file")):
            with pytest.raises(MetadataError):
                for_file("song.mp3", str(tmp_path))
