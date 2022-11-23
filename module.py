import pandas as pd
from bs4 import BeautifulSoup as bs
import requests
import numpy as np
import statistics as st
import datetime
import os
import time
import concurrent

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

class Programme():
    def __init__(self, debut, fin) -> None:
        self.programme = self._get_programme_from_letrot(debut, fin)

    def _get_programme_from_letrot(self, debut, fin):
        programme = []
        url = f"https://www.letrot.com/fr/courses/calendrier-resultats?publish_up={debut}&publish_down={fin}"
        r = requests.get(url, headers=headers)
        soup = bs(r.text, "html.parser")
        reunion_raw = soup.find_all("a", {"class": "racesHippodrome"})
        current_date_reunion = "0"
        current_programme = {}
        
        for i in range(len(reunion_raw)):
            reunion = reunion_raw[i]
            date = reunion.get("href").split("/")[-2]
            hippodrome = reunion.text[2:].strip()
            for i in range(len(hippo_letrot)):
                hippodrome = hippodrome.replace(hippo_letrot[i], hippo_pmu[i])
            
            hippodrome = hippodrome.replace(" (A ", " ").replace(")", "")
            date_pmu = "".join(date.split("-")[::-1])
            
            if current_date_reunion != date_pmu:
                current_date_reunion = date_pmu
                current_programme = requests.get(f"https://online.turfinfo.api.pmu.fr/rest/client/65/programme/{date_pmu}/", headers=headers).json()
            numReunion = 0
    #         print(hippodrome)
            for reunion_pmu in current_programme["programme"]["reunions"]:
                if hippodrome in reunion_pmu["hippodrome"]["libelleCourt"]:
                    numReunion = reunion_pmu["numOfficiel"]
                    break
            
            if numReunion == 0:
                continue
            course = {"date": date, "idHippo": reunion.get("href").split("/")[-1], "Hippodrome": hippodrome, "lien": reunion.get("href")}
            course["numReunion"] = numReunion
            programme.append(course)
        
        return pd.DataFrame(programme)


def get_courses(reunions):
    courses_list = []  
    participants_list = []

    for i, row in reunions.iterrows():
        try:
            url = f"https://www.letrot.com/{row['lien']}/json"
            date_pmu = "".join(row["date"].split("-")[::-1])    
            r = requests.get(url, headers=headers)
            courses = r.json()
            for c in courses["course"]:
                if c["discipline"] == "Attelé":
                    course_id = row["date"].replace("-", "") + str(row["idHippo"]) + str(c["numCourse"])
                    courses_list.append({"date": row["date"], "id": course_id, "numReunion": row["numReunion"], "hippodrome": courses["nomHippodrome"], "idHippo": row["idHippo"],**c})
        except:
            continue
    return pd.DataFrame(courses_list)


def info_tableau_partant(courseId, date, idHippo, numCourse, numReunion, classement, data_type="training"):
    chevaux = []
    url = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/partants/tableau"
    r = requests.get(url, headers=headers)
    soup = bs(r.text, "html.parser")
    headers_table = soup.find("table", {"id": "result_table"}).find("thead").find("tr").find_all("th")
    table = soup.find("table", {"id": "result_table"}).find("tbody")
    rows = table.find_all("tr")
    
    url_arrivee = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/resultats/arrivee-definitive"
    r_arrivee = requests.get(url_arrivee, headers=headers)
    soup_arrivee = bs(r_arrivee.text, "html.parser")
    table_arrivee = soup_arrivee.find("table", {"id": "result_table"}).find("tbody")
    rows_arrivee = table_arrivee.find_all("tr")
    
    classement = {row.select("td")[1].text : row.select("td")[0].find("span", {"class": "bold"}).text for row in rows_arrivee}
    
    
    date_pmu = "".join(date.split("-")[::-1])  
    participants_pmu = requests.get(f"https://online.turfinfo.api.pmu.fr/rest/client/65/programme/{date_pmu}/R{numReunion}/C{numCourse}/participants", headers=headers)
    try:
        participants = participants_pmu.json()["participants"]
    except:
        raise Exception("probleme api pmu")
    participants = pd.json_normalize(participants, sep="_").to_dict(orient="records")
    participants_with_id = [dict(item, **{"id": courseId, "numReunion": numReunion}) for item in participants]    
    participants_pmu_df = pd.DataFrame(participants_with_id)
    
