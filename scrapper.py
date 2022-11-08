import io
import json
import os
import sys
import pandas as pd
from bs4 import BeautifulSoup as bs
import requests
import numpy as np
from scipy import stats
import datetime
import time
import statistics as st

import module


if __name__ == "__main__":
    args = sys.argv

    if len(args) != 3:
        raise Exception("scrapper.py 'date_debut' 'date_fin'")
    
    prog = module.get_programme(args[1], args[2])
    courses = module.get_courses(prog)

    partants = module.partants(courses, "data2.csv")