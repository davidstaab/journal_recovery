import multiprocessing as mp
from os import listdir, mkdir, path, scandir #, getcwd
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

SOURCE_DIR = "./.files"
SORTING_DIR = "./.sorted"
MATCH_RATIO_THRESHOLD = 70

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
    return sorted(files, key=lambda _: _["size"], reverse=True)[0]["file"]

def yield_dirs(base_dir: str) -> str:
    for dir_item in scandir(base_dir):
        if dir_item.is_dir():
            yield dir_item.path

def pseudo_jaccard_similarity(label1: set, label2: set) -> int:
    """
    NLTK's jaccard distance (correctly) returns % of all tokens that match. I need ratio of matching
    tokens to size of shorter string.
    """
    return len(label1.intersection(label2)) / min(len(label1), len(label2))

def compare_and_assign(source_path: str, dry_run: bool=False) -> str:
    base_name = path.basename(source_path)

    with open(source_path) as f:
        try:
            source_text = rtf_to_text(f.read(), errors="ignore")
        except UnicodeDecodeError:
            print(f'Critical decoding error on {source_path}. Skipping...')
            move(source_path, path.join(SORTING_DIR, "unreadable"))
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
        except NameError:  # comp_path wasn't defined
            pass
    
    calcs.sort(reverse=True, key=lambda _: _["metric"])
    if calcs[0]["metric"] >= MATCH_RATIO_THRESHOLD:
        target_dir = calcs[0]["dir"]
        print(f'  {base_name} best match: similarity {calcs[0]["metric"]:.2f} at {calcs[0]["dir"]}')
    else:
        target_dir = path.join(SORTING_DIR, sanitize_filename(source_text[:25]))  # Make a new folder
        print(f'  {base_name} could not be matched. Best similarity: {calcs[0]["metric"]:.2f}')
    
    if not dry_run:
        try:
            mkdir(target_dir)
        except FileExistsError:
            pass

    # When saving, rename it to the first 100 (sanitized) characters of its text + a unique index + ".rtf".
    new_fname = "".join([sanitize_filename(source_text[:100]), f' {len(listdir(target_dir))}', ".rtf"])
    new_file_path = path.join(target_dir, new_fname)
    
    if not dry_run:
        move(source_path, new_file_path)
    
    print(f'  Saved {base_name} as {new_file_path}')
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
                print('Working on\n' + '\n'.join(batch))
                compare_and_assign(batch[0], dry_run)
    else:
        while len(listdir(SOURCE_DIR)):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
                print('Working on\n' + '\n'.join(batch))
                compare_and_assign(batch[0], dry_run)
        

if __name__ == '__main__':  # Need this for mp to work!
    try:
        mkdir(SORTING_DIR)
    except FileExistsError:
        pass

    # run_multi(n=100)
    run_single(n=10, dry_run=False)
    
    print('***** All Done! *****')