#     print(classement)
    
    for i,row in enumerate(rows):
            num = row.select("td")[0].find("span", {"class": "bold"}).text
            col = row.select("td")
            cheval = {}
            cheval["num"] = num
            cheval["nom"] = col[1].text

            cheval["numCoursePMU"] = f"R{numReunion}C{numCourse}"

            if data_type == "training":
                cheval["classement"] = classement[num]
            cheval["id"] = courseId
            cheval["date"] = date
            cheval["url"] = col[1].find("a").get("href")
            
            cheval.update(get_info_cheval(cheval["url"], date))

            cheval["fer"] = int(col[3].text) if col[3].text else 0
            cheval["firstTimeFer"] = True if col[3].find("div", {"class", "fer-first-time"}) else False
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
                cheval["avisTrainer"] =2

            cheval["music"] = list(filter(lambda x: "a" in x, col[9].text.replace("D", "0").replace("Ret", "0").replace("T", "0").split()))
            cheval["music"] = list(map(lambda x: x[0], cheval["music"]))

            cheval["music"] = list(filter(lambda x: x.isnumeric(), cheval["music"]))

            cheval["music"] = list(map(int, cheval["music"]))
            
            cheval["nbDiscalifieMusic"] = cheval["music"].count(0)
            cheval["nbVictoireMusic"] = cheval["music"].count(1)
            cheval["nbPlaceMusic"] = sum(map(lambda x : x <=3 and x > 0,cheval["music"]))

            if len(cheval["music"]) < 4:
                raise ValueError("not enough data")
            
            cheval["nbArrivé"] = len(cheval["music"]) - cheval["music"].count(0)
            cheval["lastPerf"] = cheval["music"][0] if cheval["nbArrivé"] else 0

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

            chevaux.append(cheval)
    combined = pd.merge(pd.DataFrame(chevaux), participants_pmu_df, how="left", left_on = ["id", "nom"], right_on = ["id", "nom"])
    return combined


def make_df_info_couple(courseId, date, idHippo, numCourse):
    couple_info = []

    date_datetime = datetime.date.fromisoformat(date)

    d = datetime.timedelta(days=1)
    d2 = datetime.timedelta(days=365)

    date_arrive = (date_datetime - d).strftime("%d-%m-%Y").replace("-", "%2F")
    date_depart = (date_datetime - d2).strftime("%d-%m-%Y").replace("-", "%2F")
    
    url = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/partants/couples/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
    r = requests.get(url, headers=headers)
    dic_json = r.json()
    data = dic_json["data"]

    data_sorted = sorted(data, key=lambda x: x["numero"])
    for couple in data_sorted:
        cheval = {}
        
        cheval["nbCourseCouple"] = bs(couple["nbre_courses"], "html.parser").find("div").text
        cheval["nbVictoiresCouple"] = bs(couple["nbre_victoires"], "html.parser").find("div").text
        cheval["nb2emeCouple"] = bs(couple["nbre_2eme"], "html.parser").find("div").text
        cheval["nb3emeCouple"] = bs(couple["nbre_3eme"], "html.parser").find("div").text
        cheval["txReussiteCouple"] = couple["taux_reussite_sort"]
        cheval["nonPartant"] = couple["nonPartant"]
        couple_info.append(cheval)
    return pd.DataFrame(couple_info)


