import multiprocessing as mp
from pathlib import Path
from shutil import copy
from time import sleep

import nltk
from pathvalidate import sanitize_filename

from striprtf.striprtf.striprtf.striprtf import rtf_to_text

"""
NOTE: Going to have to process this job in a multi-pass. Do the initial binnning with this script, then take the largest
 in each folder and put them all together to do it again with a higher MATCH_RATIO_THRESHOLD to accommodate mistakes.
"""

APP_DIR = Path(__file__).parent.parent.resolve()
SOURCE_DIR = Path.joinpath(APP_DIR.parent, "files")
SORTING_DIR = Path.joinpath(APP_DIR.parent, "sorted")
UNREADABLE_DIR = Path.joinpath(SORTING_DIR, "unreadable")
UNSAVEABLE_DIR = Path.joinpath(SORTING_DIR, "unsaveable")
MATCH_RATIO_THRESHOLD = 70


def yield_file_batch(base_dir: Path, batch_size: int) -> list[Path]:
    batch = []
    for i in base_dir.iterdir():
        item_path = base_dir / i
        
        if item_path.is_file():
            batch.append(item_path)
        
        if len(batch) >= batch_size:
            break
    
    yield batch


def biggest_file(base_dir: Path) -> Path:
    files = [
        {
            "size": (base_dir / i).stat().st_size,
            "file": base_dir / i,
        }
        for i in base_dir.iterdir()
        if i.is_file()
    ]
    return None if not files else sorted(files, key=lambda _: _["size"], reverse=True)[0]["file"]


def yield_dirs(base_dir: Path) -> Path:
    for dir_item in base_dir.iterdir():
        if dir_item.is_dir() and dir_item not in [UNREADABLE_DIR, UNSAVEABLE_DIR]:
            yield dir_item


def pseudo_jaccard_similarity(label1: set, label2: set) -> float:
    """
    NLTK's jaccard distance (correctly) returns % of all tokens that match. I need ratio of matching
    tokens to size of shorter string.
    """
    if len(label1) and len(label2):  # prevent ZeroDivisionError
        return len(label1.intersection(label2)) / min(len(label1), len(label2))
    
    return 0


def new_sorting_folder(name: str) -> Path:
    return Path.joinpath(SORTING_DIR, sanitize_filename(name))


def compare_and_assign(source_path: Path, dry_run: bool=False) -> Path:
    source_name = source_path.name
    
    with open(source_path) as f:
        try:
            source_text = rtf_to_text(f.read(), errors="ignore")
        except Exception as e:
            print(f'  Moving {source_name} to "unreadable" folder because {e}')
            copy(source_path, UNREADABLE_DIR.joinpath(source_name))
            source_path.unlink()
            return ''
    
    calcs = compare_to_sorted(SORTING_DIR, source_text)
    
    if not calcs:
        target_dir = new_sorting_folder(source_text[:25])
        print(f'  No similarities were calculated for {source_name}.')
    else:
        calcs.sort(reverse=True, key=lambda _: _["metric"])
    
        if calcs[0]["metric"] < MATCH_RATIO_THRESHOLD:
            target_dir = new_sorting_folder(source_text[:25])
            print(f'  {source_name} could not be matched. Best similarity: {calcs[0]["metric"]:.2f}')
        else:
            target_dir = calcs[0]["dir"]
            print(f'  {source_name} best match: similarity {calcs[0]["metric"]:.2f} at {calcs[0]["dir"]}')
    
    if not dry_run:
        # Use first 100 characters of text as filename stem.
        new_file_path = move_and_rename(source_path, source_text[:100], target_dir)
    
    return new_file_path


def move_and_rename(source_path: Path, new_stem: str, target_dir: Path) -> Path:
    source_name = source_path.name
    
    target_dir.mkdir(exist_ok=True)
    
    # When saving, sanitize stem, add a unique index + ".rtf".
    new_fname = "".join([sanitize_filename(new_stem), f' {len(list(target_dir.iterdir()))}', ".rtf"])
    new_file_path = target_dir / new_fname

    try:
        copy(source_path, new_file_path)
        source_path.unlink()
        print(f'  Saved {source_name} as {new_file_path}')
    except OSError as e:
        print(f'  Could not save {source_name} to {new_file_path} because {e}. Moving it to "unsaveable" folder.')
        copy(source_path, Path(UNSAVEABLE_DIR) / source_name)
        source_path.unlink()
    return new_file_path


