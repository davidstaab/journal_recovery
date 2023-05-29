from pathlib import Path
from shutil import copy

import nltk
from common import Config as C
from common import compare_to_rtf, largest_file, read_rtf, path_short_name, filtprint

SNAME_LEN = 25  # Length of shortened names, for console output


def check_dir_for_one_file(dir: Path) -> bool:
    """Return True if dir contains only one file."""
    return len([f for f in dir.iterdir() if f.is_file()]) == 1


def sanity_check() -> bool:
    """Return True if sorting dir contains only subdirs with one file each."""
    for subdir in C.SORTING_DIR.iterdir():
        if subdir.is_dir() and not check_dir_for_one_file(subdir):
            return False
    return True


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
    
    filtprint('\n'.join(opening_msgs))
    ignores = [C.UNREADABLE_DIR]
    for subdir in C.SORTING_DIR.iterdir():
    
        if subdir.is_dir() and subdir not in ignores:
            filtprint(f'Working in /{path_short_name(subdir, SNAME_LEN)}')
            largest = largest_file(subdir)

            for file in subdir.iterdir():
                
                if file.is_file() and file != largest:
                    source_tokens = set(nltk.word_tokenize(read_rtf(file)))
                    match = compare_to_rtf(source_tokens, largest)
                    
                    if  match >= C.MATCH_RATIO_THRESHOLD:
                        filtprint(f'  Deleting {path_short_name(file, SNAME_LEN)} because it matched {match:.2f}%')
                        file.unlink()
                    else:
                        filtprint(f'  {path_short_name(file, SNAME_LEN)} matched only {match:.2f}%. ' + \
                            f'Moving it back to /{C.SOURCE_DIR.stem}')
                        copy(file, C.SOURCE_DIR / file.name)
                        file.unlink()
    
    filtprint('----------------------')
    filtprint('Deleting empty subdirs')                        
    for subdir in C.SORTING_DIR.iterdir():
        if subdir.is_dir() and subdir not in ignores:
            if not len([d for d in subdir.iterdir()]):  # If empty
                filtprint(f'  Deleting /{path_short_name(subdir, SNAME_LEN)}')
                subdir.rmdir()
                
    filtprint('----------------------')
    filtprint('Sanity check: ' + ('OK' if sanity_check() else 'FAILED'))