def make_df_info_tandems(courseId, date, idHippo, numCourse):
    tandem_info = []

    date_datetime = datetime.date.fromisoformat(date)

    d = datetime.timedelta(days=1)
    d2 = datetime.timedelta(days=365)

    date_arrive = (date_datetime - d).strftime("%d-%m-%Y").replace("-", "%2F")
    date_depart = (date_datetime - d2).strftime("%d-%m-%Y").replace("-", "%2F")
    
    url = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/partants/tandems/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
    r = requests.get(url, headers=headers)
    dic_json = r.json()
    data = dic_json["data"]

    data_sorted = sorted(data, key=lambda x: x["numero"])
    for tandem in data_sorted:
        cheval = {}
        
        cheval["nbCourseTandem"] = bs(tandem["nbre_courses"], "html.parser").find("div").text
        cheval["nbVictoiresTandem"] = bs(tandem["nbre_victoires"], "html.parser").find("div").text
        cheval["nb2emeTandem"] = bs(tandem["nbre_2eme"], "html.parser").find("div").text
        cheval["nb3emeTandem"] = bs(tandem["nbre_3eme"], "html.parser").find("div").text
        cheval["txReussiteTandem"] = tandem["taux_reussite_sort"]
        tandem_info.append(cheval)
    return pd.DataFrame(tandem_info)

def make_df_info_entraineur(courseId, date, idHippo, numCourse):
    trainer_info = []

    date_datetime = datetime.date.fromisoformat(date)

    d = datetime.timedelta(days=1)
    d2 = datetime.timedelta(days=365)

    date_arrive = (date_datetime - d).strftime("%d-%m-%Y").replace("-", "%2F")
    date_depart = (date_datetime - d2).strftime("%d-%m-%Y").replace("-", "%2F")
    
    url = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/partants/entraineurs/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
    r = requests.get(url, headers=headers)
    dic_json = r.json()
    data = dic_json["data"]

    data_sorted = sorted(data, key=lambda x: x["numero"])
    for trainer in data_sorted:
        cheval = {}
        
        cheval["nbCourseTrainer"] = bs(trainer["nbre_courses"], "html.parser").find("div").text
        cheval["nbVictoiresTrainer"] = bs(trainer["nbre_victoires"], "html.parser").find("div").text
        cheval["nb2emeTrainer"] = bs(trainer["nbre_2eme"], "html.parser").find("div").text
        cheval["nb3emeTrainer"] = bs(trainer["nbre_3eme"], "html.parser").find("div").text
        cheval["txReussiteTrainer"] = trainer["taux_reussite_sort"]
        trainer_info.append(cheval)
    return pd.DataFrame(trainer_info)

def make_df_info_driver(courseId, date, idHippo, numCourse):
    driver_info = []

    date_datetime = datetime.date.fromisoformat(date)

    d = datetime.timedelta(days=1)
    d2 = datetime.timedelta(days=365)

    date_arrive = (date_datetime - d).strftime("%d-%m-%Y").replace("-", "%2F")
    date_depart = (date_datetime - d2).strftime("%d-%m-%Y").replace("-", "%2F")
    
    url = f"https://www.letrot.com/stats/fiche-course/{date}/{idHippo}/{numCourse}/partants/drivers/paginate?datepicker_du={date_depart}&datepicker_au={date_arrive}"
    r = requests.get(url, headers=headers)
    dic_json = r.json()
    data = dic_json["data"]

    data_sorted = sorted(data, key=lambda x: x["numero"])
    for driver in data_sorted:
        cheval = {}
        
        cheval["nbCourseDriver"] = bs(driver["nbre_courses"], "html.parser").find("div").text
        cheval["nbVictoiresDriver"] = bs(driver["nbre_victoires"], "html.parser").find("div").text
        cheval["nb2emeDriver"] = bs(driver["nbre_2eme"], "html.parser").find("div").text
        cheval["nb3emeDriver"] = bs(driver["nbre_3eme"], "html.parser").find("div").text
        cheval["txReussiteDriver"] = driver["taux_reussite_sort"]
        driver_info.append(cheval)
    return pd.DataFrame(driver_info)




