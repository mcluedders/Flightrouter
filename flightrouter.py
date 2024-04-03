#flightrouter.py
'''
Finds the time taken for a plane to travel from one airport to another, taking wind speed into account.
Assumptions: routes are always the shortest path between the origin and destination, the entire flight takes place at 200 hPa (about 38,000 ft), 
wind data for the entire trip is taken at the time the flight starts, and airspeed is constant.
Note also that the source of the wind data, windy.com, has updates about every 6-7 hours. This means the wind data may be a prediction from up to 7 hours ago.
'''

from urllib.request import urlopen
from selenium import webdriver
from selenium.webdriver import Chrome
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions
from math import radians, degrees, cos, acos, sin, asin, tan, atan, sqrt
import time


options = Options()
driver = webdriver.Chrome(options=options, executable_path='chromedriver.exe')


#find distance between two sets of coordinates (given in radians), in mi or km (depends on what earthradius is specified to be)
def haversine(lon1, lat1, lon2, lat2):
    #employ haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = earthradius
    return c * r


#earthradius = 6371 #kilometers
earthradius = 3956 #miles
#using imperial because it's what windy uses by default. We can convert the end results if desired.
airspeed = 550 #mph
origin = '38°44′50″N 090°21′41″W' #STL
dest = '33°26′03″N 112°00′42″W' #PHX


''' Create waypoints, find total distance '''
#convert deg,min,sec, to deg with decimal
originlat = float(origin[0:2]) + float(origin[3:5]) / 60 + float(origin[6:8]) / 3600
originlon = float(origin[11:14]) + float(origin[15:17]) / 60 + float(origin[18:20]) / 3600
if origin[21] == 'W':
    originlon = originlon * -1
destlat = float(dest[0:2]) + float(dest[3:5]) / 60 + float(dest[6:8]) / 3600
destlon = float(dest[11:14]) + float(dest[15:17]) / 60 + float(dest[18:20]) / 3600
if dest[21] == 'W':
    destlon = destlon * -1
#store origin coords for later
waypoint = list([[originlat, originlon]])
#convert to radians
originlat, destlat, originlon, destlon = map(radians, [originlat, destlat, originlon, destlon])
#find total distance between points
totaldist = haversine(originlat, originlon, destlat, destlon)
#https://commons.erau.edu/cgi/viewcontent.cgi?article=1160&context=ijaaa, Appendix C.
#let's place a waypoint every 50 mi. We have an equation for latitude on a great circle for a given longitude (equation C20 in the literature), so let's find the longitude step size.
waypointcount = int(totaldist / 50)
deltalon = destlon - originlon
lonstep = deltalon / waypointcount
#place waypoints, starting with the origin
templon = originlon
templat = originlat
for i in range(waypointcount):
    templon = templon + lonstep
    templat = atan((tan(originlat) * sin(templon - destlon) + tan(destlat) * sin(originlon - templon)) / sin(originlon - destlon))
    #convert to degrees before adding to waypoint list
    londeg, latdeg = map(degrees, [templon, templat])
    waypoint.append([latdeg, londeg])
#finally, add a waypoint at the destination.
destlat, destlon = map(degrees, [destlat, destlon])
waypoint.append([destlat, destlon])


''' Get wind data for each waypoint '''
winddata = list()
for item in waypoint:
    lat = str(item[0])
    lon = str(item[1])
    driver.get('https://www.windy.com/sounding/'+lat+'/'+lon+'?gfs,200h,'+lat+','+lon+',6')
    #time.sleep(1)
    move = ActionChains(driver)
    #slider = driver.find_element_by_class_name('infoLine')
    slider = WebDriverWait(driver, 5).until(expected_conditions.element_to_be_clickable((By.CLASS_NAME, 'infoLine')))
    move.click_and_hold(slider).move_by_offset(0,-265).release().perform()
    #time.sleep(1)

    sel = driver.find_element_by_class_name('windSpeed')
    windspeed = sel.text
    #the windspeed might look like #kt, ##kt, or ###kt; if it reads in the letters and tries to turn them into a float, it returns a ValueError.
    try:
        windspeed = float(windspeed[0:3])
    except ValueError:
        try:
            windspeed = float(windspeed[0:2])
        except ValueError:
            windspeed = float(windspeed[0:1])
    #windy gives data in knots; we'll convert to mph for simplicity
    windspeed = windspeed * 1.151
    sel = driver.find_element_by_class_name('windDir')
    winddir = sel.text
    try:
        winddir = float(winddir[0:3])
    except ValueError:
        try:
            winddir = float(winddir[0:2])
        except ValueError:
            winddir = float(winddir[0:1])
    winddir = radians(winddir)
    winddata.append([windspeed, winddir])
driver.quit()


''' Find travel time '''
groundspeed = list()
#find the unit vector that points from the origin to destination
deltalat = destlat - originlat
totaldistance = sqrt(deltalat**2 + deltalon**2)
unitlat = deltalat / totaldistance #x
unitlon = deltalon / totaldistance #y
#we'll rotate the vectors to make them easier to work with
#first, find the angle to rotate by; this is the angle between the destination unit vector and a vector pointing due north, which we'll call the y-axis.
theta = acos(unitlat)
for item in winddata:
    #convert polar to cartesian (magnitude and deg to x and y)
    xwind = item[0] * cos(item[1])
    ywind = item[0] * sin(item[1])
    #rotate (transform) the wind vector
    xwindr = xwind * cos(theta) + ywind * sin(theta)
    ywindr = -1 * xwind * sin(theta) + ywind * cos(theta)
    #x components of wind and airspeed need to cancel out, which determines the angle of the airspeed vector. The magnitude is a known constant.
    #groundspeed then comes from the y component of airspeed minus the y component of wind.
    yairspeed = sqrt(airspeed**2 - xwindr**2)
    groundspeed.append(yairspeed - ywindr)
#We'll assume that each waypoint (except the first and last) is the center of a 50 mi region of uniform windspeed.
#d = rt, so t = d/r
#first, account for the first and last sections of the trip
traveltime = (50 / 2) / groundspeed[0] + (totaldist - 50 * waypointcount - 50 / 2) / groundspeed[-1]
#then the rest
for i in range(1, waypointcount + 2):
    traveltime = traveltime + 50 / groundspeed[i]
print(traveltime) #in hours
