# Flask things.
from flask import Flask, jsonify, request
# CORS to allow cross-origin requests.
from flask_cors import CORS

# Escraping things.
from bs4 import BeautifulSoup
from requests import get
from re import compile, IGNORECASE
# The schedule page is dynamic, it expects JS otherwise it doesn't load.
# We need to use Selenium to scrape it.
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Multithreading things.
from threading import Thread
from time import sleep

# When things get serious, types come in.
# To keep the code clean and readable.
from typing import List, Dict, Optional, Union

from datetime import datetime

# Chrome options.
chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--no-sandbox")

# Chrome driver path.
chrome_driver_path = '/Users/juliusnixi/chromedriver-mac-arm64/chromedriver'
service = Service(chrome_driver_path)

# Selenium driver setup.
driver = webdriver.Chrome(service = service, options = chrome_options)

# Flask setup.
app = Flask(__name__)
CORS(app)

# Returns [{pole_name: pole_link}].
def fetch_poles_data() -> Optional[List[Dict[str, str]]]:
    URL = "https://aule.webhost1.unipi.it/poli-didattici/"
    page = get(URL)
    if page.status_code != 200:
        return None
    
    soup = BeautifulSoup(page.content, 'html.parser')

    box = soup.find('div', class_='entry-content')

    poles: List[Dict[str, str]] = []
    for pole in box.find_all('li'):
        pole_name = pole.text
        pole_link = pole.find('a')['href']
        pole = {pole_name: pole_link}
        poles.append(pole)

    return poles

# {pole_link: page_source}.
schedule_pages: Dict[str, str] = {}
# To run in a dedicated thread.
# Periodically fetches all the schedules pages, to avoid doing it when an API request is made.
def get_all_schedules_pages_thread() -> None:

    poles = fetch_poles_data()
    if poles is None:
        raise Exception("Error in fetching poles data.")
    
    urls = []
    for pole in poles:
        urls.append(pole[list(pole.keys())[0]])
    
    while True:
        for url in urls:
            driver.get(url)
            # JS is loading.
            sleep(2)
            page_source = driver.page_source
            schedule_pages[url] = str(page_source)

        # To avoid overloading the server, sleep 30 minutes.
        sleep(60 * 30)

# [
# {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
#  ...
# ] 
def escrape_page(url) -> List[Dict[str, Union[str, List[str]]]]:

    soup = BeautifulSoup(schedule_pages[url], 'html.parser')

    # The page is divided in two parts (tables).
    # The first one is a table with as rows the classrooms, each table row has a classroom's name.
    # The second one is a table with as rows the schedules.
    # The schedules could be from 0 to n. 0 means the classroom is free all day.
    # Since the content of interest is divided in two tables, we need to iterate over both of them and match the classrooms with the schedules.

    # ATTENTION: BE CAREFUL, NOT ALL POLES PAGE HAVE THE SAME STRUCTURE, SO BE AS GENERIC AS POSSIBLE.

    # [
    # {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
    #  ...
    # ]
    # Where schedule is all the plain text in the <a> tag as str.
    infos: List[Dict[str, Union[str, List[str]]]] = []

    # Iterating over the first table to get the classrooms.
    first_table = soup.find_all("td", class_=["fc-resource-area fc-widget-content"])[0]
    rows_first = first_table.find_all("td", class_=["fc-widget-content"])

    # List of classrooms' names as str.
    classrooms: List[str] = []
    for row in rows_first:
        classroom = row.text.replace(" ", "").strip()
        classrooms.append(classroom)

    # Getting second table's data.
    second_table = soup.find_all("td", class_=["fc-time-area fc-widget-content"])[0]
    all_schedules_a = second_table.find_all("a")
    rows_second = second_table.find_all("table")[0].find_all("tr")

    if len(rows_first) != len(rows_second):
        raise Exception("The tables are not in sync.")

    # Getting rows' ids, used to join the classrooms with the schedules.
    # data-resource-id is an attribute of the <tr> tag.
    rows_ids = []
    for row in rows_second:
        rows_ids.append(row['data-resource-id'])

    # Getting schedules.
    list_of_schedules = []
    current_row_id = ""
    current_row_schedules = []
    for schedule_a in all_schedules_a:
        schedule = schedule_a.text

        tr_parent = schedule_a.find_parent("tr")
        tr_parent_id = tr_parent['data-resource-id']

        if current_row_id == "":
            # First iteration.
            current_row_id = tr_parent_id
        else:
            if current_row_id != tr_parent_id:
                # New row's id.
                info = {}
                info[current_row_id] = current_row_schedules.copy()
                list_of_schedules.append(info)

                current_row_schedules.clear()

                current_row_id = tr_parent_id

        current_row_schedules.append(schedule)

    # Joining all the infos.
    for i in range(len(list(rows_second))):
        row = rows_second[i]

        info = {}
        info["Classroom"] = classrooms[i]
        info[rows_ids[i]] = []
        for schedule in list_of_schedules:
            if rows_ids[i] in schedule:
                info[rows_ids[i]] = schedule[rows_ids[i]]
                break

        infos.append(info)

    return infos

