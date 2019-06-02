import os

from ImageHash import thumb_path

for root, dirs, files in os.walk("static/thumbs/"):
    for name in files:
        filename = os.path.join(root, name)

        if name.endswith(".jpg"):

            print(filename)
            dirpath = thumb_path(int(name.split(".")[0]))
            os.makedirs(dirpath, exist_ok=True)
            os.rename(filename, os.path.join(dirpath, name))
