#!/usr/bin/python
# change this to the one you want or
import requests, json
import os
import serial
import urllib, urlparse


apikey ="YOUR API KEY"

source = "Buzzfeed"

# the url for the news api articles combining the  variables you defined above

url = 'https://newsapi.org/v1/articles?source= YOUR SOURCE&apiKey=YOUR API'


image = urllib.URLopener()

# make the get request from the url
r = requests.get(url)
# load the response as json formated data
news = json.loads(r.content)



# download images from url and save into Images folder.
# The images are used to edit photos
#fullfilename = os.path.join('/home/pi/CreativeHackLab/Images','filename')
#urllib.urlretrieve(url,"Images/Image1")


# this will list all the available keys
print(news["articles"][0].keys())
#print[u'description', u'title', u'url', u'author', u'publishedAt', u'urlToImage']

# now i will use a "for loop" to cycle through each of the articles
# and print the "title' key followed by a line break (\n  newline)
# Shows diffrent headlines, depending on what source you use

urllib.urlretrieve("http://a1.espncdn.com/combiner/i?img=%2Fphoto%2F2017%2F0524%2Fr212486_1296x729_16%2D9.jpg", "asdf.jpg")

counter = 0;
for item in news['articles']:
    counter = counter+1
    print counter
    print(item["title"] + "\n")
    print(item["description"] + "\n")
    print(item["urlToImage"] + "\n")
    imgurl = item["urlToImage"]
    a = urlparse.urlparse(imgurl)
    urllib.urlretrieve(item["urlToImage"], "Images/" + str(counter) + ".jpg"); #downloads picture from urlToImage and saves it on your computers Images folder


    # urllib.urlretrieve(item["urlToImage"]); 
    #urllib.urlretrieve("http://a1.espncdn.com/combiner/i?img=%2Fphoto%2F2017%2F0524%2Fr212486_1296x729_16%2D9.jpg")

    #print(item["url"] + "\n") #prints link to news
    #print(item["description"] + "\n") #shows description
    #print(item["publishedAt"] + "\n") #shows the publication time

