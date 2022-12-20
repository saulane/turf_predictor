import io
import json
import os
import sys
import pandas as pd
from bs4 import BeautifulSoup as bs
import logging
import src.module as module
import concurrent.futures

logging.basicConfig(filename="log.log", level=logging.ERROR, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    months_length = [31,28,31,30,31,30,31,31,30,31,30,31]
    months = ["01","02","03","04","05","06","07","08","09","10","11","12"]
    args = sys.argv

    annee = args[1]

    try:
        for j in range(len(months)):
            debut = f"01-{months[j]}-{annee}"
            fin = f"{months_length[j]}-{months[j]}-{annee}"
            prog = module.get_programme(debut, fin)
            courses = module.get_courses(prog)



            partants = module.partants(courses, f"data-{annee}.csv")
            logger.info(f"{debut}|{fin} récupéré")
    except Exception as e:
        logger.error(e)