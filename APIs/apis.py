# Flask things.
from flask import Flask, jsonify, request, Response
# CORS to allow cross-origin requests. To allow other domains to access the APIs.
from flask_cors import CORS

# Escraping things.
from bs4 import BeautifulSoup
from requests import get
from re import compile, IGNORECASE
# The schedule page is dynamic, it expects JS, otherwise it doesn't load.
# We need to use Selenium to scrape it.
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# Multithreading things.
from threading import Thread
from time import sleep
from sys import exit

# Settings things.
from subprocess import Popen, PIPE

# When things get serious, types come in. To keep the code clean and readable.
from typing import List, Dict, Optional, Union

# To manipulate times objects.
from datetime import datetime

# Returns [{pole_name: pole_link}] if the request is successful, otherwise None.
def fetch_poles_data() -> Optional[List[Dict[str, str]]]:
    URL = "https://aule.webhost1.unipi.it/poli-didattici/"
    page = ""
    try:
        page = get(URL)
        print("Error in web request to fetch poles data.")
    except:
        return None
    if page.status_code != 200:
        print("Error in web request to fetch poles data. Wrong status code.")
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
driver = None
# To run in a dedicated thread.
# Periodically fetches all the schedules pages, to avoid doing it when an API request is made.
def get_all_schedules_pages_thread() -> None:

    global schedule_pages, driver

    poles = fetch_poles_data()
    if poles is None:
        error_msg = "Error in fetching poles data by the dedicated thread."
        print(error_msg)
        # To kill all the threads.
        exit(1)
    
    urls = []
    for pole in poles:
        urls.append(pole[list(pole.keys())[0]])
    
    while True:
        for url in urls:
            try:
                driver.get(url)
            except:
                error_msg = f"Error in fetching poles data of the page (by the dedicated thread): {url}."
                print(error_msg)
                # To kill all the threads.
                exit(1)
            # JS is loading, wait 1 seconds.
            sleep(1)
            page_source = driver.page_source
            schedule_pages[url] = str(page_source)

        # To avoid overloading the servers, sleep 15 minutes.
        sleep(60 * 15)

# Returns an "infos" list, with the following structure:
# [
# {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
#  ...
# ]
# Where schedule is all the plain text in the <a> tag as str.
# url is the pole's URL.
def escrape_page(url) -> List[Dict[str, Union[str, List[str]]]]:

    soup = BeautifulSoup(schedule_pages[url], 'html.parser')

    # The page is divided in two parts (tables).
    # The first one is a table with as rows the classrooms, each table row has a classroom's name.
    # The second one is a table with as rows the schedules.

    # The schedules could be from 0 to n. 0 means the classroom is free all day.
    # Since the content of interest is divided in two tables, we need to iterate over both of them and match the classrooms with the schedules manually.

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
        # Sanitizing the classroom name.
        classroom = row.text.split("(")[0].strip()
        classrooms.append(classroom)

    # Getting second table's data.
    second_table = soup.find_all("td", class_=["fc-time-area fc-widget-content"])[0]
    all_schedules_a = second_table.find_all("a")
    rows_second = second_table.find_all("table")[0].find_all("tr")

    # DANGER IF THE TABLES ARE NOT IN SYNC.
    if len(rows_first) != len(rows_second):
        error_msg = "The tables are not in sync."
        print(error_msg)
        # To kill all the threads.
        exit(1)

    # Getting rows' ids, used to join the classrooms with the schedules.
    # data-resource-id is an attribute of the <tr> tag.
    rows_ids = []
    for row in rows_second:
        rows_ids.append(row['data-resource-id'])

    # Getting schedules.
    # list_of_schedules is the final list.
    list_of_schedules = []
    current_row_id = ""
    # current_row_schedules is a TEMPORARY list of schedules of the current row.
    current_row_schedules = []
    # Adding a None to the end to process the last row, otherwise it will be skipped wrongly.
    for schedule_a in list(all_schedules_a) + [None]:

        if schedule_a is None:
            # Last iteration.
            # current_row_schedules is not empty, setted in the previous iteration.
            info = {}
            info[current_row_id] = current_row_schedules.copy()

            list_of_schedules.append(info)

            current_row_schedules.clear()

            break

        schedule = schedule_a.text

        # We need to navigate the DOM to get the parent <tr> tag and the associated data-resource-id.
        # data-resource-id is an attribute of the <tr> tag.
        tr_parent = schedule_a.find_parent("tr")
        tr_parent_id = tr_parent['data-resource-id']

        if current_row_id == "":
            # First iteration.
            current_row_id = tr_parent_id
            # The process of the first row is skipped, balanced by the last iteration.
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
        # Initializing the list of schedules.
        info[rows_ids[i]] = []
        for schedule in list_of_schedules:
            if rows_ids[i] in schedule:
                info[rows_ids[i]] = schedule[rows_ids[i]]
                break

        infos.append(info)

    return infos

