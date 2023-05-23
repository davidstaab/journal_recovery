import multiprocessing as mp
import typing as t
from pathlib import Path
from shutil import copy
from time import sleep

import nltk
from common import Config as C
from common import (compare_to_rtf, filtprint, get_short_name, largest_file,
                    read_rtf, yield_file_batch)
from pathvalidate import sanitize_filename


def compare_and_assign(source_file: Path, dry_run: bool=False) -> Path:
    short_name = get_short_name(source_file, 40)
    
    try:
        source_text = read_rtf(source_file)
    except Exception as e:
        filtprint(f'  Moving {short_name} to "unreadable" folder because {e}')
        new_file_path = C.UNREADABLE_DIR / source_file.name
        copy(source_file, new_file_path)
        source_file.unlink()
        return new_file_path

    calcs = compare_to_sorted(source_text, C.SORTING_DIR)
    
    if not calcs:
        target_dir = C.SORTING_DIR / sanitize_filename(source_text[:25])
        filtprint(f'  No similarities were calculated for {short_name}.')
    else:
        calcs.sort(reverse=True, key=lambda _: _["metric"])
    
        if calcs[0]["metric"] < C.MATCH_RATIO_THRESHOLD:
            target_dir = C.SORTING_DIR / sanitize_filename(source_text[:25])
            filtprint(f'  {short_name} could not be matched. Best match {calcs[0]["metric"]:.2f}')
        else:
            target_dir = calcs[0]["dir"]
            filtprint(f'  {short_name} best match: {calcs[0]["metric"]:.2f} at {get_short_name(target_dir, 25)}')
    
    if not dry_run:
        # Use first 100 characters of text as filename stem.
        new_file_path = move_to_sorted(source_file, source_text[:100], target_dir)
    
    return new_file_path


def compare_to_sorted(text: str, sorted_dir: Path) -> list[dict[float, Path]]:
    """Compare to the largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}."""
    
    source_tokens = set(nltk.word_tokenize(text))

    ignores = [C.UNREADABLE_DIR]
    calcs = []
    for subdir in sorted_dir.iterdir():
        
        if subdir.is_dir() and subdir not in ignores:
            comp_file = largest_file(subdir)

            if comp_file:
                metric = compare_to_rtf(source_tokens, comp_file)
                calcs.append({"metric": metric, "dir": subdir})

    return calcs


def move_to_sorted(source_path: Path, new_stem: str, target_dir: Path) -> Path:
    target_dir.mkdir(exist_ok=True)
    
    # When saving, sanitize stem, add a unique index + ".rtf".
    new_fname: str = "".join([sanitize_filename(new_stem), f' {len(list(target_dir.iterdir()))}', ".rtf"])
    new_file_path = target_dir / new_fname.strip()
    copy(source_path, new_file_path)
    source_path.unlink()
    filtprint(f'  Saved {get_short_name(source_path, 40)} as {get_short_name(new_file_path, 40)}')
    return new_file_path


def run_multi(n: int=-1):
    worker_count = mp.cpu_count() - 1  # Leave one behind to be polite to the OS
    filtprint(f'Starting with {worker_count} workers')
    with mp.Pool(processes=worker_count) as pool:
        if n >= 0:
            for _ in range(n):
                for batch in yield_file_batch(C.SOURCE_DIR, count=worker_count):
                    filtprint('Working on\n' + '\n'.join([get_short_name(b, 40) for b in batch]))
                    pool.map(compare_and_assign, batch)             
        else:
            while len(list(C.SOURCE_DIR.iterdir())):
                for batch in yield_file_batch(C.SOURCE_DIR, count=worker_count):
                    filtprint('Working on\n' + '\n'.join([get_short_name(b, 40) for b in batch]))
                    pool.map(compare_and_assign, batch)


def run_single(n: int=-1, dry_run: bool=False):
    if n >= 0:
        for _ in range(n):
            for batch in yield_file_batch(C.SOURCE_DIR, count=1):
                filtprint('Working on\n' + '\n'.join([get_short_name(b, 40) for b in batch]))
                compare_and_assign(batch[0], dry_run)
    else:
        while len(list(C.SOURCE_DIR.iterdir())):
            for batch in yield_file_batch(C.SOURCE_DIR, count=1):
                filtprint('Working on\n' + '\n'.join([get_short_name(b, 40) for b in batch]))
                compare_and_assign(batch[0], dry_run)
        

if __name__ == '__main__':  # Need this for mp to work!
    
    C.set_app_dir(Path(__file__).parent.parent.resolve())
    C.set_match_ratio_threshold(90)
    nltk.download('punkt', quiet=True)  # Needed by nltk
    
    opening_msgs = [
        '----------------------',
        f'Application directory: {C.APP_DIR}',
        f'Looking for files in {C.SOURCE_DIR}',
        f'Sorting files into {C.SORTING_DIR}\n',
        f'Match threshold: {C.MATCH_RATIO_THRESHOLD}%',
        f'----------------------',
    ]

    filtprint('\n'.join(opening_msgs))
    for d in [C.SORTING_DIR, C.UNREADABLE_DIR]:
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
        run_single(n=-1, dry_run=False)
        # run_multi(n=min(i, 20))
