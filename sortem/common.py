import typing as t
from pathlib import Path
from shutil import copy

import nltk
from pathvalidate import sanitize_filename
from striprtf.striprtf.striprtf.striprtf import rtf_to_text


class Constants():
    # Defaults
    APP_DIR = Path(__file__).parent.parent.resolve()
    SOURCE_DIR = APP_DIR.parent / "files"
    SORTING_DIR = APP_DIR.parent / "sorted"
    UNREADABLE_DIR = SORTING_DIR / "unreadable"
    UNSAVEABLE_DIR = SORTING_DIR / "unsaveable"
    MATCH_RATIO_THRESHOLD = 70
    
    @classmethod
    def set_app_dir(cls, path: Path) -> None:
        cls.APP_DIR = path
        cls.SOURCE_DIR = cls.APP_DIR.parent / "files"
        cls.SORTING_DIR = cls.APP_DIR.parent / "sorted"
        cls.UNREADABLE_DIR = cls.SORTING_DIR / "unreadable"
        cls.UNSAVEABLE_DIR = cls.SORTING_DIR / "unsaveable"
        
    @classmethod
    def set_match_ratio_threshold(cls, threshold: int) -> None:
        cls.MATCH_RATIO_THRESHOLD = threshold


def exists(var:any) -> bool:
    try:
        var
    except NameError:
        return False
    else:
        return True
  
    
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


def move_and_rename(source_path: Path, new_stem: str, target_dir: Path) -> Path:
    target_dir.mkdir(exist_ok=True)
    
    # When saving, sanitize stem, add a unique index + ".rtf".
    new_fname = "".join([sanitize_filename(new_stem), f' {len(list(target_dir.iterdir()))}', ".rtf"])
    new_file_path = target_dir / new_fname

    try:
        copy(source_path, new_file_path)
    except OSError as e:
        
        if not exists(Constants.UNSAVEABLE_DIR):
            raise
              
        print(f'  Could not save {source_path.name} to {new_file_path} because {e}. Moving it to "unsaveable" folder.')
        try:
            new_file_path = Constants.UNSAVEABLE_DIR / source_path.name
            copy(source_path, new_file_path)
        except Exception:
            print(f"  Couldn't do that either. Leaving {source_path.name} where it is.")
            return source_path
        
    else:
        print(f'  Saved {source_path.name} as {new_file_path}')
        source_path.unlink()
        return new_file_path


def read_rtf(file: Path, handle_unreadable: bool) -> str:
    with open(file) as f:
        try:
            text = rtf_to_text(f.read(), errors="ignore")
        except Exception as e:
            
            if not handle_unreadable:
                raise
            
            if not exists(Constants.UNREADABLE_DIR):
                raise
            
            print(f'  Moving {file.name} to "unreadable" folder because {e}')
            copy(file, Constants.UNREADABLE_DIR / file.name)
            file.unlink()
            text = ''
        
        return text


def compare_to_rtf(tokens: set, file: Path) -> float:
    with open(file) as f:
        # Read 500 characters for a sanity check. If it passes, read the whole thing.
        try:
            comp_text = read_rtf(f.read(500), handle_unreadable=False)
            comp_tokens = set(nltk.word_tokenize(comp_text))
            similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
        except Exception:
            # Chopping an RTF file at a fixed offset can cause parsing errors. If so, just read the whole thing.
            similarity = 100 # To pass the next check
        
        if similarity >= Constants.MATCH_RATIO_THRESHOLD:
            f.seek(0)
            comp_text = read_rtf(f.read(500), handle_unreadable=True)
            comp_tokens = set(nltk.word_tokenize(comp_text))
            similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
                
    return similarity
