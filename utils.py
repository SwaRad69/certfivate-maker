"""
Utility functions and classes for certificate generation.
Includes CheckpointManager, logging setup, and helpers.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Set

from config import CHECKPOINT_FILENAME, LOG_FORMAT, LOG_FILENAME


class CheckpointManager:
    """
    Manages checkpoint state for resuming certificate generation.
    Saves completed row indices to JSON file.
    """

    def __init__(self, output_folder: str):
        """
        Initialize checkpoint manager.
        
        Args:
            output_folder: Path to output folder where checkpoint is stored
        """
        self.checkpoint_path = Path(output_folder) / CHECKPOINT_FILENAME
        self.completed_rows: Set[int] = set()
        self.temp_slide_ids: Dict[int, str] = {}
        self.load()

    def load(self) -> None:
        """Load checkpoint from file if it exists."""
        if self.checkpoint_path.exists():
            try:
                with open(self.checkpoint_path, 'r') as f:
                    data = json.load(f)
                    self.completed_rows = set(data.get('completed_rows', []))
                    self.temp_slide_ids = data.get('temp_slide_ids', {})
                    logging.info(
                        f"Loaded checkpoint: {len(self.completed_rows)} "
                        f"completed rows, {len(self.temp_slide_ids)} temp slides tracked"
                    )
            except Exception as e:
                logging.warning(f"Failed to load checkpoint: {e}. Starting fresh.")
                self.completed_rows = set()
                self.temp_slide_ids = {}
        else:
            logging.info("No existing checkpoint found. Starting new generation.")

    def save(self) -> None:
        """Save checkpoint to file."""
        try:
            os.makedirs(self.checkpoint_path.parent, exist_ok=True)
            data = {
                'completed_rows': sorted(list(self.completed_rows)),
                'temp_slide_ids': self.temp_slide_ids,
                'last_saved': datetime.now().isoformat(),
            }
            with open(self.checkpoint_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Failed to save checkpoint: {e}")

    def is_complete(self, row_index: int) -> bool:
        """Check if a row has already been processed."""
        return row_index in self.completed_rows

    def mark_complete(self, row_index: int, temp_slide_id: str = None) -> None:
        """Mark a row as complete and optionally track its temp slide ID."""
        self.completed_rows.add(row_index)
        if temp_slide_id:
            self.temp_slide_ids[str(row_index)] = temp_slide_id
        self.save()

    def get_temp_slide_id(self, row_index: int) -> str:
        """Get temp slide ID for a row, if tracked."""
        return self.temp_slide_ids.get(str(row_index))

    def clear(self) -> None:
        """Clear checkpoint (use with caution)."""
        self.completed_rows = set()
        self.temp_slide_ids = {}
        if self.checkpoint_path.exists():
            self.checkpoint_path.unlink()
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


def safe_filename(filename: str) -> str:
    """
    Remove or replace invalid filename characters.
    
    Args:
        filename: Original filename
        
    Returns:
        Safe filename
    """
    invalid_chars = r'[<>:"/\\|?*]'
    safe = __import__('re').sub(invalid_chars, '_', filename)
    safe = safe.strip('. ')
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
