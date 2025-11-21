# Escraping things.
from requests import get
from bs4 import BeautifulSoup
# The schedule page is dynamic, it expects JS, otherwise it doesn't load.
# We need to use Selenium to scrape it.
from selenium import webdriver
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

# When things get serious, types come in. To keep the code clean and readable.
from typing import List, Dict, Optional, Union

# Flask things.
from flask import Flask, jsonify, request
# CORS to allow cross-origin requests. To allow other domains to access the APIs.
from flask_cors import CORS

# To manipulate times objects.
from datetime import datetime

from time import sleep
from threading import Thread, Lock

# Platform checks.
from platform import platform
from os import environ

# Returns [{pole_name: pole_link}] if the request is successful, otherwise None.
def fetch_poles_data() -> Optional[List[Dict[str, str]]]:
    URL = "https://aule.webhost1.unipi.it/poli-didattici/"
    page = ""
    try:
        page = get(URL, timeout=15)
    except:
        print("Error in web request to fetch poles data.")
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

# From the pole link get with selenium the schedule page source content as str.
def selenium_get_schedule_page(pole_link, get_data_from_cache = True) -> Optional[str]:
    global src_schedules_page_cache
    if get_data_from_cache:
        with cache_lock:
            cached = src_schedules_page_cache.get(pole_link)
        if cached is not None:
            return cached

    # Chrome options.
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")

    driver = None
    try:
        service = ""
        if "linux" in str(platform()).lower():
            # Passing the path to the chromedriver to use it on my linux arm server.
            service = Service(environ.get("CHROMEDRIVER_PATH"))
        else:
            service = Service(ChromeDriverManager().install())

        # Selenium driver setup.
        driver = webdriver.Chrome(service = service, options = chrome_options)

        driver.get(pole_link)

        # Not beautiful but I cannot make it works in async way due to JS execution used to fill the page.
        sleep(5)

        page_source = str(driver.page_source)

        # Update cache.
        with cache_lock:
            src_schedules_page_cache[pole_link] = page_source

        return page_source
    except Exception as e:
        print(f"Selenium error for {pole_link}: {e}")
        return None
    finally:
        try:
            if driver is not None:
                driver.quit()
        except:
            pass

# Returns an "infos" list, with the following structure:
# [
#   {"Classroom": "classroom_name", "RESOURCE_ID_ROW_DYNAMIC": ["schedule1", "schedule2", ...]},
#   ...
# ]
# Where scheduleN is all the plain text in the <a> tag as str with each <br> row delimited by an '|'.
def escrape_schedule_page(schedule_page_source) -> Optional[List[Dict[str, Union[str, List[str]]]]]:

    soup = BeautifulSoup(schedule_page_source, 'html.parser')

    # The page is divided in two parts (tables).
    # The first one is a table with as rows the classrooms, each table row has a classroom's name.
    # The second one is a table with as rows the schedules.

    # The schedules could be from 0 to n. 0 means the classroom is free all day.
    # Since the content of interest is divided in two tables, we need to iterate over both of them and match the classrooms with the schedules manually.

    # ATTENTION: BE CAREFUL, NOT ALL POLES PAGE HAVE THE SAME STRUCTURE, SO BE AS GENERIC AS POSSIBLE.

    # [
    #   {"Classroom": "classroom_name", "RESOURCE_ID_ROW_DYNAMIC": ["schedule1", "schedule2", ...]},
    #   ...
    # ]
    # Where scheduleN is all the plain text in the <a> tag as str with each <br> row delimited by an '|'.
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
    parsed_a = ""
    all_parsed_a = []
    for a in all_schedules_a:
        spans = a.find_all("span")
        for s in spans:
            brs = s.find_all("br")
            if len(brs) > 0:
                content = s.decode_contents()
                lines = [line.strip().replace("\t", "") for line in content.split("<br/>") if line.strip()]
                parsed_a += "|".join(lines)
            else:
                parsed_a += s.text + "|"

        # Check for missing <br> after the time start - time end.
        # Sometimes it happens.
        # E.g: 08:30 - 10:00Lettorato arabo
        if not '|' in parsed_a or "Proseguimento" in parsed_a:
            print(str(a), end="\n\n\n")
            print(parsed_a)
            # Splitting manually.
            #time = parsed_a[0:13]
            #parsed_a = parsed_a[13:]
            #parsed_a = time + "|" + parsed_a
            # Missing the parsing of the rest of the string, but I don't know how to do it, since there are not delimiters.

        all_parsed_a.append(parsed_a)
        parsed_a = ""
    rows_second = second_table.find_all("table")[0].find_all("tr")

    # DANGER IF THE TABLES ARE NOT IN SYNC.
    if len(rows_first) != len(rows_second):
        return None

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

    # Replacing unparsed a datas with parsed one.
    unparsed_tmp = [e.replace("|", "") for e in all_parsed_a]
    for classroom in infos:
        rsid = list(classroom.keys())[1]
        schedules = classroom[rsid]
        for counter in range(len(schedules)):
            cu = 0
            for u in unparsed_tmp:
                if schedules[counter].startswith(u):
                    schedules[counter] = all_parsed_a[cu]
                    break
                cu += 1

    return infos