def get_info_cheval(url, date):
    r = requests.get(url + "-paginate-2", headers=headers)
    date_debut = datetime.date.fromisoformat(date)
    jsoned = r.json()["data"]

    info_dict = {}

    for c in jsoned:
        c["dateCourse"] = datetime.date.fromisoformat(c["dateCourseRaw"])
        c["categorie"] = bs(c["categorie"], "html.parser").find("span").text
        reduction = bs(c["reduction"], "html.parser").span.text
        reduction = reduction.replace("'", "").replace('\"', "")

        reduction_min = int(str(reduction)[0])
        reduction_sec = int(str(reduction)[1:3])
        reduction_ssec = int(str(reduction)[3])

        c["reduction"] = reduction_min*60*10 + reduction_sec*10 + reduction_ssec

        # c["recordAbs"] = list(map(int, reduction.text.replace(reduction.span.text, "").replace("\'", '"').split('"')))
        # c["recordAbs"] = c["recordAbs"][0] * 10 * 60 + c["recordAbs"][1] * 10 + c["recordAbs"][2]
    
    filtered = list(filter(lambda x: x["dateCourse"] < date_debut and x["specialite"] == "A", jsoned))
    
    filtered_tps = list(filter(lambda x: x["reduction"] < 1200, filtered))

    tps = [x["reduction"] for x in filtered_tps]

    info_dict["meanReduction"] = np.mean(tps)
    info_dict["medianReduction"] = np.median(tps)
    info_dict["maxReduction"] = max(tps)
    info_dict["minReduction"] = min(tps)

    info_dict["timeSinceRecord"] = next(((date_debut - item["dateCourse"]).days for item in filtered_tps if item["reduction"] == info_dict["minReduction"]), 365)

    info_dict["tpsLastRace"] = (date_debut - filtered[0]["dateCourse"]).days
    
    info_dict["last_race_dist"] = int(filtered[0]["distance"].replace(" ", ""))

    return info_dict


def partants(course, file="data.csv", save_time=60):
    last_time_saved = time.time()

    not_saved = None


    for i, course in course.iterrows():
        url = f"https://www.letrot.com/stats/fiche-course/{course['date']}/{course['idHippo']}/{course['numCourse']}"
        url_tableau_partant = url + "/partants/tableau"
        url_cheval = url + "/partants/chevaux"
        try:
            dict_tableau_partant = info_tableau_partant(course['id'],course['date'], course['idHippo'],course['numCourse'], course["numReunion"], course["classement"])
            dict_couple = make_df_info_couple(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_trainer = make_df_info_entraineur(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_tandem = make_df_info_tandems(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_driver = make_df_info_driver(course['id'],course['date'], course['idHippo'],course['numCourse'])
        except Exception:
            continue
        
#         combined = dict_tableau_partant.join(dict_couple)
        
        combined = pd.concat([dict_tableau_partant, dict_couple, dict_trainer, dict_tandem, dict_driver], axis=1)
        
        # combined = combined.reindex(sorted(combined.columns), axis=1)


        if not isinstance(not_saved, pd.DataFrame):
            not_saved = combined
        else:
            not_saved = pd.concat([not_saved, combined])

        if os.path.isfile(file):
            if time.time() - last_time_saved > save_time:

                already_saved = pd.read_csv(file)
                already_saved = pd.concat([already_saved, not_saved])
                already_saved.to_csv(file, index=False)
                last_time_saved = time.time()

                del already_saved
                not_saved = None
        else:
            not_saved.to_csv(file, index=False)

    if os.path.isfile(file):
        already_saved = pd.read_csv(file)
        already_saved = pd.concat([already_saved, not_saved])
        already_saved.to_csv(file, index=False)
    else:
        not_saved.to_csv(file, index=False)

def get_board(courses):
    tableau = pd.DataFrame()
    for i, course in courses.iterrows():
        url = f"https://www.letrot.com/stats/fiche-course/{course['date']}/{course['idHippo']}/{course['numCourse']}"
        try:
            dict_tableau_partant = info_tableau_partant(course['id'],course['date'], course['idHippo'],course['numCourse'], course["numReunion"], course["classement"], "predictions")
            dict_couple = make_df_info_couple(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_trainer = make_df_info_entraineur(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_tandem = make_df_info_tandems(course['id'],course['date'], course['idHippo'],course['numCourse'])
            dict_driver = make_df_info_driver(course['id'],course['date'], course['idHippo'],course['numCourse'])
        except:
            continue
        
        combined = pd.concat([dict_tableau_partant, dict_couple, dict_trainer, dict_tandem, dict_driver], axis=1)
        
        tableau = pd.concat([tableau, combined])

    return tableau