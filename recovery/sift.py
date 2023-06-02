from pathlib import Path
from shutil import copy

import nltk
import prune as P
import sort as S
from common import Config as C
from common import cprintif


def count_files(dir: Path) -> int:
    if dir.is_dir():
        try:
            return sum(1 for _ in dir.iterdir() if _.is_file())
        except FileNotFoundError:
            return 0
    raise ValueError(f'{dir} is not a directory.')


def sort(mp:bool = True) -> int:
    file_count = count_files(C.SOURCE_DIR)
    cprintif('----------------------', 'light_blue')
    cprintif(f'Sorting {file_count} files...', 'light_blue')
    
    if mp:
        S.run_multi()
    else:
        S.run_single()
        
    return file_count


def prune() -> bool:
    cprintif('----------------------', 'light_blue')
    cprintif('Pruning similar files')
    pruned = P.prune_similar_files()
    cprintif(f'{pruned} files removed.', 'light_yellow')

    cprintif('----------------------')
    cprintif('Removing empty sorting dirs')
    P.remove_empty_sorting_dirs()                      

                
    failed_dirs = P.sanity_check()
    if len(failed_dirs):
        cprintif('----------------------', 'light_red')
        cprintif('Directories with more than one file remaining:\n', 'light_red')
        cprintif('\n'.join([f'  {d.stem}' for d in failed_dirs]), 'light_red')
        
    return len(failed_dirs) == 0


def unsort() -> None:
    cprintif('----------------------', 'light_blue')
    cprintif('Unsorting files...', 'light_blue')
    for item in C.SORTING_DIR.iterdir():
        if item.is_dir():
            for file in item.iterdir():
                if file.is_file():
                    copy(file, C.SOURCE_DIR / file.name)
                    file.unlink()
            item.rmdir()
        elif item.is_file():
            copy(item, C.SOURCE_DIR / item.name)
            item.unlink()


if __name__ == '__main__':
    C.set_app_dir(Path(__file__).parent.parent.resolve())  
    C.set_run_quiet(False)
    nltk.download('punkt', quiet=True)  # Needed by nltk
    
    opening_msgs = [
        '----------------------',
        f'Application directory: {C.APP_DIR}',
        f'Unsorted files in {C.SOURCE_DIR}',
        f'Sorted files in {C.SORTING_DIR}',
    ]
    cprintif('\n'.join(opening_msgs), 'light_green')

    # Because prune is destructive, it should always run at a very high threshold.
	#   This will ensure it only destroys with maximum confidence.
    # Sort can be iteratively ratcheted up to meet the same threshold.
    max_thresh = 95
    for sort_thresh in range(70, max_thresh, 5):
        C.set_match_ratio_threshold(sort_thresh)
        cprintif(f'Sorting with threshold: {C.MATCH_RATIO_THRESHOLD}%', 'light_green')
        
        # Sort/Prune until they keep shuffling the same files back and forth
        prev_count = count_files(C.SOURCE_DIR)
        while True:
            sort()
            C.set_match_ratio_threshold(max_thresh)
            if not prune():
                # Sanity check failed
                exit(1)
            unsorted_count = count_files(C.SOURCE_DIR)
            if unsorted_count >= prev_count or unsorted_count == 0:
                break
            prev_count = unsorted_count
        
        if unsorted_count:
            cprintif(f'{unsorted_count} files could not be sorted.', 'light_red')
        else:
            cprintif('All files sorted.', 'light_green')
        
        unsort()
            