# INFOS ARG STRCTURE (TO BE GOT FROM escrape_schedule_page):
# [
#   {"Classroom": "classroom_name", "RESOURCE_ID_ROW_DYNAMIC": ["schedule1", "schedule2", ...]},
#   ...
# ]
# Where scheduleN is all the plain text in the <a> tag as str with each <br> row delimited by an '|'.
# Returns:
# [
#   {"classroom_name": "next_schedule_start_hour"},
#   ...
# ]
def get_free_classrooms_now(infos) -> List[Dict[str, str]]:

    # Now.
    time = datetime.now()

    year = time.year
    month = time.month
    day = time.day
    minute = time.minute
    hour = time.hour

    frees = []

    for classroom in infos:
        schedules = classroom[list(classroom.keys())[1]]

        # Detecting free classrooms.
        free = True
        for schedule in schedules:
            timestartend = schedule.split("|")[0]

            timestart = datetime.strptime(timestartend.split("-")[0].strip(), "%H:%M")
            timeend = datetime.strptime(timestartend.split("-")[1].strip(), "%H:%M")

            timestart = datetime(year=year, month=month, day=day, hour=timestart.hour, minute=timestart.minute)
            timeend = datetime(year=year, month=month, day=day, hour=timeend.hour, minute=timeend.minute)

            if timestart <= time <= timeend:
                free = False
                break

        # Detecting next schedule start time.
        if free:
            timesstarts = []
            for schedule in schedules:
                timestartend = schedule.split("|")[0]

                timestart = datetime.strptime(timestartend.split("-")[0].strip(), "%H:%M")
                timestart = datetime(year=year, month=month, day=day, hour=timestart.hour, minute=timestart.minute)

                timesstarts.append(timestart)

            sorted_times = sorted(timesstarts)

            nextstart = ""
            for timec in sorted_times:
                if time <= timec:
                    nextstart = timec
                    break

            if nextstart == "":
                nextstart = None
            else:
                nextstart = nextstart.strftime("%H:%M")

            frees.append({classroom["Classroom"]: nextstart})

    return frees

###########################################     APIs        ###########################################

# Flask setup.
app = Flask(__name__)
CORS(app)

# Used to list all the poles in the client.
@app.route('/api/poles_data', methods = ['GET'])
# Returns {"poles_data": [{"pole_name": "pole_link"}]}.
def get_poles_data():

    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    
    return jsonify({"poles_data": poles})

