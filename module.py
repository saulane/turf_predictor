import pandas as pd
from bs4 import BeautifulSoup as bs
import requests
import numpy as np
import statistics as st
import datetime
import os
import time
import concurrent
from threading import Thread,local
import requests
from requests.sessions import Session
import asyncio
import aiohttp
from scipy import stats
from sklearn.preprocessing import RobustScaler, MinMaxScaler,StandardScaler
from sklearn.linear_model import LinearRegression

import pickle
import xlogit

import lightgbm


headers = {
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
}

hippo_letrot = ["LE MONT-SAINT-MICHEL-PONTORSON", "BORDEAUX", "LE CROISE-LAROCHE", "MARSEILLE (A BORELY)"]
hippo_pmu =  ["LE MONT SAINT MICHEL", "LE BOUSCAT", "LE CROISE LAROCHE", "BORELY"]

import nest_asyncio
nest_asyncio.apply()

thread_local = local()

def get_session() -> Session:
    if not hasattr(thread_local, 'session'):
        thread_local.session =  requests.Session()
    return thread_local.session

def get_request_with_session(url:str):
    session = get_session()
    with session.get(url, headers=headers) as response:
        return response

def gen_rows(df):
    for row in df.itertuples(index=False):
        yield row._asdict()

class DataError(ValueError): pass


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
        
        url = f"https://www.letrot.com/fr/courses/calendrier-resultats?publish_up={debut}&publish_down={fin}"
        r = get_request_with_session(url)
        soup = bs(r.text, "html.parser")
        reunion_raw = soup.find_all("a", {"class": "racesHippodrome"})
        current_date_reunion = "0"
        current_programme = {}
        
        num_days = (date[0] - date[1]).days + 1
        date_list = [date[0] - datetime.timedelta(days=x) for x in range(num_days)]
        prog_pmu = {}
        
        tasks = []
        async with aiohttp.ClientSession() as session:
            for d in date_list:
                tasks.append(self._get_pmu_program(session, d))
            res_prog_pmu = await asyncio.gather(*tasks)    
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
            for reunion_pmu in current_programme["programme"]["reunions"]:
                if hippodrome in reunion_pmu["hippodrome"]["libelleCourt"]:
                    numReunion = reunion_pmu["numOfficiel"]
                    break
            
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

