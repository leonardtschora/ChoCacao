1 phrase summary : I want to create a platform that displays the top 20 hottest and 20 coolest places in France at a given time.

More detailed specifications.
App overview : With the heatwave striking Europe every summer, people are often wondering where to escape heat. France is a great country regarding climate, by blending Atlantic, MEditteranean, and Apline climate. Sometimes, even traveling 200km leads to +-10 degres. Help me build an app that automatically finds the hottest and coolest places in France.

What the user can do : from the platform, it selects a date up to 1 week ahead, and optionally and hour (between 0 and 23). The platform then displays the hottest and coolest places (Up to 20 places). It displays the name of the place, postal code, coordinates, and temperature in Celsius, as a table. Then, the user can click on the name of the place to open a google maps with this location pinned down. If the user does not specify an hour, the default is 4pm (usually hottest of the day). No input date = use today.

Data : Use the open-meteo API. Open-meteo provides temperature forecasts for given coordinates, up to 16 days-ahead. Only consider the 1h granularity data, temperature at 2m, only forecasts.

Main challenge : Which coordinates to use to query open-meteo ? There are 35 000 cities in metropolitan france. This is too much data to query at run time. So let's define a grid of 25km granularity. Metro France can approx fit in a 1000 x 1000 km square. This makes approx 40x40 = 1600 points to query. However, Maybe 1/3 would fall in the ocean or in another country, this making almost only 1000 points to query, which is manageable. So what needs to be done : Define the 25km grid and find the coordinates of all the points in France, corresponding to those coordinates. If possible, once coordinates are found, Map each coordinate to the city it lies in. You have to find a city database for this, possibly OSM. Keep in mind that this is preliminary work : we don't have to compute this grid and mapping at runtime. It has to be done once, then stored (this can maybe be stored in the repo for more simplicity).

Implement for the future : 
-If many users, implement data cache : pull forecasts on a daily basis, cache it. Caps the number of queries to a fixed number every day. 

Hosting platform : I think the simplest is to use a public hosted streamlit app. It provides hosting and deploy directly from a github repo.

Implementation details : Implement the grid computatino + city mapping in Python. Use streamlit's integrated functionality to ask for input date and display the results. No tests needed. Code everything, run the grid computation + mapping, test the deployement using a localy streamlit. Dependencies and env are managed using uv. Follow ruff/pyright syntax guidelines. Log every decision you make in .md files, in an ADR/ folder. You have to do everything : create the repo, the env, research the doc, etc...

Name of the app : ChoCacao.
