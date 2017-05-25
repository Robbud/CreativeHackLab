#!/usr/bin/python

# import the requests and json library -
# maybe you need to install something extra to get these?
# sudo pip install requests json maybe?
import requests, json
import os
import urllib
# put the apikey you got when you subscribed below:
apikey = "YOUR API KEY "

# change this to the one you want or
# maybe have an array of sources that you loop through?
source = "EXAMPLESOURCE"

# the url for the news api articles combining the  variables you defined above
url = 'https://newsapi.org/v1/articles?source= YOUR SOURCE &apiKey= YOUR API KEY'


image = urllib.URLopener()

# make the get request from the url
r = requests.get(url)
# load the response as json formated data
news = json.loads(r.content)


# download images from url and save into Images folder.

fullfilename = os.path.join('folder','filename')
urllib.urlretrieve("https://newsapi.org/v1/articles?source=espn&apiKey=YOUR API KEY","Images/Image.jpg")



# this will list all the available keys
print(news["articles"][0].keys())
#print[u'description', u'title', u'url', u'author', u'publishedAt', u'urlToImage']

# now i will use a "for loop" to cycle through each of the articles
# and print the "title' key followed by a line break (\n  newline)
for item in news['articles']:
    print(item["title"] + "\n")
    #print(item["author"] + "\n")
    print(item["urlToImage"] + "\n")
    image.retrieve(item["urlToImage"])

    #print(item["url"] + "\n") #prints link to news
    #print(item["description"] + "\n") #shows description
    #print(item["publishedAt"] + "\n") #shows the publication time

