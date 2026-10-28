from unittest.mock import patch

import pytest
from click.testing import CliRunner

from songchro.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def config_file(tmp_path):
    config = {
        "file": {
            "tracks": str(tmp_path / "tracks.json"),
            "root": str(tmp_path / "playlists"),
            "music_root": str(tmp_path / "music"),
        }
    }
    config_path = tmp_path / "config.yml"
    import yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f)
    return str(config_path), tmp_path


class TestCliVersion:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output


class TestFileCommands:
    def test_file_list(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        (tmp_path / "music").mkdir()
        result = runner.invoke(cli, ["--config", config_path, "file", "list"])
        assert result.exit_code == 0

    def test_file_list_simple(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        (tmp_path / "music").mkdir()
        result = runner.invoke(cli, ["--config", config_path, "file", "list", "--simple"])
        assert result.exit_code == 0

    def test_update_meta_single_directory(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        music = tmp_path / "music"
        music.mkdir()
        subdir = music / "artist"
        subdir.mkdir()
        (subdir / "song.mp3").touch()
        with patch("songchro.file_library.mp3_m4a_files", return_value=[]):
            result = runner.invoke(cli, ["--config", config_path, "file", "update-meta", str(subdir)])
        assert result.exit_code == 0

    def test_update_meta_multiple_directories(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        music = tmp_path / "music"
        music.mkdir()
        d1 = music / "artist1"
        d1.mkdir()
        d2 = music / "artist2"
        d2.mkdir()
        calls = []

        def capture_mp3_m4a_files(directory):
            calls.append(directory)
            return []

        with patch("songchro.file_library.mp3_m4a_files", side_effect=capture_mp3_m4a_files):
            result = runner.invoke(cli, ["--config", config_path, "file", "update-meta", str(d1), str(d2)])
        assert result.exit_code == 0
        assert len(calls) == 2

    def test_update_meta_rejects_directory_outside_music_root(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        (tmp_path / "music").mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        result = runner.invoke(cli, ["--config", config_path, "file", "update-meta", str(outside)])
        assert result.exit_code == 1
        assert "not under the music root" in result.output

    def test_update_meta_requires_at_least_one_directory(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        (tmp_path / "music").mkdir()
        result = runner.invoke(cli, ["--config", config_path, "file", "update-meta"])
        assert result.exit_code != 0

    def test_update_meta_first_valid_second_invalid(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        music = tmp_path / "music"
        music.mkdir()
        d1 = music / "artist1"
        d1.mkdir()
        outside = tmp_path / "outside"
        outside.mkdir()
        calls = []

        def capture_mp3_m4a_files(directory):
            calls.append(directory)
            return []

        with patch("songchro.file_library.mp3_m4a_files", side_effect=capture_mp3_m4a_files):
            result = runner.invoke(cli, ["--config", config_path, "file", "update-meta", str(d1), str(outside)])
        assert result.exit_code == 1
        assert len(calls) == 1


class TestSyncCommand:
    @patch("songchro.cli.fl")
    @patch("songchro.cli.it")
    @patch("songchro.cli.pl")
    @patch("songchro.cli.apple_music")
    def test_sync_help(self, mock_am, mock_pl, mock_it, mock_fl, runner):
        result = runner.invoke(cli, ["sync", "--help"])
        assert result.exit_code == 0
        assert "Synchronize" in result.output


class TestCompletionCommand:
    def test_completion_bash(self, runner):
        result = runner.invoke(cli, ["completion", "--shell", "bash"])
        assert result.exit_code == 0

    def test_completion_zsh(self, runner):
        result = runner.invoke(cli, ["completion", "--shell", "zsh"])
        assert result.exit_code == 0

    def test_completion_fish(self, runner):
        result = runner.invoke(cli, ["completion", "--shell", "fish"])
        assert result.exit_code == 0


class TestCliWithNoConfig:
    def test_file_list_no_config(self, runner):
        result = runner.invoke(cli, ["--config", "/dev/none", "file", "list"])
        assert result.exit_code != 0


class TestLoggingLevel:
    def test_logging_level_option(self, runner, config_file):
        config_path, tmp_path = config_file
        (tmp_path / "playlists").mkdir()
        (tmp_path / "music").mkdir()
        result = runner.invoke(cli, ["--logging-level", "DEBUG", "--config", config_path, "file", "list"])
        assert result.exit_code == 0
