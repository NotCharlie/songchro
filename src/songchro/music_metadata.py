import os
from functools import cached_property
from pathlib import Path
from typing import Any

import mutagen
from multimethod import multimethod
from mutagen import mp4, mp3, MutagenError

from songchro.model import SongchroException


class MetadataError(SongchroException):
    pass


class TrackMetadata:
    def __init__(self, fpath: Path):
        self.fpath = fpath

    @property
    def title(self) -> str:
        raise NotImplementedError

    @property
    def artist(self) -> str:
        raise NotImplementedError

    @property
    def album_title(self) -> str:
        raise NotImplementedError

    @property
    def album_artist(self) -> str:
        raise NotImplementedError

    @property
    def disc_number(self) -> int:
        raise NotImplementedError

    @property
    def track_number(self) -> int:
        raise NotImplementedError

    @property
    def bits_per_sample(self) -> int:
        raise NotImplementedError

    @property
    def beats_per_minute(self) -> int:
        raise NotImplementedError

    @property
    def filename(self) -> str:
        return str(self.fpath)

    @property
    def sample_rate(self) -> int:
        raise NotImplementedError

    @cached_property
    def properties(self) -> dict[str, str | int]:
        props: dict[str, str | int] = {}
        for cls in self.__class__.__mro__:
            if cls is object:
                continue
            for k, v in cls.__dict__.items():
                if isinstance(v, property) and k not in props:
                    props[k] = getattr(self, k)
        return props

    def __getitem__(self, item):
        return self.properties[item]

    def __setitem__(self, key, value):
        self.properties[key] = value
        del self.properties

    def __delitem__(self, key):
        del self.properties[key]
        del self.properties

    def __len__(self):
        return len(self.properties)

    def __contains__(self, key):
        return key in self.properties

    def json_data(self) -> dict[str, Any]:
        return self.properties


class Mp3TrackMetadata(TrackMetadata):
    def __init__(self, fpath: Path, metadata: mp3.MP3):
        super().__init__(fpath)
        self.metadata = metadata

    @property
    def title(self):
        tag = self.metadata.tags.get("TIT2")
        return tag.text[0] if tag else None

    @property
    def artist(self):
        tag = self.metadata.tags.get("TPE1")
        return tag.text[0] if tag else None

    @property
    def album_title(self):
        tag = self.metadata.tags.get("TALB")
        return tag.text[0] if tag else None

    @property
    def album_artist(self):
        tag = self.metadata.tags.get("TPE2")
        return tag.text[0] if tag else None

    @property
    def disc_number(self):
        tag = self.metadata.tags.get("TPOS")
        return +tag if tag else None

    @property
    def track_number(self):
        tag = self.metadata.tags.get("TRCK")
        return +tag if tag else None

    @property
    def bits_per_sample(self):
        return 0

    @property
    def beats_per_minute(self):
        tag = self.metadata.tags.get("TBPM")
        # return +tag if tag else None
        return int(float(tag.text[0])) if tag else None

    @property
    def sample_rate(self):
        return self.metadata.info.sample_rate


class Mp4TrackMetadata(TrackMetadata):
    def __init__(self, fpath: Path, metadata: mp4.MP4):
        super().__init__(fpath)
        self.metadata = metadata

    @property
    def title(self):
        return self.metadata.tags.get("\u00a9nam", [None])[0]

    @property
    def artist(self):
        return self.metadata.tags.get("\u00a9ART", [None])[0]

    @property
    def album_title(self):
        return self.metadata.tags.get("\u00a9alb", [None])[0]

    @property
    def album_artist(self):
        return self.metadata.tags.get("aART", [None])[0]

    @property
    def disc_number(self):
        tag = self.metadata.tags.get("disk")
        return tag[0][0] if tag else None

    @property
    def track_number(self):
        tag = self.metadata.tags.get("trkn")
        return tag[0][0] if tag else None

    @property
    def bits_per_sample(self):
        return self.metadata.info.bits_per_sample

    @property
    def beats_per_minute(self):
        return self.metadata.tags.get("tmpo")

    @property
    def sample_rate(self):
        return self.metadata.info.sample_rate


@multimethod
def metadata_wrapper(fpath: Path, metadata: mp4.MP4) -> TrackMetadata:
    return Mp4TrackMetadata(fpath, metadata)


@multimethod
def metadata_wrapper(fpath: Path, metadata: mp3.MP3) -> TrackMetadata:
    return Mp3TrackMetadata(fpath, metadata)


def for_file(fpath: Path, music_root: str):
    try:
        metadata = mutagen.File(fpath)
    except MutagenError as e:
        raise MetadataError from e
    return metadata_wrapper(Path(os.path.relpath(fpath, start=music_root)), metadata)
