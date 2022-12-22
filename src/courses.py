import pandas as pd
from bs4 import BeautifulSoup as bs
import numpy as np

import datetime
import concurrent
from threading import Thread,local
import requests
import asyncio
import aiohttp

headers = {
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
}

hippo_letrot = ["LE MONT-SAINT-MICHEL-PONTORSON", "BORDEAUX", "LE CROISE-LAROCHE","CAGNES-SUR-MER","MESLAY-DU-MAINE"]
hippo_pmu =  ["LE MONT SAINT MICHEL", "LE BOUSCAT", "LE CROISE LAROCHE","CAGNES/MER","MESLAY DU MAINE"]

class Programme():
    def __init__(self, debut, fin):
        self.date_debut = datetime.date.fromisoformat("-".join(debut.split("-")[::-1]))
        self.date_fin = datetime.date.fromisoformat("-".join(fin.split("-")[::-1]))
        
        n_days = self.date_fin - self.date_debut
        cur = max(self.date_fin - datetime.timedelta(days=90), self.date_debut)
        
        intervalle_date = [self.date_fin, cur]
        
        while cur > self.date_debut:
            cur = max(self.date_debut, cur - datetime.timedelta(days=90))
            
            intervalle_date.append(cur)        
        self.intervalles = [(i,j + datetime.timedelta(days=1)) for i,j in zip(intervalle_date, intervalle_date[1:])]
        
        
        loop = asyncio.get_event_loop()
        programme = loop.run_until_complete(asyncio.gather(*[self._get_programme_from_letrot(inter) for inter in self.intervalles]))
        
        programme = [item for sublist in programme for item in sublist]
        
        self.programme = pd.DataFrame(programme)

    async def combined_prog(self):
        return await asyncio.gather(*[self._get_programme_from_letrot(inter) for inter in self.intervalles])


    async def _get_pmu_program(self, session, date):
        date_pmu = date.strftime("%d%m%Y")
        async with session.get(f"https://online.turfinfo.api.pmu.fr/rest/client/65/programme/{date_pmu}/") as res:
            try:
                return await res.json()
            except:
                return None

    async def _get_programme_from_letrot(self, date):
        debut = date[1].strftime("%d-%m-%Y")
        fin = date[0].strftime("%d-%m-%Y")
#         print(debut)
        programme = []
        
#         async with aiohttp.ClientSession() as session:
#             async with session.get(f"https://www.letrot.com/fr/courses/calendrier-resultats?publish_up={debut}&publish_down={fin}", headers=headers) as response:
#                  r = await response.text()
        
        
        num_days = (date[0] - date[1]).days + 1
        date_list = [date[0] - datetime.timedelta(days=x) for x in range(num_days)]
        prog_pmu = {}
        
        tasks = []
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://www.letrot.com/fr/courses/calendrier-resultats?publish_up={debut}&publish_down={fin}", headers=headers) as response:
                 r = await response.text()
            for d in date_list:
                tasks.append(asyncio.ensure_future(self._get_pmu_program(session, d)))
            res_prog_pmu = await asyncio.gather(*tasks)
        soup = bs(r, "html.parser")
        reunion_raw = soup.find_all("a", {"class": "racesHippodrome"})
        current_date_reunion = "0"
        current_programme = {}    
            
            
            
        for i in range(len(res_prog_pmu)):
            prog_pmu.update({date_list[i].strftime("%Y-%m-%d"): res_prog_pmu[i]})

        
        
        for i in range(len(reunion_raw)):
            reunion = reunion_raw[i]
            date = reunion.get("href").split("/")[-2]
            hippodrome = reunion.text[2:].strip()
            for i in range(len(hippo_letrot)):
                hippodrome = hippodrome.replace(hippo_letrot[i], hippo_pmu[i])
            
            hippodrome = hippodrome.replace(" (A ", " ").replace(")", "")
            date_pmu = "".join(date.split("-")[::-1])
            
            if date in prog_pmu:
                current_programme = prog_pmu[date]
            else:
                continue
                
            numReunion = 0
            try:
                for reunion_pmu in current_programme["programme"]["reunions"]:
                    if hippodrome in reunion_pmu["hippodrome"]["libelleCourt"]:
                        numReunion = reunion_pmu["numOfficiel"]
            except:
                continue
            
            if numReunion == 0:
                continue
            course = {"date": date, "idHippo": reunion.get("href").split("/")[-1], "Hippodrome": hippodrome, "lien": reunion.get("href")}
            course["numReunion"] = numReunion
            programme.append(course)
        return programme



class Courses():
    def __init__(self, programme: Programme) -> None:
        self.programme = programme.programme
        self.courses = self._get_all_course_in_programme()

    def _get_all_course_in_programme(self):
        courses = []  

        def _request_race(row):
            courses_list = []
            try:
                url = f"https://www.letrot.com/{row['lien']}/json"
                date_pmu = "".join(row["date"].split("-")[::-1])    
                r = requests.get(url, headers=headers)
                courses = r.json()
                for c in courses["course"]:
                    if c["discipline"] == "Attelé":
                        course_id = row["date"].replace("-", "") + str(row["idHippo"]) + str(c["numCourse"])
                        courses_list.append({"date": row["date"], "id": course_id, "numReunion": row["numReunion"], "hippodrome": courses["nomHippodrome"], "idHippo": row["idHippo"],**c})
                return courses_list
            except:
                pass
            
        def gen_rows(df):
            for row in df.itertuples(index=False):
                yield row._asdict()

        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            res = executor.map(_request_race, gen_rows(self.programme))
            
            for i in res:
                courses.extend(i)
            
        return pd.DataFrame(courses)