# INFOS ARG STRCTURE (TO BE GOT FROM escrape_page):
# [
# {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
#  ...
# ]
# Where schedule is all the plain text in the <a> tag as str.
# time is the time to check if the classrooms are free, by default it's the current time.
# It has been made generic for future uses.
# RETURNS AN INFOS COPY WITH THE CLASSROOMS THAT ARE FREE AT THE GIVEN TIME + THE NEXT EVENT START TIME.
def process_datas(infos, time = None) -> List[Dict[str, Union[str, List[str]]]]:

    if time is None:
        time = datetime.now()

    if datetime.now().day != time.day or datetime.now().month != time.month or datetime.now().year != time.year:
        # Exception raised since it's probably depends from this project's development mistake.
        error_msg = "The time must be in the today's day."
        print(error_msg)
        raise Exception(error_msg)

    # Search all times in HH:MM format.
    # To match start and end times of each schedule.
    pattern = r'(?:[01]\d|2[0-3]):[0-5]\d'
    regex = compile(pattern, IGNORECASE)

    infos_to_keep_with_next_start_time = []
    for info in infos:
        for key in info:
            # Skipping the classroom name.
            if key == "Classroom":
                continue

            # Key is the row's dynamic id.
            schedules = info[key]
            # to_add is a flag to check if the classroom is free at the given time and needs to be added to the final list.
            to_add = False
            if len(schedules) == 0:
                # The classroom is free all day.
                to_add = True

            # Checking if the classroom is free at the given time, by processing the schedules.
            for i in range(len(schedules)):
                schedule = schedules[i]

                matches = regex.findall(schedule)
                if len(matches) != 2:
                    # DANGER:
                    # The schedule is not in the correct format.
                    # More than 2 times (start time / end time) found.
                    # To be sure, I DO NOT INCLUDE THIS Classroom.
                    print(f"Skipping ABNORMAL schedule: {schedule}.")
                    print("It's matches are: ", matches, ".")
                    to_add = False
                    break

                start_time = datetime.strptime(matches[0], "%H:%M")
                end_time = datetime.strptime(matches[1], "%H:%M")

                today = datetime.now()
                start_time_specific_hour = datetime(
                    year=today.year,
                    month=today.month,
                    day=today.day,
                    hour=start_time.hour,
                    minute=start_time.minute,
                    second=0
                )
                end_time_specific_hour = datetime(
                    year=today.year,
                    month=today.month,
                    day=today.day,
                    hour=end_time.hour,
                    minute=end_time.minute,
                    second=0
                )
                
                if start_time_specific_hour <= time <= end_time_specific_hour:
                    # The classroom is busy.
                    to_add = False
                    break
                else:
                    to_add = True
                    # Assuming that the classroom is free now, but it still could be busy, we need to check the other schedules.

            if to_add:
                new_info = info.copy()

                next_start_times = []
                # Find the next start time.
                for i in range(len(schedules)):
                    schedule = schedules[i]

                    matches = regex.findall(schedule)

                    start_time = datetime.strptime(matches[0], "%H:%M")

                    today = datetime.now()
                    start_time = datetime(
                        year=today.year,
                        month=today.month,
                        day=today.day,
                        hour=start_time.hour,
                        minute=start_time.minute,
                        second=0
                    )

                    if time < start_time:
                        next_start_times.append(start_time)
                    else:
                        # Exclude the schedules that are already passed.
                        pass

                # There are next start times.
                if len(next_start_times) > 0:

                    # Getting the next start time (the minimum one).
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

# Checks if the given pole name is valid.
# Returns the sanitized pole name if it's valid, otherwise an error response to be returned from the caller.
def check_given_pole_validity(pole_name) -> Union[Response, str]:

    if pole_name is None:
        return jsonify({"message": "Pole name is required."})
    
    pole_name = pole_name.lower().strip()

    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    
    if pole_name not in [list(pole.keys())[0].lower() for pole in poles]:
        return jsonify({"message": "Invalid pole name."})
    
    return pole_name