# INFOS ARG:
# [
# {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
#  ...
# ] 
# RETURNS AN INFOS COPY WITH THE CLASSROOMS THAT ARE FREE AT THE GIVEN TIME + THE NEXT EVENT START TIME.
def process_datas(infos, time = None) -> List[Dict[str, Union[str, List[str]]]]:

    if time is None:
        time = datetime.now()

    if datetime.now().day != time.day or datetime.now().month != time.month or datetime.now().year != time.year:
        raise Exception("The time must be in the today's day.")

    # Search all times in HH:MM format.
    # To match start and end times.
    pattern = r'(?:[01]\d|2[0-3]):[0-5]\d'
    regex = compile(pattern, IGNORECASE)

    infos_to_keep_with_next_start_time = []
    for info in infos:
        for key in info:
            if key == "Classroom":
                continue
            schedules = info[key]
            to_add = False
            if len(schedules) == 0:
                # The classroom is free all day.
                to_add = True
            for i in range(len(schedules)):
                schedule = schedules[i]
                matches = regex.findall(schedule)
                if len(matches) != 2:
                    # DANGER
                    # The schedule is not in the correct format.
                    # To be sure, I DO NOT INCLUDE THIS Classroom.
                    print(f"Skipping ABNORMAL schedule: {schedule}.")
                    print("It's matches are: ", matches, ".")
                    to_add = False
                    break
                start_time = datetime.strptime(matches[0], "%H:%M")
                end_time = datetime.strptime(matches[1], "%H:%M")
                if start_time <= time <= end_time:
                    # The classroom is busy.
                    to_add = False
                    break
                else:
                    to_add = True
            if to_add:
                new_info = info.copy()
                next_start_times = []
                for i in range(len(schedules)):
                    schedule = schedules[i]
                    matches = regex.findall(schedule)
                    start_time = datetime.strptime(matches[0], "%H:%M")
                    # Exclude the schedules that are already passed.
                    if time > start_time:
                        next_start_times.append(start_time)
                if len(next_start_times) > 0:
                    next_start_time = min(next_start_times)
                    today = datetime.now()
                    today_specific_hour = datetime(
                        year=today.year,
                        month=today.month,
                        day=today.day,
                        hour=next_start_time.hour,
                        minute=next_start_time.minute,
                        second=0
                    )
                    new_info["NextStartTime"] = today_specific_hour.strftime('%d-%m-%Y %H:%M')
                infos_to_keep_with_next_start_time.append(new_info)
        
    return infos_to_keep_with_next_start_time



################ APIs ################

# Used to list all the poles in the client.
@app.route('/api/poles_data', methods = ['GET'])
# Returns {"poles_data": [{pole_name: pole_link}]}.
def get_poles_data():
    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    return jsonify({"poles_data": poles})

@app.route('/api/free_classrooms_given_pole', methods = ['GET'])
def get_free_classrooms_given_pole():
    pole_name = request.args.get('pole_name')

    if pole_name is None:
        return jsonify({"message": "Pole name is required."})
    
    pole_name = pole_name.lower()

    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    
    if pole_name not in [list(pole.keys())[0].lower() for pole in poles]:
        return jsonify({"message": "Invalid pole name."})
    
    pole_url = ""
    for pole in poles:
        if list(pole.keys())[0].lower() == pole_name:
            pole_url = pole[list(pole.keys())[0]]
            break

    infos = escrape_page(pole_url)
    infos_to_keep_with_next_start_time = process_datas(infos)

    return jsonify(infos_to_keep_with_next_start_time)

# Main entry point of the application.
if __name__ == '__main__':

    # Before serving the APIs, we need to fetch all the schedules pages.
    thread = Thread(target = get_all_schedules_pages_thread)
    thread.start()
    # Wait for it to collect all the schedules pages.
    # (16 pages * 2 seconds to load JS) + 8 seconds to be sure.
    total_time = 32 + 8
    for i in range(total_time):
        print(f"Waiting for schedules pages to be fetched... {total_time - i} seconds left.")
        sleep(1)
    print("Schedules pages fetched.")

    app.run(debug = True, port = 8080, use_reloader = False)
