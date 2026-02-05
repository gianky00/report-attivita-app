import os
import re
from pathlib import Path

def fix_tests():
    # Regex per trovare stringhe che iniziano con src. all'interno di mocker.patch o import
    pattern = re.compile(r'["\']src\.([\w\.]+)["\']')
    
    for root, dirs, files in os.walk("tests"):
        for file in files:
            if file.endswith(".py"):
                path = Path(root) / file
                content = path.read_text(encoding="utf-8")
                
                # Sostituisce "src.modules..." con "modules..."
                new_content = pattern.sub(r"'\1'", content)
                
                if new_content != content:
                    path.write_text(new_content, encoding="utf-8")
                    print(f"Fixed {path}")

if __name__ == "__main__":
    fix_tests()