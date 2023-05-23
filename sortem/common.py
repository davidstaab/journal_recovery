import typing as t
from pathlib import Path

import nltk
from striprtf.striprtf.striprtf.striprtf import rtf_to_text


class Config():
    # Defaults
    APP_DIR = Path(__file__).parent.parent.resolve()
    SOURCE_DIR = APP_DIR.parent / "files"
    SORTING_DIR = APP_DIR.parent / "sorted"
    UNREADABLE_DIR = SORTING_DIR / "unreadable"
    MATCH_RATIO_THRESHOLD = 70
    RUN_QUIET = False
    
    @classmethod
    def set_app_dir(cls, path: Path) -> None:
        cls.APP_DIR = path
        cls.SOURCE_DIR = cls.APP_DIR.parent / "files"
        cls.SORTING_DIR = cls.APP_DIR.parent / "sorted"
        cls.UNREADABLE_DIR = cls.SORTING_DIR / "unreadable"
        
    @classmethod
    def set_match_ratio_threshold(cls, threshold: int) -> None:
        cls.MATCH_RATIO_THRESHOLD = threshold
        
    @classmethod
    def set_run_quiet(cls, quiet: bool) -> None:
        cls.RUN_QUIET = quiet


def filtprint(*args, **kwargs) -> None:
    if not Config.RUN_QUIET:
        print(*args, **kwargs)
  

import re
from pathlib import Path

def get_short_name(path: Path, max_len: int) -> str:
    """Shorten a file or directory name to max_len characters. Used for printouts."""

    if max_len < 3:
        raise ValueError("max_len must be at least 3")
        
    preserved_start_chars = 4
    if preserved_start_chars >= max_len:
        raise ValueError(f"preserved_start_chars ({preserved_start_chars}) must be less than max_len ({max_len})")
    
    # Regex pattern to capture trailing substrings for file names
    pattern = re.compile(r'((?:\s\d+)?\..+)?$')
    
    if path.is_file():
        match = pattern.search(path.name)
        captured = match.group(0) if match else ""
        name_without_captured = path.name[:match.start()] if match else path.name
        
        # subtract 3 for "..." and length of captured
        if len(name_without_captured) + len(captured) > max_len:
            return name_without_captured[:preserved_start_chars] + "..." + name_without_captured[-(max_len - preserved_start_chars - len(captured) - 3)] + captured
        else:
            return path.name
    else:
        # For directory, only consider the stem
        stem = path.stem
        if len(stem) > max_len:
            return stem[:preserved_start_chars] + "..." + stem[-(max_len - preserved_start_chars - 3):]
        else:
            return stem



def yield_file_batch(dir: Path, count: int) -> t.Generator[list[Path], None, None]:
    batch = [f for f in dir.iterdir() if f.is_file()][:count]
    while batch:
        yield batch
        batch = [f for f in dir.iterdir() if f not in batch and f.is_file()][:count]


def largest_file(dir: Path) -> t.Optional[Path]:
    files = [p for p in dir.iterdir() if p.is_file()]
    return max(files, key=lambda x: x.stat().st_size, default=None)


def pseudo_jaccard_similarity(label1: set, label2: set) -> float:
    """
    NLTK's jaccard distance (correctly) returns % of all tokens that match. I need ratio of matching
    tokens to size of shorter string.
    """
    if len(label1) and len(label2):  # prevent ZeroDivisionError
        return len(label1.intersection(label2)) / min(len(label1), len(label2))
    
    return 0


def read_rtf(file: Path, length: int = -1, ignore_unreadable: bool = False) -> str:
    with open(file) as f:
        try:
            # NB: 'errors' arg is the same as bytes.decode()
            # See here for possible values: https://docs.python.org/3.10/library/codecs.html#error-handlers
            text = rtf_to_text(f.read(length), errors="ignore")
        except UnicodeDecodeError as e:
            
            if not ignore_unreadable:
                raise
            
            return ''
    
    return text


def compare_to_rtf(tokens: set, file: Path) -> float:
    # Read 500 characters for a sanity check. If it passes, read the whole thing.
    try:
        comp_text = read_rtf(file, length=500, ignore_unreadable=True)
        
        if comp_text:
            comp_tokens = set(nltk.word_tokenize(comp_text))
            similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
        else:
            # probably a false negative. All 500 chars could be RTF markup.
            similarity = 0

    except Exception:
        # Chopping an RTF file at a fixed offset can cause parsing errors.
        #   If so, just read the whole thing.
        similarity = 0
    
    if similarity >= Config.MATCH_RATIO_THRESHOLD or similarity == 0:
        comp_text = read_rtf(file)
        comp_tokens = set(nltk.word_tokenize(comp_text))
        similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
                
    return similarity
