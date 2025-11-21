# Unipi free classrooms now
Simply see the classrooms that are vacant (free) now at the University of Pisa!

## Why?
Because the official schedule (available [here](https://aule.webhost1.unipi.it)), is complete, but in the large educational poles with so many classrooms and lectures throughout the day, seeing the classrooms that are free in a given time and how long they will remain so (especially on small screens like smartphone), where you can go to study (maybe with some colleagues to speak with, not allowed in the official study rooms) gives me a headache, it almost feels like solving an operations research problem...

## What does the project consist of?
A minimal frontend and more substantial APIs that perform scraping via Selenium (since JavaScript execution was necessary) of the official website to retrieve and provide data in JSON format.

## Data source
The data comes from the official schedule (available [here](https://aule.webhost1.unipi.it)). The data are simply parsed and processed.

## There are already other apps developed by other students that makes this!
Yes, but some have stopped working and some do not work on computers and iOS.

## It is very basic!
This is not meant to be a solution with lots of features, just a quick tool for what in my experience I believe is the most common need.

## It seems like an '80 site!
If escraping the CINECA site wasn't particularly painful I would have spent time on the frontend, so for now it will remain vintage, maybe one day I will add a frontend... It has to be functional, not pretty! However, if you want to add it yourself, you can, this is the power of open source!

## Where is it hosted? What do I connect to?
The frontend HTML and Javascript are static files, so are served directly by GitHub through the GitHub Pages feature. But the core of the project is its APIs, written in Python with Selenium that get, parse and process the data. Since getting the data needs a browser with enabled Javascript, a full server is needed. So the APIs are hosted on my own little free cloud machine hoping it will stay alive.

## Can I re-host the APIs?
Yes, sure, you will need a full server with Python 3 and the "APIs/python_requirements.txt" installed. Note that you also need the chrome-driver used by Selenium, you can download it for free on the web. 

## Can I use your hosted APIs to build other things?
Yes, but as previosly mentioned, my little free cloud machine is precarious, so do so at your own risk.

## Disclaimer
This tool is UNOFFICIAL, developed by a student who disclaims any responsibility as to the reliability of this data.