@app.route('/api/get_all_rooms_given_pole', methods = ['GET'])
# Returns all the rooms given the pole name.
# {
#   "all_rooms": [
#       "classroom_name1",
#       "classroom_name2"
#       ...
#   ]
# }
def get_all_rooms_given_pole():
    pole_name = request.args.get('pole_name')

    if pole_name:
        pole_name = pole_name.lower()
    else:
        return jsonify({"message": "Invalid pole."})

    pole_link = ""
    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    for pole in poles:
        if pole_name.lower() in list(pole.keys())[0].lower():
            pole_link = pole[list(pole.keys())[0]]

    if pole_link == "":
        return jsonify({"message": "Invalid pole."})

    rooms = []

    src = selenium_get_schedule_page(pole_link)
    if src is None:
        return jsonify({"message": "Error in schedules data."})
    infos = escrape_schedule_page(src)

    for classroom in infos:
        rooms.append(classroom["Classroom"])

    return jsonify({"all_rooms": rooms})

# Returns all the schedules for a room given the pole name and the room name.
# {
#  "classroom_name1": [
#    "schedule1",
#    ...
#  ],
#  ...
# }
@app.route('/api/all_schedules_given_pole_and_room', methods = ['GET'])
def all_schedules_given_pole_and_room():
    pole_name = request.args.get('pole_name')
    classroom_name = request.args.get("classroom")

    if pole_name:
        pole_name = pole_name.lower()
    else:
        return jsonify({"message": "Invalid pole."})

    if classroom_name:
        classroom_name = classroom_name.lower()
    else:
        return jsonify({"message": "Invalid classroom name for this pole."})

    pole_link = ""
    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    for pole in poles:
        if pole_name.lower() in list(pole.keys())[0].lower():
            pole_link = pole[list(pole.keys())[0]]

    if pole_link == "":
        return jsonify({"message": "Invalid pole."})

    src = selenium_get_schedule_page(pole_link)
    if src is None:
        return jsonify({"message": "Error in schedules data."})
    infos = escrape_schedule_page(src)

    return_classroom = ""
    schedules = []
    for classroom in infos:
        current_classroom = classroom["Classroom"]
        if current_classroom.lower() == classroom_name:
            return_classroom = current_classroom
            schedules = classroom[list(classroom.keys())[1]]
            break

    if return_classroom == "":
        return jsonify({"message": "Invalid classroom name for this pole."})

    return jsonify({return_classroom: schedules})

# Returns all the free rooms now given the pole name.
# {
#  "free_classrooms": [
#    {"classroom_name1": "next_lecture_start"},
#    ...
#  ]
# }
@app.route('/api/free_classrooms_now_given_pole', methods = ['GET'])
def free_classrooms_now_given_pole():
    pole_name = request.args.get('pole_name')

    if pole_name:
        pole_name = pole_name.lower()
    else:
        return jsonify({"message": "Invalid pole."})

    pole_link = ""
    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    for pole in poles:
        if pole_name.lower() in list(pole.keys())[0].lower():
            pole_link = pole[list(pole.keys())[0]]

    if pole_link == "":
        return jsonify({"message": "Invalid pole."})

    src = selenium_get_schedule_page(pole_link)
    if src is None:
        return jsonify({"message": "Error in schedules data."})
    infos = escrape_schedule_page(src)

    free_classrooms = get_free_classrooms_now(infos)
    for classroom in free_classrooms:
        for key, value in classroom.items():
            classroom[key] = "Free until: " + str(classroom[key])
            if "None" in classroom[key]:
                classroom[key] = classroom[key].replace("None", "end of day")

    return jsonify({"free_classrooms": free_classrooms}) 