# Returns the pole URL given the pole name.
# If the pole name is not valid, returns an error response to be returned from the caller.
def get_pole_url(pole_name) -> Union[Response, str]:

    pole_name = check_given_pole_validity(pole_name)
    if isinstance(pole_name, Response):
        # pole_name is a Response (jsonify).
        return pole_name

    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    
    pole_url = ""
    for pole in poles:
        if list(pole.keys())[0].lower() == pole_name:
            pole_url = pole[list(pole.keys())[0]]
            break
    
    return pole_url

###########################################     APIs        ###########################################

# Flask setup.
app = Flask(__name__)
CORS(app)

# Used to list all the poles in the client.
@app.route('/api/poles_data', methods = ['GET'])
# Returns {"poles_data": [{pole_name: pole_link}]}.
def get_poles_data():

    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    
    return jsonify({"poles_data": poles})

@app.route('/api/all_rooms_given_pole', methods = ['GET'])
# Returns all the rooms given the pole name.
# {
#   "all_rooms": [
#       {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...]},
#       ...
#   ]
# }
# Where schedule is all the plain text in the <a> tag as str.
def get_all_rooms_given_pole():
    pole_name = request.args.get('pole_name')

    pole_url = get_pole_url(pole_name)
    if isinstance(pole_url, Response):
        # pole_url is a Response (jsonify).
        return pole_url

    infos = escrape_page(pole_url)

    return jsonify({"all_rooms": infos})
    
@app.route('/api/free_classrooms_given_pole', methods = ['GET'])
# Returns all the free classrooms given the pole name.
# It's like get_all_rooms_given_pole but with ONLY the classrooms that are free at the given time + the next event start time.
# {
#   "free_classrooms": [
#       {"Classroom": classroom_name, RESOURCE_ID_ROW_DYNAMIC: [schedule1, schedule2, ...], "NextStartTime": next_start_time},
#       ...
#   ]
# }
# Where schedule is all the plain text in the <a> tag as str.
# NextStartTime is optional (for example, absent if the classroom is free all day).
def get_free_classrooms_given_pole():
    pole_name = request.args.get('pole_name')
    
    pole_url = get_pole_url(pole_name)
    if isinstance(pole_url, Response):
        # pole_url is a Response (jsonify).
        return pole_url

    infos = escrape_page(pole_url)
    infos_to_keep_with_next_start_time = process_datas(infos)

    return jsonify({"free_classrooms": infos_to_keep_with_next_start_time})

def main():

    global driver, schedule_pages

    command = Popen("uname", stdout = PIPE, shell = True)
    output, error = command.communicate()
    output = output.decode("utf-8").strip().lower()

    # Chrome driver path.
    chrome_driver_path = ""
    if "darwin" in output:
        # On my Mac.

        chrome_driver_path = '/Users/juliusnixi/chromedriver-mac-arm64/chromedriver'

    elif "linux" in output:
        # On my Ubuntu ARM64 server.

        # sudo apt install chromium-chromedriver

        from shutil import which
        chrome_driver_path = which("chromedriver")

    # Chrome options.
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    service = Service(chrome_driver_path)

    # Selenium driver setup.
    driver = webdriver.Chrome(service = service, options = chrome_options)

    # Before serving the APIs, we need to fetch all the schedules pages with a dedicated thread.
    thread = Thread(target = get_all_schedules_pages_thread)
    thread.start()
    # Wait for it to collect all the schedules pages.
    # (16 pages * 1 seconds to load JS).
    total_time = 16
    for i in range(total_time):
        print(f"Waiting for schedules pages to be fetched... {total_time - i} seconds left.")
        sleep(1)
    print("Schedules pages fetched.")

# Main entry point of the application.
if __name__ == '__main__':

    main()

    # In development, use Flask:
    app.run(debug = True, port = 8080, use_reloader = False)

    # In production, use Gunicorn:
    # pip install gunicorn
    # Apache proxy forwards the requests from 54321 port to Gunicorn on 8000 port.
    # python3 -m gunicorn --bind 127.0.0.1:8000 wsgi:app
    # HTTPS required on GitHub Pages.
