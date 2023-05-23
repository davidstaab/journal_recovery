from pathlib import Path
from shutil import copy

import nltk
from common import Config as C
from common import compare_to_rtf, largest_file, read_rtf, get_short_name, filtprint

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
            filtprint(f'Working in /{get_short_name(subdir, 40)}')
            largest = largest_file(subdir)
            source_tokens = set(nltk.word_tokenize(read_rtf(largest)))

            for file in subdir.iterdir():
                
                if file.is_file() and file != largest:
                    match = compare_to_rtf(source_tokens, file)
                    
                    if  match >= C.MATCH_RATIO_THRESHOLD:
                        filtprint(f'  Deleting {get_short_name(file, 25)} because it matched {match:.2f}%')
                        file.unlink()
                    else:
                        filtprint(f'  {get_short_name(file, 25)} matched only {match:.2f}%.' + \
                            f'Moving it back to /{C.SOURCE_DIR.stem}')
                        copy(file, C.SOURCE_DIR / file.name)
                        file.unlink()
                        
    for subdir in C.SORTING_DIR.iterdir():
        if subdir.is_dir() and subdir not in ignores:
            if not len([d for d in subdir.iterdir()]):  # If empty
                filtprint(f'Deleting empty subdir /{get_short_name(subdir, 40)}')
                subdir.rmdir()
