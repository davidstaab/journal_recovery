import multiprocessing as mp
import tempfile
import typing as t
from datetime import datetime, timedelta
from functools import partial
from pathlib import Path
from shutil import copy
from time import sleep

import nltk
from common import Config as C
from common import (batch_iterdir, compare_to_rtf, cprintif, largest_file,
                    path_short_name, read_rtf)
from pathvalidate import sanitize_filename


def _sname(path: Path) -> str:
    """Return shortened name of path. Hard-coded to 30 characters."""
    return path_short_name(path, 30)


def _safe_make_dir(d: Path):
    try:
        d.mkdir(exist_ok=False)
    except FileExistsError:
        if not d.is_dir():
            # NB: copy/delete works across file systems per https://stackoverflow.com/a/42400063/2539684
            #   whereas shutil.move() doesn't.
            # Since this script runs in a docker container with mounted volumes, have to do copy/del.
            copy(str(d), str(d) + '.bak')
            d.unlink()
            d.mkdir()
            cprintif(f'Found something named {d.name} in {d.parent} and renamed it to {d.name}.bak', 'light_red')


def _print_file_count_msg() -> None:
    file_count = sum(1 for _ in C.SOURCE_DIR.iterdir() if _.is_file())
    cprintif(datetime.now().strftime("%A, %H:%M") + f': {file_count} files remaining', 'light_yellow')


def compare_and_assign(source_file: Path, mp_cfg_file: Path = None, dry_run: bool=False) -> Path:
    """Note: Specify config_file when running in multiprocessing mode."""
    
    if mp_cfg_file and mp_cfg_file.exists():
        C.load(mp_cfg_file)
    
    file_sname = _sname(source_file)
    
    try:
        source_text = read_rtf(source_file)
    except Exception as e:
        cprintif(f'  {file_sname} -> {_sname(C.UNREADABLE_DIR)} because {e}', 'light_red')
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
            cprintif(f'  {file_sname} match {calcs[0]["metric"]:.2f}% < {C.MATCH_RATIO_THRESHOLD}%', 'light_yellow')
        else:
            target_dir = calcs[0]["dir"]
            cprintif(f'  {file_sname} match: {calcs[0]["metric"]:.2f}% in {_sname(target_dir)}')
    
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
    cprintif(f'  {_sname(source_path)} -> {_sname(target_dir)}{_sname(new_file_path)}')
    return new_file_path


def run_multi(workers:int = 0) -> None:
    
    # if __name__ != '__main__':
    #     # Multiprocessing only works (in 'spawn' mode on MacOS) when running from the command line.
    #     raise Exception('This function should only be called when running from the command line.')
    
    for d in [C.SORTING_DIR, C.UNREADABLE_DIR]:
        _safe_make_dir(d)
    
    then = datetime.now()
    _print_file_count_msg()
    
    max_workers = mp.cpu_count() - 1  # Leave one behind to be polite to the OS
    if not 1 <= workers <= max_workers:
        workers = max_workers
    cprintif(f'Using {workers} workers', 'light_blue')
    
    with tempfile.NamedTemporaryFile('wb') as f:
        # Serialize config object to file so that subprocesses can access it.
        config_file = C.dump(f)
        
        with mp.Pool(processes=workers) as pool:
            for batch in batch_iterdir(C.SOURCE_DIR, count=workers):
                now = datetime.now()
                if now - then > timedelta(minutes=5):
                    _print_file_count_msg()
                    then = now
                
                cprintif('Working on\n  ' + '\n  '.join([_sname(b) for b in batch]), 'light_blue')
                pool.map(partial(compare_and_assign, mp_cfg_file=config_file), batch)


def run_single(dry_run: bool=False) -> None:
    
    for d in [C.SORTING_DIR, C.UNREADABLE_DIR]:
        _safe_make_dir(d)
    
    then = datetime.now()
    _print_file_count_msg()
    
    cprintif(f'Using 1 worker', 'light_yellow')
    
    for file in C.SOURCE_DIR.iterdir():
        now = datetime.now()
        if now - then > timedelta(minutes=5):
            _print_file_count_msg()
            then = now
        
        cprintif(f'Working on {_sname(file)}', 'light_blue')
        compare_and_assign(file, dry_run=dry_run)


if __name__ == '__main__':
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

    while True:
        try:
            file_count = sum(1 for _ in C.SOURCE_DIR.iterdir() if _.is_file())
        except FileNotFoundError:
            file_count = 0
                
        if not file_count:
            _print_file_count_msg()
            sleep(60)
            continue

        # run_single(dry_run=False)
        run_multi()
