import multiprocessing as mp
import typing as t
from pathlib import Path
from shutil import copy
from time import sleep
from datetime import datetime, timedelta

import nltk
from common import Config as C
from common import (compare_to_rtf, cprintif, path_short_name, largest_file,
                    read_rtf, batch_iterdir)
from pathvalidate import sanitize_filename


def sname(path: Path) -> str:
    """Return shortened name of path. Hard-coded to 30 characters."""
    return path_short_name(path, 30)


def compare_and_assign(source_file: Path, dry_run: bool=False) -> Path:
    file_sname = sname(source_file)
    
    try:
        source_text = read_rtf(source_file)
    except Exception as e:
        cprintif(f'  {file_sname} -> {sname(C.UNREADABLE_DIR)} because {e}', 'light_red')
        new_file_path = C.UNREADABLE_DIR / source_file.name
        copy(source_file, new_file_path)
        source_file.unlink()
        return new_file_path

    calcs = compare_to_sorted(source_text, C.SORTING_DIR)
    
    if not calcs:
        target_dir = C.SORTING_DIR / sanitize_filename(source_text[:C.DNAME_LEN])
        cprintif(f'  {file_sname}: No similarities were calculated!', 'light_red')
    else:
        calcs.sort(reverse=True, key=lambda _: _["metric"])
    
        if calcs[0]["metric"] < C.MATCH_RATIO_THRESHOLD:
            target_dir = C.SORTING_DIR / sanitize_filename(source_text[:C.DNAME_LEN])
            cprintif(f'  {file_sname} match {calcs[0]["metric"]:.2f}%', 'light_yellow')
        else:
            target_dir = calcs[0]["dir"]
            cprintif(f'  {file_sname} match: {calcs[0]["metric"]:.2f}% in {sname(target_dir)}')
    
    if not dry_run:
        # Use first 100 characters of text as filename stem.
        new_file_path = move_to_sorted(source_file, source_text[:C.FNAME_LEN], target_dir)
    
    return new_file_path


def compare_to_sorted(text: str, sorted_dir: Path) -> list[dict[float, Path]]:
    """Compare to the largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}."""
    
    source_tokens = set(nltk.word_tokenize(text))

    ignores = [C.UNREADABLE_DIR]
    calcs = []
    for subdir in sorted_dir.iterdir():
        
        if subdir.is_dir() and subdir not in ignores:
            # NB: Certain content, like embedded images, lives in the RTF tags and not the
            #   stripped text. So the largest file on disk could have the most content,
            #   rather than the longest stripped text.
            comp_file = largest_file(subdir)

            if comp_file:
                metric = compare_to_rtf(source_tokens, comp_file)
                calcs.append({"metric": metric, "dir": subdir})

    return calcs


def move_to_sorted(source_path: Path, new_stem: str, target_dir: Path) -> Path:
    target_dir.mkdir(exist_ok=True)
    
    # When saving, sanitize stem, add a unique index + ".rtf".
    new_fname: str = ''.join([sanitize_filename(new_stem), f' {len(list(target_dir.iterdir()))}', '.rtf'])
    new_file_path = target_dir / new_fname.strip()
    copy(source_path, new_file_path)
    source_path.unlink()
    cprintif(f'  {sname(source_path)} -> {sname(target_dir)}{sname(new_file_path)}')
    return new_file_path


def print_file_count_msg(now: datetime) -> None:
    file_count = sum(1 for _ in C.SOURCE_DIR.iterdir() if _.is_file())
    cprintif(now.strftime("%A, %H:%M") + f': {file_count} files remaining', 'light_yellow')


def run_multi() -> None:
    # TODO Remove this when I've fixed the problem with mp and Config
    cprintif(f'WARNING: Using hard-coded match threshold {C.MATCH_RATIO_THRESHOLD}%', 'light_red')
    
    then = datetime.now()
    print_file_count_msg(then)
    
    worker_count = mp.cpu_count() - 1  # Leave one behind to be polite to the OS
    cprintif(f'Using {worker_count} workers', 'light_yellow')
    
    with mp.Pool(processes=worker_count) as pool:
        for batch in batch_iterdir(C.SOURCE_DIR, count=worker_count):
            now = datetime.now()
            if now - then > timedelta(minutes=5):
                print_file_count_msg(now)
                then = now
            
            cprintif('Working on\n  ' + '\n  '.join([sname(b) for b in batch]), 'light_blue')
            pool.map(compare_and_assign, batch)             


def run_single(dry_run: bool=False) -> None:
    then = datetime.now()
    print_file_count_msg(then)
    
    cprintif(f'Using 1 worker', 'light_yellow')
    
    for file in C.SOURCE_DIR.iterdir():
        now = datetime.now()
        if now - then > timedelta(minutes=5):
            print_file_count_msg(now)
            then = now
        
        cprintif(f'Working on {sname(file)}', 'light_blue')
        compare_and_assign(file, dry_run)


if __name__ == '__main__':  # Need this for mp to work!
    
    # This only works in single processing.
    # TODO Learn how to get subprocesses to inherit my Config settings.
    C.set_app_dir(Path(__file__).parent.parent.resolve())
    C.set_match_ratio_threshold(90)    
    C.set_run_quiet(False)
    
    nltk.download('punkt', quiet=True)  # Needed by nltk
    
    opening_msgs = [
        '----------------------',
        f'Application directory: {C.APP_DIR}',
        f'Looking for files in {C.SOURCE_DIR}',
        f'Sorting files into {C.SORTING_DIR}',
        f'Match threshold: {C.MATCH_RATIO_THRESHOLD}%',
        f'----------------------',
    ]

    cprintif('\n'.join(opening_msgs))
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
            file_count = sum(1 for _ in C.SOURCE_DIR.iterdir() if _.is_file())
        except FileNotFoundError:
            file_count = 0
                
        if not file_count:
            print_file_count_msg(datetime.now())
            sleep(60)
            continue

        # run_single(dry_run=False)
        run_multi()