# Returns the current (now) schedule or None for a given classroom in a given pole
# {
#  "classroom_name": "schedule"
# }
@app.route('/api/current_schedule_given_pole_and_room', methods = ['GET'])
def current_schedule_given_pole_and_room():
    pole_name = request.args.get('pole_name')
    classroom_name = request.args.get("classroom")

    if pole_name:
        pole_name = pole_name.lower()
    else:
        return jsonify({"message": "Invalid pole."})

    if classroom_name:
        classroom_name = classroom_name.lower()
    else:
        return jsonify({"message": "Invalid classroom name for this pole."})

    pole_link = ""
    poles = fetch_poles_data()
    if poles is None:
        return jsonify({"message": "Error in fetching poles data."})
    for pole in poles:
        if pole_name.lower() in list(pole.keys())[0].lower():
            pole_link = pole[list(pole.keys())[0]]

    if pole_link == "":
        return jsonify({"message": "Invalid pole."})

    src = selenium_get_schedule_page(pole_link)
    if src is None:
        return jsonify({"message": "Error in schedules data."})
    infos = escrape_schedule_page(src)

    return_classroom = ""
    schedules = []
    for classroom in infos:
        current_classroom = classroom["Classroom"]
        if current_classroom.lower() == classroom_name:
            return_classroom = current_classroom
            schedules = classroom[list(classroom.keys())[1]]
            break

    if return_classroom == "":
        return jsonify({"message": "Invalid classroom name for this pole."})

    # Now.
    time = datetime.now()

    year = time.year
    month = time.month
    day = time.day
    minute = time.minute
    hour = time.hour

    return_schedule = ""
    for schedule in schedules:
        timestartend = schedule.split("|")[0]

        timestart = datetime.strptime(timestartend.split("-")[0].strip(), "%H:%M")
        timeend = datetime.strptime(timestartend.split("-")[1].strip(), "%H:%M")

        timestart = datetime(year=year, month=month, day=day, hour=timestart.hour, minute=timestart.minute)
        timeend = datetime(year=year, month=month, day=day, hour=timeend.hour, minute=timeend.minute)

        if timestart <= time <= timeend:
            return_schedule = schedule
            break


    return jsonify({return_classroom: return_schedule})

src_schedules_page_cache = {}
cache_lock = Lock()
def src_schedules_page_cache_thread():
    # Initialization.
    global src_schedules_page_cache
    try:
        poles = fetch_poles_data()
        if poles is None:
            raise Exception()
        for pole in poles:
            for key, value in pole.items():
                src = selenium_get_schedule_page(value, False)
                if src is None:
                    raise Exception()
                with cache_lock:
                    src_schedules_page_cache[value] = src
        print("Cache initialization completed.")
    except Exception as e:
        print(f"Cache initialization error: {e}")

    # 15 minutes.
    clean_cache_after_seconds = 900
    seconds_counter = 0
    while True:
        sleep(1)
        seconds_counter += 1
        if seconds_counter >= clean_cache_after_seconds:
            seconds_counter = 0
            try:
                poles = fetch_poles_data()
                if poles is None:
                    raise Exception()
                for pole in poles:
                    for key, value in pole.items():
                        src = selenium_get_schedule_page(value, False)
                        if src is None:
                            raise Exception()
                        with cache_lock:
                            src_schedules_page_cache[value] = src
                print("Cache update completed.")
            except Exception as e:
                print(f"Cache update error: {e}")


def main():
    print("Starting schedules cache thread...")
    cache_thread = Thread(target = src_schedules_page_cache_thread, daemon=True)
    cache_thread.start()
    print("Cache thread started.")
    print("Initialization completed, starting serving requests.")


# Main entry point of the application.
if __name__ == '__main__':

    # Placeholder for an initialization.
    main()

    # In development, use Flask:
    app.run(debug = True, port = 8080, use_reloader = False)

    # In production, use Gunicorn:
    # pip install gunicorn
    # python3 -m gunicorn --bind 127.0.0.1:8000 wsgi:app

    # Apache proxy forwards the requests from 54321 port to Gunicorn on 8000 port.

    # HTTPS required on GitHub Pages.

    # sudo apt install chromium-chromedriver

    # which chromedriver
