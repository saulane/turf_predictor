import pandas as pd
from bs4 import BeautifulSoup as bs

import numpy as np
import statistics as st
import datetime
from threading import Thread,local

import asyncio
import aiohttp
from scipy import stats
from sklearn.preprocessing import RobustScaler, MinMaxScaler,StandardScaler,binarize
from sklearn.linear_model import LinearRegression

headers = {
    'Accept-Encoding': 'gzip, deflate, sdch',
    'Accept-Language': 'en-US,en;q=0.8',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/56.0.2924.87 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
    'Cache-Control': 'max-age=0',
    'Connection': 'keep-alive',
}
class DataError(ValueError): pass
class PMUError(ValueError): pass

# Stop the loop concurrently           
@asyncio.coroutine                                       
def exit():                                              
    loop = asyncio.get_event_loop()                      
    print("Stop")                                        
    loop.stop()    

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
                    'txReussiteHippo',
                    "mean_reduc_driver",
                    "prefered_dist_driver"]
        
        self.course = course
        self.courseId = course["id"]
        self.date = course["date"]
        self.idHippo = course["idHippo"]
        self.numCourse = course["numCourse"]
        self.numReunion = course["numReunion"]
        self.heure = course["heureCourse"]
        self.r_tab_partant = None
        self.r_tab_arrivee = None
        self.r_partant_pmu = None
        
        
        self.distance = int(course["distance"].replace(" ", ""))
        self.categorie = course["categorie"].split(" ")[1]
        
        self.training = training
        self.classement = None
        
        scaler = StandardScaler()
        
        
        
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            programme = loop.run_until_complete(self._info_tableau_partant())
        
        
#             self.info_partants = self._info_tableau_partant()
            df = pd.DataFrame(self.info_partants)
            df.loc[:, df.columns.isin(to_scale)] = scaler.fit_transform(df.loc[:, df.columns.isin(to_scale)].to_numpy())
            
            self.info_partants = df.to_dict('records')
        except:
            self.info_partants = None
        
        
    async def _request_tableau_partants(self, session):
        async with session.get(f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/tableau", headers=headers) as response:
             r = await response.text()
        soup = bs(r, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        self.r_tab_partant = rows, headers_table
    
    async def _request_tableau_arrive(self, session):
        async with session.get(f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/resultats/arrivee-definitive", headers=headers) as response:
             r = await response.text()
        soup = bs(r, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        
        classement = {row.select("td")[1].text : row.select("td")[0].find("span", {"class": "bold"}).text for row in rows}       
        self.classement = classement
        self.r_tab_arrivee = rows,classement
    
    async def _request_partant_pmu(self, session):
        date_pmu = "".join(self.date.split("-")[::-1]) 
        async with session.get(f"https://online.turfinfo.api.pmu.fr/rest/client/65/programme/{date_pmu}/R{self.numReunion}/C{self.numCourse}/participants", headers=headers) as response:
             participants_pmu = await response.json()
        try:
            pmu_jsoned = participants_pmu["participants"]
            participants = pd.json_normalize(pmu_jsoned, sep="_").to_dict(orient="records")
            participants_with_id = [dict(item, **{"id": self.courseId, "numReunion": self.numReunion}) for item in participants]  
            self.r_partant_pmu = participants_with_id
        except:
            raise PMUError("Erreur API PMU")
            
        
        
    async def _info_tableau_partant(self):
        chevaux = []
        
        tasks = []
        async with aiohttp.ClientSession() as session:
            tasks.append(asyncio.ensure_future(self._request_tableau_partants(session)))
            tasks.append(asyncio.ensure_future(self._request_tableau_arrive(session)))
            tasks.append(asyncio.ensure_future(self._request_partant_pmu(session)))
            tasks.append(asyncio.ensure_future(self.get_info_couple(session)))
            tasks.append(asyncio.ensure_future(self.get_info_cheval_hippo(session)))
            res = await asyncio.gather(*tasks, return_exceptions=True)
            
        for r in res:
            if type(r) == PMUError:
                raise PMUError("dsfgkjh")
       
        try:
            tableau_partants, headers_table = self.r_tab_partant
            tableau_arrivee,classement = self.r_tab_arrivee
            tableau_pmu = self.r_partant_pmu
            
        except:
            return None
        try:
            info_chevaux_hippo = self.info_cheval_hippo
            info_couple = self.couple_info
        except:
            pass
    
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

                cheval["heureCourse"] = self.heure
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
                
                t_cheval = []
                async with aiohttp.ClientSession() as session:
                    t_cheval.append(asyncio.ensure_future(self.get_info_cheval(session,cheval["url"], self.date,cheval["driver"])))
                    t_cheval.append(asyncio.ensure_future(self.get_info_driver(session,cheval["driver"])))
                    t_cheval.append(asyncio.ensure_future(self.get_tracking(session,cheval["url"])))
                    res = await asyncio.gather(*t_cheval, return_exceptions=True)
                for r in res:
                    if type(r) == DataError:
                        raise DataError("dsfgkjh")
                for dic in res:
                    cheval.update(dic)

                try:
                    cheval.update(info_couple[i])
                    cheval.update(info_chevaux_hippo[i])
                except:
                    pass

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
        self.info_partants = chevaux
    
    async def get_info_cheval(self,session, url, date, driver):
        async with session.get(url + "-paginate-2", headers=headers) as response:
             r = await response.json()
        date_debut = datetime.date.fromisoformat(date)
        jsoned = r["data"]

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
                c["allocation"] = int(bs(c["allocation"], "html.parser").span.text.lstrip("0"))
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

    async def get_info_driver(self,session, url):

        date = datetime.date.fromisoformat(self.date)
        
        d = datetime.timedelta(days=1)
        d2 = datetime.timedelta(days=365)

        date_arrive = (date - d).strftime("%d-%m-%Y").replace("-", "%2F")
        date_depart = (date  - d2).strftime("%d-%m-%Y").replace("-", "%2F")
        driver_id = url.split("/")[-3]
        n_url = f"https://www.letrot.com/stats/fiche-homme/analysesperformances-paginate?lenght=100&firstTime=true&hom_type=jockey&hom_num_encode={driver_id}&ferrure=all&hippodrome=all&corde=all&sol=all&discipline=A&depart=all&datepicker_du={date_depart}&datepicker_au={date_arrive}"
        async with session.get(n_url, headers=headers) as response:
             r = await response.json()
        jsoned = r["data"]
        info_dict = {}
        
        for d in jsoned:
            d["dateCourse"] = datetime.date.fromisoformat(bs(d["date_course"], "html.parser").span.text)
            d["rang"] = int(bs(d["rang"], "html.parser").find("span").text)

            reduction = d["reduction"].replace("'", "").replace('\"', "")
            
            if reduction != "":
                reduction_min = int(str(reduction)[0])
                reduction_sec = int(str(reduction)[1:3])
                reduction_ssec = int(str(reduction)[3])
                d["reduction"] = reduction_min*60*10 + reduction_sec*10 + reduction_ssec
            else:
                d["reduction"] = np.nan
            
            d["distance"] = int(d["distance"].replace(" ", "")) if d["distance"] != None else None
            try:
                d["allocation"] = int(bs(d["allocation"], "html.parser").span.text.lstrip("0"))
            except:
                d["allocation"] = 0


        
        weights = [ max(x["allocation"], 1) for x in jsoned]
        if sum(weights) == 0:
            raise DataError("Not enough Data")

        prefered_dist = int(np.average([ x["distance"] for x in jsoned if x["distance"] != None ], weights=weights))
        
        mean_reduc = pd.Series([d["reduction"] for d in jsoned][::-1]).dropna().ewm(20).mean().iloc[-1]
        
        info_dict["mean_reduc_driver"] = mean_reduc
        info_dict["prefered_dist_driver"] = prefered_dist
        
        return info_dict
    
    async def get_info_couple(self, session):
        couple_info = []

        date = datetime.date.fromisoformat(self.date)
        
        d = datetime.timedelta(days=1)
        d2 = datetime.timedelta(days=365)

        date_arrive = (date - d).strftime("%d-%m-%Y").replace("-", "%2F")
        date_depart = (date  - d2).strftime("%d-%m-%Y").replace("-", "%2F")
        
        url = f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/couples/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
                
        async with session.get(url, headers=headers) as response:
             r = await response.json()
        data = r["data"]

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
        self.couple_info = couple_info
    
    async def get_info_cheval_hippo(self, session):
        couple_info = []

        date = datetime.date.fromisoformat(self.date)
        
        d = datetime.timedelta(days=1)
        d2 = datetime.timedelta(days=365)

        date_arrive = (date - d).strftime("%d-%m-%Y").replace("-", "%2F")
        date_depart = (date  - d2).strftime("%d-%m-%Y").replace("-", "%2F")
        url = f"https://www.letrot.com/stats/fiche-course/{self.date}/{self.idHippo}/{self.numCourse}/partants/chevaux/paginate?numHippodrome={self.idHippo}&piste=all&datepicker_du={date_depart}&datepicker_au={date_arrive}"
        
        async with session.get(url, headers=headers) as response:
             r = await response.json()
        data = r["data"]

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
        self.info_cheval_hippo = couple_info
    
    async def get_tracking(self,session, url):
        async with session.get(url.replace("dernieres-performances", "tracking"), headers=headers) as response:
             r = await response.text()
        soup = bs(r, "html.parser")
        headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
        table = soup.find("table", {"id": "result_table"}).find("tbody")
        rows = table.find_all("tr")
        
        info_tracking = {}
        
        distance_au_premier_arrivee = []
        accélération_500m = []
        gain_classement_500m = []
        for row in rows:
            dist_prem = int(row.find_all("td")[2].span.text)
            if dist_prem < 9999:
                distance_au_premier_arrivee.append(dist_prem)
            
            pre_fin = int(row.find_all("td")[17].span.text)
            fin = int(row.find_all("td")[18].span.text)
            if pre_fin < 2000 and fin < 2000:                                            
                accélération_500m.append(pre_fin - fin)
                

            try:
                class_500m = int(row.find_all("td")[16].span.text)
                class_final = int(row.find_all("td")[1].find("span", {"class": "bold"}).text)
                if class_500m -  class_final < 10:
                    gain_classement_500m.append(class_500m -  class_final)
            except:
                gain_classement_500m.append(0)
            
        info_tracking["mean_dist_arrivee"] = np.mean(distance_au_premier_arrivee) if len(distance_au_premier_arrivee) > 0 else np.nan
        info_tracking["acceleration_500m"] = np.mean(accélération_500m) if len(accélération_500m) > 0 else np.nan
        info_tracking["gain_classement_fin"] = np.mean(gain_classement_500m) if len(gain_classement_500m) > 0 else np.nan
        return info_tracking