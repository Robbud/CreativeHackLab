#!/usr/bin/python

# import the requests and json library -
# maybe you need to install something extra to get these?
# sudo pip install requests json maybe?
import requests, json

# put the apikey you got when you subscribed below:
apikey = "9e752fd5350b41efb5a11b25818d8eaa "

# change this to the one you want or
# maybe have an array of sources that you loop through?
source = "techcrunch"

# the url for the news api articles combining the  variables you defined above
url = 'https://newsapi.org/v1/articles?source=bbc-news&apiKey=9e752fd5350b41efb5a11b25818d8eaa'
#url = 'https://newsapi.org/v1/articles?source= source here&apiKey= api key here '



# make the get request from the url
r = requests.get(url)
# load the response as json formated data
news = json.loads(r.content)

# this will list all the available keys
print(news["articles"][0].keys())
# this outputs [u'description', u'title', u'url', u'author', u'publishedAt', u'urlToImage']

# now i will use a "for loop" to cycle through each of the articles
# and print the "title' key followed by a line break (\n  newline)
for item in news['articles']:
    print(item["title"] + "\n")
