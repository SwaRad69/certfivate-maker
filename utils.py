"""
Utility functions and classes for certificate generation.
Includes CheckpointManager, logging setup, and helpers.
"""

import json
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from config import CHECKPOINT_FILENAME, LOG_FORMAT, LOG_FILENAME


@contextmanager
def output_checkpoint_lock(output_folder):
    """Keep two CLI processes from reserving or writing the same output."""
    lock_path = Path(output_folder) / '.certificate_checkpoint.lock'
    with lock_path.open('a+b') as lock:
        lock.seek(0)
        try:
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Could not lock the output folder. Check for another running generation.") from error
        # Closing the handle releases the lock, including after a process exit.
        yield


class CheckpointManager:
    """Store independent CLI checkpoints for each input and template revision."""

    def __init__(self, output_folder: str, identity=None):
        self.checkpoint_path = Path(output_folder) / CHECKPOINT_FILENAME
        self.identity = identity
        self.batches = self._load_batches()
        self.state = self.batches.get(identity, {})
        self.completed_rows = set(self.state.get('completed_rows', []))
        self.temp_slide_ids = self.state.get('temp_slide_ids', {})
        self.output_files = self.state.get('output_files', {})

    def _load_batches(self):
        try:
            with self.checkpoint_path.open(encoding='utf-8') as checkpoint:
                data = json.load(checkpoint)
                if data.get('version') == 2 and isinstance(data.get('batches'), dict):
                    return data['batches']
                logging.warning("Ignoring a legacy checkpoint without input and template identity.")
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError, AttributeError) as error:
            logging.warning("Ignoring an unreadable checkpoint: %s", error)
        return {}

    def save(self) -> None:
        if self.identity is None:
            return
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self.batches[self.identity] = {
            'completed_rows': sorted(self.completed_rows),
            'temp_slide_ids': self.temp_slide_ids,
            'output_files': self.output_files,
            'last_saved': datetime.now().isoformat(),
        }
        # Preserve the last good checkpoint if writing is interrupted.
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode='w', encoding='utf-8', suffix='.tmp',
                dir=self.checkpoint_path.parent, delete=False,
            ) as temporary:
                temp_path = Path(temporary.name)
                json.dump({'version': 2, 'batches': self.batches}, temporary, indent=2)
                temporary.flush()
                os.fsync(temporary.fileno())
            temp_path.replace(self.checkpoint_path)
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)

    def is_complete(self, row_index: int) -> bool:
        key = str(row_index)
        filename = self.output_files.get(key)
        path = self._output_path(filename) if filename else None
        return (
            row_index in self.completed_rows
            and path is not None
            and filename.casefold() not in self._other_outputs(key)
            and not path.is_symlink()
            and path.is_file()
        )

    def _output_path(self, filename):
        relative = Path(filename)
        if relative.anchor or len(relative.parts) not in (1, 2) or '..' in relative.parts:
            return None
        path = self.checkpoint_path.parent / relative
        if path.parent.resolve() == path.parent.absolute():
            return path
        return None

    def _other_outputs(self, row_key):
        reserved = {
            filename.casefold() for identity, batch in self.batches.items()
            if identity != self.identity for filename in batch.get('output_files', {}).values()
        }
        reserved.update(name.casefold() for key, name in self.output_files.items() if key != row_key)
        return reserved

    def plan_output(self, row_index: int, filename: str, group_name: str = '') -> str:
        key = str(row_index)
        reserved = self._other_outputs(key)
        previous = self.output_files.get(key)
        previous_path = self._output_path(previous) if previous else None
        if (previous_path and Path(previous).parent == Path(group_name)
                and previous.casefold() not in reserved and not os.path.lexists(previous_path)):
            return previous
        suffix = 1
        candidate = (Path(group_name) / f'{filename}.pdf').as_posix()
        while True:
            path = self._output_path(candidate)
            if path is None:
                raise ValueError(f'Invalid certificate output path: {candidate}')
            if candidate.casefold() not in reserved and not os.path.lexists(path):
                break
            suffix += 1
            candidate = (Path(group_name) / f'{filename}_{suffix}.pdf').as_posix()
        self.completed_rows.discard(row_index)
        self.output_files[key] = candidate
        self.save()
        return candidate

    def mark_complete(self, row_index: int, temp_slide_id: str = None) -> None:
        self.completed_rows.add(row_index)
        if temp_slide_id:
            self.temp_slide_ids[str(row_index)] = temp_slide_id
        self.save()

    def get_temp_slide_id(self, row_index: int) -> str:
        return self.temp_slide_ids.get(str(row_index))

    def clear(self) -> None:
        self.completed_rows = set()
        self.temp_slide_ids = {}
        self.output_files = {}
        if self.identity is None:
            self.checkpoint_path.unlink(missing_ok=True)
        else:
            self.save()
        logging.info("Checkpoint cleared.")


def setup_logging(output_folder: str, verbose: bool = False) -> None:
    """
    Setup logging to file and console.
    
    Args:
        output_folder: Path to output folder for log file
        verbose: If True, set console level to DEBUG; otherwise INFO
    """
    os.makedirs(output_folder, exist_ok=True)
    
    log_file = Path(output_folder) / LOG_FILENAME
    
    # Root logger
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    
    # File handler (DEBUG level)
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    # Console handler (INFO or DEBUG level)
    console_handler = logging.StreamHandler()
    console_level = logging.DEBUG if verbose else logging.INFO
    console_handler.setLevel(console_level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    logging.info(f"Logging initialized. Log file: {log_file}")


def safe_filename(filename: str, *, max_bytes=220) -> str:
    """
    Remove or replace invalid filename characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    safe = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', filename).strip('. ')
    stem = safe.split('.', 1)[0].upper()
    if re.fullmatch(r'CON|PRN|AUX|NUL|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3]', stem):
        safe = f'_{safe}'
    # Leave room for PDF extensions and collision suffixes on local filesystems.
    safe = safe.encode('utf-8')[:max_bytes].decode('utf-8', errors='ignore').rstrip('. ')
    return safe or 'certificate'


def ensure_output_folder(output_folder: str) -> str:
    """
    Ensure output folder exists and is writable.
    
    Args:
        output_folder: Path to output folder
        
    Returns:
        Absolute path to output folder
        
    Raises:
        OSError: If folder cannot be created or is not writable
    """
    path = Path(output_folder).resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
        # Test write permission
        test_file = path / '.write_test'
        test_file.touch()
        test_file.unlink()
        logging.info(f"Output folder ready: {path}")
        return str(path)
    except Exception as e:
        logging.error(f"Cannot write to output folder {path}: {e}")
        raise OSError(f"Output folder not writable: {path}") from e
