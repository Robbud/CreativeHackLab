#!/usr/bin/python
# import the requests and json library -
# maybe you need to install something extra to get these?
# sudo pip install requests json maybe?
import requests, json
import os
import serial
import urllib, urlparse
# put the apikey you got when you subscribed below:
apikey = "9e752fd5350b41efb5a11b25818d8eaa"

# change this to the one you want or
# maybe have an array of sources that you loop through?
source = "The Guardian"

# the url for the news api articles combining the  variables you defined above

url = 'https://newsapi.org/v1/articles?source=the-guardian-uk&apiKey=9e752fd5350b41efb5a11b25818d8eaa'


#ser = serial.Serial('/dev/ttyACM0', 9600')
image = urllib.URLopener()

# make the get request from the url
r = requests.get(url)
# load the response as json formated data
news = json.loads(r.content)


# download images from url and save into Images folder.

#fullfilename = os.path.join('/home/pi/CreativeHackLab/Images','filename')
#urllib.urlretrieve(url,"Images/Image1")


# this will list all the available keys
print(news["articles"][0].keys())
#print[u'description', u'title', u'url', u'author', u'publishedAt', u'urlToImage']

# now i will use a "for loop" to cycle through each of the articles
# and print the "title' key followed by a line break (\n  newline)


#urllib.urlretrieve("https://newsapi.org/v1/articles?source=the-guardian-uk&apiKey=9e752fd5350b41efb5a11b25818d8eaa")


ser = serial.Serial('/dev/ttyACM0',9600)
s = [0,1]

 	
counter = 0;
for item in news['articles']:
    counter = counter+1
    print counter
    print(item["title"] + "\n")   
    print(item["description"] + "\n")
    print(item["urlToImage"] + "\n")
    imgurl = item["urlToImage"]
    a = urlparse.urlparse(imgurl)
    urllib.urlretrieve(item["urlToImage"], "Images/" + str(counter) + ".jpg");


while True:
        read_serial=ser.readline()
        s[0] = str(int (ser.readline(),16))
        print s[0]
        print read_serial
	Serial.write(item["title"] +"\n") #write out title to arduino display
	
#   b= urlparse.urlparse(title)
#    urllib.urlretrieve(item["title"], "title/" + str(counter) + ".txt");
     

    # urllib.urlretrieve(item["urlToImage"]); 
    #urllib.urlretrieve("http://a1.espncdn.com/combiner/i?img=%2Fphoto%2F2017%2F0524%2Fr212486_1296x729_16%2D9.jpg")
   
    #print(item["url"] + "\n") #prints link to news
    #print(item["description"] + "\n") #shows description
    #print(item["publishedAt"] + "\n") #shows the publication time


