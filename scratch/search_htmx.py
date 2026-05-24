import urllib.request
import re

url = "https://cdnjs.cloudflare.com/ajax/libs/htmx/1.9.12/htmx.js"
with urllib.request.urlopen(url) as response:
    content = response.read().decode('utf-8')

# We want to find function blocks or loops where 'forEach' is used
# and matches() is called inside. Let's find matches of forEach(..., function(...) { ... matches(...) ... })
# Let's search for all files/lines where 'forEach' appears, and print if 'matches' is within the surrounding lines
lines = content.split('\n')
for i, line in enumerate(lines):
    if 'forEach(' in line:
        # Check if 'matches(' is in the next 15 lines
        has_matches = False
        for j in range(i, min(len(lines), i+15)):
            if 'matches(' in lines[j]:
                has_matches = True
                break
        if has_matches:
            print(f"Line {i+1}: {line.strip()}")
            for j in range(max(0, i-2), min(len(lines), i+15)):
                print(f"  {j+1}: {lines[j]}")