def compare_to_sorted(sorting_dir: Path, source_text: str) -> list[tuple[int, Path]]:
    """Compare to the largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}."""
    
    source_tokens = set(nltk.word_tokenize(source_text))
    calcs = []
    for dir_path in yield_dirs(sorting_dir):
        comp_path = biggest_file(dir_path)

        try:
            calcs.append(compare_to_file(source_tokens, dir_path, comp_path))
        except (NameError, FileNotFoundError):  # comp_path wasn't defined
            pass
        except UnicodeDecodeError as e:  # somehow comp_path has invalid RTF encoding
            print(f'  Moving {comp_path} to "unreadable" folder because {e}')
            copy(comp_path, UNREADABLE_DIR.joinpath(comp_path.name))
            comp_path.unlink()
            
        return calcs

def compare_to_file(tokens: set, dir_path: Path, file: Path) -> dict[float, Path]:
    with open(file) as f:
        # Read 500 characters for a sanity check. If it passes, read the whole thing.
        try:
            comp_text = rtf_to_text(f.read(500), errors="ignore")
            comp_tokens = set(nltk.word_tokenize(comp_text))
            similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
        except Exception:
            # Chopping an RTF file at a fixed offset can cause parsing errors. If so, just read the whole thing.
            similarity = 100 # To pass the next check
        
        if similarity >= MATCH_RATIO_THRESHOLD:
            comp_text = rtf_to_text(f.read(), errors="ignore")
            comp_tokens = set(nltk.word_tokenize(comp_text))
            similarity = 100 * pseudo_jaccard_similarity(tokens, comp_tokens)
                
    return {"metric": similarity, "dir": dir_path}


def run_multi(n: int=-1):
    worker_count = mp.cpu_count() - 1  # Leave one behind to be polite to the OS
    print(f'Starting with {worker_count} workers')
    with mp.Pool(processes=worker_count) as pool:
        if n >= 0:
            for _ in range(n):
                for batch in yield_file_batch(SOURCE_DIR, batch_size=worker_count):
                    print('Working on\n' + '\n'.join([str(_) for _ in batch]))
                    pool.map(compare_and_assign, batch)             
        else:
            while len(list(SOURCE_DIR.iterdir())):
                for batch in yield_file_batch(SOURCE_DIR, batch_size=worker_count):
                    print('Working on\n' + '\n'.join([str(_) for _ in batch]))
                    pool.map(compare_and_assign, batch)


def run_single(n: int=-1, dry_run: bool=False):
    if n >= 0:
        for _ in range(n):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
                print(f'Working on {str(batch[0])}...')
                compare_and_assign(batch[0], dry_run)
    else:
        while len(list(SOURCE_DIR.iterdir())):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
                print(f'Working on {str(batch[0])}...')
                compare_and_assign(batch[0], dry_run)
        

if __name__ == '__main__':  # Need this for mp to work!
    print('----------------------')
    nltk.download('punkt')  # Needed by nltk
    print(f'Application directory: {APP_DIR}\n' + \
          f'Looking for files in {SOURCE_DIR}\n' + \
          f'Sorting files into {SORTING_DIR}\n' + \
          f'----------------------')
    for d in [SORTING_DIR, UNREADABLE_DIR, UNSAVEABLE_DIR]:
        try:
            d.mkdir()
        except FileExistsError:
            if not d.is_dir():
                # NB: copy/delete works across file systems per https://stackoverflow.com/a/42400063/2539684
                #   whereas shutil.move() doesn't.
                # Since this script runs in a docker container with mounted volumes, have to do copy/del.
                copy(str(d), str(d) + '.bak')
                d.unlink()
                d.mkdir()

    while True:
        try:
            # Count files in SOURCE_DIR.
            i = 0
            for j, _ in enumerate(SOURCE_DIR.iterdir()):
                i = j + 1
            print(f'{i} files remaining in {SOURCE_DIR}')
        except (FileNotFoundError):
            pass
        
        if 0 == i:
            sleep(10)
            continue

        # compare_and_assign('./.files/File Name Lost (5469).rtf')  # Do one specific file
        # run_single(n=-1, dry_run=False)
        run_multi(n=min(i, 20))
