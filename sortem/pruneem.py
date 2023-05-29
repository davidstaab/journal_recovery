from pathlib import Path
from shutil import copy

import nltk
from common import Config as C
from common import compare_to_rtf, largest_file, read_rtf, path_short_name, cprintif


def sname(path: Path) -> str:
    """Return shortened name of path. Hard-coded to 30 characters."""
    return path_short_name(path, 30)


def check_dir_for_one_file(dir: Path) -> bool:
    """Return True if dir contains only one file."""
    return len([f for f in dir.iterdir() if f.is_file()]) == 1


def sanity_check() -> list[Path]:
    """Return paths that don't have only one file in them."""
    ret = []
    for subdir in C.SORTING_DIR.iterdir():
        if subdir.is_dir() and not subdir == C.UNREADABLE_DIR and not check_dir_for_one_file(subdir):
            ret.append(subdir)
    return ret


if __name__ == '__main__':
    
    C.set_app_dir(Path(__file__).parent.parent.resolve())
    C.set_match_ratio_threshold(90)
    C.set_run_quiet(False)
    nltk.download('punkt', quiet=True)  # Needed by nltk
    
    opening_msgs = [
        '----------------------',
        f'Application directory: {C.APP_DIR}',
        f'Looking for files in subdirs of {C.SORTING_DIR}',
        f'Match threshold: {C.MATCH_RATIO_THRESHOLD}%',
        f'----------------------',
    ]
    
    cprintif('\n'.join(opening_msgs))
    ignores = [C.UNREADABLE_DIR]
    for subdir in C.SORTING_DIR.iterdir():
    
        if subdir.is_dir() and subdir not in ignores:
            cprintif(f'Working in {sname(subdir)}', 'light_blue')
            # Compare to the largest file on disk because sortem does.
            largest = largest_file(subdir)

            for file in subdir.iterdir():
                
                if file.is_file() and file != largest:
                    source_tokens = set(nltk.word_tokenize(read_rtf(file)))
                    match = compare_to_rtf(source_tokens, largest)
                    
                    if  match >= C.MATCH_RATIO_THRESHOLD:
                        cprintif(f'  {sname(file)} match {match:.2f}% -> Deleted.', 'light_yellow')
                        file.unlink()
                    else:
                        cprintif(f'  {sname(file)} match {match:.2f}% -> Returned to /{C.SOURCE_DIR.stem}')
                        copy(file, C.SOURCE_DIR / file.name)
                        file.unlink()
    
    cprintif('----------------------')
    cprintif('Deleting empty subdirs')                        
    for subdir in C.SORTING_DIR.iterdir():
        if subdir.is_dir() and subdir not in ignores:
            if not len([i for i in subdir.iterdir()]):  # If empty
                cprintif(f'  Deleting /{sname(subdir)}', 'light_yellow')
                subdir.rmdir()
                
    failed_dirs = sanity_check()
    if len(failed_dirs):
        cprintif('----------------------', 'light_red')
        cprintif('Directories with more than one file remaining:\n', 'light_red')
        cprintif('\n'.join([f'  {d.stem}' for d in failed_dirs]), 'light_red')
