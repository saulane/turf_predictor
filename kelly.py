import sys
import numpy as np

def kelly(p, rapport):
    return p - (1-p)/rapport

if __name__ == "__main__":
    args = sys.argv
    try:
        rapport = float(args[1])
        capital = int(args[2])

        p = 1.5 * 1/rapport

        print(f"Mise: {kelly(p, rapport) * capital}")

    except:
        raise Exception("Please enter a valid number")

