import functools
import inspect
import re
import typing as t
from pathlib import Path

import nltk
from striprtf.striprtf.striprtf.striprtf import rtf_to_text
from termcolor import cprint


class Config():
    # Defaults
    APP_DIR = Path(__file__).parent.parent.resolve()
    SOURCE_DIR = APP_DIR.parent / "files"
    SORTING_DIR = APP_DIR.parent / "sorted"
    UNREADABLE_DIR = SORTING_DIR / "unreadable"
    MATCH_RATIO_THRESHOLD = 90
    RUN_QUIET = False
    FNAME_LEN = 40
    # More important that this be a high number than FNAME_LEN
    #  to prevent sorting distinct files into the same directory.
    DNAME_LEN = 100
    
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
    def set_run_quiet(cls, quiet: bool = True) -> None:
        cls.RUN_QUIET = quiet


def _conditional_print(func) -> callable:
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if not Config.RUN_QUIET:
            return func(*args, **kwargs)
    wrapper.__signature__ = inspect.signature(func)
    return wrapper


@_conditional_print
def cprintif(*args, **kwargs) -> None:
    cprint(*args, **kwargs)
  

def path_short_name(path: Path, max_len: int) -> str:
    """Shorten a file name or directory stem to max_len characters. Used for printouts."""
        
    head_len = 4  # Arbitrary
    tail_len = 7  # To accommodate " ###.ext"
    placeholder = '...'
    
    if max_len <= head_len + tail_len + len(placeholder):
        raise ValueError(f"max_len ({max_len}) must be > {head_len + tail_len + len(placeholder)}")
    
    # Capture trailing substrings like " 123.rtf" or ".rtf"
    pattern = re.compile(r'((?:\s\d{1,3})\.rtf)$')
    
    if path.is_dir():
        name = path.stem + '/'
        tail = name[-tail_len:]
        name_wo_tail = name[:-tail_len]
    else:
        name = path.name
        match = pattern.search(name)
        tail = match.group(0) if match else name[-tail_len:]
        name_wo_tail = name[:match.start()] if match else name[:-tail_len]

        
    if len(name_wo_tail) + len(tail) > max_len:
        body_len = max_len - head_len - len(placeholder) - len(tail)
        return name_wo_tail[:head_len + body_len] + placeholder + tail

    return name


def batch_iterdir(dir: Path, count: int) -> t.Generator[list[Path], None, None]:
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
