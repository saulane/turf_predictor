import src.module as module
from src.courses import Programme, Courses

from src.predictions import Predicion

import datetime
import os
import sys
import pandas as pd
import asyncio
import numpy as np

def kelly(p,b):
    if b > 0:
        return (p-(1/b))/(1-1/b)
    else:
        return 0

if __name__ == "__main__":
    args = sys.argv

    delta_d = 0

    if "-d" in args:
        delta_d = int(args[args.index("-d") + 1])

    today = datetime.date.today() + datetime.timedelta(days=delta_d)
    yesterday = today - datetime.timedelta(days=1)

    today_str = today.strftime("%d-%m-%Y")

    yesterday_str = yesterday.strftime("%d-%m-%Y")
    if not os.path.exists(f"programmes/{today_str}.csv"):
        programme = Programme(yesterday_str, today_str)
        courses = Courses(programme).courses
        courses.to_csv(f"programmes/{today_str}.csv")
    else:
        courses = pd.read_csv(f"programmes/{today_str}.csv", index_col=0)

    courses.sort_values(by="heureCourse", inplace=True)

    today = datetime.date.today().strftime("%Y-%m-%d")

    courses["heureCourse"] = pd.to_datetime(today + " " + courses["heureCourse"], format='%Y-%m-%d %H:%M')
    if len(args) > 1 and "-d" not in args:
        if args[1] == "next":
            tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > (datetime.datetime.now() - datetime.timedelta(minutes=15))])
        elif args[1] == "one":
            tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > (datetime.datetime.now() - datetime.timedelta(minutes=15))].iloc[:2])
        elif args[1] == "-n":
            tableau_partant = module.get_df_partants(courses[courses["heureCourse"] > (datetime.datetime.now() - datetime.timedelta(minutes=15))].iloc[:int(args[2])])
    else:
        tableau_partant = module.get_df_partants(courses)

    tableau_partant = tableau_partant.groupby("id").filter(lambda x: len(x) > 8)
    tableau_partant = tableau_partant.groupby("id").filter(lambda x: x["dernierRapportDirect_rapport"].all())
    pred = Predicion(tableau_partant)

    choice,proba,odds = pred.predict()
    

    sorted_proba = np.argsort(proba)

    nom = tableau_partant["nom"].to_numpy()
    num = tableau_partant["num"].to_numpy()
  
    for i in range(len(choice)):
        if np.sum(proba[i]) > 0.8:
            try:
                SR = (proba[i, :] - (1/odds[i, :])) / np.sqrt(proba[i, :] * (1-proba[i, :]))

                sr_c = np.argmax(SR)
                sr_c_p = proba[i, sr_c]
                sr_c_o = odds[i, sr_c]
                numcourses = tableau_partant["numCoursePMU"].unique()

                cur_course = tableau_partant[tableau_partant["numCoursePMU"] == numcourses[i]]
                # print(cur_course)
                cheval = cur_course[cur_course["num"] == str(choice[i])].iloc[0]
                # print(cheval)
                # print(np.argsort(proba[i]))

                expe_pos = np.max(proba[i]) * cheval["dernierRapportDirect_rapport"] - (1-np.max(proba[i]))

                place = [sorted_proba[i,-1] +1, sorted_proba[i,-2] +1, sorted_proba[i,-3] +1, sorted_proba[i,-4] +1, sorted_proba[i,-5] +1]

                c = sorted_proba[i,-1]

                should_bet = expe_pos > 0.4

                if sr_c_o > 0:
                    kelfrac = kelly(np.mean([1/sr_c_o, sr_c_p]), sr_c_o) / 5
                else:
                    kelfrac = 0
                print(cheval["heureCourse"],numcourses[i],"=>",cheval["nom"], c+1,f"(SR: {sr_c+1}, {round(sr_c_p, 3)}, {round(kelfrac, 3)})","|",round(proba[i, c], 3), should_bet, place)
            except Exception as e:
                continue