class Partants():
    def __init__(self, course, training=False):
        
        to_scale = ['nombreCourses',
                    'nombreVictoires',
                    'nombrePlaces',
                    'nombrePlacesSecond',
                    'nombrePlacesTroisieme',
                    'gainsParticipant_gainsCarriere',
                    'gainsParticipant_gainsVictoires',
                    'gainsParticipant_gainsPlace',
                    'gainsParticipant_gainsAnneeEnCours',
                    'gainsParticipant_gainsAnneePrecedente',
                    'nbDiscalifieMusic',
                    'nbVictoireMusic',
                    'nbPlaceMusic',
                    'prefered_dist',
                    'distToPreferedDist',
                    'meanReduction',
                    'medianReduction',
                    'maxReduction',
                    'minReduction',
                    'timeSinceRecord',
                    'tpsLastRace',
                    'nbArriveMusic',
                    'recordAbs',
                    'nbCourseCouple',
                    'nbVictoiresCouple',
                    'nb2emeCouple',
                    'nb3emeCouple',
                    'txReussiteCouple',
                    'nbCourseHippo',
                    'nbVictoiresHippo',
                    'nb2emeHippo',
                    'nb3emeHippo',
                    'txReussiteHippo']
        
        self.course = course
        self.courseId = course["id"]
        self.heure = course["heureCourse"]
        self.date = course["date"]
        self.idHippo = course["idHippo"]
        self.numCourse = course["numCourse"]
        self.numReunion = course["numReunion"]
        
        
        self.distance = int(course["distance"].replace(" ", ""))
        self.categorie = course["categorie"].split(" ")[1]
        
        self.training = training
        self.classement = None
        
        scaler = StandardScaler()
        
        try:
            self.info_partants = self._info_tableau_partant()
            df = pd.DataFrame(self.info_partants)
            df["heureCourse"] = self.heure
            df.loc[:, df.columns.isin(to_scale)] = scaler.fit_transform(df.loc[:, df.columns.isin(to_scale)].to_numpy())
            df.sort_values(by="heureCourse", inplace=True)
            self.info_partants = df.to_dict('records')
            
        except:
            self.info_partants = None
        
        
    def _request_tableau_partants(self):
        r = get_request_with_session(f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/tableau")
        soup = bs(r.text, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        return rows, headers_table
    
    def _request_tableau_arrive(self):
        r = get_request_with_session(f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/resultats/arrivee-definitive")
        soup = bs(r.text, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        
        classement = {row.select("td")[1].text : row.select("td")[0].find("span", {"class": "bold"}).text for row in rows}       
        self.classement = classement
        return rows,classement
    
    def _request_partant_pmu(self):
        date_pmu = "".join(self.date.split("-")[::-1])  
        participants_pmu = get_request_with_session(f"https://online.turfinfo.api.pmu.fr/rest/client/65/programme/{date_pmu}/R{self.numReunion}/C{self.numCourse}/participants")
        try:
            pmu_jsoned = participants_pmu.json()["participants"]
            participants = pd.json_normalize(pmu_jsoned, sep="_").to_dict(orient="records")
            participants_with_id = [dict(item, **{"id": self.courseId, "numReunion": self.numReunion}) for item in participants]  
            return participants_with_id
        except:
            raise Exception("Erreur API PMU")
            
        
        
    def _info_tableau_partant(self):
        chevaux = []
        
        try:
            tableau_partants, headers_table = self._request_tableau_partants()
            tableau_arrivee,classement = self._request_tableau_arrive()
            tableau_pmu = self._request_partant_pmu()
        except:
            return None

        info_couple = self.get_info_couple()
        info_chevaux_hippo = self.get_info_cheval_hippo()
    
        chevaux.extend(tableau_pmu)
        
        for i,row in enumerate(tableau_partants):
                num = row.select("td")[0].find("span", {"class": "bold"}).text
                col = row.select("td")
                cheval = {}
                cheval["num"] = num
                cheval["nom"] = col[1].text
                
                
                
                cheval["numCoursePMU"] = f"R{self.numReunion}C{self.numCourse}"

                if self.training:
                    if num == "NP":
                        cheval["classement"] = "NP"
                    else:
                        cheval["classement"] = classement[num]
                cheval["id"] = self.courseId
                cheval["date"] = self.date
                cheval["url"] = col[1].find("a").get("href")


                cheval["fer"] = int(col[3].text) if col[3].text else 0
                cheval["firstTimeFer"] = 1 if col[3].find("div", {"class", "fer-first-time"}) else 0
                cheval["sex"] = 0 if col[4].text == "M" else 1
                cheval["age"] = int(col[5].text)
                cheval["dist"] = int(col[6].text.replace(" ", "").replace("\n", ""))
                cheval["driver"] = col[7].find("a").get("href")
                cheval["trainer"] = col[8].find("a").get("href")

                if "Avis" in headers_table[9].text:
                    cheval["avisTrainer"] = int(col[9].get("data-order"))
                    avis = col.pop(9)
                    col.insert(-1, avis)
                else:
                    cheval["avisTrainer"] = 2

                cheval["music"] = list(filter(lambda x: "a" in x, col[9].text.replace("D", "0").replace("Ret", "0").replace("T", "0").split()))
                cheval["music"] = list(map(lambda x: x[0], cheval["music"]))

                cheval["music"] = list(filter(lambda x: x.isnumeric(), cheval["music"]))

                cheval["music"] = list(map(int, cheval["music"]))

                cheval["nbDiscalifieMusic"] = cheval["music"].count(0)
                cheval["nbVictoireMusic"] = cheval["music"].count(1)
                cheval["nbPlaceMusic"] = sum(map(lambda x : x <=3 and x > 0,cheval["music"]))
                
                
                if len(cheval["music"]) < 4:
                    raise DataError("not enough data")
                    
                cheval.update(self.get_info_cheval(cheval["url"], self.date,cheval["driver"]))
                cheval.update(self.get_tracking(cheval["url"]))
                cheval.update(info_couple[i])
                cheval.update(info_chevaux_hippo[i])

                cheval["formeVictoire"] = 1 if cheval["nbVictoireMusic"]/len(cheval["music"]) > 0.33 else 0
                cheval["formePlace"] = 1 if cheval["nbPlaceMusic"]/len(cheval["music"]) > 0.33 else 0
                    
                cheval["nbArriveMusic"] = len(cheval["music"]) - cheval["music"].count(0)
                cheval["lastPerf"] = cheval["music"][0] if cheval["nbArriveMusic"] else 0

                arriveOnly = list(filter(None, cheval["music"]))
                if len(arriveOnly) > 0:
                    try:
                        cheval["meanPerf"] = np.mean(arriveOnly)
                        cheval["medianPerf"] = np.median(arriveOnly)
                        cheval["modePerf"] = st.mode(cheval["music"])
                    except:
                        cheval["meanPerf"] = 0
                        cheval["medianPerf"] = 0
                        cheval["modePerf"] = 0
                else:
                    cheval["meanPerf"] = 0
                    cheval["medianPerf"] = 0
                    cheval["modePerf"] = 0

                try:
                    cheval["recordAbs"] = list(map(int, col[10].text.replace(col[10].span.text, "").replace("\'", '"').split('"')))
                    cheval["recordAbs"] = cheval["recordAbs"][0] * 10 * 60 + cheval["recordAbs"][1] * 10 + cheval["recordAbs"][2]
                except:
                    cheval["recordAbs"] = None

                cheval["gain"] = int(col[11].find("div", class_="gains").text.replace(" ", "")[:-1])
                
                chevaux[i].update(cheval)
        return chevaux
    
    def get_info_cheval(self, url, date, driver):
        r = requests.get(url + "-paginate-2", headers=headers)
        date_debut = datetime.date.fromisoformat(date)
        jsoned = r.json()["data"]

        info_dict = {}

        for c in jsoned:
            c["dateCourse"] = datetime.date.fromisoformat(c["dateCourseRaw"])
            c["categorie"] = bs(c["categorie"], "html.parser").find("span").text
            try:
            
                c["driver"] = bs(c["nomDriver"], "html.parser").find("a").get("href").split("/")[-3] == driver.split("/")[-3]
            except:
                c["driver"] = 0
            reduction = bs(c["reduction"], "html.parser").span.text
            reduction = reduction.replace("'", "").replace('\"', "")
            try:
                c["allocation"] = int(bs(c["reduction"], "html.parser").span.text.lstrip("0"))
            except:
                c["allocation"] = 0
            

            c["distance"] = int(c["distance"].replace(" ", "")) if c["distance"] != None else None

            reduction_min = int(str(reduction)[0])
            reduction_sec = int(str(reduction)[1:3])
            reduction_ssec = int(str(reduction)[3])

            c["reduction"] = reduction_min*60*10 + reduction_sec*10 + reduction_ssec

            # c["recordAbs"] = list(map(int, reduction.text.replace(reduction.span.text, "").replace("\'", '"').split('"')))
            # c["recordAbs"] = c["recordAbs"][0] * 10 * 60 + c["recordAbs"][1] * 10 + c["recordAbs"][2]

        filtered = list(filter(lambda x: x["dateCourse"] < date_debut and x["specialite"] == "A", jsoned))

        if len(filtered) == 0:
            raise DataError("Not enough Data")
        
        perc_jockey = sum([x["driver"] for x in filtered])/len(filtered)
        info_dict["jockeyHabitude"] = 1 if perc_jockey > 0.5 else 0
        
        last_30_days = list(filter(lambda x: x["dateCourse"] > date_debut - datetime.timedelta(days=30) and x["specialite"] == "A", jsoned))
        
        weights = [ max(x["allocation"], 1) for x in filtered if x["distance"] != None  ]
        if sum(weights) == 0:
            raise DataError("Not enough Data")
#         print(weights)
        prefered_dist = int(np.average([ x["distance"] for x in filtered if x["distance"] != None ], weights=weights))
        
        info_dict["prefered_dist"] = prefered_dist
        info_dict["distToPreferedDist"] = abs(self.distance - prefered_dist)
        
        info_dict["changementCategorie"] = 1 if filtered[0]["categorie"] != self.categorie else 0
        
        if len(last_30_days) > 0:
            dist_30_days = np.array([x["distance"] for x in last_30_days])
            info_dict["newDist"] = 1 if np.max(dist_30_days - self.distance) > 200 else 0
        else:
            info_dict["newDist"] = 1
            
        
        filtered_tps = list(filter(lambda x: x["reduction"] < 1200, filtered))
        
        dps_race = [(date_debut - x["dateCourse"]).days for x in filtered_tps]
        tps = [x["reduction"] for x in filtered_tps]
        
        if len(tps) > 0:
            info_dict["meanReduction"] = np.mean(tps)
            info_dict["medianReduction"] = np.median(tps)
            info_dict["maxReduction"] = max(tps)
            info_dict["minReduction"] = min(tps)
            
            lin_reg = LinearRegression().fit(np.array(dps_race).reshape(-1, 1), np.array(tps).reshape(-1, 1))
            info_dict["progressTps"] = np.exp(lin_reg.coef_[0][0])
            
        else:
            info_dict["meanReduction"] = 0
            info_dict["medianReduction"] = 0
            info_dict["maxReduction"] = 0
            info_dict["minReduction"] = 0
            info_dict["progressTps"] = 0

        info_dict["timeSinceRecord"] = next(((date_debut - item["dateCourse"]).days for item in filtered_tps if item["reduction"] == info_dict["minReduction"]), 365)

        info_dict["tpsLastRace"] = (date_debut - filtered[0]["dateCourse"]).days

        info_dict["last_race_dist"] = filtered[0]["distance"]
        info_dict["rentree"] = 1 if info_dict["tpsLastRace"] > 30 else 0

        return info_dict
    
    
    def get_info_couple(self):
        couple_info = []

        date = datetime.date.fromisoformat(self.date)
        
        d = datetime.timedelta(days=1)
        d2 = datetime.timedelta(days=365)

        date_arrive = (date - d).strftime("%d-%m-%Y").replace("-", "%2F")
        date_depart = (date  - d2).strftime("%d-%m-%Y").replace("-", "%2F")

        url = f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/couples/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
        r = requests.get(url, headers=headers)
        dic_json = r.json()
        data = dic_json["data"]

        data_sorted = sorted(data, key=lambda x: x["numero"])
        for couple in data_sorted:
            cheval = {}

            cheval["nbCourseCouple"] = int(bs(couple["nbre_courses"], "html.parser").find("div").text)
            cheval["nbVictoiresCouple"] = int(bs(couple["nbre_victoires"], "html.parser").find("div").text)
            cheval["nb2emeCouple"] = int(bs(couple["nbre_2eme"], "html.parser").find("div").text)
            cheval["nb3emeCouple"] = int(bs(couple["nbre_3eme"], "html.parser").find("div").text)
            cheval["txReussiteCouple"] = int(couple["taux_reussite_sort"])/100
            try:
                cheval["txVictoireCouple"] = cheval["nbVictoiresCouple"] / cheval["nbCourseCouple"]
            except:
                cheval["txVictoireCouple"] = 0.0
            cheval["nonPartant"] = couple["nonPartant"]
            cheval["moreFirstThanThirdCouple"] = 1 if cheval["nbVictoiresCouple"] > cheval["nb3emeCouple"] + cheval["nb2emeCouple"] else 0
            couple_info.append(cheval)
        return couple_info
    
    def get_info_cheval_hippo(self):
        couple_info = []

        date = datetime.date.fromisoformat(self.date)
        
        d = datetime.timedelta(days=1)
        d2 = datetime.timedelta(days=365)

        date_arrive = (date - d).strftime("%d-%m-%Y").replace("-", "%2F")
        date_depart = (date  - d2).strftime("%d-%m-%Y").replace("-", "%2F")

        url = f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/chevaux/paginate?numHippodrome={self.idHippo}&piste=all&datepicker_du={date_depart}&datepicker_au={date_arrive}"
        r = requests.get(url, headers=headers)
        dic_json = r.json()
        data = dic_json["data"]

        data_sorted = sorted(data, key=lambda x: x["numero"])
        for couple in data_sorted:
            cheval = {}

            cheval["nbCourseHippo"] = int(bs(couple["nbre_courses"], "html.parser").find("div").text)
            cheval["nbVictoiresHippo"] = int(bs(couple["nbre_victoires"], "html.parser").find("div").text)
            cheval["nb2emeHippo"] = int(bs(couple["nbre_2eme"], "html.parser").find("div").text)
            cheval["nb3emeHippo"] = int(bs(couple["nbre_3eme"], "html.parser").find("div").text)
            try:
                cheval["txVictoireHippo"] = cheval["nbVictoiresHippo"] / cheval["nbCourseHippo"]
            except:
                cheval["txVictoireHippo"] = 0.0
            try:
                cheval["txReussiteHippo"] =int(couple["taux_reussite_sort"])/100
            except:
                cheval["txReussiteHippo"] = 0.0
                                              
            cheval["perfHippo"] = 1 if cheval["txReussiteHippo"] > 0.5 and cheval["nbCourseHippo"] > 5 else 0
            couple_info.append(cheval)
        return couple_info
    
    def get_tracking(self, url):
        r = requests.get(url.replace("dernieres-performances", "tracking"), headers=headers)
        soup = bs(r.text, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        
        info_tracking = {}
        
        distance_au_premier_arrivee = []
        accélération_500m = []
        for row in rows:
            dist_prem = int(row.find_all("td")[2].span.text)
            if dist_prem < 9999:
                distance_au_premier_arrivee.append(dist_prem)
            
            pre_fin = int(row.find_all("td")[17].span.text)
            fin = int(row.find_all("td")[18].span.text)
            if pre_fin < 2000 and fin < 2000:                                            
                accélération_500m.append(pre_fin - fin)
            
        info_tracking["mean_dist_arrivee"] = np.mean(distance_au_premier_arrivee) if len(distance_au_premier_arrivee) > 0 else np.nan
        info_tracking["acceleration_500m"] = np.mean(accélération_500m) if len(accélération_500m) else np.nan
            
        return info_tracking


class Predicion():
    def __init__(self, tableau_partant) -> None:
        self.X: pd.DataFrame = tableau_partant

        self.prepare_for_pred()

        self.model1: xlogit.MultinomialLogit = pickle.load(open("models/cl_v1.pickle", "rb"))
        self.model2: xlogit.MultinomialLogit = pickle.load(open("models/cl_v2.pickle", "rb"))

        self.model_ranker: lightgbm.LGBMRanker = pickle.load(open("models/rankerv1.pickle", "rb"))

        # self.predict()

    def prepare_for_pred(self):
        self.X.groupby("id").filter(lambda x: len(x) > 8)
        self.X["lifepercwin"] = self.X["nombreVictoires"] / self.X["nombreCourses"]
        self.X["winPrace"] = self.X["gainsParticipant_gainsCarriere"] / self.X["nombreCourses"]
        self.X["available"] = 1

        self.X["publicProbaOfWinning"] = 1 / self.X["dernierRapportDirect_rapport"]
        self.X.fillna(0, inplace=True)
        self.X.replace([np.inf, -np.inf], 0, inplace=True)


        multiindex = [[],[]]

        for i in self.X.id.unique():
            for j in range(0,18):
                multiindex[0].append(i)
                multiindex[1].append(j)

        self.X = self.X.set_index(["id", self.X.groupby("id").cumcount()])
        new_index = pd.MultiIndex.from_arrays(multiindex, names=["id", "num"])
        self.X = self.X.reindex(new_index, fill_value=0).reset_index(level=1, drop=True).reset_index()

        nindex = len(self.X.groupby("id")) * list(range(1,self.X.groupby("id").cumcount().max()+2))
        self.X = self.X.assign(num=nindex)
        
        self.X.to_csv("test.csv")

    def predict(self):
        features = ['acceleration_500m','nbVictoiresCouple','nbCourseCouple','rentree','last_race_dist','tpsLastRace','timeSinceRecord',
                    'minReduction','medianReduction','meanReduction','changementCategorie','distToPreferedDist','prefered_dist','jockeyHabitude',
                    'nbDiscalifieMusic','nbVictoireMusic','nbPlaceMusic',
                    'fer','gainsParticipant_gainsCarriere','sex','age','dist', 'firstTimeFer',
                    'formePlace','formeVictoire','lastPerf','mean_dist_arrivee','nbVictoiresHippo','nombreCourses','nbCourseHippo',
                    'txVictoireCouple','txVictoireHippo']

        for f in features:
            if f not in list(self.X):
                self.X[f] = 0

        self.X["rank_pred"] = self.model_ranker.predict(self.X[self.model_ranker.feature_name_])

        # choice_estimate, proba_estimate = self.model1.predict(X=self.X[features], varnames=features, ids=self.X["id"], alts=self.X["num"], avail=self.X["available"],return_proba=True)         
        # self.X["proba_1"] = proba_estimate.flatten()
        # self.X["proba_1"].replace(-np.inf,0, inplace=True)
        # self.X["proba_1"].fillna(0, inplace=True)

        choice, proba = self.model2.predict(X=self.X[["publicProbaOfWinning","rank_pred"]],varnames=["publicProbaOfWinning","rank_pred"], ids=self.X["id"],alts=self.X["num"],avail=self.X["available"], return_proba=True)

        return choice,proba


def get_df_partants(courses):
    info = []
    t = time.time()
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        res = executor.map(Partants, gen_rows(courses))
        for i in res:
            if isinstance(i.info_partants, list):
                info.extend(i.info_partants)
    return pd.DataFrame(info)