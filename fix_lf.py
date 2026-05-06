with open('entrypoint.sh', 'rb') as f:
    content = f.read()
with open('entrypoint.sh', 'wb') as f:
    f.write(content.replace(b'\r\n', b'\n'))
print("Fixed entrypoint.sh line endings.")
