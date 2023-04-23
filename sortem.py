import multiprocessing as mp
from os import listdir, mkdir, path, scandir #, getcwd
from pathlib import Path
from shutil import move #, copyfile, rmtree

from nltk import word_tokenize
# from nltk.metrics.distance import jaccard_distance
import nltkmodules
from pathvalidate import sanitize_filename

from striprtf.striprtf.striprtf.striprtf import rtf_to_text

"""
NOTE: Going to have to process this job in a multi-pass. Do the initial binnning with this script, then take the largest
 in each folder and put them all together to do it again with a higher MATCH_RATIO_THRESHOLD to accommodate mistakes.
"""

SOURCE_DIR = Path('.source_dir').read_text().strip()
SORTING_DIR = Path('.sorting_dir').read_text().strip()
UNREADABLE_DIR = path.join(SORTING_DIR, "unreadable")
UNSAVEABLE_DIR = path.join(SORTING_DIR, "unsaveable")
MATCH_RATIO_THRESHOLD = 70

for d in [SORTING_DIR, UNREADABLE_DIR, UNSAVEABLE_DIR]:
    try:
        mkdir(d)
    except FileExistsError:
        if path.isfile(d):
            move(d, d + '.bak')
            mkdir(d)

def yield_file_batch(base_dir: str, batch_size: int) -> list:
    batch = []
    for i in listdir(base_dir):
        item_path = path.join(base_dir, i)
        if path.isfile(item_path):
            batch.append(item_path)
        if len(batch) >= batch_size:
            break
    yield batch

def biggest_file(base_dir: str) -> str:
    files = [{"size": path.getsize(path.join(base_dir, i)), "file": path.join(base_dir, i)} for i in listdir(base_dir)]
    return sorted(files, key=lambda _: _["size"], reverse=True)[0]["file"] if len(files) else ''

def yield_dirs(base_dir: str) -> str:
    for dir_item in scandir(base_dir):
        if dir_item.is_dir():
            if dir_item.path not in [UNREADABLE_DIR, UNSAVEABLE_DIR]:
                yield dir_item.path

def pseudo_jaccard_similarity(label1: set, label2: set) -> int:
    """
    NLTK's jaccard distance (correctly) returns % of all tokens that match. I need ratio of matching
    tokens to size of shorter string.
    """
    if len(label1) and len(label2):  # prevent ZeroDivisionError
        return len(label1.intersection(label2)) / min(len(label1), len(label2))
    else:
        return 0

def make_new_folder(name: str) -> str:
    return path.join(SORTING_DIR, sanitize_filename(name))

def compare_and_assign(source_path: str, dry_run: bool=False) -> str:
    base_name = path.basename(source_path)
    
    with open(source_path) as f:
        try:
            source_text = rtf_to_text(f.read(), errors="ignore")
        except Exception as e:
            print(f'  Moving {base_name} to "unreadable" folder because {e}')
            move(source_path, path.join(UNREADABLE_DIR, base_name))
            return

    # Compare to the largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}.
    source_tokens = set(word_tokenize(source_text))
    calcs = []
    for dir_path in yield_dirs(SORTING_DIR):
        comp_path = biggest_file(dir_path)

        try:
            with open(comp_path) as c:
                comp_text = rtf_to_text(c.read(), errors="ignore")
                comp_tokens = set(word_tokenize(comp_text))
                # jaccard_dist = jaccard_distance(source_tokens, comp_tokens)
                # similarity = (1 - jaccard_dist) * 100
                similarity = 100 * pseudo_jaccard_similarity(source_tokens, comp_tokens)
                calcs.append({"metric": similarity, "dir": dir_path})
        except (NameError, FileNotFoundError):  # comp_path wasn't defined
            pass
        except UnicodeDecodeError as e:  # somehow comp_path has invalid RTF encoding
            print(f'  Moving {comp_path} to "unreadable" folder because {e}')
            move(comp_path, path.join(UNREADABLE_DIR, path.basename(comp_path)))
    
    if len(calcs):
        calcs.sort(reverse=True, key=lambda _: _["metric"])
        if calcs[0]["metric"] >= MATCH_RATIO_THRESHOLD:
            target_dir = calcs[0]["dir"]
            print(f'  {base_name} best match: similarity {calcs[0]["metric"]:.2f} at {calcs[0]["dir"]}')
        else:
            target_dir = make_new_folder(source_text[:25])
            print(f'  {base_name} could not be matched. Best similarity: {calcs[0]["metric"]:.2f}')
    else:
        target_dir = make_new_folder(source_text[:25])
        print(f'  No similarities were calculated for {base_name}.')
    
    if not dry_run:
        try:
            mkdir(target_dir)
        except FileExistsError:
            pass
    
        # When saving, rename it to the first 100 (sanitized) characters of its text + a unique index + ".rtf".
        new_fname = "".join([sanitize_filename(source_text[:100]), f' {len(listdir(target_dir))}', ".rtf"])
        new_file_path = path.join(target_dir, new_fname)

        try:
            move(source_path, new_file_path)
            print(f'  Saved {base_name} as {new_file_path}')
        except OSError as e:
            print(f'  Could not save {base_name} to {new_file_path} because {e}. Moving it to "unsaveable" folder.')
            move(source_path, path.join(UNSAVEABLE_DIR, base_name))
    
    return new_file_path

def run_multi(n: int=-1):
    worker_count = mp.cpu_count() - 2
    print(f'Starting with {worker_count} workers')
    with mp.Pool(processes=worker_count) as pool:
        if n >= 0:
            for _ in range(n):
                for batch in yield_file_batch(SOURCE_DIR, batch_size=worker_count):
                    print('Working on\n' + '\n'.join(batch))
                    pool.map(compare_and_assign, batch)             
        else:
            while len(listdir(SOURCE_DIR)):
                for batch in yield_file_batch(SOURCE_DIR, batch_size=worker_count):
                    print('Working on\n' + '\n'.join(batch))
                    pool.map(compare_and_assign, batch)

def run_single(n: int=-1, dry_run: bool=False):
    if n >= 0:
        for _ in range(n):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
                print(f'Working on {batch[0]}...')
                compare_and_assign(batch[0], dry_run)
    else:
        while len(listdir(SOURCE_DIR)):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
                print(f'Working on {batch[0]}...')
                compare_and_assign(batch[0], dry_run)
        

if __name__ == '__main__':  # Need this for mp to work!
    try:
        mkdir(SORTING_DIR)
    except FileExistsError:
        pass

    # compare_and_assign('./.files/File Name Lost (5469).rtf')  # Do one specific file
    # run_single(n=-1, dry_run=False)
    run_multi(n=1000)
    print('***** All Done! *****')