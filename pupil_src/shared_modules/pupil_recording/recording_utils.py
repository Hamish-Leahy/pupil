import enum
from pathlib import Path

from pupil_recording.info import recording_info_utils
from pupil_recording.info.recording_info import RecordingInfoFile
from video_capture.utils import VIDEO_EXTS as VALID_VIDEO_EXTENSIONS


class InvalidRecordingException(Exception):
    def __init__(self, reason: str, recovery: str = ""):
        message = (reason + "\n" + recovery) if recovery else reason
        super().__init__(message)
        self.reason = reason
        self.recovery = recovery

    def __str__(self):
        return f"{type(self).__name__}: {super().__str__()}"


def assert_valid_recording_type(rec_dir: str):
    assert get_recording_type(rec_dir) in RecordingType


class RecordingType(enum.Enum):
    MOBILE = enum.auto()
    INVISIBLE = enum.auto()
    OLD_STYLE = enum.auto()
    NEW_STYLE = enum.auto()


def get_recording_type(rec_dir: str) -> RecordingType:
    _assert_valid_rec_dir(rec_dir)

    if RecordingInfoFile.does_recording_contain_info_file(rec_dir):
        return RecordingType.NEW_STYLE

    elif was_recording_opened_in_player_before(rec_dir):
        return RecordingType.OLD_STYLE

    elif is_pupil_invisible_recording(rec_dir):
        return RecordingType.INVISIBLE

    elif is_pupil_mobile_recording(rec_dir):
        return RecordingType.MOBILE

    raise InvalidRecordingException(
        reason=f"There is no info file in the target directory.", recovery=""
    )


def _assert_valid_rec_dir(rec_dir: str):
    rec_dir = Path(rec_dir).resolve()

    def normalize_extension(ext: str) -> str:
        if ext.startswith("."):
            ext = ext[1:]
        return ext

    def is_video_file(file_path: Path):
        if not file_path.is_file():
            return False
        ext = file_path.suffix
        ext = normalize_extension(ext)
        valid_video_extensions = map(normalize_extension, VALID_VIDEO_EXTENSIONS)
        if ext not in valid_video_extensions:
            return False
        return True

    if not rec_dir.exists():
        raise InvalidRecordingException(
            reason=f"Target at path does not exist: {rec_dir}", recovery=""
        )

    if not rec_dir.is_dir():
        if is_video_file(rec_dir):
            raise InvalidRecordingException(
                reason=f"The provided path is a video, not a recording directory",
                recovery="Please provide a recording directory",
            )
        else:
            raise InvalidRecordingException(
                reason=f"Target at path is not a directory: {rec_dir}", recovery=""
            )


def is_pupil_invisible_recording(rec_dir: str) -> bool:
    try:
        recording_info_utils.read_info_json_file(rec_dir)
        return True
    except FileNotFoundError:
        return False


def is_pupil_mobile_recording(rec_dir: str) -> bool:
    info_csv = recording_info_utils.read_info_csv_file(rec_dir)
    try:
        return (
            info_csv["Capture Software"] == "Pupil Mobile"
            and "Data Format Version" not in info_csv
        )
    except KeyError:
        return False


def was_recording_opened_in_player_before(rec_dir: str) -> bool:
    info_csv = recording_info_utils.read_info_csv_file(rec_dir)
    return "Data Format Version" in info_csv
