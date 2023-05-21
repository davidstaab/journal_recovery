import multiprocessing as mp
import typing as t
from pathlib import Path
from shutil import copy
from time import sleep

import nltk
from pathvalidate import sanitize_filename

from common import Constants as C
from common import (compare_to_rtf, exists, largest_file, move_and_rename,
                     read_rtf, yield_file_batch)


def compare_and_assign(source_file: Path, dry_run: bool=False) -> Path:
    source_text = read_rtf(source_file, handle_unreadable=True)
    
    calcs = compare_to_sorted(source_text, C.SORTING_DIR)
    
    if not calcs:
        target_dir = C.SORTING_DIR / sanitize_filename(source_text[:25])
        print(f'  No similarities were calculated for {source_file.name}.')
    else:
        calcs.sort(reverse=True, key=lambda _: _["metric"])
    
        if calcs[0]["metric"] < C.MATCH_RATIO_THRESHOLD:
            target_dir = C.SORTING_DIR / sanitize_filename(source_text[:25])
            print(f'  {source_file.name} could not be matched. Best similarity: {calcs[0]["metric"]:.2f}')
        else:
            target_dir = calcs[0]["dir"]
            print(f'  {source_file.name} best match: similarity {calcs[0]["metric"]:.2f} at {calcs[0]["dir"]}')
    
    if not dry_run:
        # Use first 100 characters of text as filename stem.
        new_file_path = move_and_rename(source_file, source_text[:100], target_dir)
    
    return new_file_path


def compare_to_sorted(text: str, sorted_dir: Path) -> list[dict[float, Path]]:
    """Compare to the largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}."""
    
    source_tokens = set(nltk.word_tokenize(text))

    ignores = [i for i in [C.UNREADABLE_DIR, C.UNSAVEABLE_DIR] if exists(i)]    
    calcs = []
    for subdir in sorted_dir.iterdir():
        
        if subdir.is_dir() and subdir not in ignores:
            comp_file = largest_file(subdir)

            if comp_file:
                calcs.append({"metric": compare_to_rtf(source_tokens, comp_file), "dir": subdir})
            
    return calcs


def run_multi(n: int=-1):
    worker_count = mp.cpu_count() - 1  # Leave one behind to be polite to the OS
    print(f'Starting with {worker_count} workers')
    with mp.Pool(processes=worker_count) as pool:
        if n >= 0:
            for _ in range(n):
                for batch in yield_file_batch(C.SOURCE_DIR, count=worker_count):
                    print('Working on\n' + '\n'.join([str(_) for _ in batch]))
                    pool.map(compare_and_assign, batch)             
        else:
            while len(list(C.SOURCE_DIR.iterdir())):
                for batch in yield_file_batch(C.SOURCE_DIR, count=worker_count):
                    print('Working on\n' + '\n'.join([str(_) for _ in batch]))
                    pool.map(compare_and_assign, batch)


def run_single(n: int=-1, dry_run: bool=False):
    if n >= 0:
        for _ in range(n):
            for batch in yield_file_batch(C.SOURCE_DIR, count=1):
                print(f'Working on {str(batch[0])}...')
                compare_and_assign(batch[0], dry_run)
    else:
        while len(list(C.SOURCE_DIR.iterdir())):
            for batch in yield_file_batch(C.SOURCE_DIR, count=1):
                print(f'Working on {str(batch[0])}...')
                compare_and_assign(batch[0], dry_run)
        

if __name__ == '__main__':  # Need this for mp to work!
    
    C.set_app_dir(Path(__file__).parent.parent.resolve())
    C.set_match_ratio_threshold(70)
    nltk.download('punkt', quiet=True)  # Needed by nltk
    
    print('----------------------')
    print(f'Application directory: {C.APP_DIR}\n' + \
          f'Looking for files in {C.SOURCE_DIR}\n' + \
          f'Sorting files into {C.SORTING_DIR}\n' + \
          f'----------------------')
    for d in [C.SORTING_DIR, C.UNREADABLE_DIR, C.UNSAVEABLE_DIR]:
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
            for j, _ in enumerate(C.SOURCE_DIR.iterdir()):
                i = j + 1
            print(f'{i} files remaining in {C.SOURCE_DIR}')
        except FileNotFoundError:
            pass
        
        if 0 == i:
            sleep(10)
            continue

        # compare_and_assign('./.files/File Name Lost (5469).rtf')  # Do one specific file
        # run_single(n=-1, dry_run=False)
        run_multi(n=min(i, 20))
