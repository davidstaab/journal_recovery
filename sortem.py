# import logging as log
import multiprocessing as mp
from os import getcwd, listdir, mkdir, path, scandir
from shutil import copyfile, move, rmtree
from time import sleep

from pathvalidate import sanitize_filename
from rapidfuzz import fuzz

from striprtf.striprtf.striprtf import rtf_to_text

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

def compare_and_assign(source_path: str):
    with open(source_path) as f:
        try:
            source_text = rtf_to_text(f.read(), errors="ignore")
        except UnicodeDecodeError:
            print(f'Critical decoding error on {source_path}. Skipping...')
            move(source_path, path.join(SORTING_DIR, "unreadable"))
            return

    # Compare to largest file in each subdir of SORTING_DIR. Build a list of {metric, dir}.
    results = []
    for dir_path in yield_dirs(SORTING_DIR):
        comp_path = biggest_file(dir_path)

        try:
            with open(comp_path) as c:
                comp_text = rtf_to_text(c.read(), errors="ignore")
                results.append({"metric": fuzz.partial_ratio(source_text, comp_text), "dir": dir_path})
        except NameError:
            #comp_path wasn't defined
            pass
    
    results = [r for r in results if r["metric"] >= MATCH_RATIO_THRESHOLD]
    results.sort(reverse=True, key=lambda _: _["metric"])
    matched = True
    if len(results):
        # Place in same folder as file it matches best with.
        best_match = results[0]
        if best_match["metric"] >= MATCH_RATIO_THRESHOLD:
            target_dir = best_match["dir"]
        else:
            matched = False
    else:
        matched = False

    if not matched:
        # If no matches, make new folder and put it in there.
        target_dir = path.join(SORTING_DIR, sanitize_filename(source_text[:25]))
    
    try:
        mkdir(target_dir)
    except FileExistsError:
        pass

    # When saving, rename it to the first 100 (sanitized) characters of its text + a unique index + ".rtf".
    new_fname = "".join([sanitize_filename(source_text[:100]), f' {len(listdir(target_dir))}', ".rtf"])
    new_file_path = path.join(target_dir, new_fname)
    move(source_path, new_file_path)
    print(f'Saved {new_file_path}')

def run_multi():
    worker_count = mp.cpu_count() - 2
    print(f'Starting with {worker_count} workers')
    with mp.Pool(processes=worker_count) as pool:
        while len(listdir(SOURCE_DIR)):
            for batch in yield_file_batch(SOURCE_DIR, batch_size=worker_count):
                print('Working on\n' + '\n'.join(batch))
                pool.map(compare_and_assign, batch)

def run_single():
    for batch in yield_file_batch(SOURCE_DIR, batch_size=1):
        print('Working on\n' + '\n'.join(batch))
        compare_and_assign(batch[0])

if __name__ == '__main__':  # Need this for mp to work!
    try:
        mkdir(SORTING_DIR)
    except FileExistsError:
        pass

    # log.basicConfig(filename='./log.txt', filemode='w', format='%(message)s', level=log.INFO)
    # run_multi()

    # while len(listdir(SOURCE_DIR)):  # Run until all source files are consumed
    for i in range(2):  # Run N times, for debugging
        run_single()
    
    print('***** All Done! *****')