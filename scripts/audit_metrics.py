
import os
import pathlib

def count_loc(path):
    with open(path, 'r', encoding='utf-8', errors='ignore') as f:
        return sum(1 for line in f if line.strip() and not line.strip().startswith('#'))

def main():
    src_path = pathlib.Path('src')
    files_data = []
    
    print("--- LOC & SIZE METRICS ---")
    for file_path in src_path.rglob('*.py'):
        loc = count_loc(file_path)
        files_data.append((str(file_path), loc))
    
    # Sort by LOC descending
    files_data.sort(key=lambda x: x[1], reverse=True)
    
    print(f"{'File':<60} | {'LOC':<5}")
    print("-" * 70)
    for f, loc in files_data[:20]:
        print(f"{f:<60} | {loc:<5}")
        
    total_loc = sum(x[1] for x in files_data)
    print("-" * 70)
    print(f"Total LOC: {total_loc}")
    print(f"Total Files: {len(files_data)}")

if __name__ == "__main__":
    main()
