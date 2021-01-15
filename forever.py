import sys
from subprocess import Popen

filename = sys.argv[1]
while True:
    print("\nStarting " + filename)
    p = Popen("python3 " + filename, shell=True)
    p.wait()
