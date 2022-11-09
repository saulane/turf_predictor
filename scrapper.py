import io
import json
import os
import sys
import pandas as pd
from bs4 import BeautifulSoup as bs
import logging
import module

logging.basicConfig(filename="log.log", level=logging.ERROR, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    args = sys.argv

    if len(args) != 3:
        raise Exception("scrapper.py 'date_debut' 'date_fin'")
    
    try:
        prog = module.get_programme(args[1], args[2])
        courses = module.get_courses(prog)

        partants = module.partants(courses, "data2.csv")
    except Exception as e:
        logger.error(e)